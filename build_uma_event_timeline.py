from __future__ import annotations

import argparse
import glob
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import pandas as pd

# The Graph's hosted UMA subgraphs are dead (301) and the current gateway requires a paid
# API key (see docs.uma.xyz/resources/subgraph-data). This script gets the same proposal/
# dispute/vote/resolution timeline directly from contract logs via free RPC endpoints instead.
POLYGON_RPC = "https://polygon.gateway.tenderly.co"
MAINNET_RPC = "https://mainnet.gateway.tenderly.co"

CTF_CONTRACT = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"
OOV2_POLYGON = "0xee3afe347d5c74317041e2618c49534daf887c24"
VOTING_V2_MAINNET = "0x004395edb43efca9885cedad51ec9faf93bd34ac"
CONDITION_PREPARATION_TOPIC = "0xab3760c3bd2bb38b5bcf54dc79802ed67338b4cf29f3054ded67ed24661e4177"
REQUEST_PRICE_TOPIC = "0xf1679315ff325c257a944e0ca1bfe7b26616039e9511f9610d4ba3eca851027b"
PROPOSE_PRICE_TOPIC = "0x6e51dd00371aabffa82cd401592f76ed51e98a9ea4b58751c70463a2c78b5ca1"
DISPUTE_PRICE_TOPIC = "0x5165909c3d1c01c5d1e121ac6f6d01dda1ba24bc9e1f975b5a375339c15be7f3"
SETTLE_TOPIC = "0x3f384afb4bd9f0aef0298c80399950011420eb33b0e1a750b20966270247b9a0"
REQUEST_ADDED_TOPIC = "0x4161f76cfc9e9ae436231be94fe49310565599b4549176e7471c5dff78abcbf1"
VOTE_COMMITTED_TOPIC = "0xcb3360a5c92f7310d655266c30a450dae6323bc9773aad5959198ed60a03111b"
VOTE_REVEALED_TOPIC = "0x97fd2ce926defea5c438a5e8084209a81af5ad8539d8198af200a52e0b7b374c"
REQUEST_RESOLVED_TOPIC = "0x4bd654e0f2fccf397ffdd356a54802a5a7888799057ecac1ca29c523bbeb1433"

PRICE_MEANING = {
    1_000_000_000_000_000_000: "Yes",
    0: "No",
    500_000_000_000_000_000: "50/50 (unknown)",
    -(2**255): "Ignore (too early / reset)",
}

# The two controversies studied in resolution_risk_outline_revised.tex. condition_id comes
# from contract_matching.py's join key; block_search_start/end bound the RPC log scan and
# should cover from well before market creation through well after the market's end_date.
TARGET_MARKETS = {
    "mineral_rights": {
        "condition_id": "0x1663edea3eba0d1ae8f064276dd426cb0497a19bb5188dae48a2f8fa8ea34da8",
        "label": "Ukraine agrees to give Trump rare earth metals before April?",
        "block_search_start": 67490629,
        "block_search_end": 69905589,
    },
    "zelensky_suit": {
        "condition_id": "0x655e5ca101c466b6293aa15e06173b78b293221803d56e35551f708cd82eb352",
        "label": "Will Zelenskyy wear a suit before July?",
        "block_search_start": 71834524,
        "block_search_end": 74168600,
    },
}


def rpc_call(rpc_url: str, method: str, params: list, retries: int = 5) -> object:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
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
            time.sleep(2 * (attempt + 1))
            continue
        if "error" in out:
            if attempt == retries - 1:
                raise RuntimeError(f"RPC error: {out['error']}")
            time.sleep(2 * (attempt + 1))
            continue
        return out["result"]
    raise RuntimeError("RPC request failed unexpectedly.")


def norm32(value: str) -> str:
    return "0x" + value.lower().replace("0x", "").rjust(64, "0")


def chunks(hexstr: str, n: int = 64) -> list[str]:
    return [hexstr[i : i + n] for i in range(0, len(hexstr), n)]


def tail_bytes(words: list[str], offset_word_value: int) -> bytes:
    idx = offset_word_value // 32
    length = int(words[idx], 16)
    hexdata = "".join(words[idx + 1 :])
    return bytes.fromhex(hexdata)[:length]


def scan_logs(rpc_url: str, address: str, topics: list, from_block: int, to_block: int, chunk_size: int = 50_000, sleep_seconds: float = 0.2) -> list[dict]:
    found: list[dict] = []
    start = from_block
    while start <= to_block:
        end = min(start + chunk_size - 1, to_block)
        logs = rpc_call(rpc_url, "eth_getLogs", [{"address": address, "fromBlock": hex(start), "toBlock": hex(end), "topics": topics}])
        found.extend(logs)
        start = end + 1
        if sleep_seconds:
            time.sleep(sleep_seconds)
    return found


