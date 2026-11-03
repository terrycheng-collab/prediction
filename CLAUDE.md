# Resolution Risk in Prediction Markets

Research project (draft paper + code) studying whether prediction-market prices reflect
**resolution risk** — uncertainty that a contract will be resolved the way traders expect,
separate from uncertainty about the underlying event itself.

## Core idea

A binary market price is usually read as "the market's probability the event happens." That
reading assumes the exchange will map the realized event onto the contract's payoff the way
traders expect. This project tests that assumption by comparing:

- **Polymarket** — matched contracts are ultimately resolved by UMA's optimistic oracle
  (directly, or through Polymarket's negative-risk adapter). Outcomes can be disputed and go to
  a token-weighted vote.
- **Kalshi** — resolves contracts internally; no token-holder dispute mechanism.

Same underlying event, different resolution institution. The hypothesis: a public controversy
over how a contract will be resolved should push Polymarket's price toward 0.50 (more
uncertain) relative to the matched Kalshi price, even if beliefs about the actual event haven't
changed.

Two outcome variables, per matched contract `i` at time `t`:
- `A^P_it = |p^P_it - 0.5|` — Polymarket price extremity
- `R_it = A^P_it - A^K_it` — Polymarket extremity relative to matched Kalshi contract (the
  cleaner outcome, since it nets out how close the underlying event is to resolved)

Two studied controversies: the Mar 24, 2025 Ukraine mineral-rights resolution, and the
Jun 30–Jul 8, 2025 Zelensky-suit dispute.

The full writeup is `resolution_risk_outline_revised.tex`/`.pdf`; slides are in `slides/`.

## Current direction (from 2026-10)

The two-event, last-price, lifetime-volume-weighted design in the outline is now the baseline,
not the destination. The plan, in order:

1. **Trade-level panel** — *done*, `trade_panel.py` (see below). Use the trade data we already
   have (size, direction, wallets), not just last prices; fixed pre-event weights instead of
   ex-post lifetime volume; explicit staleness.
2. **Kalshi quotes** — pull official Kalshi candlesticks (bid/ask OHLC, volume, open interest)
   for the matched markets and use the bid/ask midpoint instead of last trade. Kalshi is the
   stale leg (median 20.6h since last trade at a snapshot, 90th percentile 19 days). Check
   that settled 2025 markets are still reachable (Kalshi moved settled markets to separate
   historical endpoints).
3. **Dispute panel as the main design** — replace the two hand-picked events with:
   (a) a staggered market-level event study over the 3,853-row dispute catalog, using sibling
   outcomes in the same neg-risk group as controls (most disputed markets have no Kalshi twin)
   and Kalshi matches where they exist; (b) a daily platform-level dispute-intensity index
   (open disputes, DVM escalations), regressed against the PM-Kalshi gap of *non-disputed*
   matched markets, to test whether disputes erode trust in UMA generally. Separate
   procedural "too early" disputes from substantive ones, and control for pre-dispute
   ambiguity. Keep the two current events as case studies.
4. **Controversy intensity from text** — Polymarket's public Gamma comments API
   (`/comments`, timestamped, optionally with commenter positions) as a measured, not
   hand-coded, controversy signal.

