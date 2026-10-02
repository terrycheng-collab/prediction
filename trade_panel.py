"""
Trade-level rebuild of the resolution-risk event-study panel.

resolution_risk_event_study.py keeps only one number per trade (its price) and weights every
regression by each Polymarket market's lifetime volume, which is recorded after the fact and
is itself a plausible response to a controversy. This script keeps that script's price
snapshots unchanged (so its baseline row equals the corrected Table 1) and adds, for every
matched contract and every 5am/5pm PT cutoff:

  - staleness: hours since the trade behind each venue's snapshot price
  - activity in the 12h interval ending at the cutoff: shares/contracts, Yes-equivalent USD
    notional, trade count, unique wallets (Polymarket), signed taker flow and its imbalance,
    and a share-weighted VWAP
  - fixed pre-event weights: each contract's Polymarket share volume over the pre-event
    snapshots of that event, alongside the legacy lifetime-volume weight and equal weights

It then runs the existing contract-fixed-effect Post regression over a grid of sample x weight
x staleness filter x outcome.

Polymarket fills come from CTF Exchange / NegRisk CTF Exchange OrderFilled logs. Every match
logs one fill per maker order (taker = the real taker wallet) plus one summary fill for the
taker order (taker = the exchange contract). Only maker fills are counted, so each trade is
counted once. Fills on both the Yes and the No token are read, since "mint" matches (one side
buys Yes, the other buys No) only show up on one token. A fill is converted to Yes exposure:
a taker buying No is a taker selling Yes, at price 1 - p_No.

Usage (from the repo root):
    python trade_panel.py [--data-root data] [--window-days 7] [--max-staleness-hours 24]
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np
import pandas as pd

import resolution_risk_event_study as es

EXCHANGE_CONTRACTS = (
    "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",  # CTF Exchange
    "0xC5d563A36AE78145C45a50134d48A1215220f80a",  # NegRisk CTF Exchange
)
INTERVAL = pd.Timedelta(hours=12)
TOKEN_SCALE = 1e6  # USDC and outcome tokens both use 6 decimals

SAMPLES = {
    "all": None,
    "uma_risk_exposed": "uma_risk_exposed",
}
WEIGHTS = {
    "lifetime_volume": "weight_pm_volume",
    "pre_event_pm_shares": "weight_pre_event_pm_shares",
    "equal": "weight_equal",
}
OUTCOMES = [
    "pm_abs_from_50",
    "pm_abs_minus_k_abs_from_50",
    "pm_vwap_abs_minus_k_vwap_abs_from_50",
    "log1p_pm_shares",
    "log1p_k_contracts",
    "pm_flow_imbalance",
    "k_flow_imbalance",
]


def parquet_files(data_root: Path, *parts: str) -> list[str]:
    pattern = str(data_root.joinpath(*parts) / "**" / "*.parquet")
    return [path for path in glob.glob(pattern, recursive=True) if not Path(path).name.startswith("._")]


def complement_tokens(data_root: Path, matches: pd.DataFrame) -> pd.DataFrame:
    """Map each matched token to its market's other outcome token."""
    import duckdb

    ids = pd.DataFrame({"market_id_pm": sorted(set(matches["market_id_pm"]))})
    con = duckdb.connect()
    con.register("ids", ids)
    markets = con.execute(
        """
        SELECT CAST(m.id AS VARCHAR) AS market_id_pm, m.clob_token_ids
        FROM read_parquet(?) m JOIN ids ON CAST(m.id AS VARCHAR) = ids.market_id_pm
        """,
        [parquet_files(data_root, "polymarket", "markets")],
    ).fetchdf()
    markets = markets.drop_duplicates("market_id_pm")
    tokens = dict(zip(markets["market_id_pm"], markets["clob_token_ids"].map(json.loads)))

    rows = []
    for market_id, token_id in matches[["market_id_pm", "token_id_pm"]].drop_duplicates().itertuples(index=False):
        pair = [str(t) for t in tokens.get(market_id, [])]
        if len(pair) != 2 or token_id not in pair:
            raise ValueError(f"Market {market_id}: expected a binary market containing token {token_id}, got {pair}")
        rows.append({"token_id_pm": token_id, "complement_token_id_pm": pair[1 - pair.index(token_id)]})
    return pd.DataFrame(rows)