def find_oracle_and_question_id(condition_id: str, block_search_start: int, block_search_end: int) -> tuple[str, str, dict]:
    logs = scan_logs(
        POLYGON_RPC,
        CTF_CONTRACT,
        [CONDITION_PREPARATION_TOPIC, norm32(condition_id)],
        block_search_start,
        block_search_end,
    )
    if not logs:
        raise RuntimeError(f"No ConditionPreparation log found for {condition_id} in the given block range.")
    log = logs[0]
    oracle_address = "0x" + log["topics"][2][-40:]
    question_id = norm32(log["topics"][3])
    receipt = rpc_call(POLYGON_RPC, "eth_getTransactionReceipt", [log["transactionHash"]])
    return oracle_address, question_id, receipt


def decode_oo_log(log: dict) -> dict:
    topic0 = log["topics"][0]
    c = chunks(log["data"][2:])
    block = int(log["blockNumber"], 16)
    tx = log["transactionHash"]
    if topic0 == REQUEST_PRICE_TOPIC:
        ancillary = tail_bytes(c, int(c[2], 16))
        return {"event": "RequestPrice", "block": block, "tx": tx, "request_timestamp": int(c[1], 16), "ancillary_head": ancillary[:150]}
    if topic0 == PROPOSE_PRICE_TOPIC:
        ancillary = tail_bytes(c, int(c[2], 16))
        proposed_price = int.from_bytes(bytes.fromhex(c[3]), "big", signed=True)
        return {
            "event": "ProposePrice", "block": block, "tx": tx, "request_timestamp": int(c[1], 16),
            "ancillary_head": ancillary[:150], "proposer": "0x" + log["topics"][2][-40:],
            "proposed_price": proposed_price, "proposed_price_meaning": PRICE_MEANING.get(proposed_price, str(proposed_price)),
        }
    if topic0 == DISPUTE_PRICE_TOPIC:
        ancillary = tail_bytes(c, int(c[2], 16))
        return {
            "event": "DisputePrice", "block": block, "tx": tx, "request_timestamp": int(c[1], 16),
            "ancillary_head": ancillary[:150], "proposer": "0x" + log["topics"][2][-40:],
            "disputer": "0x" + log["topics"][3][-40:],
        }
    if topic0 == SETTLE_TOPIC:
        ancillary = tail_bytes(c, int(c[2], 16))
        price = int.from_bytes(bytes.fromhex(c[3]), "big", signed=True)
        return {
            "event": "Settle", "block": block, "tx": tx, "request_timestamp": int(c[1], 16),
            "ancillary_head": ancillary[:150], "price": price, "price_meaning": PRICE_MEANING.get(price, str(price)),
            "payout": int(c[4], 16),
        }
    return {"event": "unknown", "block": block, "tx": tx}


def block_timestamp(rpc_url: str, block_number: int) -> int:
    block = rpc_call(rpc_url, "eth_getBlockByNumber", [hex(block_number), False])
    return int(block["timestamp"], 16)


def binary_search_block_for_timestamp(rpc_url: str, target_ts: int, lo: int = 1, hi: int | None = None) -> int:
    if hi is None:
        hi = int(rpc_call(rpc_url, "eth_blockNumber", []), 16)
    while lo < hi:
        mid = (lo + hi) // 2
        if block_timestamp(rpc_url, mid) < target_ts:
            lo = mid + 1
        else:
            hi = mid
    return lo


def build_polygon_timeline(oracle_address: str, needle: bytes, block_search_start: int, block_search_end: int) -> pd.DataFrame:
    logs = scan_logs(POLYGON_RPC, OOV2_POLYGON, [None, norm32(oracle_address)], block_search_start, block_search_end)
    rows = []
    for log in logs:
        decoded = decode_oo_log(log)
        if needle in decoded.get("ancillary_head", b""):
            rows.append(decoded)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).sort_values("block").reset_index(drop=True)
    df["block_timestamp"] = df["block"].map(lambda b: block_timestamp(POLYGON_RPC, b))
    df["block_time_utc"] = pd.to_datetime(df["block_timestamp"], unit="s", utc=True)
    df = df.drop(columns=["ancillary_head"])
    return df


