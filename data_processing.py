import duckdb
import glob
import pandas as pd
import json
import ast
import re
from pathlib import Path
from decimal import Decimal, InvalidOperation, getcontext


# ============================================================
# HELPER FUNCTIONS
# ============================================================

def parse_list_like(x):
    """Parse JSON/list-like strings from dataframe columns."""
    if pd.isna(x):
        return []
    if isinstance(x, list):
        return x
    s = str(x).strip()
    if s == "":
        return []
    try:
        out = json.loads(s)
        if isinstance(out, list):
            return out
    except Exception:
        pass
    try:
        out = ast.literal_eval(s)
        if isinstance(out, list):
            return out
    except Exception:
        pass
    return []


def slugify(s):
    """Convert string to URL-safe slug."""
    if s is None:
        return "outcome"
    s = str(s).strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s or "outcome"


def build_cutoffs(start_date_local, end_date_local):
    """Build 5am and 5pm PT cutoff timestamps for each date in range."""
    dates = pd.date_range(start=start_date_local, end=end_date_local, freq="D", tz="America/Los_Angeles")
    rows = []
    for d in dates:
        for hour, tag in [(5, "open_0500_PT"), (17, "close_1700_PT")]:
            cutoff_local = d.normalize() + pd.Timedelta(hours=hour)
            rows.append({
                "cutoff_local": cutoff_local,
                "cutoff_utc": cutoff_local.tz_convert("UTC"),
                "cutoff_label": f"{d.strftime('%Y_%m_%d')}_{tag}",
            })
    return pd.DataFrame(rows)


def asof_snapshots(trades_df, targets_df, by_col, trade_time_col="trade_ts_utc", target_time_col="cutoff_utc"):
    """Perform backward merge-asof to find nearest trade price at each cutoff time."""
    left = targets_df.dropna(subset=[by_col, target_time_col]).copy()
    right = trades_df.dropna(subset=[by_col, trade_time_col]).copy()

    left[target_time_col] = pd.to_datetime(left[target_time_col], utc=True)
    right[trade_time_col] = pd.to_datetime(right[trade_time_col], utc=True)

    left = left.sort_values([target_time_col, by_col]).reset_index(drop=True)
    right = right.sort_values([trade_time_col, by_col]).reset_index(drop=True)

    snap = pd.merge_asof(
        left,
        right,
        left_on=target_time_col,
        right_on=trade_time_col,
        by=by_col,
        direction="backward",
        allow_exact_matches=True,
    )
    return snap


def infer_minimum_tick_size(prices):
    """Infer the minimum tick size (most common decimal increment) from prices."""
    getcontext().prec = 28

    def tick_for_price(x):
        try:
            d = Decimal(str(x)).normalize()
        except (InvalidOperation, ValueError, TypeError):
            return None
        exp = d.as_tuple().exponent
        if exp >= 0:
            return Decimal(1)
        return Decimal(10) ** exp

    ticks = [tick_for_price(x) for x in prices.dropna()]
    ticks = [t for t in ticks if t is not None]
    if not ticks:
        return 1.0
    mode_tick = max(set(ticks), key=ticks.count)
    return float(mode_tick)


def apply_minimum_tick_size_rounding(df, id_col="id", price_col="price"):
    """Add minimum_tick_size per market and round prices to that tick size."""
    tick_map = (
        df.groupby(id_col)[price_col]
        .apply(infer_minimum_tick_size)
        .reset_index(name="minimum_tick_size")
    )
    df = df.merge(tick_map, on=id_col, how="left")

    mask = df[price_col].notna() & df["minimum_tick_size"].notna() & (df["minimum_tick_size"] > 0)
    df.loc[mask, price_col] = (
        (df.loc[mask, price_col] / df.loc[mask, "minimum_tick_size"])
        .round()
        * df.loc[mask, "minimum_tick_size"]
    )

    return df


# ============================================================
# MAIN FUNCTION
# ============================================================

