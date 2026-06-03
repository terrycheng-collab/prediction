from __future__ import annotations

import argparse
import glob
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

import pandas as pd


PERSON_ALIASES = {
    "donald trump": "donald_trump",
    "trump": "donald_trump",
    "vladimir putin": "vladimir_putin",
    "putin": "vladimir_putin",
    "volodymyr zelenskyy": "volodymyr_zelenskyy",
    "volodymyr zelensky": "volodymyr_zelenskyy",
    "volodomyr zelenskyy": "volodymyr_zelenskyy",
    "zelenskyy": "volodymyr_zelenskyy",
    "zelensky": "volodymyr_zelenskyy",
    "pope leo xiv": "pope_leo_xiv",
    "pope leo": "pope_leo_xiv",
}

PLACE_ALIASES = {
    "united states": "united_states",
    "usa": "united_states",
    "u.s.": "united_states",
    "us": "united_states",
    "ukraine": "ukraine",
    "the ukraine": "ukraine",
    "russia": "russia",
    "russian federation": "russia",
    "mar-a-lago": "mar_a_lago",
    "white house": "white_house",
}

PARTY_ALIASES = {
    "democratic": "democratic_party",
    "democratic party": "democratic_party",
    "republican": "republican_party",
    "republican party": "republican_party",
}

TEAM_ALIASES = {
    "los angeles d": "los_angeles_dodgers",
    "los angeles dodgers": "los_angeles_dodgers",
    "la dodgers": "los_angeles_dodgers",
    "new york y": "new_york_yankees",
    "new york yankees": "new_york_yankees",
    "ny yankees": "new_york_yankees",
    "indiana": "indiana_pacers",
    "indiana pacers": "indiana_pacers",
    "sacramento kings": "sacramento_kings",
    "toronto raptors": "toronto_raptors",
    "aston villa": "aston_villa",
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

UMA_VALUE_PATTERN = re.compile(r"\b(uma|optimistic\s+oracle|oo\s*v?2|oo\s*v?3)\b", re.I)
RESOLVER_COLUMN_PATTERN = re.compile(r"(uma|oracle|resolver|resolution|adapter|arbitrator)", re.I)


@dataclass
class ParsedContract:
    market_family: str = ""
    predicate: str = ""
    subject: str = ""
    obj: str = ""
    scope: str = ""
    deadline: str = ""
    season: str = ""
    threshold: str = ""
    direction: str = ""
    contract_key: str = ""
    entity_signature: str = ""
    parse_confidence: float = 0.0
    parse_reason: str = ""


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).lower()
    text = text.replace("**", "")
    text = text.replace("’", "'")
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(value: object) -> str:
    text = clean_text(value)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def canonical_alias(value: str, aliases: dict[str, str] | None = None) -> str:
    text = clean_text(value).strip(" ?.,")
    if aliases and text in aliases:
        return aliases[text]
    return slugify(text)


def first_alias_in_text(text: str, aliases: dict[str, str]) -> str:
    text = clean_text(text)
    for label in sorted(aliases, key=len, reverse=True):
        if re.search(rf"\b{re.escape(label)}\b", text):
            return aliases[label]
    return ""


def infer_context_year(row: pd.Series) -> str:
    for col in ("end_date", "close_time", "end_ts", "close_ts", "created_at", "created_time"):
        value = row.get(col)
        if pd.notna(value):
            match = re.search(r"\b(20\d{2})\b", str(value))
            if match:
                return match.group(1)
    return ""


