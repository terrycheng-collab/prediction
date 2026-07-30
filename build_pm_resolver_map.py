from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd


CTF_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
UMA_ADAPTER_V1 = "0xCB1822859cEF82Cd2Eb4E6276C7916e692995130"
UMA_ADAPTER_V2 = "0x6A9D222616C90FcA5754cd1333cFD9b7fb6a4F74"
UMA_ADAPTER_V3 = "0x157Ce2d672854c848c9b79C49a8Cc6cc89176a49"
NEG_RISK_ADAPTER = "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296"
NEG_RISK_OPERATOR = "0x71523d0f655B41E805Cec45b17163f528B59B820"
NEG_RISK_UMA_ADAPTER = "0x2F5e3684cb1F318ec51b00Edba38d79Ac2c0aA9d"
CONDITION_PREPARATION_TOPIC = "0xab3760c3bd2bb38b5bcf54dc79802ed67338b4cf29f3054ded67ed24661e4177"
NEG_RISK_QUESTION_PREPARED_TOPIC = "0xcdc45423ec79c60a3fe3de57272e598d71a4ec88822e822ac8e134184a8435aa"
UMA_QUESTION_INITIALIZED_TOPIC = "0xeee0897acd6893adcaf2ba5158191b3601098ab6bece35c5d57874340b64c5b7"
ORACLE_SELECTOR = "0x7dc0d1d0"
CTF_SELECTOR = "0x22a9339f"
DEFAULT_RPC = "https://polygon-bor-rpc.publicnode.com"
KNOWN_ORACLE_ADDRESSES = {
    UMA_ADAPTER_V1.lower(): "uma_adapter_v1",
    UMA_ADAPTER_V2.lower(): "uma_adapter_v2",
    UMA_ADAPTER_V3.lower(): "uma_adapter_v3",
    NEG_RISK_ADAPTER.lower(): "neg_risk_adapter",
}


