from __future__ import annotations

import argparse
import glob
import math
import struct
import zlib
from pathlib import Path

import numpy as np
import pandas as pd


EVENTS = {
    "mineral_rights": {
        "event_start": "2025-03-24",
        "event_end": "2025-03-24",
        "label": "Mineral rights",
    },
    "zelensky_suit": {
        "event_start": "2025-06-30",
        "event_end": "2025-07-08",
        "label": "Zelensky suit",
    },
}

PACIFIC_TZ = "America/Los_Angeles"
PM_RESOLVER_PROXIES = {
    "uma_risk_exposed": {"election", "office_exit", "leader_contact", "policy_action"},
    "uma_likely_objective": {"sports", "fed_count", "fed_decision"},
    "chainlink_or_automated_likely": {"asset_threshold"},
}

OUTCOME_MODES = {
    "raw": ["pm_yes_price", "pm_minus_k"],
    "attenuation": ["pm_abs_from_50", "pm_abs_minus_k_abs_from_50"],
    "both": ["pm_yes_price", "pm_minus_k", "pm_abs_from_50", "pm_abs_minus_k_abs_from_50"],
}

PLOT_SERIES = {
    "raw": [
        ("weighted_pm_yes_price", "Weighted PM Yes price", "#1f77b4"),
        ("weighted_pm_minus_k", "Weighted PM - Kalshi spread", "#2ca02c"),
    ],
    "attenuation": [
        ("weighted_pm_abs_from_50", "Weighted |PM - 0.50|", "#1f77b4"),
        ("weighted_pm_abs_minus_k_abs_from_50", "Weighted |PM - 0.50| - |K - 0.50|", "#2ca02c"),
    ],
}


def classify_pm_resolver_proxy(market_family: object) -> str:
    family = str(market_family or "").strip()
    for proxy, families in PM_RESOLVER_PROXIES.items():
        if family in families:
            return proxy
    return "unknown"


def event_start_timestamp(event_spec: dict[str, str]) -> pd.Timestamp:
    return pd.Timestamp(event_spec["event_start"], tz=PACIFIC_TZ)


def event_end_exclusive_timestamp(event_spec: dict[str, str]) -> pd.Timestamp:
    return pd.Timestamp(event_spec["event_end"], tz=PACIFIC_TZ) + pd.Timedelta(days=1)