Ideas noted but not scheduled: post-outcome "resolution-risk discount" (gap between a
near-certain contract's price and $1 after the real-world outcome is known, PM vs Kalshi);
linking UMA voter addresses (Ethereum) to Polymarket trader addresses (Polygon) to see whether
voters held positions in markets they voted on; Polymarket open interest from Goldsky's public
Polymarket subgraphs; commercial order-book data only once the event sample is large (coverage
starts Aug 2025, after both current events).

## Pipeline (what's built so far)

Data flows through these scripts in order:

1. **`data_downloader.py`** — downloads and extracts the public J.D. Becker Polymarket/Kalshi
   archive (`https://s3.jbecker.dev/data.tar.zst`, ~36 GB compressed) into `data/`. `data/` is
   gitignored — not part of the repo, re-download instead of transferring between machines.
2. **`data_processing.py`** — normalizes the raw archive into a workable form.
3. **`contract_matching.py`** (~1,800 lines) — deterministic matcher. Parses each contract title
   into a structured key (predicate/subject/object/threshold/deadline) across 17 contract
   families (elections, Fed decisions, asset thresholds, etc.), normalizes aliases/deadlines,
   then joins exact keys across exchanges. From 5,680 Polymarket / 8,992 Kalshi markets, this
   currently produces 150 deterministic matched pairs. An earlier fuzzy
   Levenshtein+Jaccard matcher was superseded by this approach and lives in
   `scratch/archive_matching_v1_levenshtein_jaccard.py` for reference.
4. **`build_pm_resolver_map.py`** — classifies each matched Polymarket market by its actual
   on-chain resolver (UMA adapter v1/v2/v3 vs. negative-risk adapter) via direct Polygon
   `eth_call`/log-topic queries against a public RPC — no subgraph dependency. Its
   `DEFAULT_RPC` (`polygon-bor-rpc.publicnode.com`) now rejects historical `eth_getLogs`
   without a paid archive token (policy changed after this script was last run); use
   `--rpc-url https://polygon.gateway.tenderly.co` (free, no key, confirmed working
   2026-07-30) instead.
5. **`build_uma_event_timeline.py`** — pulls precise proposal/dispute/DVM-vote/resolution
   timelines for the two studied controversies, condition_id-anchored, straight from Polygon's
   OptimisticOracleV2 and Ethereum mainnet's VotingV2 over RPC (same free Tenderly gateway
   endpoints, no subgraph dependency). See "Completed" below for what it found.
