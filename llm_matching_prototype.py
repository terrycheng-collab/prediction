"""Prototype: two-stage LLM-assisted cross-exchange market matching.

Stage 1 (candidate generation): TF-IDF cosine similarity over market titles
narrows each Polymarket market down to its top-K most textually similar
Kalshi markets. Cheap, no LLM calls, runs over the full market universe.

Stage 2 (adjudication): for a sample of Polymarket markets, a Haiku model
call is shown the market plus its Stage 1 candidates and asked to pick the
one that refers to the same real-world event (or none). Evaluated against
contract_matching.py's deterministic matches as a sanity check.

Usage:
    python llm_matching_prototype.py candidates
    python llm_matching_prototype.py adjudicate --sample-size 100 --concurrency 10
"""

from __future__ import annotations

import argparse
import json
import random
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

DEFAULT_CANONICAL = "exports/event_active_contracts/contract_canonical_markets.csv"
DEFAULT_MATCHES = "exports/event_active_contracts/contract_matches.csv"
DEFAULT_OUTDIR = "exports/llm_matching_prototype"
HAIKU_MODEL = "haiku"


def combined_text(df: pd.DataFrame) -> pd.Series:
    return (
        df["title"].fillna("").astype(str)
        + " "
        + df["yes_sub_title"].fillna("").astype(str)
        + " "
        + df["no_sub_title"].fillna("").astype(str)
    ).str.strip()


