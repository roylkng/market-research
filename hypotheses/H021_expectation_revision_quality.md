# H021: Forward expectation revision with quality confirmation

Status: **DESIGN / SOURCE-FEASIBILITY ONLY**
Created: 2026-09-11
Live capital: disabled

## Question

Do upward changes in point-in-time forward earnings expectations, when the underlying accounting quality is not deteriorating, predict subsequent 20- and 60-session excess returns in liquid Indian equities?

H021 is deliberately separate from price momentum and entry timing. Its primary signal may not use stock returns, moving averages, RSI, MACD, volume breakouts, support/resistance or H020 action states.

## Motivation

Earlier project evidence says raw accounting growth is insufficient. H009's medium-horizon accounting rank failed its frozen validation gate, while a separately frozen prior-60-session relative-momentum comparator was materially stronger. H013 subsequently produced a historical challenge pass using regime-aware risk-adjusted momentum. H020 now covers current entry timing.

The missing independent question is whether the market underreacts to **changes in forward expectations**, not merely to reported growth or current price momentum.

External design evidence available before H021 outcomes are opened:

- NSE corporate earnings reviews explicitly track consensus earnings revisions for well-covered Indian companies using IBES/LSEG data.
- Trendlyne documents current and historical consensus estimates and revision windows for Indian equities.
- Finance Research Letters, 2026, reports return predictability from analyst forecast-earnings-growth revisions in another Asian equity market. This motivates testing in India but is not evidence that H021 works in India.

## Architecture boundary

- H019: point-in-time accounting observations and quality inputs.
- H021: expectation-change stock-selection hypothesis.
- H013: independent price-momentum/regime hypothesis.
- H020: downstream entry-timing/execution hypothesis.

No H013 or H020 variable can enter the primary H021 score. A later ensemble is permitted only after each component has independent evidence.

## Stage A: source feasibility, no return outcomes

Before freezing a tradable H021 signal, prove that analyst-expectation data can be acquired reproducibly with historical or prospective timestamps.

Required fields at each observation timestamp:

- exchange symbol and stable company identity
- estimate horizon / fiscal period
- consensus EPS estimate
- consensus revenue estimate when available
- analyst count
- observation timestamp or conservative capture timestamp
- source identity and retained content hash where permitted
- comparable earlier estimate used to calculate a revision

Desirable fields, not required for Stage A:

- net-profit / EBIT / EBITDA consensus
- target price
- analyst recommendation breadth
- number of upward and downward individual revisions
- cash-flow and capex estimates

A source passes Stage A only if the observation can be reconstructed without using data published after the decision timestamp. A current webpage that shows a 30-day change but cannot establish what was knowable 30 days earlier is not automatically historical point-in-time evidence.

## Stage B: candidate primary signal

Stage B may be frozen only after Stage A establishes what data fields and history are genuinely available. The simplest candidate mechanism should be tested first:

`forward_eps_revision_30d = consensus_forward_eps_now / consensus_forward_eps_30d_ago - 1`

Primary direction:

- positive revision: candidate long signal
- zero/negative revision: no positive H021 signal

Do not add optimized weights before testing the simple revision signal.

Potential preregistered challengers, only if source coverage supports them:

1. 90-day EPS revision
2. revenue revision
3. revision breadth, using up/down analyst counts
4. revision acceleration, e.g. recent 30-day change versus the preceding 30-day change

Each challenger must be versioned and must not silently replace the primary result.

## Quality confirmation

H021 should test whether accounting quality improves the revision signal, but quality must be a separately reported guardrail/challenger rather than a hindsight-weighted mega-score.

Candidate point-in-time quality variables from H019 or equivalent audited sources:

- operating cash flow / PAT
- working-capital intensity and direction
- net debt / EBITDA or borrowing direction
- ROIC/ROCE direction where reconstructable without vendor leakage
- finance-cost burden
- exceptional / other-income dependence
- audit qualifications or material auditor issues

Missing quality data remains missing. It cannot be imputed as neutral or good.

## Valuation

Valuation is a separate challenger/guardrail. The primary revision test must first establish whether revision information has predictive value on its own.

Candidate valuation variables include forward P/E, EV/EBITDA and valuation relative to the company's own prior history or sector. Historical vendor values must be point-in-time. Current multiples must never be inserted into historical decisions.

## Universe and coverage

The primary universe must be defined independently from subsequent returns. Because analyst coverage is endogenous, H021 must explicitly report:

- number of covered companies per decision date
- analyst-count distribution
- market-cap and sector distribution
- excluded/no-coverage companies
- survivorship/lifecycle treatment

A minimum analyst-count rule, if used, must be fixed before opening returns. It cannot be increased after seeing noisy outcomes.

## Outcomes

Primary horizon: 60 completed NSE sessions.
Secondary horizon: 20 completed NSE sessions.

Report at least:

- raw return
- Nifty 500 excess return
- sector-relative excess return where a frozen sector mapping exists
- beat rate
- median and mean excess return
- maximum adverse excursion
- concentration of positive P&L
- turnover and implementation costs for any portfolio simulation

If H020 is later applied downstream, report H021-alone and H021+H020 separately. H020 may improve execution but cannot be used to rewrite a failed H021 selection result.

## Baselines

Compare H021 against:

- all eligible covered stocks
- raw reported earnings growth
- simple valuation where point-in-time data are available
- prior-60-session relative momentum
- H013 where its exact frozen data contract is available

Do not compare only against random selection.

## Validation

Historical validation is allowed only if genuine point-in-time revision history is sourced and retained. Otherwise H021 becomes prospective-only from the first frozen capture date.

Required safeguards:

- chronological train/design/validation separation
- no future consensus snapshots
- no current-constituent survivorship substitution
- corporate-action-safe price returns
- all failed variants retained
- no threshold tuning using Transrail, Genus, Arvind, WABAG, or other stocks already discussed during H020 design
- live capital remains disabled until independent validation and prospective evidence exist

## Decision rule for proceeding

Proceed beyond Stage A only if a reproducible expectation-revision source exists with enough timestamped cross-sectional coverage to evaluate the mechanism without fabricating historical snapshots.

If clean revision history is unavailable, do not scrape together narrative broker calls as a pseudo-consensus backtest. Start a prospective daily/weekly consensus snapshot ledger instead and wait for forward outcomes.
