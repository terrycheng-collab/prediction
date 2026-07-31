# The UMA Dispute Landscape on Polymarket

Generated 2026-07-30. Data pulled directly from UMA's own Optimistic Oracle V2 subgraphs
(the same GraphQL endpoints that power `oracle.uma.xyz`), not from press coverage or Dune
dashboards. This directly implements the "expanding the event sample" item in
`CLAUDE.md`'s future-work section.

## Data sources

Two generations of Polymarket's UMA integration, both queried in full (paginated, no row cap):

| Adapter | Requester address | Era | Disputed requests pulled |
|---|---|---|---|
| `uma_adapter_v2` (legacy OOv2) | `0x6a9d2226...` | ~2022–2026 | 725 |
| `uma_adapter_v3` (legacy OOv2, v3 flavor) | `0x157ce2d6...` | 2025–2026 | 110 |
| `neg_risk_uma_adapter` (legacy, multi-outcome markets) | `0x2f5e3684...` | 2022–2026 | 1,011 |
| `managed_adapter_main` (current Managed OOv2) | `0x65070be9...` | Aug 2025–present | 1,623 |
| `managed_adapter_neg_risk` (current Managed OOv2, neg-risk) | `0x69c47de9...` | Aug 2025–present | 384 |
| **Total** | | | **3,853 disputed price requests** |

Endpoints: `api.goldsky.com/api/public/project_clus2fndawbcc01w31192938i/subgraphs/{polygon-optimistic-oracle-v2,polygon-managed-optimistic-oracle-v2}/.../gn`.
Polymarket migrated most new markets to the "Managed" OOv2 adapter around August 2025; both
generations are still active in parallel, so both had to be pulled — the legacy-only pull
(first pass) silently missed 2,007 disputes, including the entire pool of most-recent 2026
headline cases. There is also an OOv1-era adapter (2020–2022) not pulled here — likely small,
low-volume markets, but this is a scope gap, not zero disputes.

By year (dispute-event rows, not unique markets): 2023: 75 · 2024: 394 · 2025: 1,315 · 2026
(through Jul 30): 2,068 — consistent with Polymarket's own reporting of 1,150+ disputed
markets in 2026 alone (event-level counts run higher than market-level counts because ~14%
of disputed markets get re-disputed across multiple proposal rounds before final settlement).

Each request records `proposedPrice` vs `settlementPrice` (in UMA's 0 / 1e18 / 0.5e18 =
No/Yes/50-50 convention), bond size, and full proposal→dispute→DVM-vote→settlement
timestamps — this is a strictly richer timeline than the single assumed-discontinuity
event windows currently used for the two hand-picked controversies, and could replace them.

**Caveat on volume matching**: dispute titles were joined to Polymarket's `question` field
(from the project's own downloaded archive, `data/polymarket/markets/`) to pull trading
volume. That archive was itself snapshotted 2026-02-03, so a market created after that date
generally can't have a volume match. 1,728 of the 3,853 disputes were themselves disputed
after the snapshot date; of those, 280 still matched (the market existed before the snapshot
and was simply disputed later), leaving 1,448 unmatched purely because of the cutoff. A
further 187 pre-snapshot disputes didn't match on title text (parsing/formatting
mismatches). Combined, 1,635 of 3,853 disputes (42.4%) land in an "unknown volume" bucket —
not necessarily low-profile, just outside the archive's coverage or title-join reach — and
are excluded from the ranked/grouped analysis below. Net: volume-based rankings below cover
2,218 of 3,853 disputes (57.6%); full raw catalog (all 3,853, with an explicit
`volume_bucket` column showing which case each falls into) is in
`exports/uma_polymarket_dispute_catalog.csv`.

## Top 20 highest-volume disputes (all Polymarket, all time)