def load_markets(canonical_csv: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    canonical = pd.read_csv(canonical_csv, low_memory=False)
    canonical["market_id"] = canonical["market_id"].astype(str)
    pm = canonical[canonical["exchange"].eq("polymarket")].drop_duplicates(subset=["market_id"]).reset_index(drop=True)
    k = canonical[canonical["exchange"].eq("kalshi")].drop_duplicates(subset=["market_id"]).reset_index(drop=True)
    return pm, k


def load_matches(matches_csv: str) -> pd.DataFrame:
    matches = pd.read_csv(matches_csv, low_memory=False)
    matches["market_id_pm"] = matches["market_id_pm"].astype(str)
    matches["market_id_kalshi"] = matches["market_id_kalshi"].astype(str)
    return matches


def load_candidates(candidates_path: Path) -> pd.DataFrame:
    candidates = pd.read_csv(candidates_path)
    candidates["pm_market_id"] = candidates["pm_market_id"].astype(str)
    candidates["k_market_id"] = candidates["k_market_id"].astype(str)
    return candidates


def build_candidates(canonical_csv: str, outdir: Path, top_k: int, min_score: float, chunk_size: int) -> pd.DataFrame:
    pm, k = load_markets(canonical_csv)
    print(f"Polymarket markets: {len(pm):,} | Kalshi markets: {len(k):,}")

    pm_text = combined_text(pm)
    k_text = combined_text(k)

    vectorizer = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", min_df=1, sublinear_tf=True)
    vectorizer.fit(pd.concat([pm_text, k_text], ignore_index=True))
    pm_vecs = vectorizer.transform(pm_text)  # L2-normalized rows -> dot product == cosine similarity
    k_vecs = vectorizer.transform(k_text)

    rows = []
    n = len(pm)
    for start in range(0, n, chunk_size):
        end = min(start + chunk_size, n)
        sims = (pm_vecs[start:end] @ k_vecs.T).toarray()
        for local_i, global_i in enumerate(range(start, end)):
            scores = sims[local_i]
            top_idx = np.argsort(-scores)[:top_k]
            for rank, k_idx in enumerate(top_idx, start=1):
                score = float(scores[k_idx])
                if score < min_score:
                    continue
                rows.append(
                    {
                        "pm_market_id": pm.loc[global_i, "market_id"],
                        "pm_title": pm.loc[global_i, "title"],
                        "pm_end_date": pm.loc[global_i, "end_date"],
                        "rank": rank,
                        "k_market_id": k.loc[k_idx, "market_id"],
                        "k_title": k.loc[k_idx, "title"],
                        "k_yes_sub_title": k.loc[k_idx, "yes_sub_title"],
                        "k_end_date": k.loc[k_idx, "end_date"],
                        "tfidf_score": score,
                    }
                )
        print(f"  scored {end:,}/{n:,} Polymarket markets", end="\r")
    print()

    candidates = pd.DataFrame(rows)
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / "candidates.csv"
    candidates.to_csv(out_path, index=False)
    with_any = candidates["pm_market_id"].nunique() if not candidates.empty else 0
    print(f"Candidates: {len(candidates):,} rows covering {with_any:,}/{len(pm):,} Polymarket markets -> {out_path}")
    return candidates


ADJUDICATE_SYSTEM_PROMPT = (
    "You are adjudicating whether two prediction-market contracts, listed from different "
    "exchanges, refer to the same real-world question and resolution event. Respond with "
    "raw JSON only: no markdown code fences, no text outside the JSON object."
)


def build_prompt(pm_row: pd.Series, cands: pd.DataFrame) -> str:
    lines = [
        "Polymarket market:",
        f'  title: "{pm_row["pm_title"]}"',
        f'  resolves by: {pm_row["pm_end_date"]}',
        "",
        "Candidate Kalshi markets (pick the one describing the same underlying event/question,",
        "if any -- same subject, same predicate/threshold, same deadline; not just similar topic):",
    ]
    for _, c in cands.iterrows():
        lines.append(
            f'  [{int(c["rank"])}] title: "{c["k_title"]}" | subtitle: "{c["k_yes_sub_title"]}" | resolves by: {c["k_end_date"]}'
        )
    lines += [
        "",
        'Respond with JSON: {"match_rank": <int from the candidate list above, or null if none match>, '
        '"confidence": "high"|"medium"|"low", "reason": "<one short sentence>"}',
    ]
    return "\n".join(lines)


def call_haiku(prompt: str, timeout: int = 60) -> dict:
    try:
        result = subprocess.run(
            [
                "claude",
                "-p",
                "--model",
                HAIKU_MODEL,
                "--append-system-prompt",
                ADJUDICATE_SYSTEM_PROMPT,
                prompt,
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        raw = result.stdout.strip()
    except subprocess.TimeoutExpired:
        return {"match_rank": None, "confidence": "low", "reason": "TIMEOUT", "_raw": ""}

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {"match_rank": None, "confidence": "low", "reason": "PARSE_ERROR", "_raw": raw}
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"match_rank": None, "confidence": "low", "reason": "PARSE_ERROR", "_raw": raw}
    parsed["_raw"] = raw
    return parsed


def build_sample(pm: pd.DataFrame, candidates: pd.DataFrame, matches: pd.DataFrame, sample_size: int) -> pd.DataFrame:
    matched_ids = set(matches["market_id_pm"])
    has_candidates = set(candidates["pm_market_id"])

    matched_sample = [pid for pid in matched_ids if pid in has_candidates]
    unmatched_pool = [pid for pid in has_candidates if pid not in matched_ids]

    rng = random.Random(0)
    n_unmatched = max(0, sample_size - len(matched_sample))
    unmatched_sample = rng.sample(unmatched_pool, min(n_unmatched, len(unmatched_pool)))

    sample_ids = matched_sample + unmatched_sample
    sample = pm[pm["market_id"].isin(sample_ids)].copy()
    sample["has_deterministic_match"] = sample["market_id"].isin(matched_ids)
    print(
        f"Sample: {len(sample):,} Polymarket markets "
        f"({len(matched_sample):,} with a deterministic match, {len(unmatched_sample):,} without)"
    )
    return sample


def adjudicate(canonical_csv: str, matches_csv: str, outdir: Path, sample_size: int, top_k: int, concurrency: int) -> pd.DataFrame:
    candidates_path = outdir / "candidates.csv"
    if not candidates_path.exists():
        raise FileNotFoundError(f"{candidates_path} not found -- run the 'candidates' stage first.")
    candidates = load_candidates(candidates_path)
    matches = load_matches(matches_csv)
    pm, _ = load_markets(canonical_csv)

    sample = build_sample(pm, candidates, matches, sample_size)
    match_lookup = dict(zip(matches["market_id_pm"], matches["market_id_kalshi"]))

    def process_one(pm_row: pd.Series) -> dict:
        pid = pm_row["market_id"]
        cands = candidates[candidates["pm_market_id"].eq(pid)].sort_values("rank").head(top_k)
        prompt = build_prompt(
            pd.Series({"pm_title": pm_row["title"], "pm_end_date": pm_row["end_date"]}),
            cands,
        )
        result = call_haiku(prompt)
        if result.get("reason") in ("PARSE_ERROR", "TIMEOUT"):
            print(f"\n[{result['reason']}] pm_market_id={pid} raw={result.get('_raw', '')[:300]!r}")
        chosen_k_id = None
        if result.get("match_rank") is not None:
            picked = cands[cands["rank"].eq(result["match_rank"])]
            if not picked.empty:
                chosen_k_id = picked.iloc[0]["k_market_id"]
        deterministic_k_id = match_lookup.get(pid)
        return {
            "pm_market_id": pid,
            "pm_title": pm_row["title"],
            "has_deterministic_match": pm_row["has_deterministic_match"],
            "deterministic_k_market_id": deterministic_k_id,
            "llm_k_market_id": chosen_k_id,
            "llm_confidence": result.get("confidence"),
            "llm_reason": result.get("reason"),
            "agrees_with_deterministic": (chosen_k_id == deterministic_k_id) if deterministic_k_id else None,
            "num_candidates_shown": len(cands),
        }

    rows = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(process_one, row): row["market_id"] for _, row in sample.iterrows()}
        done = 0
        for fut in as_completed(futures):
            rows.append(fut.result())
            done += 1
            print(f"  adjudicated {done}/{len(futures)}", end="\r")
    print()

    results = pd.DataFrame(rows)
    outdir.mkdir(parents=True, exist_ok=True)
    out_path = outdir / "adjudications.csv"
    results.to_csv(out_path, index=False)
    print(f"Adjudications -> {out_path}")
    summarize(results)
    return results


def summarize(results: pd.DataFrame) -> None:
    with_det = results[results["has_deterministic_match"]]
    without_det = results[~results["has_deterministic_match"]]

    n_det = len(with_det)
    n_recovered = int(with_det["agrees_with_deterministic"].fillna(False).sum())
    n_found_new = int(without_det["llm_k_market_id"].notna().sum())

    print("\n=== Summary ===")
    print(f"Deterministically-matched PM markets sampled: {n_det}")
    print(f"  LLM picked the same Kalshi market:           {n_recovered} ({n_recovered / n_det:.0%})" if n_det else "  n/a")
    print(f"Deterministically-UNmatched PM markets sampled: {len(without_det)}")
    print(f"  LLM proposed a match anyway:                  {n_found_new} ({n_found_new / len(without_det):.0%})" if len(without_det) else "  n/a")
    print("\nNote: 'proposed a match anyway' could be new coverage the deterministic parser")
    print("missed, or an LLM false positive -- needs human spot-check, not taken at face value.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("stage", choices=["candidates", "adjudicate"])
    parser.add_argument("--canonical-csv", default=DEFAULT_CANONICAL)
    parser.add_argument("--matches-csv", default=DEFAULT_MATCHES)
    parser.add_argument("--outdir", default=DEFAULT_OUTDIR)
    parser.add_argument("--top-k", type=int, default=5, help="Kalshi candidates kept per Polymarket market.")
    parser.add_argument("--min-score", type=float, default=0.05, help="Minimum TF-IDF cosine similarity to keep a candidate.")
    parser.add_argument("--chunk-size", type=int, default=200, help="Polymarket rows per similarity batch (memory control).")
    parser.add_argument(
        "--sample-size",
        type=int,
        default=100,
        help="Adjudication stage: total Polymarket markets to send to the LLM. All markets with a "
        "deterministic match are always included (for recall testing); the remainder of this budget "
        "is filled with a random sample of unmatched markets (for false-positive testing).",
    )
    parser.add_argument("--concurrency", type=int, default=10, help="Adjudication stage: parallel `claude -p` calls.")
    args = parser.parse_args()

    outdir = Path(args.outdir)
    if args.stage == "candidates":
        build_candidates(args.canonical_csv, outdir, args.top_k, args.min_score, args.chunk_size)
    else:
        adjudicate(args.canonical_csv, args.matches_csv, outdir, args.sample_size, args.top_k, args.concurrency)


if __name__ == "__main__":
    main()