def extract_deadline(text: str, row: pd.Series) -> str:
    text = clean_text(text)

    if "first 100 days" in text:
        return "period:first_100_days"
    if "first year" in text:
        return "period:first_year"

    match = re.search(r"\bin\s+(20\d{2})\b", text)
    if match:
        return f"year:{match.group(1)}"

    match = re.search(r"\bbefore\s+(20\d{2})\b", text)
    if match:
        return f"year:{int(match.group(1)) - 1}"

    match = re.search(r"\bbefore\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2}),?\s+(20\d{2})", text)
    if match:
        month = MONTHS[match.group(1)]
        day = int(match.group(2))
        year = int(match.group(3))
        if month == 1 and day == 1:
            return f"year:{year - 1}"
        return f"before:{year:04d}-{month:02d}-{day:02d}"

    match = re.search(r"\bby\s+(dec(?:ember)?|jan(?:uary)?)\s+31,?\s+(20\d{2})", text)
    if match and MONTHS[match.group(1)] == 12:
        return f"year:{match.group(2)}"

    match = re.search(r"\bbefore\s+(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t|tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\b", text)
    if match:
        year = infer_context_year(row)
        month = MONTHS[match.group(1)]
        return f"before:{year}-{month:02d}-01" if year else f"before_month:{month:02d}"

    match = re.search(r"\bby\s+december\s+31,?\s+(20\d{2})", text)
    if match:
        return f"year:{match.group(1)}"

    return ""


def make_key(parsed: ParsedContract) -> ParsedContract:
    fields = [
        parsed.market_family,
        parsed.predicate,
        parsed.subject,
        parsed.obj,
        parsed.scope,
        parsed.deadline,
        parsed.season,
        parsed.direction,
        parsed.threshold,
    ]
    parsed.contract_key = "|".join(str(f) for f in fields if str(f))
    parsed.entity_signature = "|".join(
        str(f)
        for f in [parsed.market_family, parsed.predicate, parsed.subject, parsed.obj, parsed.scope, parsed.season, parsed.direction, parsed.threshold]
        if str(f)
    )
    return parsed


def normalize_meeting_participants(parsed: ParsedContract) -> ParsedContract:
    if parsed.predicate == "meet" and parsed.subject and parsed.obj:
        parsed.subject, parsed.obj = sorted([parsed.subject, parsed.obj])
    return parsed


def parse_leader_contact(text: str, row: pd.Series) -> ParsedContract | None:
    if "meet with" not in text and "visit" not in text:
        return None

    if re.search(r"\b(first|next)\b", text) and not re.search(r"\bwill\s+.+\s+(meet with|visit)\b", text):
        return None

    predicate = "meet" if "meet with" in text else "visit"
    subject = ""
    obj = ""

    if predicate == "meet":
        before, after = text.split("meet with", 1)
        subject = first_alias_in_text(before, PERSON_ALIASES)
        obj = first_alias_in_text(after, PERSON_ALIASES)
    else:
        before = text.split("visit", 1)[0]
        subject = first_alias_in_text(before, PERSON_ALIASES)
        match = re.search(r"\bvisit\s+([a-z.\- ]+?)(?:\s+in\b|\s+before\b|\s+by\b|\?|$)", text)
        if match:
            obj = canonical_alias(match.group(1), PLACE_ALIASES)

    if not subject and predicate == "visit" and "trump" in text:
        subject = "donald_trump"

    if not subject or not obj:
        return None

    parsed = ParsedContract(
        market_family="leader_contact",
        predicate=predicate,
        subject=subject,
        obj=obj,
        deadline=extract_deadline(text, row),
        parse_confidence=0.92,
        parse_reason="leader contact template",
    )
    return make_key(normalize_meeting_participants(parsed))


def parse_office_exit(text: str, row: pd.Series) -> ParsedContract | None:
    person = first_alias_in_text(text, PERSON_ALIASES)
    if not person:
        return None

    if re.search(r"\bresigns?\b", text):
        predicate = "resign"
    elif "removed from office" in text or "impeach" in text:
        predicate = "removed_from_office"
    elif re.search(r"\bout as .*president\b|\bfirst leader out\b|\bout this year\b", text):
        predicate = "leave_office"
    else:
        return None

    deadline = extract_deadline(text, row)
    if not deadline and "this year" in text:
        context_year = infer_context_year(row)
        deadline = f"year:{context_year}" if context_year else ""

    parsed = ParsedContract(
        market_family="office_exit",
        predicate=predicate,
        subject=person,
        deadline=deadline,
        parse_confidence=0.88,
        parse_reason="office exit template",
    )
    return make_key(parsed)