FONT_5X7 = {
    " ": ["00000", "00000", "00000", "00000", "00000", "00000", "00000"],
    "-": ["00000", "00000", "00000", "11111", "00000", "00000", "00000"],
    ".": ["00000", "00000", "00000", "00000", "00000", "01100", "01100"],
    ":": ["00000", "01100", "01100", "00000", "01100", "01100", "00000"],
    "/": ["00001", "00010", "00100", "01000", "10000", "00000", "00000"],
    "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01110", "10001", "10000", "10000", "10000", "10001", "01110"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01110", "10001", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["01110", "00100", "00100", "00100", "00100", "00100", "01110"],
    "J": ["00001", "00001", "00001", "00001", "10001", "10001", "01110"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "10101", "01010"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
}


def normalize_id(series: pd.Series) -> pd.Series:
    return series.astype(str).str.replace(r"\.0$", "", regex=True)


def build_cutoffs(event_spec: dict[str, str], window_days: int) -> pd.DataFrame:
    event_start = event_start_timestamp(event_spec)
    event_end = pd.Timestamp(event_spec["event_end"], tz=PACIFIC_TZ)
    start_date_local = (event_start - pd.Timedelta(days=window_days)).normalize()
    end_date_local = (event_end + pd.Timedelta(days=window_days)).normalize()

    rows = []
    for day in pd.date_range(start_date_local, end_date_local, freq="D", tz=PACIFIC_TZ):
        for hour, tag in [(5, "open_0500_PT"), (17, "close_1700_PT")]:
            cutoff_local = day.normalize() + pd.Timedelta(hours=hour)
            rows.append(
                {
                    "cutoff_local": cutoff_local,
                    "cutoff_utc": cutoff_local.tz_convert("UTC"),
                    "cutoff_label": f"{day.strftime('%Y_%m_%d')}_{tag}",
                }
            )
    return pd.DataFrame(rows)


def asof_snapshots(
    trades_df: pd.DataFrame,
    targets_df: pd.DataFrame,
    by_col: str,
    trade_time_col: str = "trade_ts_utc",
    target_time_col: str = "cutoff_utc",
) -> pd.DataFrame:
    left = targets_df.dropna(subset=[by_col, target_time_col]).copy()
    right = trades_df.dropna(subset=[by_col, trade_time_col]).copy()

    left[target_time_col] = pd.to_datetime(left[target_time_col], utc=True)
    right[trade_time_col] = pd.to_datetime(right[trade_time_col], utc=True)
    left = left.sort_values([target_time_col, by_col]).reset_index(drop=True)
    right = right.sort_values([trade_time_col, by_col]).reset_index(drop=True)

    return pd.merge_asof(
        left,
        right,
        left_on=target_time_col,
        right_on=trade_time_col,
        by=by_col,
        direction="backward",
        allow_exact_matches=True,
    )


def read_strict_matches(exports_dir: Path, event_slug: str) -> pd.DataFrame:
    matches = pd.read_csv(exports_dir / "contract_matches.csv")
    matches = matches[matches["match_basis"].eq("deterministic_contract_key")].copy()
    event_mask = (
        matches["source_slug_pm"].fillna("").str.contains(event_slug, regex=False)
        | matches["source_slug_kalshi"].fillna("").str.contains(event_slug, regex=False)
    )
    matches = matches[event_mask].copy()
    matches["market_id_pm"] = normalize_id(matches["market_id_pm"])
    matches["market_id_kalshi"] = matches["market_id_kalshi"].astype(str)
    matches["contract_pair_id"] = (
        event_slug
        + "|"
        + matches["contract_key"].astype(str)
        + "|"
        + matches["market_id_pm"]
        + "|"
        + matches["market_id_kalshi"]
    )
    return matches


def require_unique(df: pd.DataFrame, keys: list[str], name: str) -> None:
    dupes = df[df.duplicated(keys, keep=False)]
    if not dupes.empty:
        sample = dupes[keys].head(10).to_dict("records")
        raise ValueError(f"{name} has duplicate rows for {keys}: {sample}")


def read_event_prices(exports_dir: Path, event_slug: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    pm = pd.read_csv(exports_dir / f"{event_slug}_pm_long.csv")
    pm["id"] = normalize_id(pm["id"])
    pm = pm[pm["outcome_slug"].eq("yes")].copy()
    pm = pm.rename(columns={"id": "market_id_pm", "price": "pm_yes_price"})
    pm = pm[["market_id_pm", "cutoff_label", "cutoff_utc", "cutoff_local", "pm_yes_price"]]
    require_unique(pm, ["market_id_pm", "cutoff_label"], f"{event_slug} PM Yes prices")

    kalshi = pd.read_csv(exports_dir / f"{event_slug}_k_long.csv")
    kalshi["ticker"] = kalshi["ticker"].astype(str)
    kalshi = kalshi.rename(columns={"ticker": "market_id_kalshi", "price": "k_yes_price"})
    kalshi = kalshi[["market_id_kalshi", "cutoff_label", "k_yes_price"]]
    require_unique(kalshi, ["market_id_kalshi", "cutoff_label"], f"{event_slug} Kalshi prices")
    return pm, kalshi


def build_event_panel(exports_dir: Path, event_slug: str, event_spec: dict[str, str]) -> pd.DataFrame:
    matches = read_strict_matches(exports_dir, event_slug)
    pm, kalshi = read_event_prices(exports_dir, event_slug)

    panel = (
        matches.merge(pm, on="market_id_pm", how="inner")
        .merge(kalshi, on=["market_id_kalshi", "cutoff_label"], how="inner")
        .copy()
    )
    panel = panel.dropna(subset=["pm_yes_price", "k_yes_price", "volume_pm"])
    panel = panel[panel["volume_pm"].gt(0)].copy()

    event_start = event_start_timestamp(event_spec)
    event_end = pd.Timestamp(event_spec["event_end"], tz=PACIFIC_TZ)
    cutoff_local = pd.to_datetime(panel["cutoff_local"], utc=True).dt.tz_convert(PACIFIC_TZ)

    panel["event_slug"] = event_slug
    panel["event_start"] = event_start.date().isoformat()
    panel["event_end"] = event_end.date().isoformat()
    panel["cutoff_local"] = cutoff_local
    panel["cutoff_date"] = cutoff_local.dt.date.astype(str)
    panel["relative_day"] = (cutoff_local.dt.normalize() - event_start).dt.days
    panel["post"] = (cutoff_local >= event_start).astype(int)
    panel["pm_minus_k"] = panel["pm_yes_price"] - panel["k_yes_price"]
    panel["pm_abs_from_50"] = (panel["pm_yes_price"] - 0.5).abs()
    panel["k_abs_from_50"] = (panel["k_yes_price"] - 0.5).abs()
    panel["pm_abs_minus_k_abs_from_50"] = panel["pm_abs_from_50"] - panel["k_abs_from_50"]
    panel["weight_pm_volume"] = panel["volume_pm"].astype(float)

    output_cols = [
        "event_slug",
        "event_start",
        "event_end",
        "cutoff_label",
        "cutoff_utc",
        "cutoff_local",
        "cutoff_date",
        "relative_day",
        "post",
        "contract_pair_id",
        "contract_key",
        "market_id_pm",
        "title_pm",
        "market_id_kalshi",
        "title_kalshi",
        "volume_pm",
        "weight_pm_volume",
        "pm_yes_price",
        "k_yes_price",
        "pm_minus_k",
        "pm_abs_from_50",
        "k_abs_from_50",
        "pm_abs_minus_k_abs_from_50",
        "match_confidence",
        "match_basis",
    ]
    panel = panel[output_cols].sort_values(["event_slug", "cutoff_local", "contract_pair_id"])
    require_unique(panel, ["event_slug", "contract_pair_id", "cutoff_label"], f"{event_slug} matched panel")
    return panel


def read_event_active_matches(matches_dir: Path) -> pd.DataFrame:
    matches = pd.read_csv(matches_dir / "contract_matches.csv")
    matches = matches[matches["match_basis"].eq("deterministic_contract_key")].copy()
    matches["pm_resolver_proxy"] = matches["market_family_pm"].map(classify_pm_resolver_proxy)
    matches["resolver_type_onchain"] = pd.NA
    matches["ultimate_resolver_type"] = pd.NA
    matches["uma_backed"] = pd.NA
    matches["neg_risk_request_initialized"] = pd.NA
    matches["market_id_pm"] = normalize_id(matches["market_id_pm"])
    matches["market_id_kalshi"] = matches["market_id_kalshi"].astype(str)
    matches["token_id_pm"] = matches["token_id_pm"].astype(str)
    matches["contract_pair_id"] = (
        matches["contract_key"].astype(str)
        + "|"
        + matches["market_id_pm"]
        + "|"
        + matches["token_id_pm"]
        + "|"
        + matches["market_id_kalshi"]
    )
    matches["pm_price_source"] = np.where(
        matches["synthetic_binary_pm"].astype(str).str.lower().eq("true"),
        "synthetic_binary_outcome_token_price",
        "binary_yes_token_price",
    )
    return matches


def attach_resolver_map(matches: pd.DataFrame, resolver_map_path: Path | None) -> pd.DataFrame:
    if resolver_map_path is None or not resolver_map_path.exists():
        return matches

    resolver_map = pd.read_csv(resolver_map_path)
    wanted = [
        "market_id_pm",
        "resolver_type_onchain",
        "ultimate_resolver_type",
        "uma_backed",
        "neg_risk_request_initialized",
    ]
    available = [col for col in wanted if col in resolver_map.columns]
    resolver_map = resolver_map[available].drop_duplicates("market_id_pm").copy()
    resolver_map["market_id_pm"] = normalize_id(resolver_map["market_id_pm"])

    out = matches.merge(resolver_map, on="market_id_pm", how="left", suffixes=("", "_onchain"))
    for col in wanted[1:]:
        onchain_col = f"{col}_onchain"
        if onchain_col in out.columns:
            out[col] = out[onchain_col].combine_first(out[col])
            out = out.drop(columns=[onchain_col])
    out["uma_backed"] = out["uma_backed"].map(
        lambda value: value if pd.isna(value) or isinstance(value, bool) else str(value).strip().lower() == "true"
    )
    out["neg_risk_request_initialized"] = out["neg_risk_request_initialized"].map(
        lambda value: value if pd.isna(value) or isinstance(value, bool) else str(value).strip().lower() == "true"
    )
    return out


def fetch_pm_token_prices(data_root: Path, token_ids: pd.Series, max_cutoff_utc: pd.Timestamp) -> pd.DataFrame:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required to build price histories from raw parquet data.") from exc

    pm_trade_files = [
        path
        for path in glob.glob(str(data_root / "polymarket" / "trades" / "**" / "*.parquet"), recursive=True)
        if not Path(path).name.startswith("._")
    ]
    pm_block_files = [
        path
        for path in glob.glob(str(data_root / "polymarket" / "blocks" / "**" / "*.parquet"), recursive=True)
        if not Path(path).name.startswith("._")
    ]
    if not pm_trade_files or not pm_block_files:
        raise FileNotFoundError("Could not find Polymarket trade/block parquet files under data_root.")

    token_keys = pd.DataFrame({"token_id_pm": sorted(set(token_ids.dropna().astype(str)))})
    con = duckdb.connect()
    con.register("pm_token_keys", token_keys)
    final_cutoff = max_cutoff_utc.tz_convert("UTC").tz_localize(None).strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        WITH trades AS (
            SELECT
                CASE
                    WHEN CAST(t.maker_asset_id AS VARCHAR) = '0'
                        THEN CAST(t.taker_asset_id AS VARCHAR)
                    ELSE CAST(t.maker_asset_id AS VARCHAR)
                END AS token_id_pm,
                t.block_number,
                CASE
                    WHEN CAST(t.maker_asset_id AS VARCHAR) = '0'
                        THEN CAST(t.maker_amount AS DOUBLE) / NULLIF(CAST(t.taker_amount AS DOUBLE), 0)
                    ELSE CAST(t.taker_amount AS DOUBLE) / NULLIF(CAST(t.maker_amount AS DOUBLE), 0)
                END AS pm_yes_price
            FROM read_parquet(?) t
            WHERE CAST(t.maker_asset_id AS VARCHAR) IN (SELECT token_id_pm FROM pm_token_keys)
               OR CAST(t.taker_asset_id AS VARCHAR) IN (SELECT token_id_pm FROM pm_token_keys)
        ),
        blocks AS (
            SELECT
                block_number,
                CAST(timestamp AS TIMESTAMP) AS block_ts
            FROM read_parquet(?)
            WHERE CAST(timestamp AS TIMESTAMP) <= CAST(? AS TIMESTAMP)
        )
        SELECT
            t.token_id_pm,
            b.block_ts AS trade_ts_utc,
            t.pm_yes_price
        FROM trades t
        JOIN pm_token_keys k
          ON t.token_id_pm = k.token_id_pm
        JOIN blocks b
          ON t.block_number = b.block_number
    """
    trades = con.execute(sql, [pm_trade_files, pm_block_files, final_cutoff]).fetchdf()
    trades["token_id_pm"] = trades["token_id_pm"].astype(str)
    trades["trade_ts_utc"] = pd.to_datetime(trades["trade_ts_utc"], utc=True)
    return trades


def fetch_kalshi_prices(data_root: Path, tickers: pd.Series, max_cutoff_utc: pd.Timestamp) -> pd.DataFrame:
    try:
        import duckdb
    except ImportError as exc:
        raise RuntimeError("DuckDB is required to build price histories from raw parquet data.") from exc

    kalshi_trade_files = [
        path
        for path in glob.glob(str(data_root / "kalshi" / "trades" / "**" / "*.parquet"), recursive=True)
        if not Path(path).name.startswith("._")
    ]
    if not kalshi_trade_files:
        raise FileNotFoundError("Could not find Kalshi trade parquet files under data_root.")

    ticker_keys = pd.DataFrame({"market_id_kalshi": sorted(set(tickers.dropna().astype(str)))})
    con = duckdb.connect()
    con.register("kalshi_ticker_keys", ticker_keys)
    final_cutoff = max_cutoff_utc.tz_convert("UTC").tz_localize(None).strftime("%Y-%m-%d %H:%M:%S")
    sql = """
        SELECT
            t.ticker AS market_id_kalshi,
            CAST(t.created_time AS TIMESTAMP) AS trade_ts_utc,
            CAST(t.yes_price AS DOUBLE) / 100.0 AS k_yes_price
        FROM read_parquet(?) t
        JOIN kalshi_ticker_keys k
          ON t.ticker = k.market_id_kalshi
        WHERE CAST(t.created_time AS TIMESTAMP) <= CAST(? AS TIMESTAMP)
    """
    trades = con.execute(sql, [kalshi_trade_files, final_cutoff]).fetchdf()
    trades["market_id_kalshi"] = trades["market_id_kalshi"].astype(str)
    trades["trade_ts_utc"] = pd.to_datetime(trades["trade_ts_utc"], utc=True)
    return trades


def build_event_active_panel(matches: pd.DataFrame, data_root: Path, window_days: int) -> pd.DataFrame:
    all_cutoffs = []
    for event_slug, event_spec in EVENTS.items():
        cutoffs = build_cutoffs(event_spec, window_days)
        cutoffs["event_slug"] = event_slug
        all_cutoffs.append(cutoffs)
    cutoffs = pd.concat(all_cutoffs, ignore_index=True)
    max_cutoff_utc = pd.to_datetime(cutoffs["cutoff_utc"], utc=True).max()

    pm_trades = fetch_pm_token_prices(data_root, matches["token_id_pm"], max_cutoff_utc)
    k_trades = fetch_kalshi_prices(data_root, matches["market_id_kalshi"], max_cutoff_utc)

    pm_targets = (
        matches[["contract_pair_id", "token_id_pm"]]
        .drop_duplicates()
        .assign(_tmp=1)
        .merge(cutoffs.assign(_tmp=1), on="_tmp", how="inner")
        .drop(columns="_tmp")
    )
    k_targets = (
        matches[["contract_pair_id", "market_id_kalshi"]]
        .drop_duplicates()
        .assign(_tmp=1)
        .merge(cutoffs.assign(_tmp=1), on="_tmp", how="inner")
        .drop(columns="_tmp")
    )

    pm_snaps = asof_snapshots(pm_trades, pm_targets, "token_id_pm")
    k_snaps = asof_snapshots(k_trades, k_targets, "market_id_kalshi")
    pm_snaps = pm_snaps.rename(columns={"trade_ts_utc": "pm_source_trade_ts_utc"})
    k_snaps = k_snaps.rename(columns={"trade_ts_utc": "k_source_trade_ts_utc"})

    panel = (
        matches.merge(pm_snaps, on=["contract_pair_id", "token_id_pm"], how="inner", suffixes=("", "_pm_snap"))
        .merge(
            k_snaps,
            on=["contract_pair_id", "market_id_kalshi", "event_slug", "cutoff_label", "cutoff_utc", "cutoff_local"],
            how="inner",
            suffixes=("", "_k_snap"),
        )
    )

    panel["cutoff_local"] = pd.to_datetime(panel["cutoff_local"], utc=True).dt.tz_convert(PACIFIC_TZ)
    panel["cutoff_utc"] = pd.to_datetime(panel["cutoff_utc"], utc=True)
    panel["created_at_pm_ts"] = pd.to_datetime(panel["created_at_pm"], utc=True, errors="coerce")
    panel["end_date_pm_ts"] = pd.to_datetime(panel["end_date_pm"], utc=True, errors="coerce")
    panel["created_at_kalshi_ts"] = pd.to_datetime(panel["created_at_kalshi"], utc=True, errors="coerce")
    panel["end_date_kalshi_ts"] = pd.to_datetime(panel["end_date_kalshi"], utc=True, errors="coerce")
    early_bound = pd.Timestamp("1900-01-01", tz="UTC")
    late_bound = pd.Timestamp("2100-01-01", tz="UTC")
    active_mask = (
        panel["cutoff_utc"].ge(panel["created_at_pm_ts"].fillna(early_bound))
        & panel["cutoff_utc"].ge(panel["created_at_kalshi_ts"].fillna(early_bound))
        & panel["cutoff_utc"].le(panel["end_date_pm_ts"].fillna(late_bound))
        & panel["cutoff_utc"].le(panel["end_date_kalshi_ts"].fillna(late_bound))
    )
    panel = panel[active_mask].dropna(subset=["pm_yes_price", "k_yes_price", "volume_pm"]).copy()
    panel = panel[panel["volume_pm"].astype(float).gt(0)].copy()

    event_meta = pd.DataFrame(
        [
            {"event_slug": slug, "event_start": spec["event_start"], "event_end": spec["event_end"]}
            for slug, spec in EVENTS.items()
        ]
    )
    panel = panel.merge(event_meta, on="event_slug", how="left")
    event_starts = {slug: event_start_timestamp(spec) for slug, spec in EVENTS.items()}
    panel["cutoff_date"] = panel["cutoff_local"].dt.date.astype(str)
    panel["relative_day"] = [
        (cutoff.normalize() - event_starts[event_slug]).days
        for cutoff, event_slug in zip(panel["cutoff_local"], panel["event_slug"])
    ]
    panel["post"] = [
        int(cutoff >= event_starts[event_slug])
        for cutoff, event_slug in zip(panel["cutoff_local"], panel["event_slug"])
    ]
    panel["pm_minus_k"] = panel["pm_yes_price"] - panel["k_yes_price"]
    panel["pm_abs_from_50"] = (panel["pm_yes_price"] - 0.5).abs()
    panel["k_abs_from_50"] = (panel["k_yes_price"] - 0.5).abs()
    panel["pm_abs_minus_k_abs_from_50"] = panel["pm_abs_from_50"] - panel["k_abs_from_50"]
    panel["weight_pm_volume"] = panel["volume_pm"].astype(float)
    panel["pm_source_trade_ts_local"] = pd.to_datetime(panel["pm_source_trade_ts_utc"], utc=True).dt.tz_convert(PACIFIC_TZ)
    panel["k_source_trade_ts_local"] = pd.to_datetime(panel["k_source_trade_ts_utc"], utc=True).dt.tz_convert(PACIFIC_TZ)

    output_cols = [
        "event_slug",
        "event_start",
        "event_end",
        "cutoff_label",
        "cutoff_utc",
        "cutoff_local",
        "cutoff_date",
        "relative_day",
        "post",
        "contract_pair_id",
        "contract_key",
        "market_family_pm",
        "pm_resolver_proxy",
        "resolver_type_onchain",
        "ultimate_resolver_type",
        "uma_backed",
        "neg_risk_request_initialized",
        "market_id_pm",
        "title_pm",
        "outcome_index_pm",
        "outcome_name_pm",
        "token_id_pm",
        "synthetic_binary_pm",
        "pm_price_source",
        "market_id_kalshi",
        "title_kalshi",
        "yes_sub_title_kalshi",
        "volume_pm",
        "weight_pm_volume",
        "pm_yes_price",
        "k_yes_price",
        "pm_minus_k",
        "pm_abs_from_50",
        "k_abs_from_50",
        "pm_abs_minus_k_abs_from_50",
        "pm_source_trade_ts_local",
        "k_source_trade_ts_local",
        "match_confidence",
        "match_basis",
    ]
    panel = panel[output_cols].sort_values(["event_slug", "cutoff_local", "contract_pair_id"])
    require_unique(panel, ["event_slug", "contract_pair_id", "cutoff_label"], "event-active matched panel")
    return panel


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    values = values.astype(float)
    weights = weights.astype(float)
    mask = values.notna() & weights.notna() & weights.gt(0)
    if not mask.any():
        return np.nan
    return float(np.average(values[mask], weights=weights[mask]))


def build_timeseries(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for keys, group in panel.groupby(
        ["event_slug", "event_start", "event_end", "cutoff_label", "cutoff_utc", "cutoff_local", "cutoff_date", "relative_day", "post"],
        sort=True,
    ):
        row = dict(
            zip(
                [
                    "event_slug",
                    "event_start",
                    "event_end",
                    "cutoff_label",
                    "cutoff_utc",
                    "cutoff_local",
                    "cutoff_date",
                    "relative_day",
                    "post",
                ],
                keys,
            )
        )
        row["weighted_pm_yes_price"] = weighted_mean(group["pm_yes_price"], group["weight_pm_volume"])
        row["weighted_pm_minus_k"] = weighted_mean(group["pm_minus_k"], group["weight_pm_volume"])
        row["weighted_pm_abs_from_50"] = weighted_mean(group["pm_abs_from_50"], group["weight_pm_volume"])
        row["weighted_k_abs_from_50"] = weighted_mean(group["k_abs_from_50"], group["weight_pm_volume"])
        row["weighted_pm_abs_minus_k_abs_from_50"] = weighted_mean(
            group["pm_abs_minus_k_abs_from_50"], group["weight_pm_volume"]
        )
        row["pair_count"] = int(group["contract_pair_id"].nunique())
        row["total_pm_weight"] = float(group["weight_pm_volume"].sum())
        rows.append(row)
    return pd.DataFrame(rows).sort_values(["event_slug", "cutoff_local"])


def fixed_effect_post_regression(panel: pd.DataFrame, outcome: str) -> dict[str, float | int | str]:
    df = panel.dropna(subset=[outcome, "post", "weight_pm_volume", "contract_pair_id"]).copy()
    df = df[df["weight_pm_volume"].gt(0)].copy()
    n_obs = len(df)
    n_contracts = int(df["contract_pair_id"].nunique())

    if n_obs == 0 or n_contracts == 0:
        return {
            "outcome": outcome,
            "n_obs": n_obs,
            "n_contracts": n_contracts,
            "post_coef": np.nan,
            "post_se": np.nan,
            "post_t": np.nan,
            "pre_mean": np.nan,
            "post_mean": np.nan,
            "post_minus_pre": np.nan,
        }

    df["_y"] = df[outcome].astype(float)
    df["_x"] = df["post"].astype(float)
    df["_w"] = df["weight_pm_volume"].astype(float)
    df["_y_mean_i"] = df.groupby("contract_pair_id")["_y"].transform("mean")
    df["_x_mean_i"] = df.groupby("contract_pair_id")["_x"].transform("mean")
    df["_yd"] = df["_y"] - df["_y_mean_i"]
    df["_xd"] = df["_x"] - df["_x_mean_i"]

    denom = float((df["_w"] * df["_xd"] * df["_xd"]).sum())
    if denom <= 0:
        beta = np.nan
        se = np.nan
        t_stat = np.nan
    else:
        beta = float((df["_w"] * df["_xd"] * df["_yd"]).sum() / denom)
        resid = df["_yd"] - beta * df["_xd"]
        df_resid = n_obs - n_contracts - 1
        if df_resid > 0:
            sigma2 = float((df["_w"] * resid * resid).sum() / df_resid)
            se = math.sqrt(sigma2 / denom)
            t_stat = beta / se if se > 0 else np.nan
        else:
            se = np.nan
            t_stat = np.nan

    pre = df[df["post"].eq(0)]
    post = df[df["post"].eq(1)]
    pre_mean = weighted_mean(pre["_y"], pre["_w"])
    post_mean = weighted_mean(post["_y"], post["_w"])

    return {
        "outcome": outcome,
        "n_obs": n_obs,
        "n_contracts": n_contracts,
        "post_coef": beta,
        "post_se": se,
        "post_t": t_stat,
        "pre_mean": pre_mean,
        "post_mean": post_mean,
        "post_minus_pre": post_mean - pre_mean if pd.notna(pre_mean) and pd.notna(post_mean) else np.nan,
    }


def build_regressions(panel: pd.DataFrame, outcomes: list[str]) -> pd.DataFrame:
    rows = []
    for event_slug, event_panel in panel.groupby("event_slug", sort=True):
        for outcome in outcomes:
            row = fixed_effect_post_regression(event_panel, outcome)
            row["event_slug"] = event_slug
            row["event_start"] = event_panel["event_start"].iloc[0]
            row["event_end"] = event_panel["event_end"].iloc[0]
            rows.append(row)
    columns = [
        "event_slug",
        "event_start",
        "event_end",
        "outcome",
        "n_obs",
        "n_contracts",
        "post_coef",
        "post_se",
        "post_t",
        "pre_mean",
        "post_mean",
        "post_minus_pre",
    ]
    return pd.DataFrame(rows)[columns]


def build_group_regressions(panel: pd.DataFrame, outcomes: list[str], group_col: str = "pm_resolver_proxy") -> pd.DataFrame:
    rows = []
    for (event_slug, group_value), event_panel in panel.groupby(["event_slug", group_col], sort=True):
        for outcome in outcomes:
            row = fixed_effect_post_regression(event_panel, outcome)
            row["event_slug"] = event_slug
            row[group_col] = group_value
            row["event_start"] = event_panel["event_start"].iloc[0]
            row["event_end"] = event_panel["event_end"].iloc[0]
            rows.append(row)
    columns = [
        "event_slug",
        group_col,
        "event_start",
        "event_end",
        "outcome",
        "n_obs",
        "n_contracts",
        "post_coef",
        "post_se",
        "post_t",
        "pre_mean",
        "post_mean",
        "post_minus_pre",
    ]
    return pd.DataFrame(rows)[columns] if rows else pd.DataFrame(columns=columns)


def try_matplotlib_plot(event_ts: pd.DataFrame, event_spec: dict[str, str], outpath: Path, outcome_mode: str) -> bool:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
    except Exception:
        return False

    df = event_ts.sort_values("cutoff_local").copy()
    x = pd.to_datetime(df["cutoff_local"])
    event_start = event_start_timestamp(event_spec)
    event_end_exclusive = event_end_exclusive_timestamp(event_spec)

    fig, axes = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    fig.suptitle(f"{event_spec['label']} strict matched markets")
    series = PLOT_SERIES["attenuation" if outcome_mode == "both" else outcome_mode]
    for ax, (col, label, color) in zip(axes, series):
        ax.plot(x, df[col], marker="o", linewidth=1.8, markersize=3, color=color)
        ax.axvspan(event_start, event_end_exclusive, color="#d62728", alpha=0.08, label="Event window")
        ax.axvline(event_start, color="#d62728", linestyle="-", linewidth=1.2, label="Event start")
        ax.axvline(event_end_exclusive, color="#d62728", linestyle="--", linewidth=1.2, label="Event end")
        ax.set_ylabel(label)
        ax.grid(True, alpha=0.25)
        ax.annotate(
            event_start.strftime("Start %Y-%m-%d"),
            xy=(event_start, 0.98),
            xycoords=("data", "axes fraction"),
            xytext=(4, -4),
            textcoords="offset points",
            ha="left",
            va="top",
            fontsize=8,
            color="#a32020",
        )
        ax.annotate(
            pd.Timestamp(event_spec["event_end"]).strftime("End %Y-%m-%d"),
            xy=(event_end_exclusive, 0.98),
            xycoords=("data", "axes fraction"),
            xytext=(-4, -4),
            textcoords="offset points",
            ha="right",
            va="top",
            fontsize=8,
            color="#a32020",
        )
    axes[-1].set_xlabel("Cutoff time (PT)")
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter("%m-%d"))
    axes[0].legend(loc="best")
    fig.tight_layout()
    fig.savefig(outpath, dpi=150)
    plt.close(fig)
    return True


class SimpleCanvas:
    def __init__(self, width: int, height: int, bg: tuple[int, int, int] = (255, 255, 255)):
        self.width = width
        self.height = height
        self.buf = bytearray(bg * (width * height))

    def set_pixel(self, x: int, y: int, color: tuple[int, int, int]) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            idx = (y * self.width + x) * 3
            self.buf[idx : idx + 3] = bytes(color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int], width: int = 1) -> None:
        dx = abs(x1 - x0)
        dy = -abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            half = width // 2
            for xx in range(x0 - half, x0 + half + 1):
                for yy in range(y0 - half, y0 + half + 1):
                    self.set_pixel(xx, yy, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def rect(self, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int], fill: bool = False) -> None:
        if fill:
            for y in range(min(y0, y1), max(y0, y1) + 1):
                self.line(x0, y, x1, y, color)
        else:
            self.line(x0, y0, x1, y0, color)
            self.line(x1, y0, x1, y1, color)
            self.line(x1, y1, x0, y1, color)
            self.line(x0, y1, x0, y0, color)

    def translucent_rect(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        color: tuple[int, int, int],
        alpha: float = 0.12,
    ) -> None:
        left, right = sorted((max(0, x0), min(self.width - 1, x1)))
        top, bottom = sorted((max(0, y0), min(self.height - 1, y1)))
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                idx = (y * self.width + x) * 3
                old = self.buf[idx : idx + 3]
                blended = bytes(int(old[i] * (1 - alpha) + color[i] * alpha) for i in range(3))
                self.buf[idx : idx + 3] = blended

    def text(self, x: int, y: int, text: str, color: tuple[int, int, int], scale: int = 2) -> None:
        cursor = x
        for char in text.upper():
            glyph = FONT_5X7.get(char, FONT_5X7[" "])
            for row_idx, row in enumerate(glyph):
                for col_idx, pixel in enumerate(row):
                    if pixel == "1":
                        self.rect(
                            cursor + col_idx * scale,
                            y + row_idx * scale,
                            cursor + (col_idx + 1) * scale - 1,
                            y + (row_idx + 1) * scale - 1,
                            color,
                            fill=True,
                        )
            cursor += 6 * scale

    def save_png(self, path: Path) -> None:
        raw = bytearray()
        stride = self.width * 3
        for y in range(self.height):
            raw.append(0)
            raw.extend(self.buf[y * stride : (y + 1) * stride])
        compressed = zlib.compress(bytes(raw), 9)

        def chunk(tag: bytes, data: bytes) -> bytes:
            return (
                struct.pack(">I", len(data))
                + tag
                + data
                + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
            )

        ihdr = struct.pack(">IIBBBBB", self.width, self.height, 8, 2, 0, 0, 0)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", compressed) + chunk(b"IEND", b""))


def fallback_png_plot(event_ts: pd.DataFrame, event_spec: dict[str, str], outpath: Path, outcome_mode: str) -> None:
    width, height = 1100, 760
    canvas = SimpleCanvas(width, height)
    canvas.text(45, 20, f"{event_spec['label']} strict matched markets", (30, 30, 30), scale=2)

    if outcome_mode in {"attenuation", "both"}:
        panels = [
            (120, 85, 1040, 350, "|PM - 0.50|", "weighted_pm_abs_from_50", "WEIGHTED |PM - 0.50|", (31, 119, 180)),
            (
                120,
                430,
                1040,
                695,
                "|PM - 0.50| - |K - 0.50|",
                "weighted_pm_abs_minus_k_abs_from_50",
                "WEIGHTED PM-K DISTANCE SPREAD",
                (44, 160, 44),
            ),
        ]
    else:
        panels = [
            (120, 85, 1040, 350, "PM YES PRICE", "weighted_pm_yes_price", "WEIGHTED PM YES", (31, 119, 180)),
            (120, 430, 1040, 695, "PM-K SPREAD", "weighted_pm_minus_k", "WEIGHTED PM-K", (44, 160, 44)),
        ]
    df = event_ts.sort_values("cutoff_local").copy()
    x_datetimes = pd.to_datetime(df["cutoff_local"], utc=True)
    x_values = x_datetimes.map(lambda value: value.timestamp())
    x_min = float(x_values.min())
    x_max = float(x_values.max())
    if x_max <= x_min:
        x_max = x_min + 1.0
    event_start = event_start_timestamp(event_spec).tz_convert("UTC").timestamp()
    event_end = event_end_exclusive_timestamp(event_spec).tz_convert("UTC").timestamp()
    event_start_label = pd.Timestamp(event_spec["event_start"]).strftime("%m-%d")
    event_end_label = pd.Timestamp(event_spec["event_end"]).strftime("%m-%d")

    def x_to_px(value: float, left: int, right: int) -> int:
        return int(left + (value - x_min) / (x_max - x_min) * (right - left))

    x_tick_count = 6
    x_ticks = np.linspace(x_min, x_max, x_tick_count)
    x_tick_labels = [
        pd.Timestamp.fromtimestamp(float(value), tz="UTC").strftime("%m-%d")
        for value in x_ticks
    ]

    for left, top, right, bottom, title, col, y_axis_label, color in panels:
        y_values = df[col].astype(float)
        y_min = float(y_values.min())
        y_max = float(y_values.max())
        if y_max <= y_min:
            y_max = y_min + 1.0
        pad = (y_max - y_min) * 0.12
        y_min -= pad
        y_max += pad

        def y_to_px(value: float) -> int:
            return int(bottom - (value - y_min) / (y_max - y_min) * (bottom - top))

        canvas.text(left, top - 30, title, (35, 35, 35), scale=2)
        canvas.rect(left, top, right, bottom, (40, 40, 40))

        event_start_x = x_to_px(event_start, left, right)
        event_end_x = x_to_px(event_end, left, right)
        canvas.translucent_rect(event_start_x, top, event_end_x, bottom, (210, 45, 45), alpha=0.10)

        y_tick_values = np.linspace(y_min, y_max, 6)
        for y_tick in y_tick_values:
            y = y_to_px(float(y_tick))
            canvas.line(left, y, right, y, (225, 225, 225))
            canvas.line(left - 5, y, left, y, (40, 40, 40))
            canvas.text(38, y - 5, f"{y_tick:.3f}", (70, 70, 70), scale=1)

        for x_tick, x_label in zip(x_ticks, x_tick_labels):
            x = x_to_px(float(x_tick), left, right)
            canvas.line(x, bottom, x, bottom + 5, (40, 40, 40))
            canvas.text(x - 15, bottom + 12, x_label, (70, 70, 70), scale=1)

        for marker, dashed in [(event_start, False), (event_end, True)]:
            x = x_to_px(marker, left, right)
            if dashed:
                for yy in range(top, bottom, 12):
                    canvas.line(x, yy, x, min(yy + 6, bottom), (210, 45, 45), width=2)
            else:
                canvas.line(x, top, x, bottom, (210, 45, 45), width=2)

        canvas.text(max(left, event_start_x - 28), top + 8, f"START {event_start_label}", (160, 30, 30), scale=1)
        canvas.text(min(right - 58, event_end_x - 28), top + 22, f"END {event_end_label}", (160, 30, 30), scale=1)

        points = [(x_to_px(float(x), left, right), y_to_px(float(y))) for x, y in zip(x_values, y_values)]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            canvas.line(x0, y0, x1, y1, color, width=3)
        for x, y in points:
            canvas.rect(x - 2, y - 2, x + 2, y + 2, color, fill=True)

        canvas.text(left + 355, bottom + 35, "CUTOFF DATE PT", (70, 70, 70), scale=1)
        canvas.text(8, top + 118, y_axis_label, (70, 70, 70), scale=1)
    canvas.text(120, 728, "SHADED RED AREA IS EVENT RANGE / SOLID START / DASHED END", (90, 90, 90), scale=1)
    canvas.save_png(outpath)


def write_plots(timeseries: pd.DataFrame, exports_dir: Path, output_prefix: str, outcome_mode: str) -> list[Path]:
    paths = []
    for event_slug, event_spec in EVENTS.items():
        event_ts = timeseries[timeseries["event_slug"].eq(event_slug)].copy()
        if event_ts.empty:
            continue
        outpath = exports_dir / f"{output_prefix}_{event_slug}_timeseries.png"
        if not try_matplotlib_plot(event_ts, event_spec, outpath, outcome_mode):
            fallback_png_plot(event_ts, event_spec, outpath, outcome_mode)
        paths.append(outpath)
    return paths


def validate_outputs(panel: pd.DataFrame, timeseries: pd.DataFrame, regressions: pd.DataFrame, plot_paths: list[Path]) -> None:
    if panel.empty:
        raise ValueError("Matched price panel is empty.")
    if panel[["pm_yes_price", "k_yes_price"]].isna().any().any():
        raise ValueError("Matched price panel contains missing PM or Kalshi prices.")
    if not panel["match_basis"].eq("deterministic_contract_key").all():
        raise ValueError("Non-strict matches entered the analysis panel.")
    require_unique(panel, ["event_slug", "contract_pair_id", "cutoff_label"], "final matched panel")
    if timeseries.empty:
        raise ValueError("Timeseries output is empty.")
    if regressions.empty:
        raise ValueError("Regression output is empty.")
    missing_plots = [path for path in plot_paths if not path.exists() or path.stat().st_size == 0]
    if missing_plots:
        raise ValueError(f"Plot files were not created: {missing_plots}")


def write_csv_with_fallback(df: pd.DataFrame, path: Path) -> Path:
    try:
        df.to_csv(path, index=False)
        return path
    except PermissionError:
        fallback = path.with_name(f"{path.stem}_updated{path.suffix}")
        df.to_csv(fallback, index=False)
        print(f"Warning: {path} is locked; wrote {fallback} instead.")
        return fallback


def main() -> None:
    parser = argparse.ArgumentParser(description="Resolution-risk event study on strict PM/K matched markets.")
    parser.add_argument("--exports-dir", default="exports", type=Path)
    parser.add_argument("--matches-dir", default=Path("exports/event_active_contracts"), type=Path)
    parser.add_argument("--resolver-map-path", default=Path("exports/pm_matched_resolver_map.csv"), type=Path)
    parser.add_argument("--data-root", default=Path("data"), type=Path)
    parser.add_argument("--window-days", default=7, type=int)
    parser.add_argument(
        "--pm-resolver-proxy",
        default="",
        choices=["", *PM_RESOLVER_PROXIES.keys(), "unknown"],
        help="Optional Polymarket resolver proxy filter.",
    )
    parser.add_argument("--ultimate-resolver-type", default="", help="Optional on-chain ultimate resolver type filter.")
    parser.add_argument("--uma-backed-only", action="store_true", help="Keep only markets classified as UMA-backed on chain.")
    parser.add_argument(
        "--outcome-mode",
        default="raw",
        choices=OUTCOME_MODES.keys(),
        help="Regression and plot outcome set.",
    )
    parser.add_argument("--output-prefix", default="resolution_risk")
    args = parser.parse_args()

    exports_dir = args.exports_dir
    exports_dir.mkdir(parents=True, exist_ok=True)

    matches = read_event_active_matches(args.matches_dir)
    matches = attach_resolver_map(matches, args.resolver_map_path)
    if args.pm_resolver_proxy:
        matches = matches[matches["pm_resolver_proxy"].eq(args.pm_resolver_proxy)].copy()
        if matches.empty:
            raise ValueError(f"No matches survived --pm-resolver-proxy={args.pm_resolver_proxy}.")
    if args.ultimate_resolver_type:
        matches = matches[matches["ultimate_resolver_type"].eq(args.ultimate_resolver_type)].copy()
        if matches.empty:
            raise ValueError(f"No matches survived --ultimate-resolver-type={args.ultimate_resolver_type}.")
    if args.uma_backed_only:
        matches = matches[matches["uma_backed"].eq(True)].copy()
        if matches.empty:
            raise ValueError("No matches survived --uma-backed-only.")
    panel = build_event_active_panel(matches, args.data_root, args.window_days)
    outcomes = OUTCOME_MODES[args.outcome_mode]
    timeseries = build_timeseries(panel)
    regressions = build_regressions(panel, outcomes)
    regressions_by_proxy = build_group_regressions(panel, outcomes)

    panel_path = exports_dir / f"{args.output_prefix}_matched_price_panel.csv"
    timeseries_path = exports_dir / f"{args.output_prefix}_event_timeseries.csv"
    regressions_path = exports_dir / f"{args.output_prefix}_regressions.csv"
    regressions_by_proxy_path = exports_dir / f"{args.output_prefix}_regressions_by_proxy.csv"

    panel_path = write_csv_with_fallback(panel, panel_path)
    timeseries_path = write_csv_with_fallback(timeseries, timeseries_path)
    regressions_path = write_csv_with_fallback(regressions, regressions_path)
    regressions_by_proxy_path = write_csv_with_fallback(regressions_by_proxy, regressions_by_proxy_path)
    plot_paths = write_plots(timeseries, exports_dir, args.output_prefix, args.outcome_mode)
    validate_outputs(panel, timeseries, regressions, plot_paths)

    print(f"Matched panel: {panel_path} ({len(panel):,} rows)")
    print(f"Timeseries:    {timeseries_path} ({len(timeseries):,} rows)")
    print(f"Regressions:   {regressions_path} ({len(regressions):,} rows)")
    print(f"By proxy regs: {regressions_by_proxy_path} ({len(regressions_by_proxy):,} rows)")
    print(f"Match source:  {args.matches_dir / 'contract_matches.csv'} ({len(matches):,} strict matches)")
    print(f"Resolver map:  {args.resolver_map_path if args.resolver_map_path.exists() else 'not found'}")
    if args.pm_resolver_proxy:
        print(f"PM proxy:      {args.pm_resolver_proxy}")
    if args.ultimate_resolver_type:
        print(f"Resolver type: {args.ultimate_resolver_type}")
    if args.uma_backed_only:
        print("UMA filter:    UMA-backed only")
    print(f"Outcome mode:  {args.outcome_mode}")
    for event_slug, event_panel in panel.groupby("event_slug", sort=True):
        print(f"{event_slug}: {event_panel['contract_pair_id'].nunique()} strict matched pairs in panel")
        print(
            f"{event_slug}: {event_panel['synthetic_binary_pm'].astype(str).str.lower().eq('true').sum()} "
            "synthetic-binary panel rows"
        )
    for path in plot_paths:
        print(f"Plot:          {path}")


if __name__ == "__main__":
    main()