6. **`resolution_risk_event_study.py`** (~840 lines) — builds the as-of price panel (5am/5pm
   Pacific snapshots, most-recent-trade-at-or-before-cutoff), computes the extremity outcomes,
   runs the contract-fixed-effects pre/post regression, and renders event-window plots with
   matplotlib. `exports/` holds the resulting CSVs and PNGs; subfolders under it
   (`event_active_contracts/`, `archive_match_top1000/`, etc.) are outputs from different
   matching/filter runs. The live 150-pair match set is
   `exports/event_active_contracts/contract_matches.csv` (the script's default); the 3-row
   top-level `exports/contract_matches.csv` is a stale test output.
7. **`trade_panel.py`** — trade-level rebuild of step 6's panel (~40 s). Keeps step 6's snapshot
   prices unchanged and adds, per contract x 5am/5pm PT cutoff: staleness of each venue's
   price; 12h-interval share/contract volume, Yes-equivalent USD notional, trade counts, unique
   Polymarket wallets, signed taker flow and imbalance, VWAP; and three weights (legacy
   lifetime volume, pre-event PM share volume, equal). Runs the step-6 FE regression over
   sample x staleness filter x weight x outcome. Outputs `exports/trade_panel/trade_panel.csv`
   and `trade_panel_regressions.csv`. Its `all / none / lifetime_volume` rows equal the
   corrected Table 1. Polymarket volume rules (verified against raw fills): count only maker
   fills (drop rows whose `taker` is the CTF Exchange `0x4bFb...982E` or NegRisk CTF Exchange
   `0xC5d5...f80a`, which are per-match summary fills and would double-count); read both the
   Yes and No token, since mint matches only show up on one; a taker buying No is a taker
   selling Yes at 1 - p_No.
8. `data_source_explore.ipynb` — the original exploratory notebook (has the download URL);
   superseded by the scripts above but kept for reference.
9. `scratch/` — debug and archived one-off scripts, not part of the active pipeline.

Setup: `pip install -r requirements.txt`, then run the scripts in the order above with
`--data-root` pointing at the extracted archive (default `data/`).

**Kalshi time-zone bug (found and fixed 2026-10).** DuckDB casts `TIMESTAMPTZ` columns (Kalshi
`created_time`) to naive `TIMESTAMP` in the *session* time zone, which defaults to the machine's
zone; the event study then labelled the result UTC. On a Pacific machine every Kalshi trade was
shifted 7-8h earlier, so Kalshi snapshots used trades from after the cutoff: 29% of
mineral-rights and 47% of Zelensky-suit Kalshi snapshots (median 4.8h ahead, max 7h), and at
the resolution-day 17:00 PT snapshots 28/104 and 22/56 Kalshi prices came from trades after
the on-chain settlement. Polymarket was unaffected (block timestamps are `...Z` strings). The
event study now sets `TimeZone = 'UTC'` by default; `--duckdb-timezone America/Los_Angeles`
reproduces the old behaviour on any machine. The same naive-cast pattern remains in
`contract_matching.py` and `data_processing.py`; there it only shifts market active-window
filters by a few hours and doesn't feed snapshot prices, so the matches were not rebuilt.

**Reproducing Table 1:** `python scripts/reproduce_table1.py` (add `--data-root <path>` if the
archive isn't at `data/`; ~80 s). It runs `resolution_risk_event_study.py` for each panel (Panel
A: `--uma-backed-only --outcome-mode attenuation`; Panel B: same plus `--pm-resolver-proxy
uma_risk_exposed`) twice: *published* (`--duckdb-timezone America/Los_Angeles`), checked against
the .tex and setting the exit status, and *corrected* (UTC), printed with differences. Outputs go
to `exports/table1/` (gitignored). The event study's default `--outcome-mode raw` regresses
price *levels*, not extremity, so its default output (`exports/resolution_risk_regressions.csv`,
negative coefficients) is not Table 1.

| Post coefficient | MR \|P-.5\| | MR rel. Kalshi | ZS \|P-.5\| | ZS rel. Kalshi |
|---|---|---|---|---|
| Panel A, published | 0.0010 | 0.0003 | 0.0197 | 0.0047 |
| Panel A, corrected | 0.0008 | 0.0003 | 0.0197 | 0.0055 |
| Panel B, published | 0.0117 | 0.0012 | 0.0204 | 0.0147 |
| Panel B, corrected | 0.0117 | 0.0037 | 0.0204 | 0.0152 |

The .tex still shows the published numbers; whether to revise it is an open call.

**Current headline result** (Table 1): estimated `Post` coefficients are generally *positive*,
not negative — i.e. Polymarket prices become *more* extreme, not less, after both controversies,
including relative to Kalshi after the Zelensky-suit episode. This rejects the simplest version
of the attenuation hypothesis in the current specification, and survives the time-zone fix.
**Caveat from the trade panel:** the relative-to-Kalshi result is fragile to weighting and
staleness. Under pre-event or equal weights the mineral-rights relative coefficient turns
negative (-0.0005 to -0.0114 across samples and staleness filters), and under pre-event weights
the Zelensky relative coefficient shrinks from 0.0055 to 0.0003-0.0004 in the full sample
(equal weights: 0.0033-0.0056). Pre-event weights are concentrated (top 5
pairs hold 62% of Zelensky weight), and 10 of 105 mineral-rights pairs have no pre-event
Polymarket volume. Treat the sign of the relative outcome as unsettled until Kalshi quotes
(direction step 2) replace stale Kalshi last trades.

## Limitations already identified (see the outline's own Limitations section)

- **Data frequency/quality** — prices are last-trade-at-cutoff snapshots, not synchronized
  quotes. No bid/ask, depth, or open-interest time series yet. Kalshi is far staler than
  Polymarket (median hours since last trade at a snapshot: 20.6 vs 1.9; Kalshi traded in only
  42% of 12h intervals vs 80% for Polymarket). `trade_panel.py` now measures staleness and
  offers fixed pre-event weights in place of the ex-post lifetime-volume weights, which could
  themselves respond to the controversy.
- **Matching/contract equivalence** — exact-key title parsing doesn't compare full resolution
  rule text, so accepted matches could still hide economically important differences (deadline,
  resolution source, cancellation provisions).
- **Event definition/windows** — the 1-day mineral-rights window and 8-day Zelensky window
  aren't directly comparable. A documented timeline of proposal/dispute/vote/resolution
  timestamps for both episodes now exists (see "Completed" below) — it shows both windows'
  final on-chain resolution lands *after* the last in-window price snapshot, so the current
  design can't observe the price response to resolution itself. Whether to redraw either
  window based on this is an open call, not yet made.
- **Inference** — standard errors are unclustered and explicitly not valid for formal inference;
  only two controversy events means results should stay descriptive, not causal.

## Completed (2026-07-30)

- **UMA subgraph access.** The Graph's own hosted UMA subgraphs are dead (301) and its
  current gateway requires a paid API key — but Goldsky hosts a free public mirror of the
  same OOv2 subgraph data (`api.goldsky.com/api/public/project_clus2fndawbcc01w31192938i/
  subgraphs/...`), which is live and was used to pull **all 3,853 disputed Polymarket/UMA
  requests, ever**, with proposal/dispute/settlement timestamps. See
  `exports/uma_dispute_landscape_summary.md` (write-up),
  `exports/uma_polymarket_dispute_catalog.csv` (full catalog),
  `exports/uma_high_profile_disputes_top20.csv` (ranked top 20). No mainnet-voting subgraph
  was found mirrored under the same Goldsky project, so DVM commit/reveal-level detail
  (round IDs, individual vote timestamps) isn't in that catalog.
- **Precise timelines for the two studied controversies**, condition_id-anchored (the
  catalog above joins by title text, which leaves the mineral-rights row unkeyed) and
  extended down to the mainnet DVM vote: `build_uma_event_timeline.py`, a new script that
  reads Polygon's OptimisticOracleV2 and Ethereum mainnet's VotingV2 directly over RPC (no
  subgraph dependency — useful as an independent cross-check, which is exactly what it did:
  every timestamp it produced matches the Goldsky catalog to the second). Outputs
  `exports/uma_event_timeline_{mineral_rights,zelensky_suit}.csv` and
  `exports/uma_dvm_vote_timeline_{mineral_rights,zelensky_suit}.csv`. Findings are written
  up in the "Update" section at the bottom of `exports/uma_dispute_landscape_summary.md`.
- **Expanding the event sample beyond n=2** is not done, but the catalog above is exactly
  the candidate list needed (see "Future work / data options explored" below).

## Future work / data options explored

Researched while extending this project (2026-07-30). The current plan is "Current direction"
above; these notes are the background:

- **Expanding the event sample** — currently only 2 controversies feed the regression. The
  dispute catalog above (3,853 rows, ranked by volume) is the candidate list; turning it into
  a real panel still requires re-running contract matching against these markets and rebuilding
  the price panel for each. Other known 2025-2026 UMA/Polymarket disputes flagged as good
  candidates: the MicroStrategy Bitcoin-sale dispute (~$60M volume, sent to token vote), the
  UFO-declassification market ($16M, resolved "Yes" despite no declassification), several
  Trump-declassification markets. Polymarket logged 1,150+ disputed markets in 2026 alone
  (already exceeding all of 2025) — this would move the analysis from "descriptive, n=2"
  toward something closer to a real panel.
- **Third-party orderbook/depth data** — neither exchange's official API exposes historical
  order books (Kalshi is deprecating its endpoint in favor of a sub-cent version; Polymarket's
  API has no historical orderbook endpoint at all). Commercial providers cover the gap for both
  venues (e.g. Oddpool, DepthFeed) or per-venue (Predexon/Lychee Data for Kalshi;
  PolymarketData/Telonex for Polymarket, from Aug 2025 onward). Unvetted for cost/reliability —
  would need evaluation before relying on them, but this is the only route to real bid/ask/depth
  data given the official APIs' gaps.
- **LLM-assisted matching** — the outline proposes separating candidate generation (embeddings/
  lexical retrieval within family+date+entity segments) from adjudication (an LLM comparing full
  contract text against a fixed schema, with human review of accepted matches) to extend
  coverage beyond the current 23%/22% parse rate without sacrificing precision. A prototype
  (TF-IDF candidates, Haiku adjudication, `llm_matching_prototype.py`) exists on the unmerged
  branch `origin/worktree-polished-launching-naur`.

## Data gotchas

- The extracted archive contains macOS `._*` metadata files next to the parquet files. A bare
  `read_parquet('.../*.parquet')` glob fails on them; glob `trades_*.parquet` etc., or filter
  `._` names as the scripts do.
- Set `TimeZone = 'UTC'` on every DuckDB connection that touches Kalshi timestamps (see the
  time-zone bug above).