def parse_election(text: str, row: pd.Series) -> ParsedContract | None:
    if "election" not in text and "mayor race" not in text:
        return None

    deadline = extract_deadline(text, row)
    year_match = re.search(r"\b(20\d{2})\b", text)
    season = year_match.group(1) if year_match else deadline.replace("year:", "")

    if "ukraine" in text and "presidential election" in text:
        predicate = "hold_election"
        scope = "ukraine_presidential"
    elif "ukraine election called" in text:
        predicate = "election_called"
        scope = "ukraine_presidential"
    elif "nyc mayor" in text or "new york city mayor" in text:
        predicate = "win"
        scope = "nyc_mayor_candidate"
        party_match = re.search(r"representative of the (.+?) party", text)
        candidate_match = re.search(r"will\s+(.+?)\s+win\s+the\s+20\d{2}\s+nyc mayor", text)
        if party_match:
            scope = "nyc_mayor_party_line"
            subject = canonical_alias(party_match.group(1))
        elif candidate_match:
            subject = canonical_alias(candidate_match.group(1))
        else:
            subject = canonical_alias(row.get("yes_sub_title", ""))
    else:
        return None

    if scope != "nyc_mayor_candidate" and scope != "nyc_mayor_party_line":
        subject = first_alias_in_text(text, PARTY_ALIASES)
        if not subject:
            subject = first_alias_in_text(text, PERSON_ALIASES)
    if not deadline and season:
        deadline = f"year:{season}"

    parsed = ParsedContract(
        market_family="election",
        predicate=predicate,
        subject=subject,
        scope=scope,
        deadline=deadline,
        season=season,
        parse_confidence=0.86,
        parse_reason="election template",
    )
    return make_key(parsed)


def parse_sports(text: str, row: pd.Series) -> ParsedContract | None:
    if "qualify" in text:
        predicate = "qualify"
    elif re.search(r"\bwin\b", text):
        predicate = "win"
    else:
        return None

    league_patterns = [
        ("nba_finals", r"nba finals|pro basketball championship"),
        ("mlb_championship", r"pro baseball championship|world series|mlb"),
        ("uefa_champions_league", r"uefa champions league|champions league"),
        ("fifa_world_cup", r"fifa world cup|men's world cup|mens world cup|world cup"),
        ("nfl_super_bowl", r"super bowl|nfl championship"),
        ("nhl_stanley_cup", r"stanley cup|nhl"),
    ]
    scope = ""
    for league, pattern in league_patterns:
        if re.search(pattern, text):
            scope = league
            break
    if not scope:
        return None

    subject = ""
    match = re.search(r"will\s+(?:the\s+)?(.+?)\s+win\s+the\b", text)
    if match:
        subject = canonical_alias(match.group(1), TEAM_ALIASES)
    elif predicate == "qualify":
        match = re.search(r"will\s+(?:the\s+)?(.+?)\s+qualify\b", text)
        if match:
            subject = canonical_alias(match.group(1), TEAM_ALIASES | PLACE_ALIASES)

    if not subject:
        subject = canonical_alias(row.get("yes_sub_title", ""), TEAM_ALIASES | PLACE_ALIASES)

    season_match = re.search(r"\b(20\d{2})\b", text)
    season = season_match.group(1) if season_match else ""
    if not season:
        ticker = clean_text(row.get("ticker", ""))
        ticker_match = re.search(r"-(\d{2})(?:-|$)", ticker)
        if ticker_match:
            season = f"20{ticker_match.group(1)}"

    parsed = ParsedContract(
        market_family="sports",
        predicate=predicate,
        subject=subject,
        scope=scope,
        season=season,
        parse_confidence=0.86,
        parse_reason="sports outcome template",
    )
    return make_key(parsed)