def extract_event_study(
    event_start_date,
    event_end_date,
    window_days,
    topic_regex,
    slug,
    root_dir="data",
    outdir="exports"
):
    """
    Extract filtered market snapshots and price time-series for event study analysis.
    
    Parameters:
        event_start_date (str): Event start date in format YYYY-MM-DD (local timezone)
        event_end_date (str): Event end date in format YYYY-MM-DD (local timezone)
        window_days (int): Number of days before event_start and after event_end to include
        topic_regex (str): Regex pattern to filter markets by topic
        slug (str): Slug identifier for output files (e.g., 'ukraine_russia', 'zelensky_suit')
        root_dir (str): Root directory containing data (default: 'data')
        outdir (str): Output directory for CSV files (default: 'exports')
    
    Output Files:
        - {slug}_pm_topics.csv: Polymarket markets filtered by topic
        - {slug}_k_topics.csv: Kalshi markets filtered by topic
        - {slug}_pm_long.csv: Polymarket price snapshots (long format)
        - {slug}_k_long.csv: Kalshi price snapshots (long format)
        - {slug}_pm_wide.csv: Polymarket markets + prices (wide format)
        - {slug}_k_wide.csv: Kalshi markets + prices (wide format)
    """
    
    # ========== SETUP ==========
    outdir = Path(outdir)
    outdir.mkdir(exist_ok=True)
    
    con = duckdb.connect()
    
    # Parse event dates and build window
    event_start = pd.Timestamp(event_start_date, tz="America/Los_Angeles")
    event_end = pd.Timestamp(event_end_date, tz="America/Los_Angeles")
    
    start_date_local = (event_start - pd.Timedelta(days=window_days)).normalize()
    end_date_local = (event_end + pd.Timedelta(days=window_days)).normalize()
    
    created_cutoff = start_date_local.strftime("%Y-%m-%d")
    end_cutoff = end_date_local.strftime("%Y-%m-%d")
    
    # Acquire file paths
    root = Path(root_dir)
    pm_market_files = glob.glob(str(root / "polymarket" / "markets" / "**" / "*.parquet"), recursive=True)
    pm_trade_files = glob.glob(str(root / "polymarket" / "trades" / "**" / "*.parquet"), recursive=True)
    pm_block_files = glob.glob(str(root / "polymarket" / "blocks" / "**" / "*.parquet"), recursive=True)
    
    kalshi_market_files = glob.glob(str(root / "kalshi" / "markets" / "**" / "*.parquet"), recursive=True)
    kalshi_trade_files = glob.glob(str(root / "kalshi" / "trades" / "**" / "*.parquet"), recursive=True)
    
    # Build cutoffs
    cutoffs = build_cutoffs(start_date_local, end_date_local)
    final_cutoff_utc_str = (
        cutoffs["cutoff_utc"]
        .max()
        .tz_convert("UTC")
        .tz_localize(None)
        .strftime("%Y-%m-%d %H:%M:%S")
    )
    
    print(f"\n=== Event Study: {slug.upper()} ===")
    print(f"Event window: {event_start.date()} to {event_end.date()}")
    print(f"Analysis window: {start_date_local.date()} to {end_date_local.date()}")
    print(f"Final cutoff UTC: {final_cutoff_utc_str}")
    
    # ========== MARKET FILTERING ==========
    
    pm_sql = """
    WITH base AS (
        SELECT
            *,
            TRY_CAST(created_at AS TIMESTAMP) AS created_ts,
            TRY_CAST(end_date   AS TIMESTAMP) AS end_ts,
            LOWER(
                COALESCE(CAST(question AS VARCHAR), '') || ' ' ||
                COALESCE(CAST(slug AS VARCHAR), '')
            ) AS search_text
        FROM read_parquet(?)
    ),
    filtered AS (
        SELECT *
        FROM base
        WHERE created_ts <= CAST(? AS TIMESTAMP)
          AND COALESCE(end_ts, CAST('2100-01-01' AS TIMESTAMP)) >= CAST(? AS TIMESTAMP)
          AND regexp_matches(search_text, ?)
    )
    SELECT *
    FROM filtered
    ORDER BY created_ts, id
    """
    
    pm_markets = con.execute(
        pm_sql,
        [pm_market_files, created_cutoff, end_cutoff, topic_regex],
    ).fetchdf()
    
    pm_topics_path = outdir / f"{slug}_pm_topics.csv"
    pm_markets.to_csv(pm_topics_path, index=False)
    print(f"\nPolymarket topic markets: {len(pm_markets):,} -> {pm_topics_path}")
    
    kalshi_sql = """
    WITH base AS (
        SELECT
            *,
            TRY_CAST(created_time AS TIMESTAMP) AS created_ts,
            TRY_CAST(close_time   AS TIMESTAMP) AS close_ts,
            LOWER(
                COALESCE(CAST(title AS VARCHAR), '') || ' ' ||
                COALESCE(CAST(ticker AS VARCHAR), '') || ' ' ||
                COALESCE(CAST(event_ticker AS VARCHAR), '') || ' ' ||
                COALESCE(CAST(yes_sub_title AS VARCHAR), '') || ' ' ||
                COALESCE(CAST(no_sub_title AS VARCHAR), '')
            ) AS search_text
        FROM read_parquet(?)
    ),
    filtered AS (
        SELECT *
        FROM base
        WHERE created_ts <= CAST(? AS TIMESTAMP)
          AND COALESCE(close_ts, CAST('2100-01-01' AS TIMESTAMP)) >= CAST(? AS TIMESTAMP)
          AND regexp_matches(search_text, ?)
    )
    SELECT *
    FROM filtered
    ORDER BY created_ts, ticker
    """
    
    kalshi_markets = con.execute(
        kalshi_sql,
        [kalshi_market_files, created_cutoff, end_cutoff, topic_regex],
    ).fetchdf()
    
    k_topics_path = outdir / f"{slug}_k_topics.csv"
    kalshi_markets.to_csv(k_topics_path, index=False)
    print(f"Kalshi topic markets: {len(kalshi_markets):,} -> {k_topics_path}")
    
    # ========== KALSHI SNAPSHOTS ==========
    
    if len(kalshi_markets) > 0:
        kalshi_markets["ticker"] = kalshi_markets["ticker"].astype(str)
        kalshi_keys = pd.DataFrame({"ticker": sorted(kalshi_markets["ticker"].dropna().astype(str).unique())})
        con.register("kalshi_keys", kalshi_keys)
        
        kalshi_trade_sql = """
        SELECT
            t.ticker,
            CAST(t.created_time AS TIMESTAMP) AS trade_ts,
            CAST(t.yes_price AS DOUBLE) / 100.0 AS price
        FROM read_parquet(?) t
        JOIN kalshi_keys k
          ON t.ticker = k.ticker
        WHERE CAST(t.created_time AS TIMESTAMP) <= CAST(? AS TIMESTAMP)
        """
        
        kalshi_trades = con.execute(
            kalshi_trade_sql,
            [kalshi_trade_files, final_cutoff_utc_str],
        ).fetchdf()
        
        kalshi_trades["ticker"] = kalshi_trades["ticker"].astype(str)
        kalshi_trades["trade_ts_utc"] = pd.to_datetime(kalshi_trades["trade_ts"], utc=True)
        
        kalshi_targets = (
            kalshi_keys.assign(_tmp=1)
            .merge(cutoffs.assign(_tmp=1), on="_tmp", how="inner")
            .drop(columns="_tmp")
        )
        kalshi_targets["cutoff_utc"] = pd.to_datetime(kalshi_targets["cutoff_utc"], utc=True)
        
        kalshi_snaps = asof_snapshots(
            trades_df=kalshi_trades[["ticker", "trade_ts_utc", "price"]],
            targets_df=kalshi_targets[["ticker", "cutoff_utc", "cutoff_label", "cutoff_local"]],
            by_col="ticker",
        )
        
        # Long format (prices only)
        kalshi_long = kalshi_snaps.copy()
        kalshi_long["source_trade_ts_local"] = kalshi_long["trade_ts_utc"].dt.tz_convert("America/Los_Angeles")
        k_long_path = outdir / f"{slug}_k_long.csv"
        kalshi_long.to_csv(k_long_path, index=False)
        
        # Wide format (markets + prices)
        kalshi_wide = (
            kalshi_snaps.pivot(index="ticker", columns="cutoff_label", values="price")
            .reset_index()
        )
        kalshi_wide = kalshi_wide.rename(
            columns={c: f"yes_{c}" for c in kalshi_wide.columns if c != "ticker"}
        )
        
        k_wide_path = outdir / f"{slug}_k_wide.csv"
        kalshi_aug = kalshi_markets.merge(kalshi_wide, on="ticker", how="left")
        kalshi_aug.to_csv(k_wide_path, index=False)
        
        print(f"Kalshi trades pulled: {len(kalshi_trades):,}")
        print(f"Kalshi long  -> {k_long_path}")
        print(f"Kalshi wide  -> {k_wide_path}")
    else:
        print("No Kalshi topic markets matched the filter.")
    
    # ========== POLYMARKET SNAPSHOTS ==========
    
    if len(pm_markets) > 0:
        pm_markets["id"] = pm_markets["id"].astype(str)
        
        token_rows = []
        for _, row in pm_markets.iterrows():
            market_id = str(row["id"])
            token_ids = parse_list_like(row.get("clob_token_ids"))
            outcomes = parse_list_like(row.get("outcomes"))
            
            for i, tok in enumerate(token_ids):
                tok_str = str(tok)
                outcome_name = outcomes[i] if i < len(outcomes) else f"outcome_{i}"
                token_rows.append({
                    "id": market_id,
                    "token_id": tok_str,
                    "outcome_index": i,
                    "outcome_name": outcome_name,
                    "outcome_slug": slugify(outcome_name),
                })
        
        token_map = pd.DataFrame(token_rows).drop_duplicates()
        
        if token_map.empty:
            raise ValueError("No Polymarket token mapping found. Check clob_token_ids / outcomes in filtered file.")
        
        con.register("pm_token_map", token_map)
        
        pm_trade_sql = """
        WITH trades AS (
            SELECT
                CASE
                    WHEN CAST(maker_asset_id AS VARCHAR) = '0'
                        THEN CAST(taker_asset_id AS VARCHAR)
                    ELSE CAST(maker_asset_id AS VARCHAR)
                END AS token_id,
                block_number,
                CASE
                    WHEN CAST(maker_asset_id AS VARCHAR) = '0'
                        THEN CAST(maker_amount AS DOUBLE) / NULLIF(CAST(taker_amount AS DOUBLE), 0)
                    ELSE CAST(taker_amount AS DOUBLE) / NULLIF(CAST(maker_amount AS DOUBLE), 0)
                END AS price
            FROM read_parquet(?)
        ),
        blocks AS (
            SELECT
                block_number,
                CAST(timestamp AS TIMESTAMP) AS block_ts
            FROM read_parquet(?)
            WHERE CAST(timestamp AS TIMESTAMP) <= CAST(? AS TIMESTAMP)
        )
        SELECT
            m.id,
            m.token_id,
            m.outcome_index,
            m.outcome_name,
            m.outcome_slug,
            b.block_ts,
            t.price
        FROM trades t
        JOIN pm_token_map m
          ON t.token_id = m.token_id
        JOIN blocks b
          ON t.block_number = b.block_number
        """
        
        pm_trades = con.execute(
            pm_trade_sql,
            [pm_trade_files, pm_block_files, final_cutoff_utc_str],
        ).fetchdf()
        
        pm_trades["id"] = pm_trades["id"].astype(str)
        pm_trades["token_id"] = pm_trades["token_id"].astype(str)
        pm_trades["trade_ts_utc"] = pd.to_datetime(pm_trades["block_ts"], utc=True)
        
        pm_targets = (
            token_map.assign(_tmp=1)
            .merge(cutoffs.assign(_tmp=1), on="_tmp", how="inner")
            .drop(columns="_tmp")
        )
        pm_targets["cutoff_utc"] = pd.to_datetime(pm_targets["cutoff_utc"], utc=True)
        
        pm_snaps = asof_snapshots(
            trades_df=pm_trades[["token_id", "trade_ts_utc", "price"]],
            targets_df=pm_targets[["id", "token_id", "outcome_index", "outcome_name", "outcome_slug", "cutoff_utc", "cutoff_label", "cutoff_local"]],
            by_col="token_id",
        )
        
        pm_snaps = apply_minimum_tick_size_rounding(pm_snaps, id_col="id", price_col="price")
        
        # Long format (prices only)
        pm_long = pm_snaps.copy()
        pm_long["source_trade_ts_local"] = pm_long["trade_ts_utc"].dt.tz_convert("America/Los_Angeles")
        pm_long_path = outdir / f"{slug}_pm_long.csv"
        pm_long.to_csv(pm_long_path, index=False)
        
        # Wide format (markets + prices)
        pm_snaps["wide_col"] = pm_snaps.apply(
            lambda r: f"outcome_{int(r['outcome_index'])}_{r['outcome_slug']}_{r['cutoff_label']}",
            axis=1
        )
        
        pm_wide = (
            pm_snaps.pivot(index="id", columns="wide_col", values="price")
            .reset_index()
        )
        pm_wide = pm_wide.merge(
            pm_snaps[["id", "minimum_tick_size"]].drop_duplicates(subset=["id"]),
            on="id",
            how="left",
        )
        
        outcome_name_wide = (
            token_map.assign(name_col=lambda df: df["outcome_index"].map(lambda i: f"outcome_{i}_name"))
            .pivot(index="id", columns="name_col", values="outcome_name")
            .reset_index()
        )
        
        pm_aug = pm_markets.merge(outcome_name_wide, on="id", how="left").merge(pm_wide, on="id", how="left")
        pm_wide_path = outdir / f"{slug}_pm_wide.csv"
        pm_aug.to_csv(pm_wide_path, index=False)
        
        print(f"Polymarket trades pulled: {len(pm_trades):,}")
        print(f"Polymarket long  -> {pm_long_path}")
        print(f"Polymarket wide  -> {pm_wide_path}")
    else:
        print("No Polymarket topic markets matched the filter.")
    
    print("\nDone.\n")