def decode_dvm_log(log: dict, wanted_times: set[int]) -> dict | None:
    topic0 = log["topics"][0]
    c = chunks(log["data"][2:]) if log["data"] != "0x" else []
    block = int(log["blockNumber"], 16)
    tx = log["transactionHash"]
    if topic0 == REQUEST_ADDED_TOPIC:
        time_ = int(c[0], 16)
        if time_ not in wanted_times:
            return None
        return {"event": "RequestAdded", "block": block, "tx": tx, "time": time_, "round_id": int(log["topics"][2], 16)}
    if topic0 == VOTE_COMMITTED_TOPIC:
        time_ = int(c[1], 16)
        if time_ not in wanted_times:
            return None
        return {"event": "VoteCommitted", "block": block, "tx": tx, "time": time_, "voter": "0x" + log["topics"][1][-40:]}
    if topic0 == VOTE_REVEALED_TOPIC:
        time_ = int(c[1], 16)
        if time_ not in wanted_times:
            return None
        price = int.from_bytes(bytes.fromhex(c[3]), "big", signed=True)
        return {"event": "VoteRevealed", "block": block, "tx": tx, "time": time_, "voter": "0x" + log["topics"][1][-40:], "price": price}
    if topic0 == REQUEST_RESOLVED_TOPIC:
        time_ = int(c[0], 16)
        if time_ not in wanted_times:
            return None
        price = int.from_bytes(bytes.fromhex(c[2]), "big", signed=True)
        return {"event": "RequestResolved", "block": block, "tx": tx, "time": time_, "round_id": int(log["topics"][1], 16), "price": price}
    return None


def build_dvm_window(identifier: str, dispute_block_timestamps: list[int], propose_block_timestamps: set[int], search_pad_days: int = 10) -> pd.DataFrame:
    # Empirically (verified against known outcomes), the OOv2 -> DVM escalation uses the
    # *proposal* block timestamp as the DVM request's "time" key, not the OO request's
    # original timestamp parameter. Filter on propose_block_timestamps accordingly.
    if not dispute_block_timestamps:
        return pd.DataFrame()
    start_ts = min(dispute_block_timestamps) - search_pad_days * 86400
    end_ts = max(dispute_block_timestamps) + search_pad_days * 86400
    start_block = binary_search_block_for_timestamp(MAINNET_RPC, start_ts)
    end_block = binary_search_block_for_timestamp(MAINNET_RPC, end_ts)
    identifier_topic = "0x" + identifier.encode().ljust(32, b"\x00").hex()
    logs = scan_logs(MAINNET_RPC, VOTING_V2_MAINNET, [None, None, None, identifier_topic], start_block, end_block, chunk_size=10_000)
    rows = []
    for log in logs:
        decoded = decode_dvm_log(log, propose_block_timestamps)
        if decoded:
            rows.append(decoded)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates().sort_values("block").reset_index(drop=True)
    df["block_timestamp"] = df["block"].map(lambda b: block_timestamp(MAINNET_RPC, b))
    df["block_time_utc"] = pd.to_datetime(df["block_timestamp"], unit="s", utc=True)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Build precise UMA proposal/dispute/vote/resolution timelines for the resolution-risk controversy events, via direct contract logs (The Graph's UMA subgraphs are no longer freely queryable).")
    parser.add_argument("--out-dir", type=Path, default=Path("exports"))
    parser.add_argument("--skip-dvm", action="store_true", help="Skip the mainnet VotingV2 commit/reveal scan (Polygon timeline only).")
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    for name, spec in TARGET_MARKETS.items():
        print(f"=== {name}: {spec['label']} ===")
        oracle_address, question_id, _receipt = find_oracle_and_question_id(
            spec["condition_id"], spec["block_search_start"], spec["block_search_end"]
        )
        print(f"  oracle/adapter: {oracle_address}  question_id: {question_id}")

        needle = spec["label"].encode()
        timeline = build_polygon_timeline(oracle_address, needle, spec["block_search_start"], spec["block_search_end"])
        if timeline.empty:
            print("  no OOv2 events found; skipping.")
            continue
        out_path = args.out_dir / f"uma_event_timeline_{name}.csv"
        timeline.to_csv(out_path, index=False)
        print(f"  wrote {out_path} ({len(timeline)} rows)")
        print(timeline[["block_time_utc", "event"]].to_string(index=False))

        if args.skip_dvm:
            continue
        dispute_rows = timeline[timeline["event"] == "DisputePrice"]
        if dispute_rows.empty:
            continue
        propose_ts = set(timeline.loc[timeline["event"] == "ProposePrice", "block_timestamp"])
        dvm = build_dvm_window(identifier="YES_OR_NO_QUERY", dispute_block_timestamps=dispute_rows["block_timestamp"].tolist(), propose_block_timestamps=propose_ts)
        if dvm.empty:
            print("  no matching DVM (mainnet VotingV2) events found.")
            continue
        dvm_out_path = args.out_dir / f"uma_dvm_vote_timeline_{name}.csv"
        dvm.to_csv(dvm_out_path, index=False)
        print(f"  wrote {dvm_out_path} ({len(dvm)} rows)")
        print(dvm[["block_time_utc", "event"]].to_string(index=False))


if __name__ == "__main__":
    main()