def parse_economic_threshold(text: str, row: pd.Series) -> ParsedContract | None:
    if not re.search(r"\babove\b|\bbelow\b|\breach\b", text):
        return None

    indicator_patterns = [
        ("thirty_year_fixed_mortgage_rate", r"30[- ]year fixed rate mortgage|30-year fixed rate mortgage|mortgage rate"),
        ("new_home_sales", r"new u\.?s\.? home sales|new home sales"),
    ]
    scope = ""
    for indicator, pattern in indicator_patterns:
        if re.search(pattern, text):
            scope = indicator
            break
    if not scope:
        return None

    direction = "above" if "above" in text else "below" if "below" in text else ""
    threshold_match = re.search(r"(\d+(?:,\d{3})*(?:\.\d+)?)\s*%?", text)
    threshold = threshold_match.group(1).replace(",", "") if threshold_match else ""

    parsed = ParsedContract(
        market_family="economic_threshold",
        predicate="threshold",
        scope=scope,
        deadline=extract_deadline(text, row),
        direction=direction,
        threshold=threshold,
        parse_confidence=0.84,
        parse_reason="economic threshold template",
    )
    return make_key(parsed)


def parse_market(exchange: str, row: pd.Series) -> ParsedContract:
    title_col = "question" if exchange == "polymarket" else "title"
    title = clean_text(row.get(title_col, ""))

    if exchange == "polymarket":
        outcomes = clean_text(row.get("outcomes", ""))
        if outcomes and "yes" not in outcomes:
            return ParsedContract(parse_reason="non-binary or non-yes-no polymarket outcome")

    parsers = [
        parse_leader_contact,
        parse_office_exit,
        parse_election,
        parse_sports,
        parse_economic_threshold,
    ]
    for parser in parsers:
        parsed = parser(title, row)
        if parsed and parsed.contract_key:
            return parsed
    return ParsedContract(parse_reason="no supported template")


def row_id(exchange: str, row: pd.Series) -> str:
    return str(row.get("id" if exchange == "polymarket" else "ticker", ""))


def event_group(exchange: str, row: pd.Series) -> str:
    return str(row.get("condition_id" if exchange == "polymarket" else "event_ticker", ""))


def canonicalize(exchange: str, df: pd.DataFrame, source_slug: str = "") -> pd.DataFrame:
    records = []
    title_col = "question" if exchange == "polymarket" else "title"
    for _, row in df.iterrows():
        parsed = parse_market(exchange, row)
        record = {
            "exchange": exchange,
            "source_slug": source_slug,
            "market_id": row_id(exchange, row),
            "event_group": event_group(exchange, row),
            "title": row.get(title_col, ""),
            "yes_sub_title": row.get("yes_sub_title", ""),
            "no_sub_title": row.get("no_sub_title", ""),
            "volume": row.get("volume", ""),
            "created_at": row.get("created_at", row.get("created_time", "")),
            "end_date": row.get("end_date", row.get("close_time", "")),
            "resolver_type": row.get("resolver_type", ""),
            "resolver_evidence": row.get("resolver_evidence", ""),
        }
        record.update(asdict(parsed))
        records.append(record)
    return pd.DataFrame(records)


def resolver_columns(df: pd.DataFrame) -> list[str]:
    generated = {"resolver_type", "resolver_evidence"}
    return [col for col in df.columns if col not in generated and RESOLVER_COLUMN_PATTERN.search(str(col))]


def annotate_pm_resolver_type(pm_df: pd.DataFrame) -> pd.DataFrame:
    pm_df = pm_df.copy()
    cols = resolver_columns(pm_df)
    resolver_types = []
    evidence = []
    for _, row in pm_df.iterrows():
        hits = []
        for col in cols:
            value = row.get(col)
            if pd.notna(value) and UMA_VALUE_PATTERN.search(str(value)):
                hits.append(f"{col}={value}")
        resolver_types.append("uma" if hits else "")
        evidence.append("; ".join(hits))
    pm_df["resolver_type"] = resolver_types
    pm_df["resolver_evidence"] = evidence
    return pm_df