def fetch_pm_fills(data_root: Path, tokens: pd.DataFrame, start_utc: pd.Timestamp, end_utc: pd.Timestamp) -> pd.DataFrame:
    """Polymarket maker fills on either token, expressed as Yes exposure of the matched token."""
    import duckdb

    keys = pd.concat(
        [
            tokens.assign(fill_token=tokens["token_id_pm"], is_complement=False),
            tokens.assign(fill_token=tokens["complement_token_id_pm"], is_complement=True),
        ]
    )[["fill_token", "token_id_pm", "is_complement"]]
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.register("keys", keys)
    sql = """
        WITH fills AS (
            SELECT
                t.block_number,
                t.maker,
                t.taker,
                CAST(t.maker_asset_id AS VARCHAR) = '0' AS maker_pays_usdc,
                CASE WHEN CAST(t.maker_asset_id AS VARCHAR) = '0'
                     THEN CAST(t.taker_asset_id AS VARCHAR) ELSE CAST(t.maker_asset_id AS VARCHAR) END AS fill_token,
                CASE WHEN CAST(t.maker_asset_id AS VARCHAR) = '0'
                     THEN CAST(t.taker_amount AS DOUBLE) ELSE CAST(t.maker_amount AS DOUBLE) END AS token_amount,
                CASE WHEN CAST(t.maker_asset_id AS VARCHAR) = '0'
                     THEN CAST(t.maker_amount AS DOUBLE) ELSE CAST(t.taker_amount AS DOUBLE) END AS usdc_amount
            FROM read_parquet(?) t
            WHERE t.taker NOT IN (?, ?)
        ),
        blocks AS (
            SELECT block_number, CAST(timestamp AS TIMESTAMPTZ) AS block_ts
            FROM read_parquet(?)
            WHERE CAST(timestamp AS TIMESTAMPTZ) > CAST(? AS TIMESTAMPTZ)
              AND CAST(timestamp AS TIMESTAMPTZ) <= CAST(? AS TIMESTAMPTZ)
        )
        SELECT k.token_id_pm, k.is_complement, b.block_ts AS trade_ts_utc,
               f.maker, f.taker, f.maker_pays_usdc, f.token_amount, f.usdc_amount
        FROM fills f
        JOIN keys k ON f.fill_token = k.fill_token
        JOIN blocks b ON f.block_number = b.block_number
        WHERE f.token_amount > 0
    """
    fills = con.execute(
        sql,
        [
            parquet_files(data_root, "polymarket", "trades"),
            *EXCHANGE_CONTRACTS,
            parquet_files(data_root, "polymarket", "blocks"),
            start_utc.isoformat(),
            end_utc.isoformat(),
        ],
    ).fetchdf()
    fills["trade_ts_utc"] = pd.to_datetime(fills["trade_ts_utc"], utc=True)
    fills["shares"] = fills["token_amount"] / TOKEN_SCALE
    token_price = fills["usdc_amount"] / fills["token_amount"]
    fills["yes_price"] = np.where(fills["is_complement"], 1.0 - token_price, token_price)
    # The maker paying USDC is buying the fill token, so the taker is selling it.
    taker_buys_fill_token = ~fills["maker_pays_usdc"]
    taker_buys_yes = np.where(fills["is_complement"], ~taker_buys_fill_token, taker_buys_fill_token)
    fills["signed_shares"] = np.where(taker_buys_yes, fills["shares"], -fills["shares"])
    fills["usd_yes_equiv"] = fills["shares"] * fills["yes_price"]
    return fills[["token_id_pm", "trade_ts_utc", "maker", "taker", "shares", "signed_shares", "yes_price", "usd_yes_equiv"]]


def fetch_kalshi_fills(data_root: Path, tickers: pd.Series, start_utc: pd.Timestamp, end_utc: pd.Timestamp) -> pd.DataFrame:
    import duckdb

    keys = pd.DataFrame({"market_id_kalshi": sorted(set(tickers.astype(str)))})
    con = duckdb.connect()
    con.execute("SET TimeZone = 'UTC'")
    con.register("keys", keys)
    trades = con.execute(
        """
        SELECT t.ticker AS market_id_kalshi, t.created_time AS trade_ts_utc,
               CAST(t.count AS DOUBLE) AS contracts,
               CAST(t.yes_price AS DOUBLE) / 100.0 AS yes_price,
               t.taker_side
        FROM read_parquet(?) t JOIN keys k ON t.ticker = k.market_id_kalshi
        WHERE t.created_time > CAST(? AS TIMESTAMPTZ) AND t.created_time <= CAST(? AS TIMESTAMPTZ)
          AND t.count > 0
        """,
        [parquet_files(data_root, "kalshi", "trades"), start_utc.isoformat(), end_utc.isoformat()],
    ).fetchdf()
    trades["trade_ts_utc"] = pd.to_datetime(trades["trade_ts_utc"], utc=True)
    trades["signed_contracts"] = np.where(trades["taker_side"].eq("yes"), trades["contracts"], -trades["contracts"])
    trades["usd_yes_equiv"] = trades["contracts"] * trades["yes_price"]
    return trades


