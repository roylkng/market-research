# H004-HR001 manual challenge v1

Date: 2026-09-08
Status: **RECONSTRUCTED MANUAL CHALLENGE, NOT VALIDATION**
Live capital: **NO**

## Purpose

Challenge frozen H004-R001 against explosive movers from periods that were not used to design H004. This is intentionally small and incomplete. It is a falsification check before a broad point-in-time replay, not a success claim.

The H004 design set of 2026-08-31 through 2026-09-07 remains excluded.

## Challenge cases

### Entero Healthcare Solutions — HIT

Public information before the move:

- Q1 FY27 result published 2026-08-07.
- Consolidated revenue ₹1,940.5 crore, +38.23% YoY.
- Operating profit approximately +79% YoY.
- PAT ₹52.05 crore, +72.17% YoY.
- No exceptional item in the comparable quarter columns.
- Stock closed ₹1,242.70 on 2026-08-07 with essentially no result-day repricing.

H004 interpretation:

- Stage 1: `EARNINGS_INFLECTION` and `EXPECTATION_GAP`.
- On 2026-08-10 the stock gained 5.83% with roughly 1.41 million shares traded versus 46 thousand on the preceding session. This is consistent with an early Stage-2 recognition event.
- It subsequently closed ₹1,808.60 on 2026-08-28, approximately +37.5% from the 2026-08-10 close.

Sources:

- https://www.stockwatch.live/in/results/entero-healthcare-solutions-544122/2027/1
- https://in.investing.com/equities/entero-healthcare-solutions-historical-data

### Bodal Chemicals — HIT

Public information before the move:

- Strong Q1 FY27 earnings were available in early August.
- Revenue / total income rose roughly 56% YoY and PAT roughly tripled.
- The stock did not immediately reprice. It fell from ₹75.19 on 2026-08-05 to ₹68.98 on 2026-08-07 and remained around ₹67-69 through 2026-08-18.
- The first persistent recognition leg began on 2026-08-19 at ₹71.75, +4.29%, followed by repeated positive sessions.

H004 interpretation:

- Stage 1: earnings inflection with a very strong expectation gap.
- Stage 2: around 2026-08-19/20 rather than the later upper-circuit days.
- By 2026-08-31 the close was ₹118.89, well after the information-first watchlist should have existed.

Source:

- https://www.investing.com/equities/bodal-chemicals-ltd-historical-data

### Huhtamaki India — MISS BY PRE-MOMENTUM RULE

Observed pattern:

- Q2 CY2026 result was published 2026-07-21 and net sales rose about 23% YoY.
- The stock had already been appreciating materially before / into the result window.

H004 interpretation:

- This is not a valid pre-momentum success if the prior 5-day / 20-day thresholds are already breached at the decision timestamp.
- A momentum baseline may capture this class better.
- Do not relax H004 thresholds retrospectively to count the mover.

Sources:

- https://www.whalesbook.com/company/profile/consolidated/HUHTAMAKI
- https://ca.marketscreener.com/news/huhtamaki-india-limited-reports-earnings-results-for-the-second-quarter-and-six-months-ended-june-30-ce7f51d8d980f322

### Oriental Aromatics — MISS, NO QUALIFYING PUBLIC ANCHOR

Observed pattern:

- The stock made an explosive late-August move.
- On 2026-08-27 the exchanges sought clarification regarding abnormal price/volume behaviour.
- The company replied that there was no pending material information and that the price/volume movement was market-driven.

H004 interpretation:

- H004 should miss a move that has no qualifying public earnings, turnaround, or Grade-3/4 corporate catalyst precursor.
- This belongs in a separate price/flow anomaly engine once movement begins.

Sources:

- https://www.moneycontrol.com/company-notices/orientalaromaticsltd/notices/CAP/
- https://www.screener.in/company/500078/

### VTM — MISS, FUNDAMENTALS DID NOT QUALIFY

Observed pattern:

- Q1 FY27 revenue increased materially, but profit before tax declined versus the comparable period.
- The stock later accelerated sharply in late August.

H004 interpretation:

- No earnings-inflection anchor should be created merely from revenue growth when profit economics deteriorate.
- This is a correct information-first miss unless an independently timestamped Grade-3/4 catalyst is found.

### Sri Lotus Developers — OUTSIDE H004 PRIMARY CLASS

The large July move occurred in a newly listed / IPO context. IPO demand, listing mechanics, anchor-book behaviour and first-weeks price discovery need their own experiment. It should not be forced into H004.

## Preliminary falsification read

Using only the obvious >=25% weekly-mover cases in these small challenge windows and excluding the IPO/new-listing case, the manual classification is approximately:

- information-driven H004 catches: Entero, Bodal
- H004 misses / rejects: Huhtamaki, Oriental Aromatics, VTM

Naive count: 2/5 = 40%.

This **does not measure the frozen success gate** because:

1. the sample was selected from weekly winner lists rather than the full point-in-time universe,
2. H004's primary label is maximum forward 20-session return >=25%, not weekly return,
3. executability and exact decision timestamps are not yet reconstructed for every case,
4. false positives are absent from a winner-only sample.

Nevertheless, the challenge is important: if the broad replay produces recall near 40%, H004 fails its frozen >=50% recall gate.

## Research consequence

Do not weaken H004 to catch unexplained moves. Use two complementary engines:

1. **H004 information-first pre-momentum engine** for earnings/catalyst/turnaround-driven repricing.
2. **H005 anomaly-discovery candidate** for unexplained price/volume/flow dislocations after they begin, evaluated independently and without contaminating H004.

The broad H004 replay must now use the complete eligible universe, all Stage-1 signals including false positives, exact publication timestamps where available, and the frozen thresholds without further tuning.