| Title | Volume |
|---|---|
| Will Zelenskyy wear a suit before July? | $242.2M |
| TikTok banned in the US before May 2025? | $119.7M |
| Fed increases interest rates by 25+ bps after October 2025 meeting? | $102.2M |
| Will Trump release the Epstein files by December 19? | $90.9M |
| Will Inter Milan win the UEFA Champions League? | $83.0M |
| Will Eleven die in "Stranger Things: Season 5"? | $80.8M |
| Xi Jinping out in 2025? | $78.7M |
| Will Trump launch a coin before the election? | $76.9M |
| Will Polymarket US go live in 2025? | $65.4M |
| Lighter market cap (FDV) >$1B one day after launch? | $55.1M |
| Israel x Iran ceasefire before July? | $51.8M |
| US x Venezuela military engagement by December 31? | $51.1M |
| Yoon out as president of South Korea before May? | $40.2M |
| Israel x Hezbollah Ceasefire in 2024? | $40.1M |
| Monad market cap (FDV) >$4B one day after launch? | $34.9M |
| Will Melania say "Career" during AI talk on Friday? | $31.1M |
| Will Trump nominate Kevin Warsh as the next Fed chair? | $28.8M |
| Fordow nuclear facility destroyed before July? | $28.6M |
| U.S. anti-cartel ground operation in Mexico by January 31? | $27.8M |
| Israel military action against Iraq before November? | $27.8M |

Full ranked table (top 20 with dispute dates and flip outcomes): `exports/uma_high_profile_disputes_top20.csv`.

**Both of this project's studied controversies show up here, and by construction they are
outliers on this list**: the Zelensky-suit market is *the single largest UMA dispute in
Polymarket's history* ($242M, disputed 5 separate times between 2025-05-29 and 2025-07-05 —
a noticeably wider window than the paper's assumed 2025-06-30–07-08 discontinuity). The
Ukraine mineral-rights episode is smaller and messier in this data: no single market titled
"mineral rights" cleared the volume-match bar, but the closely related "Trump x Ukraine
mineral deal signed before May?" ($6.8M) and "Energy infrastructure ceasefire in Ukraine in
March?" ($5.7M, disputed 2025-03-25 — one day after the paper's Mar-24 event date) both
appear as genuine mid-size disputes in the same window.

Other 2025–2026 disputes with $10M+ volume not previously in the paper's sample (good
candidates for extending it): MicroStrategy/Strategy Bitcoin-purchase markets (several,
$0.7M–$18M), "Trump declassifies UFO files in 2025?" ($16.7M), "Trump meet with Xi Jinping by
October 31?" ($9.1M, price swung 17%→95% on the disputed vote), "Trump declassifies JFK files
in first week?" ($5.2M, flipped twice across 3 dispute rounds).

## High-profile vs. regular disputes

Threshold: **high-profile = matched trading volume ≥ $5M** (168 dispute events / 94 unique
markets). Everything else with a volume match is "regular" (2,050 events / 1,751 markets).

