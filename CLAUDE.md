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
   matching/filter runs.
7. `data_source_explore.ipynb` — the original exploratory notebook (has the download URL);
   superseded by the scripts above but kept for reference.
8. `scratch/` — debug and archived one-off scripts, not part of the active pipeline.

Setup: `pip install -r requirements.txt`, then run the scripts in the order above with
`--data-root` pointing at the extracted archive (default `data/`).

**Current headline result** (see the outline's Table 1): estimated `Post` coefficients are
generally *positive*, not negative — i.e. Polymarket prices become *more* extreme, not less,
after both controversies, including relative to Kalshi after the Zelensky-suit episode. This
rejects the simplest version of the attenuation hypothesis in the current specification. This is
reported as a genuine (if surprising) finding, not a bug to chase.

## Limitations already identified (see the outline's own Limitations section)

- **Data frequency/quality** — prices are last-trade-at-cutoff snapshots, not synchronized
  quotes. No bid/ask, depth, or open-interest time series; Kalshi observations are noticeably
  staler than Polymarket's; volume weights are ex-post and could themselves respond to the
  controversy.
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

Researched while extending this project (2026-07-30) — not yet implemented:

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
  coverage beyond the current 23%/22% parse rate without sacrificing precision.