def read_market_key_set(path: str) -> dict[str, set[str]]:
    df = pd.read_csv(path)
    key_map: dict[str, set[str]] = {}
    for col in ("id", "market_id", "pm_id", "condition_id", "slug"):
        if col in df.columns:
            key_map[col] = set(df[col].dropna().astype(str))
    if not key_map:
        raise ValueError("--pm-uma-markets must contain at least one of: id, market_id, pm_id, condition_id, slug.")
    return key_map


def apply_pm_uma_filter(pm_df: pd.DataFrame, uma_path: str = "", uma_only: bool = False) -> pd.DataFrame:
    pm_df = annotate_pm_resolver_type(pm_df)
    if uma_path:
        key_map = read_market_key_set(uma_path)
        mask = pd.Series(False, index=pm_df.index)
        for source_col, values in key_map.items():
            col = "id" if source_col in {"market_id", "pm_id"} and "id" in pm_df.columns else source_col
            if col in pm_df.columns:
                mask = mask | pm_df[col].astype(str).isin(values)
        pm_df = pm_df[mask].copy()
        pm_df["resolver_type"] = "uma"
        current = pm_df.get("resolver_evidence", pd.Series("", index=pm_df.index)).fillna("").astype(str)
        pm_df["resolver_evidence"] = current.mask(current.eq(""), f"external_list:{Path(uma_path).name}")
        return pm_df

    if uma_only:
        detected = pm_df["resolver_type"].eq("uma")
        if detected.any():
            return pm_df[detected].copy()
        cols = resolver_columns(pm_df)
        raise ValueError(
            "No UMA-resolved Polymarket rows were detected. "
            f"Resolver-like columns found: {cols or 'none'}. "
            "Pass --pm-uma-markets with id, market_id, pm_id, condition_id, or slug to define the UMA sample."
        )

    return pm_df


def load_topic_pairs(exports_dir: Path, pm_uma_markets: str = "", pm_uma_only: bool = False) -> list[tuple[str, pd.DataFrame, pd.DataFrame]]:
    pairs = []
    for pm_path in sorted(exports_dir.glob("*_pm_topics.csv")):
        slug = pm_path.name[: -len("_pm_topics.csv")]
        k_path = exports_dir / f"{slug}_k_topics.csv"
        if not k_path.exists():
            continue
        pm_df = apply_pm_uma_filter(pd.read_csv(pm_path), pm_uma_markets, pm_uma_only)
        pairs.append((slug, pm_df, pd.read_csv(k_path)))
    return pairs