def rpc_call(rpc_url: str, method: str, params: list, request_id: int = 1, retries: int = 4) -> dict:
    payload = {"jsonrpc": "2.0", "id": request_id, "method": method, "params": params}
    data = json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": "prediction-market-research"}
    for attempt in range(retries):
        request = urllib.request.Request(rpc_url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                out = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == retries - 1:
                raise RuntimeError(f"RPC request failed after {retries} attempts: {exc}") from exc
            time.sleep(1.5 * (attempt + 1))
            continue
        if "error" in out:
            message = out["error"].get("message", str(out["error"]))
            if attempt == retries - 1:
                raise RuntimeError(f"RPC error: {message}")
            time.sleep(1.5 * (attempt + 1))
            continue
        return out["result"]
    raise RuntimeError("RPC request failed unexpectedly.")


def normalize_hex(value: object, bytes_len: int | None = None) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    if not text.startswith("0x"):
        text = "0x" + text
    if bytes_len is not None:
        text = "0x" + text[2:].rjust(bytes_len * 2, "0")
    return text


def topic_address(address: str) -> str:
    return normalize_hex(address, bytes_len=32)


def eth_call_address(rpc_url: str, contract: str, selector: str, request_id: int) -> str:
    result = rpc_call(rpc_url, "eth_call", [{"to": contract, "data": selector}, "latest"], request_id=request_id)
    if not isinstance(result, str) or len(result) < 42:
        return ""
    return "0x" + result[-40:].lower()


def block_for_timestamp(blocks_df: pd.DataFrame, timestamp: pd.Timestamp, side: str) -> int:
    ts = timestamp.tz_convert("UTC").tz_localize(None)
    if side == "left":
        subset = blocks_df[blocks_df["ts"].le(ts)]
        if subset.empty:
            return int(blocks_df["block_number"].min())
        return int(subset.iloc[-1]["block_number"])
    subset = blocks_df[blocks_df["ts"].ge(ts)]
    if subset.empty:
        return int(blocks_df["block_number"].max())
    return int(subset.iloc[0]["block_number"])


def load_block_bounds(data_root: Path, start_ts: pd.Timestamp, end_ts: pd.Timestamp, buffer_blocks: int) -> tuple[int, int]:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required to map timestamps to Polygon blocks.") from exc

    block_files = [
        str(path)
        for path in (data_root / "polymarket" / "blocks").glob("**/*.parquet")
        if not path.name.startswith("._")
    ]
    if not block_files:
        raise FileNotFoundError(f"No block parquet files found under {data_root / 'polymarket' / 'blocks'}.")

    con = duckdb.connect()
    start_naive = (start_ts - pd.Timedelta(days=30)).tz_convert("UTC").tz_localize(None)
    end_naive = (end_ts + pd.Timedelta(days=30)).tz_convert("UTC").tz_localize(None)
    blocks = con.execute(
        """
        SELECT block_number, CAST(timestamp AS TIMESTAMP) AS ts
        FROM read_parquet(?)
        WHERE CAST(timestamp AS TIMESTAMP) BETWEEN CAST(? AS TIMESTAMP) AND CAST(? AS TIMESTAMP)
        ORDER BY block_number
        """,
        [block_files, start_naive, end_naive],
    ).fetchdf()
    if blocks.empty:
        raise ValueError("No local block timestamps found for requested time range.")
    from_block = max(0, block_for_timestamp(blocks, start_ts, "left") - buffer_blocks)
    to_block = block_for_timestamp(blocks, end_ts, "right") + buffer_blocks
    return from_block, to_block


def load_matched_conditions(matches_path: Path) -> pd.DataFrame:
    matches = pd.read_csv(matches_path)
    out = matches[
        [
            "market_id_pm",
            "event_group_pm",
            "title_pm",
            "market_family_pm",
            "contract_key",
            "created_at_pm",
            "end_date_pm",
            "match_basis",
        ]
    ].drop_duplicates()
    out = out.rename(columns={"event_group_pm": "condition_id"})
    out["condition_id"] = out["condition_id"].map(lambda value: normalize_hex(value, bytes_len=32))
    out["created_at_pm"] = pd.to_datetime(out["created_at_pm"], utc=True, errors="coerce")
    out["end_date_pm"] = pd.to_datetime(out["end_date_pm"], utc=True, errors="coerce")
    return out


def scan_condition_preparation_logs(
    rpc_url: str,
    condition_ids: list[str],
    from_block: int,
    to_block: int,
    chunk_size: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    rows = []
    condition_topics = sorted(set(condition_ids))
    request_id = 1
    for start in range(from_block, to_block + 1, chunk_size):
        end = min(start + chunk_size - 1, to_block)
        params = [
            {
                "address": CTF_CONTRACT,
                "fromBlock": hex(start),
                "toBlock": hex(end),
                "topics": [CONDITION_PREPARATION_TOPIC, condition_topics],
            }
        ]
        logs = rpc_call(rpc_url, "eth_getLogs", params, request_id=request_id)
        request_id += 1
        for log in logs:
            topics = log.get("topics", [])
            if len(topics) < 4:
                continue
            data = str(log.get("data", "0x0"))
            outcome_slot_count = int(data, 16) if data and data != "0x" else None
            rows.append(
                {
                    "condition_id": normalize_hex(topics[1], bytes_len=32),
                    "oracle_address": "0x" + topics[2][-40:].lower(),
                    "question_id": normalize_hex(topics[3], bytes_len=32),
                    "outcome_slot_count": outcome_slot_count,
                    "prepared_block": int(log["blockNumber"], 16),
                    "prepared_tx": log["transactionHash"],
                    "log_index": int(log["logIndex"], 16),
                }
            )
        if sleep_seconds:
            time.sleep(sleep_seconds)
        print(f"scanned {start:,}-{end:,}; logs={len(logs)}")
    return pd.DataFrame(rows)


def build_resolver_map(matches: pd.DataFrame, logs: pd.DataFrame) -> pd.DataFrame:
    if logs.empty:
        merged = matches.copy()
        for col in ["oracle_address", "question_id", "outcome_slot_count", "prepared_block", "prepared_tx", "log_index"]:
            merged[col] = pd.NA
    else:
        logs = logs.sort_values(["condition_id", "prepared_block", "log_index"]).drop_duplicates("condition_id", keep="first")
        merged = matches.merge(logs, on="condition_id", how="left")
    merged["resolver_contract_type"] = merged["oracle_address"].fillna("").str.lower().map(
        lambda address: KNOWN_ORACLE_ADDRESSES.get(address, "other") if address else "not_found"
    )
    merged["resolver_type_onchain"] = merged["resolver_contract_type"].map(
        lambda contract_type: "uma_direct"
        if contract_type.startswith("uma_adapter")
        else "neg_risk_adapter"
        if contract_type == "neg_risk_adapter"
        else "other"
        if contract_type == "other"
        else "not_found"
    )
    merged["resolver_source"] = merged["resolver_type_onchain"].map(
        {
            "uma_direct": "ctf_condition_preparation_oracle",
            "neg_risk_adapter": "ctf_condition_preparation_oracle",
            "other": "ctf_condition_preparation_oracle",
            "not_found": "no_condition_preparation_log_found",
        }
    )
    return merged


def extract_neg_risk_request_ids(rpc_url: str, resolver_map: pd.DataFrame) -> pd.DataFrame:
    neg = resolver_map[resolver_map["resolver_type_onchain"].eq("neg_risk_adapter")].copy()
    if neg.empty:
        return pd.DataFrame(columns=["condition_id", "neg_risk_market_id", "neg_risk_request_id"])

    receipts: dict[str, dict] = {}
    rows = []
    request_id = 20_000
    for _, row in neg.iterrows():
        tx_hash = str(row["prepared_tx"])
        if tx_hash not in receipts:
            receipts[tx_hash] = rpc_call(rpc_url, "eth_getTransactionReceipt", [tx_hash], request_id=request_id)
            request_id += 1
        receipt = receipts[tx_hash]
        row_question_id = normalize_hex(row["question_id"], bytes_len=32)
        matching_logs = []
        for log in receipt.get("logs", []):
            if str(log.get("address", "")).lower() != NEG_RISK_OPERATOR.lower():
                continue
            topics = log.get("topics", [])
            if len(topics) < 4 or topics[0].lower() != NEG_RISK_QUESTION_PREPARED_TOPIC:
                continue
            if normalize_hex(topics[2], bytes_len=32) == row_question_id:
                matching_logs.append(log)

        if len(matching_logs) == 1:
            topics = matching_logs[0]["topics"]
            rows.append(
                {
                    "condition_id": row["condition_id"],
                    "neg_risk_market_id": normalize_hex(topics[1], bytes_len=32),
                    "neg_risk_request_id": normalize_hex(topics[3], bytes_len=32),
                }
            )
        else:
            rows.append(
                {
                    "condition_id": row["condition_id"],
                    "neg_risk_market_id": "",
                    "neg_risk_request_id": "",
                }
            )
    return pd.DataFrame(rows)


def scan_neg_risk_uma_initialization_logs(
    rpc_url: str,
    request_ids: list[str],
    from_block: int,
    to_block: int,
    chunk_size: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    rows = []
    request_topics = sorted({rid for rid in request_ids if rid})
    if not request_topics:
        return pd.DataFrame(columns=["neg_risk_request_id", "neg_risk_request_init_block", "neg_risk_request_init_tx"])

    request_id = 30_000
    for start in range(from_block, to_block + 1, chunk_size):
        end = min(start + chunk_size - 1, to_block)
        params = [
            {
                "address": NEG_RISK_UMA_ADAPTER,
                "fromBlock": hex(start),
                "toBlock": hex(end),
                "topics": [UMA_QUESTION_INITIALIZED_TOPIC, request_topics],
            }
        ]
        logs = rpc_call(rpc_url, "eth_getLogs", params, request_id=request_id)
        request_id += 1
        for log in logs:
            rows.append(
                {
                    "neg_risk_request_id": normalize_hex(log["topics"][1], bytes_len=32),
                    "neg_risk_request_init_block": int(log["blockNumber"], 16),
                    "neg_risk_request_init_tx": log["transactionHash"],
                    "neg_risk_request_init_log_index": int(log["logIndex"], 16),
                }
            )
        if sleep_seconds:
            time.sleep(sleep_seconds)
        print(f"scanned NegRisk UMA init {start:,}-{end:,}; logs={len(logs)}")
    return pd.DataFrame(rows)


def classify_neg_risk_resolvers(
    rpc_url: str,
    resolver_map: pd.DataFrame,
    from_block: int,
    to_block: int,
    chunk_size: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    out = resolver_map.copy()
    out["neg_risk_operator_address"] = pd.NA
    out["neg_risk_operator_oracle"] = pd.NA
    out["neg_risk_uma_adapter_ctf"] = pd.NA
    out["neg_risk_market_id"] = pd.NA
    out["neg_risk_request_id"] = pd.NA
    out["neg_risk_request_initialized"] = False
    out["neg_risk_request_init_block"] = pd.NA
    out["neg_risk_request_init_tx"] = pd.NA
    out["neg_risk_request_init_log_index"] = pd.NA

    operator_oracle = eth_call_address(rpc_url, NEG_RISK_OPERATOR, ORACLE_SELECTOR, request_id=10_001)
    uma_adapter_ctf = eth_call_address(rpc_url, NEG_RISK_UMA_ADAPTER, CTF_SELECTOR, request_id=10_002)
    neg_mask = out["resolver_type_onchain"].eq("neg_risk_adapter")
    out.loc[neg_mask, "neg_risk_operator_address"] = NEG_RISK_OPERATOR.lower()
    out.loc[neg_mask, "neg_risk_operator_oracle"] = operator_oracle
    out.loc[neg_mask, "neg_risk_uma_adapter_ctf"] = uma_adapter_ctf

    request_links = extract_neg_risk_request_ids(rpc_url, out)
    if not request_links.empty:
        out = out.merge(request_links, on="condition_id", how="left", suffixes=("", "_from_receipt"))
        for col in ["neg_risk_market_id", "neg_risk_request_id"]:
            receipt_col = f"{col}_from_receipt"
            if receipt_col in out.columns:
                out[col] = out[receipt_col].combine_first(out[col])
                out = out.drop(columns=[receipt_col])

        init_logs = scan_neg_risk_uma_initialization_logs(
            rpc_url=rpc_url,
            request_ids=request_links["neg_risk_request_id"].dropna().tolist(),
            from_block=from_block,
            to_block=to_block,
            chunk_size=max(chunk_size, 500_000),
            sleep_seconds=sleep_seconds,
        )
        if not init_logs.empty:
            init_logs = init_logs.sort_values(
                ["neg_risk_request_id", "neg_risk_request_init_block", "neg_risk_request_init_log_index"]
            ).drop_duplicates("neg_risk_request_id", keep="first")
            out = out.merge(init_logs, on="neg_risk_request_id", how="left", suffixes=("", "_from_log"))
            for col in ["neg_risk_request_init_block", "neg_risk_request_init_tx", "neg_risk_request_init_log_index"]:
                log_col = f"{col}_from_log"
                if log_col in out.columns:
                    out[col] = out[log_col].combine_first(out[col])
                    out = out.drop(columns=[log_col])
            out["neg_risk_request_initialized"] = out["neg_risk_request_init_block"].notna()

    operator_uses_neg_risk_uma = operator_oracle.lower() == NEG_RISK_UMA_ADAPTER.lower()
    neg_risk_uma_points_to_operator = uma_adapter_ctf.lower() == NEG_RISK_OPERATOR.lower()
    out["ultimate_resolver_type"] = out["resolver_type_onchain"]
    out.loc[out["resolver_type_onchain"].eq("uma_direct"), "ultimate_resolver_type"] = "uma"
    out.loc[
        neg_mask & operator_uses_neg_risk_uma & neg_risk_uma_points_to_operator & out["neg_risk_request_initialized"],
        "ultimate_resolver_type",
    ] = "uma_via_neg_risk_adapter"
    out.loc[
        neg_mask & operator_uses_neg_risk_uma & neg_risk_uma_points_to_operator & ~out["neg_risk_request_initialized"],
        "ultimate_resolver_type",
    ] = "neg_risk_configured_to_uma_unverified_question"
    if not (operator_uses_neg_risk_uma and neg_risk_uma_points_to_operator):
        out.loc[neg_mask, "ultimate_resolver_type"] = "neg_risk_not_uma_or_unknown"
    out["uma_backed"] = out["ultimate_resolver_type"].isin(["uma", "uma_via_neg_risk_adapter"])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify matched Polymarket market resolvers from CTF ConditionPreparation logs.")
    parser.add_argument("--matches-path", type=Path, default=Path("exports/event_active_contracts/contract_matches.csv"))
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("exports/pm_matched_resolver_map.csv"))
    parser.add_argument("--rpc-url", default=DEFAULT_RPC)
    parser.add_argument("--chunk-size", type=int, default=10_000)
    parser.add_argument("--buffer-blocks", type=int, default=200_000)
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument(
        "--skip-neg-risk-classification",
        action="store_true",
        help="Skip receipt-level NegRiskOperator to NegRiskUmaCtfAdapter classification.",
    )
    args = parser.parse_args()

    matches = load_matched_conditions(args.matches_path)
    start_ts = matches["created_at_pm"].min() - pd.Timedelta(days=7)
    end_ts = matches["created_at_pm"].max() + pd.Timedelta(days=7)
    from_block, to_block = load_block_bounds(args.data_root, start_ts, end_ts, args.buffer_blocks)
    print(f"matched conditions: {matches['condition_id'].nunique():,}")
    print(f"block scan range: {from_block:,}-{to_block:,}")

    logs = scan_condition_preparation_logs(
        rpc_url=args.rpc_url,
        condition_ids=matches["condition_id"].dropna().tolist(),
        from_block=from_block,
        to_block=to_block,
        chunk_size=args.chunk_size,
        sleep_seconds=args.sleep_seconds,
    )
    resolver_map = build_resolver_map(matches, logs)
    if not args.skip_neg_risk_classification:
        resolver_map = classify_neg_risk_resolvers(
            rpc_url=args.rpc_url,
            resolver_map=resolver_map,
            from_block=from_block,
            to_block=to_block,
            chunk_size=args.chunk_size,
            sleep_seconds=args.sleep_seconds,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    resolver_map.to_csv(args.out, index=False)

    print(f"logs found: {len(logs):,}")
    print(f"resolver map: {args.out}")
    print(resolver_map["resolver_type_onchain"].value_counts(dropna=False).to_string())
    if "ultimate_resolver_type" in resolver_map.columns:
        print(resolver_map["ultimate_resolver_type"].value_counts(dropna=False).to_string())
        print(f"UMA-backed share: {resolver_map['uma_backed'].mean():.1%}")
    coverage = resolver_map["resolver_type_onchain"].ne("not_found").mean()
    print(f"coverage: {coverage:.1%}")


if __name__ == "__main__":
    main()
