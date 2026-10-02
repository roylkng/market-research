# RM001-SC002 Prospective Nifty Total Market Industry Capture v1

Status: FROZEN BEFORE FIRST PROSPECTIVE SOURCE ACCESS
Frozen: 2026-10-02
First observation date: 2026-10-05
Live capital: DISABLED

## Objective

Establish a clean point-in-time company-industry mapping for RM001 without
projecting today's classification backward.

SC002 is source/timing evidence only. It does not add an industry factor yet.

## Parent evidence

SC002 is authorized by:

- RM001-D015: failed broad source-feasibility diagnostic;
- RM001-D015-R1: failed Symbol+ISIN EQ-projection diagnostic;
- RM001-D015-R2: failed exact triplet diagnostic;
- RM001-D015-R3: PASS_DOCUMENTED_DUMMY_SEPARATION_SEMANTICS.

All failed parent statuses remain failed.

D015-R3 proved that ordinary tradable EQ constituents can be separated from
documented index-only dummy placeholders using exact same-snapshot Security File
correspondence.

## Sources

For decision session D, capture before 18:30 IST:

1. Nifty Total Market constituent file:
   https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv
2. NSE same-session Security File returned by the frozen
   `security_master_url(D)` contract.

Full raw bytes from both sources are retained.

## Exact correspondence

Normalize:

- Symbol = uppercase(trim(Symbol))
- ISIN = uppercase(trim(ISIN))
- Series = uppercase(trim(Series))

### Ordinary tradable EQ

A parent row is eligible only if:

- Series == EQ;
- Symbol does not start with literal DUMMY;
- exactly one Security File row matches the exact Symbol+ISIN+Series triplet.

Any ordinary EQ missing or ambiguity makes the whole session ineligible.

### Index-only dummy

A parent row may be excluded as an index-only dummy only if all are true:

- Series == EQ;
- Symbol starts with literal DUMMY;
- exact Symbol+ISIN+Series Security File match count == 0;
- same Symbol+ISIN Security File match count across all series == 0.

Dummy count is variable and is not frozen to the five rows observed in D015-R3.

A literal DUMMY row that exists as a security is not silently reclassified.
The session fails closed.

### Non-EQ source consistency

Every parent non-EQ row must also have exactly one exact Security File triplet.
These rows are audited but never enter the projected tradable-EQ industry
snapshot.

## Frozen session-quality gates

A capture is source-quality READY only if all are true:

- parent row count >= 700;
- ordinary non-dummy EQ row count >= 700;
- zero ordinary EQ missing;
- zero ordinary EQ ambiguity;
- every literal DUMMY EQ row satisfies the frozen dummy rule;
- every non-EQ parent row exact-matches uniquely;
- projected EQ row count equals unique Symbol+ISIN identity count;
- zero duplicate projected identities;
- zero Symbol -> multiple ISIN conflicts;
- zero ISIN -> multiple Symbol conflicts;
- projected Industry coverage = 100%;
- projected ISIN coverage = 100%;
- Company Name and Symbol are complete;
- distinct Industry labels are between 10 and 40 inclusive.

No fuzzy matching, company-name fallback, symbol-only fallback or ISIN-only
fallback is allowed.

## Timing gate

Frozen EOD cutoff:

18:30:00 Asia/Kolkata.

Actual timestamp after both HTTP requests complete is authoritative.

A session is `READY_BEFORE_CUTOFF` only when:

- semantic source-quality status is READY;
- actual capture timestamp <= 18:30 IST.

A delayed workflow is operational missingness. It must not be interpreted as
proof that the source itself was unavailable.

## Canonical evidence

Ledger:

`research/prospective/rm001-sc002/source-ledger.json`

Exact raw bytes:

`research/prospective/rm001-sc002/raw/<session>/`

Projected industry snapshots:

`research/prospective/rm001-sc002/snapshots/<session>-v1.json.gz`

Each snapshot is outcome-free and contains only exact tradable EQ
Symbol+ISIN+Industry+Company Name identities plus source hashes.

## Readiness gate

Three distinct READY_BEFORE_CUTOFF sessions are required before the next stage
may be designed.

Three ready sessions authorize only a separately frozen prospective RM001
industry-factor design.

They do not authorize:

- historical backfill;
- retroactive sector/industry exposure;
- return-label opening;
- risk-model refit;
- PO001 portfolio refit;
- live capital.

## Promotion

After >=3 clean sessions:

`AUTHORIZE_RM001_PROSPECTIVE_INDUSTRY_FACTOR_DESIGN`

The future factor design must consume only industry snapshots captured
prospectively under this protocol.