def load_archive_markets(data_root: Path, top_n: int, pm_uma_markets: str = "", pm_uma_only: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required for --data-root archive loading.") from exc

    con = duckdb.connect()
    pm_files = glob.glob(str(data_root / "polymarket" / "markets" / "**" / "*.parquet"), recursive=True)
    k_files = glob.glob(str(data_root / "kalshi" / "markets" / "**" / "*.parquet"), recursive=True)
    if not pm_files or not k_files:
        raise FileNotFoundError("Could not find both Polymarket and Kalshi market parquet files.")

    pm_limit = "LIMIT ?" if top_n > 0 else ""
    k_limit = "LIMIT ?" if top_n > 0 else ""
    pm_sql = f"""
        WITH base AS (
            SELECT id, condition_id, question, slug, outcomes, volume, liquidity,
                   active, closed, end_date, created_at, _fetched_at,
                   TRY_CAST(volume AS DOUBLE) AS volume_num,
                   ROW_NUMBER() OVER (
                       PARTITION BY id
                       ORDER BY TRY_CAST(_fetched_at AS TIMESTAMP) DESC
                   ) AS rn
            FROM read_parquet(?)
        )
        SELECT id, condition_id, question, slug, outcomes, volume, liquidity,
               active, closed, end_date, created_at, _fetched_at
        FROM base
        WHERE rn = 1
        ORDER BY COALESCE(volume_num, 0) DESC
        {pm_limit}
    """
    k_sql = f"""
        WITH base AS (
            SELECT ticker, event_ticker, market_type, title, yes_sub_title, no_sub_title,
                   status, yes_bid, yes_ask, no_bid, no_ask, last_price, volume,
                   open_interest, result, created_time, close_time, _fetched_at,
                   TRY_CAST(volume AS DOUBLE) AS volume_num,
                   ROW_NUMBER() OVER (
                       PARTITION BY ticker
                       ORDER BY TRY_CAST(_fetched_at AS TIMESTAMP) DESC
                   ) AS rn
            FROM read_parquet(?)
        )
        SELECT ticker, event_ticker, market_type, title, yes_sub_title, no_sub_title,
               status, yes_bid, yes_ask, no_bid, no_ask, last_price, volume,
               open_interest, result, created_time, close_time, _fetched_at
        FROM base
        WHERE rn = 1
        ORDER BY COALESCE(volume_num, 0) DESC
        {k_limit}
    """
    pm_args = [pm_files, top_n] if top_n > 0 else [pm_files]
    k_args = [k_files, top_n] if top_n > 0 else [k_files]
    pm_df = con.execute(pm_sql, pm_args).fetchdf()
    pm_df = apply_pm_uma_filter(pm_df, pm_uma_markets, pm_uma_only)
    return pm_df, con.execute(k_sql, k_args).fetchdf()


def compare_rows(pm: pd.Series, k: pd.Series) -> str:
    checks = [
        "market_family",
        "predicate",
        "subject",
        "obj",
        "scope",
        "deadline",
        "season",
        "direction",
        "threshold",
    ]
    reasons = []
    for col in checks:
        left = str(pm.get(col, ""))
        right = str(k.get(col, ""))
        if left != right:
            reasons.append(f"{col}_mismatch:{left or '<blank>'}!={right or '<blank>'}")
    return "; ".join(reasons) or "same_contract_key"


def build_matches(canonical: pd.DataFrame) -> pd.DataFrame:
    parsed = canonical[canonical["contract_key"].astype(str).ne("")].copy()
    parsed = parsed.drop_duplicates(subset=["exchange", "market_id", "contract_key"])
    pm = parsed[parsed["exchange"].eq("polymarket")]
    k = parsed[parsed["exchange"].eq("kalshi")]
    matches = pm.merge(k, on="contract_key", suffixes=("_pm", "_kalshi"))
    if matches.empty:
        return matches
    matches["match_confidence"] = matches[["parse_confidence_pm", "parse_confidence_kalshi"]].min(axis=1)
    matches["match_basis"] = "deterministic_contract_key"
    return matches.sort_values(["match_confidence", "contract_key"], ascending=[False, True])


def build_review_candidates(canonical: pd.DataFrame, max_pairs_per_bucket: int = 200) -> pd.DataFrame:
    parsed = canonical[canonical["market_family"].astype(str).ne("")].copy()
    parsed = parsed.drop_duplicates(subset=["exchange", "market_id", "contract_key"])
    pm = parsed[parsed["exchange"].eq("polymarket")]
    k = parsed[parsed["exchange"].eq("kalshi")]
    rows = []
    for signature, pm_bucket in pm.groupby("entity_signature"):
        if not signature:
            continue
        k_bucket = k[k["entity_signature"].eq(signature)]
        if k_bucket.empty:
            continue
        count = 0
        for _, pm_row in pm_bucket.iterrows():
            for _, k_row in k_bucket.iterrows():
                if pm_row["contract_key"] == k_row["contract_key"]:
                    continue
                rows.append(
                    {
                        "entity_signature": signature,
                        "pm_market_id": pm_row["market_id"],
                        "pm_title": pm_row["title"],
                        "pm_contract_key": pm_row["contract_key"],
                        "kalshi_market_id": k_row["market_id"],
                        "kalshi_title": k_row["title"],
                        "kalshi_contract_key": k_row["contract_key"],
                        "reject_reason": compare_rows(pm_row, k_row),
                    }
                )
                count += 1
                if count >= max_pairs_per_bucket:
                    break
            if count >= max_pairs_per_bucket:
                break
    return pd.DataFrame(rows)


def consolidate_canonical(canonical: pd.DataFrame) -> pd.DataFrame:
    if canonical.empty:
        return canonical
    group_cols = [col for col in canonical.columns if col != "source_slug"]
    out = (
        canonical.groupby(group_cols, dropna=False)["source_slug"]
        .apply(lambda s: ";".join(sorted(set(str(x) for x in s if str(x)))))
        .reset_index()
    )
    cols = list(canonical.columns)
    return out[cols]


def write_outputs(canonical_frames: Iterable[pd.DataFrame], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    canonical = consolidate_canonical(pd.concat(list(canonical_frames), ignore_index=True))
    matches = build_matches(canonical)
    review = build_review_candidates(canonical)

    canonical.to_csv(outdir / "contract_canonical_markets.csv", index=False)
    matches.to_csv(outdir / "contract_matches.csv", index=False)
    review.to_csv(outdir / "contract_match_review_candidates.csv", index=False)

    print(f"Canonical markets: {len(canonical):,} -> {outdir / 'contract_canonical_markets.csv'}")
    print(f"Rule matches:      {len(matches):,} -> {outdir / 'contract_matches.csv'}")
    print(f"Review candidates: {len(review):,} -> {outdir / 'contract_match_review_candidates.csv'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build high-precision cross-exchange market matches.")
    parser.add_argument("--exports-dir", default="exports", help="Directory containing *_pm_topics.csv and *_k_topics.csv files.")
    parser.add_argument("--data-root", default="", help="Optional full archive data root containing kalshi/ and polymarket/.")
    parser.add_argument("--top-n", type=int, default=5000, help="In archive mode, keep the top N latest unique markets by volume per exchange. Use 0 for all.")
    parser.add_argument("--kalshi-csv", default="", help="Optional Kalshi market CSV.")
    parser.add_argument("--polymarket-csv", default="", help="Optional Polymarket market CSV.")
    parser.add_argument("--pm-uma-only", action="store_true", help="Restrict Polymarket inputs to rows detected as UMA-resolved.")
    parser.add_argument("--pm-uma-markets", default="", help="CSV defining UMA-resolved PM markets by id, market_id, pm_id, condition_id, or slug.")
    parser.add_argument("--outdir", default="exports", help="Output directory.")
    args = parser.parse_args()

    frames = []
    if args.kalshi_csv and args.polymarket_csv:
        pm_df = apply_pm_uma_filter(pd.read_csv(args.polymarket_csv), args.pm_uma_markets, args.pm_uma_only)
        frames.append(canonicalize("polymarket", pm_df, "custom"))
        frames.append(canonicalize("kalshi", pd.read_csv(args.kalshi_csv), "custom"))
    elif args.data_root:
        pm_df, k_df = load_archive_markets(Path(args.data_root), args.top_n, args.pm_uma_markets, args.pm_uma_only)
        frames.append(canonicalize("polymarket", pm_df, "archive"))
        frames.append(canonicalize("kalshi", k_df, "archive"))
    else:
        pairs = load_topic_pairs(Path(args.exports_dir), args.pm_uma_markets, args.pm_uma_only)
        if not pairs:
            raise FileNotFoundError(f"No *_pm_topics.csv / *_k_topics.csv pairs found in {args.exports_dir}.")
        for slug, pm_df, k_df in pairs:
            frames.append(canonicalize("polymarket", pm_df, slug))
            frames.append(canonicalize("kalshi", k_df, slug))

    write_outputs(frames, Path(args.outdir))


if __name__ == "__main__":
    main()