| Metric | High-profile | Regular |
|---|---|---|
| n (dispute events) | 168 | 2,050 |
| Median volume | $11.0M | $52.4K |
| Median bond posted | $500 | $500 |
| **Outcome flip rate (event-level)** | **36.3%** | **71.6%** |
| **Outcome flip rate (market-level, dedup'd)** | **47.9%** | **76.9%** |
| Went to 50/50 ("Unknown") outcome | 0.0% | 1.2% |
| Median hours proposal→dispute | 0.53h | 0.24h |
| Median days dispute→settlement | 3.25 | 3.17 |
| Mean dispute rounds per market | 1.79 | 1.17 |
| Markets disputed >1 time | 69% (65/94) | 14.5% (254/1,751) |

### What this says

1. **Bond size does not scale with stakes.** Median dispute bond is $500 whether the market
   has $50K or $240M in volume. Economic security per dollar at risk falls by roughly 3–4
   orders of magnitude as market size grows — the $500 bond that deters bad-faith disputes on
   a niche sports market is a rounding error against a $240M market's dispute-resolution fee
   pool. This is the cleanest, most robust finding here (holds regardless of the volume-match
   caveats above, since bond is a request-level field, not a title-joined one).

2. **Regular disputes usually side with the disputer; high-profile disputes are a near
   coin-flip.** For the median $52K market, the disputer wins ~72–77% of the time — consistent
   with these being routine corrections of an erroneous or premature automated proposal (see
   title sample below), not genuine controversies. For $5M+ markets, the vote is far more
   contested (36–48% flip rate) — the DVM is not simply rubber-stamping the "obviously
   correct" side, it's genuinely split. The gap holds under both measures: event-level
   (36.3% vs. 71.6%) and market-level dedup via `max(flip)` per market (47.9% vs. 76.9%).
   Note the dedup measure is *biased toward narrowing the gap*, not widening it — it takes
   the most-favorable-to-disputer round for every market, and high-profile markets get
   re-disputed far more often (1.79 rounds/market vs. 1.17), so `max()` has more chances to
   flip the label to "flipped" for high-profile markets specifically. That the ~35-point gap
   survives a dedup method biased against finding it is a stronger result than either number
   alone. This is directly relevant to the paper's resolution-risk thesis: it's
   independent evidence that high-profile UMA disputes carry more *genuine* adjudication
   uncertainty than the median dispute, even though the paper's own price-based `Post`
   coefficients came out in the opposite (attenuation-rejecting) direction.

3. **High-profile markets get re-disputed far more often** (69% see a second round vs. 14.5%
   of regular markets) — a proposal gets rejected, re-proposed, and disputed again, which is
   itself a longer, more visible public controversy than a single-shot regular dispute.

4. **A small number of addresses specialize in "regular" disputes.** The single most
   active disputer address (`0x0db5aea9...`) filed 293 of the 3,853 disputes (7.6%) but only
   3 of the 168 high-profile ones — consistent with a bot/professional operator that
   routinely catches bad automated proposals on templated/recurring markets, rather than
   engaging in headline controversies. (Not yet checked against the "60%+ of active UMA
   voters have Polymarket accounts" conflict-of-interest claim reported in press coverage —
   would need voter-level DVM data, not proposer/disputer data, to test that directly.)

5. **What "regular" disputes actually look like** (most frequent titles, all volume < $5M):
   templated in-game esports/sports totals ("Total Kills Over/Under 25.5 in Game 1?", "Games
   Total: O/U 2.5" — 30 separate disputed instances of this exact template), daily/weekly
   crypto price-threshold markets, minor-country election turnout/vote-share markets, and
   Trump-says-a-word novelty markets. These read as recurring markets where an automated
   proposer's price gets challenged as mechanically wrong (e.g., proposed before the game
   ended, or misread a source), not as sites of public controversy over resolution authority.

## Files produced

- `exports/uma_polymarket_dispute_catalog.csv` — all 3,853 disputed requests, one row each,
  with `volume_bucket` (`high_profile` / `regular` / `unknown_volume`), flip/50-50 flags,
  full timing, bond/reward, proposer/disputer addresses.
- `exports/uma_high_profile_disputes_top20.csv` — the top 20 by volume with dispute dates.

## Suggested next steps if this is extended into the paper

- Re-pull post-2026-02-03 volumes (the current `data_downloader.py` archive is stale for this
  purpose) to resolve the 1,728 "unknown volume" disputes — this is nearly half the 2026
  sample and would change which recent cases qualify as "high-profile."
  Also worth pulling the OOv1-era adapter and doing a proper condition_id-based join (title
  matching is a reasonable proxy but a real key join would fix the 187 pre-snapshot misses).
- The dispute timeline fields here (proposal/dispute/settlement timestamps) are exactly the
  "documented timeline of proposal/dispute/vote/resolution timestamps" the outline's
  Limitations section says is missing — could replace the single assumed-discontinuity event
  windows for both existing controversies and any new ones drawn from this list.

## Update (same day): condition_id-anchored timelines + mainnet DVM vote detail

The catalog above joins disputes to markets by title text, so the mineral-rights row has
`condition_id = NaN` — the title-match is a proxy, not a key join, as this file's own
"suggested next steps" flags. `build_uma_event_timeline.py` (new script, this session) closes
that gap for the two paper controversies specifically: it starts from the exact matched
`condition_id` (`0x1663edea...` for mineral rights, `0x655e5ca1...` for Zelensky-suit, both
from `contract_matching.py`'s join key), resolves the on-chain adapter/question via
`ConditionPreparation` logs, then pulls every `RequestPrice`/`ProposePrice`/`DisputePrice`/
`Settle` event from Polygon's OptimisticOracleV2 (`0xee3afe34...`) directly over RPC — no
subgraph dependency. Every timestamp this produced matches the Goldsky-sourced catalog above
to the second, which is a strong independent cross-check of both methods. Output:
`exports/uma_event_timeline_{mineral_rights,zelensky_suit}.csv`.

It goes one step further than the catalog by also resolving the mainnet DVM side —
`VotingV2` (`0x0043...bd34ac`) `RequestAdded`/`VoteCommitted`/`VoteRevealed`/`RequestResolved`
events — which isn't in this project's Goldsky pull (no mirrored mainnet-voting subgraph was
found under the same Goldsky project; common name guesses all 404'd). One non-obvious wrinkle
required to join Polygon and mainnet: the DVM's `time` key for an escalated dispute is the
*proposal's* block timestamp, not the OO request's own `timestamp` parameter — the two differ
by minutes to hours once a market has been reset and re-proposed. Output:
`exports/uma_dvm_vote_timeline_{mineral_rights,zelensky_suit}.csv`.

**Mineral rights — single decisive round.** Proposed "Yes" 2025-03-22 21:58 UTC, disputed 2
min later; reset and re-proposed "Yes" the same evening (23:04 UTC), disputed again 1 min
later. Both disputes landed in the *same* DVM round (10085): commit 03-23 00:00 UTC → 03-24
00:00 UTC, reveal 03-24 00:00 UTC → 03-25 00:00 UTC, resolved "Yes" for both simultaneously at
03-25 00:00:23 UTC, settled on Polygon at **03-25 00:21–00:23 UTC (= 03-24 17:21 PT)**.
Confirmed via plaintext ancillary-data match on both mainnet `RequestAdded` rows.

**Zelensky-suit — five rounds, only the last two are substantive.** The market's own terms
("photographed or videotaped wearing a suit between May 22 and June 30, 2025") make rounds 1–2
(propose 05-29, 06-02, both "Yes") premature by construction — no qualifying event had
occurred yet, so the DVM's "too early" (`Ignore`) response in both cases is the DVM behaving
correctly, not evidence of ongoing controversy (this is the same "regular dispute" pattern the
catalog's finding #5 describes). Round 3 (propose 06-26 08:47 UTC, "Yes") is the first
*substantive* round — it follows Zelenskyy's 06-24 NATO-summit appearance — and the DVM again
returned "too early" (round settled 06-29). Rounds 4 (propose 07-01, disputed 28 sec later)
and 5 (propose 07-05, "No" this time, disputed 40 min later) are also substantive; round 5's
DVM vote (round 10138) is the one that stuck: commit 07-07 00:00 UTC → 07-08 00:00 UTC, reveal
07-08 00:00 UTC → 07-09 00:00 UTC, resolved "No" at 07-09 00:00:35 UTC, settled on Polygon at
**07-09 00:27:37 UTC (= 07-08 17:27 PT)**. (Caveat: the mainnet `RequestAdded` row for this
round carries a stamped `ancillaryDataHash` rather than plaintext — the cross-chain relay
hashes the assertion once it exceeds a size threshold — so this match rests on
time+round-id+resolved-price consistency rather than a plaintext check; round-id and price
both line up exactly with the Polygon-side settlement, making an accidental collision very
unlikely but not textually proven the way the mineral-rights match is.)

**What this means for the paper's coded event windows.** Both events' final on-chain
resolutions land *inside* the paper's currently-coded window but *after* the window's last
price snapshot — meaning the current design cannot observe the price response to the
resolution itself, for either event:
- Mineral rights (coded as the single day 2025-03-24): resolution settles at 17:21 PT, 21
  minutes past the 17:00 PT close snapshot that day; the next snapshot (03-25 05:00 PT) falls
  outside the coded window.
- Zelensky-suit (coded as 2025-06-30–07-08): resolution settles at 17:27 PT on the window's
  last day; the next snapshot (07-09 05:00 PT) is likewise outside the window.
This is a sharper, directly checkable version of the outline's existing "single discontinuity"
limitation, and doesn't require deciding whether to redraw either window — that judgment call
(and any change to `EVENTS` in `resolution_risk_event_study.py`) is left to whoever extends the
regression, not made here.
