import duckdb
import glob
from pathlib import Path

def analyze_market_data_for_all(start_date, end_date, root_dir="data"):
    """
    Analyze market and trade data for both Polymarket and Kalshi.

    Parameters:
        start_date (str): Start date for the analysis window (YYYY-MM-DD).
        end_date (str): End date for the analysis window (YYYY-MM-DD).
        root_dir (str): Root directory containing the data files.
    """
    con = duckdb.connect()

    platforms = ["polymarket", "kalshi"]

    for platform in platforms:
        print(f"\n=== Analyzing {platform.capitalize()} Data ===")

        # Dynamically find files for the platform
        root = Path(root_dir) / platform
        market_files = glob.glob(str(root / "markets" / "**" / "*.parquet"), recursive=True)
        trade_files = glob.glob(str(root / "trades" / "**" / "*.parquet"), recursive=True)
        block_files = glob.glob(str(root / "blocks" / "**" / "*.parquet"), recursive=True)

        # 1) Block timestamp range
        if block_files:
            q_blocks = """
            SELECT
                MIN(CAST(timestamp AS TIMESTAMP)) AS min_block_ts,
                MAX(CAST(timestamp AS TIMESTAMP)) AS max_block_ts,
                COUNT(*) AS n_rows
            FROM read_parquet(?)
            """
            print("\n=== BLOCK TIMESTAMP RANGE ===")
            print(con.execute(q_blocks, [block_files]).fetchdf().to_string(index=False))

        # 2) Trade coverage via join to blocks
        if trade_files and block_files:
            q_trades = """
            WITH trades AS (
                SELECT block_number
                FROM read_parquet(?)
            ),
            blocks AS (
                SELECT
                    block_number,
                    CAST(timestamp AS TIMESTAMP) AS block_ts
                FROM read_parquet(?)
            )
            SELECT
                MIN(block_ts) AS min_trade_ts,
                MAX(block_ts) AS max_trade_ts,
                COUNT(*)      AS n_trade_rows
            FROM trades t
            LEFT JOIN blocks b
              ON t.block_number = b.block_number
            """
            print("\n=== TRADE TIMESTAMP RANGE ===")
            print(con.execute(q_trades, [trade_files, block_files]).fetchdf().to_string(index=False))

        # 3) Trades in the specified window
        if trade_files and block_files:
            q_window = f"""
            WITH trades AS (
                SELECT block_number
                FROM read_parquet(?)
            ),
            blocks AS (
                SELECT
                    block_number,
                    CAST(timestamp AS TIMESTAMP) AS block_ts
                FROM read_parquet(?)
            )
            SELECT
                COUNT(*) AS trades_in_window,
                MIN(block_ts) AS first_trade_in_window,
                MAX(block_ts) AS last_trade_in_window
            FROM trades t
            JOIN blocks b
              ON t.block_number = b.block_number
            WHERE block_ts >= TIMESTAMP '{start_date}'
              AND block_ts <  TIMESTAMP '{end_date}'
            """
            print("\n=== TRADES IN SPECIFIED WINDOW ===")
            print(con.execute(q_window, [trade_files, block_files]).fetchdf().to_string(index=False))

        # 4) Markets touching the specified window
        if market_files:
            q_market_window = f"""
            SELECT
                COUNT(*) AS markets_touching_window
            FROM read_parquet(?)
            WHERE
                COALESCE(end_date, TIMESTAMP '2100-01-01') >= TIMESTAMP '{start_date}'
                AND COALESCE(created_at, TIMESTAMP '1900-01-01') < TIMESTAMP '{end_date}'
            """
            print("\n=== MARKETS TOUCHING SPECIFIED WINDOW ===")
            print(con.execute(q_market_window, [market_files]).fetchdf().to_string(index=False))

        # Generate price histories
        if market_files:
            q_price_history = f"""
            WITH base AS (
                SELECT
                    *,
                    TRY_CAST(created_at AS TIMESTAMP) AS created_ts,
                    TRY_CAST(end_date   AS TIMESTAMP) AS end_ts,
                    TRY_CAST(volume     AS DOUBLE)    AS volume_num
                FROM read_parquet(?)
            ),
            filtered AS (
                SELECT *
                FROM base
                WHERE created_ts <= TIMESTAMP '{end_date}'
                  AND COALESCE(end_ts, TIMESTAMP '2100-01-01') >= TIMESTAMP '{start_date}'
            )
            SELECT *
            FROM filtered
            ORDER BY volume_num DESC NULLS LAST, id
            LIMIT 100
            """
            price_history_df = con.execute(q_price_history, [market_files]).fetchdf()
            output_path = Path("exports") / f"{platform}_price_history_{start_date}_to_{end_date}.csv"
            output_path.parent.mkdir(exist_ok=True)
            price_history_df.to_csv(output_path, index=False)
            print(f"\nPrice history saved to {output_path}")