def assign_intervals(trades: pd.DataFrame, cutoffs: pd.DataFrame) -> pd.DataFrame:
    """Tag each trade with every (event, cutoff) whose 12h interval (cutoff - 12h, cutoff] holds it."""
    tagged = []
    for event_slug, grid in cutoffs.groupby("event_slug"):
        grid = grid.sort_values("cutoff_utc")
        edges = [grid["cutoff_utc"].iloc[0] - INTERVAL, *grid["cutoff_utc"]]
        bins = pd.cut(trades["trade_ts_utc"], bins=pd.DatetimeIndex(edges), labels=grid["cutoff_label"].tolist(), right=True)
        part = trades[bins.notna()].copy()
        part["cutoff_label"] = bins[bins.notna()].astype(str)
        part["event_slug"] = event_slug
        tagged.append(part)
    return pd.concat(tagged, ignore_index=True)


def pm_interval_features(fills: pd.DataFrame, cutoffs: pd.DataFrame) -> pd.DataFrame:
    tagged = assign_intervals(fills, cutoffs)
    keys = ["event_slug", "cutoff_label", "token_id_pm"]
    tagged["_px_x_shares"] = tagged["yes_price"] * tagged["shares"]
    agg = tagged.groupby(keys).agg(
        pm_shares=("shares", "sum"),
        pm_signed_shares=("signed_shares", "sum"),
        pm_usd=("usd_yes_equiv", "sum"),
        pm_n_fills=("shares", "size"),
        pm_n_takers=("taker", "nunique"),
        _px_x_shares=("_px_x_shares", "sum"),
    )
    wallets = pd.concat([tagged[keys + ["maker"]].rename(columns={"maker": "wallet"}), tagged[keys + ["taker"]].rename(columns={"taker": "wallet"})])
    agg["pm_n_wallets"] = wallets.groupby(keys)["wallet"].nunique()
    agg["pm_vwap"] = agg.pop("_px_x_shares") / agg["pm_shares"]
    return agg.reset_index()


def kalshi_interval_features(trades: pd.DataFrame, cutoffs: pd.DataFrame) -> pd.DataFrame:
    tagged = assign_intervals(trades, cutoffs)
    tagged["_px_x_contracts"] = tagged["yes_price"] * tagged["contracts"]
    agg = tagged.groupby(["event_slug", "cutoff_label", "market_id_kalshi"]).agg(
        k_contracts=("contracts", "sum"),
        k_signed_contracts=("signed_contracts", "sum"),
        k_usd=("usd_yes_equiv", "sum"),
        k_n_trades=("contracts", "size"),
        _px_x_contracts=("_px_x_contracts", "sum"),
    )
    agg["k_vwap"] = agg.pop("_px_x_contracts") / agg["k_contracts"]
    return agg.reset_index()


