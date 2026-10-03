# RR001 Protocol Amendment P1: Complete-Field Scoring

Status: FROZEN BEFORE RR001-v2 MATERIALIZATION  
Frozen: 2026-10-03  
RR001-v1 status: DIAGNOSTIC ONLY, NOT PROMOTED  
Outcome-bearing experiment: NO  
Live capital: DISABLED

## Trigger

RR001-v1 was materialized exactly under its frozen rules.

Opening the v1 artifact revealed a structural source-coverage fact:

- reliable forward revenue-growth rows: 95 / 100;
- reliable forward profit-growth rows: 0 / 100;
- reliable consensus target-upside rows: 0 / 100.

Therefore the frozen v1 mid/long composites did not contain the intended number
of independent components.

In particular, the v1 long score reduced to one populated component for the
95 analyst-covered names:

`forward revenue growth`

divided by the original three-component denominator.

That is a valid diagnostic of the frozen input contract, but it is not an
adequate research-priority heuristic and must not be promoted.

No post-2026-10-01 return outcome was opened in making this diagnosis.

## P1 correction

RR001-v2 may use only fields that are present at cohort scale in the already
sealed 2026-09-25 H021 capture.

### Short horizon

Unchanged from v1:

1. 20-session stock return minus Nifty 500 return;
2. distance from trailing 20-session high;
3. current turnover divided by prior-20 median turnover.

### Mid horizon

Equal-weight percentile average of:

1. 60-session stock return minus Nifty 500 return;
2. current forward revenue-growth forecast;
3. current annual forward EPS yield.

### Long horizon

Equal-weight percentile average of:

1. current forward revenue-growth forecast;
2. current annual forward EPS yield.

Forward EPS yield is:

`consensus annual EPS / 2026-10-01 close price`

and is eligible only when:

- H021 analyst count is at least 5;
- EPS currency is INR;
- current price is positive.

Negative consensus EPS is retained as a negative yield rather than converted to
missing.

For display only, positive EPS also produces:

`forward P/E = current price / consensus annual EPS`

## Removed score components

The following remain attached as context when available but have zero scoring
weight in RR001-v2:

- profit-growth estimate;
- consensus target upside.

They may return in a future radar version only after a separately frozen source
capture demonstrates adequate point-in-time coverage.

## Anti-tuning rule

This amendment is motivated solely by field coverage, not by which companies
ranked in RR001-v1.

No v1 company rank or subsequent return may determine v2 weights.

All v2 component weights remain equal.

## V1 preservation

The immutable v1 artifact is retained at:

`research/rr001/radar-2026-10-01-v1.json`

with radar SHA-256:

`d1e4d019c7fe100cf339a16e3fd79d2ffceef2f4093a7b941b091318d32ad9ef`

It is evidence of the rejected input-coverage design and is not deleted or
rewritten.

## Promotion boundary

RR001-v2 remains a research-attention queue only.

It is not a buy list, expected-return model, or PF001 eligibility rule.

## Materialized v2 result

The frozen P1 implementation was materialized from official NSE history through
2026-10-01 and the byte-verified H021 2026-09-25 capture.

Observed coverage:

- reliable forward revenue growth: 95 / 100;
- reliable INR annual EPS yield: 93 / 100;
- reliable profit-growth estimate: 0 / 100;
- reliable consensus target upside: 0 / 100.

Canonical v2 artifact:

`research/rr001/radar-2026-10-01-v2.json`

RR001-v2 radar SHA-256:

`371e978120e9ac2aeba1368cb00e2a82e9be6e42bfad80fde2834d9c433ac31c`

The materialization does not open future-return outcomes.