def build_trade_panel(matches: pd.DataFrame, data_root: Path, window_days: int) -> pd.DataFrame:
    panel = es.build_event_active_panel(matches, data_root, window_days)
    cutoffs = pd.concat(
        [es.build_cutoffs(spec, window_days).assign(event_slug=slug) for slug, spec in es.EVENTS.items()],
        ignore_index=True,
    )
    start_utc = cutoffs["cutoff_utc"].min() - INTERVAL
    end_utc = cutoffs["cutoff_utc"].max()

    tokens = complement_tokens(data_root, matches)
    pm = pm_interval_features(fetch_pm_fills(data_root, tokens, start_utc, end_utc), cutoffs)
    k = kalshi_interval_features(fetch_kalshi_fills(data_root, matches["market_id_kalshi"], start_utc, end_utc), cutoffs)

    panel = panel.merge(pm, on=["event_slug", "cutoff_label", "token_id_pm"], how="left")
    panel = panel.merge(k, on=["event_slug", "cutoff_label", "market_id_kalshi"], how="left")
    for col in ["pm_shares", "pm_signed_shares", "pm_usd", "pm_n_fills", "pm_n_takers", "pm_n_wallets",
                "k_contracts", "k_signed_contracts", "k_usd", "k_n_trades"]:
        panel[col] = panel[col].fillna(0)
    panel["pm_flow_imbalance"] = panel["pm_signed_shares"] / panel["pm_shares"].where(panel["pm_shares"].gt(0))
    panel["k_flow_imbalance"] = panel["k_signed_contracts"] / panel["k_contracts"].where(panel["k_contracts"].gt(0))
    panel["log1p_pm_shares"] = np.log1p(panel["pm_shares"])
    panel["log1p_k_contracts"] = np.log1p(panel["k_contracts"])
    panel["pm_vwap_abs_minus_k_vwap_abs_from_50"] = (panel["pm_vwap"] - 0.5).abs() - (panel["k_vwap"] - 0.5).abs()

    cutoff_utc = pd.to_datetime(panel["cutoff_utc"], utc=True)
    for venue in ("pm", "k"):
        source = pd.to_datetime(panel[f"{venue}_source_trade_ts_local"], utc=True)
        panel[f"{venue}_staleness_hours"] = (cutoff_utc - source).dt.total_seconds() / 3600
    if panel[["pm_staleness_hours", "k_staleness_hours"]].lt(0).any().any():
        raise ValueError("A snapshot price comes from a trade after its cutoff; check time-zone handling.")

    pre_volume = panel[panel["post"].eq(0)].groupby(["event_slug", "contract_pair_id"])["pm_shares"].sum()
    panel = panel.merge(pre_volume.rename("weight_pre_event_pm_shares").reset_index(), on=["event_slug", "contract_pair_id"], how="left")
    panel["weight_pre_event_pm_shares"] = panel["weight_pre_event_pm_shares"].fillna(0)
    panel["weight_equal"] = 1.0
    es.require_unique(panel, ["event_slug", "contract_pair_id", "cutoff_label"], "trade panel")
    return panel


def regression_grid(panel: pd.DataFrame, max_staleness_hours: float) -> pd.DataFrame:
    fresh = panel["pm_staleness_hours"].le(max_staleness_hours) & panel["k_staleness_hours"].le(max_staleness_hours)
    filters = {"none": pd.Series(True, index=panel.index), f"both_legs_le_{max_staleness_hours:g}h": fresh}
    rows = []
    for sample, proxy in SAMPLES.items():
        in_sample = pd.Series(True, index=panel.index) if proxy is None else panel["pm_resolver_proxy"].eq(proxy)
        for filter_name, keep in filters.items():
            sub = panel[in_sample & keep]
            for weight_name, weight_col in WEIGHTS.items():
                for event_slug, event_panel in sub.groupby("event_slug", sort=True):
                    for outcome in OUTCOMES:
                        row = es.fixed_effect_post_regression(event_panel, outcome, weight_col)
                        rows.append({"sample": sample, "staleness_filter": filter_name, "weight": weight_name,
                                     "event_slug": event_slug, **row})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--data-root", default=Path("data"), type=Path)
    parser.add_argument("--matches-dir", default=Path("exports/event_active_contracts"), type=Path)
    parser.add_argument("--resolver-map-path", default=Path("exports/pm_matched_resolver_map.csv"), type=Path)
    parser.add_argument("--out-dir", default=Path("exports/trade_panel"), type=Path)
    parser.add_argument("--window-days", default=7, type=int)
    parser.add_argument("--max-staleness-hours", default=24.0, type=float)
    args = parser.parse_args()

    matches = es.attach_resolver_map(es.read_event_active_matches(args.matches_dir), args.resolver_map_path)
    matches = matches[matches["uma_backed"].eq(True)].copy()
    panel = build_trade_panel(matches, args.data_root, args.window_days)
    grid = regression_grid(panel, args.max_staleness_hours)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    panel_path = args.out_dir / "trade_panel.csv"
    grid_path = args.out_dir / "trade_panel_regressions.csv"
    panel.to_csv(panel_path, index=False)
    grid.to_csv(grid_path, index=False)

    print(f"Panel:       {panel_path} ({len(panel):,} rows, {panel['contract_pair_id'].nunique()} pairs)")
    print(f"Regressions: {grid_path} ({len(grid):,} rows)")
    print()
    print("Staleness of snapshot prices (hours), by venue:")
    print(panel[["pm_staleness_hours", "k_staleness_hours"]].describe(percentiles=[0.5, 0.9]).round(1).to_string())
    print()
    headline = grid[grid["outcome"].isin(["pm_abs_from_50", "pm_abs_minus_k_abs_from_50"])]
    print("Post coefficients on extremity outcomes (rows: sample/filter/weight; cols: event x outcome):")
    print(
        headline.pivot_table(
            index=["sample", "staleness_filter", "weight"], columns=["event_slug", "outcome"], values="post_coef"
        ).round(4).to_string()
    )


if __name__ == "__main__":
    main()
