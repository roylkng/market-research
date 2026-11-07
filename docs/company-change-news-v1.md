# CC001 P009: original-announcement reading, without invented economics

## Missing path addressed

The existing queue retained financial announcements but had no automatic reader
for its 6,404 non-financial announcement candidates. The new lane routes every
retained announcement into a disclosure family, then retrieves a bounded and
rotating selection of actual original attachments. It does not pretend that
routing the queue is equivalent to reading every attachment or verifying events.

The chain is:

    retained exchange response -> exact row -> issuer/security checks
        -> original attachment bytes -> original text -> quoted page windows
        -> semantic review -> economic interpretation -> valuation

The first six steps are implemented here. Semantic review is not auto-approved.
A stock-return predictor is not created from unreviewed keywords.

## Evidence and clocks

Each candidate is linked to the SHA-256 of its retained exchange response, row
index and full row hash. Discovery receipt hashes and original response hashes
are checked. Symbol, ISIN and attachment URL must agree with the queue identity.
An apparent historic/current ISIN difference is retained as an identity blocker,
not waived by matching company names. That condition is about security linkage,
not an allegation concerning the issuer.

The actual attachment is retained in the existing byte store before text parsing.
An exact issuer symbol, ISIN or full issuer name must also appear in its text.
This corroborates exchange linkage but is not legal identity verification. PDF
page markers and exact character offsets are retained for quoted passages.
Published time, first-seen time and attachment-reading time remain separate.
Evidence read today is not backdated into any existing experiment.

The exchange `voiceSummary` and `attchmntText` fields are NOT financial facts.
In particular, voice summaries are never sent into the extraction path. One
retained newspaper-summary row includes figures for multiple different issuers.
Reading such a summary as if every figure belonged to its headline company would
create a false financial record. Original attachments may also contain multiple
entities, so literal amounts stay unattributed until reviewed.

## What the output means

Disclosure families route attention: risk, orders, capacity, acquisitions,
financing, credit, capital return, governance, business updates, presentations,
routine filings and other disclosures. These are exchange-subject routing
categories, not learned stock-selection scores.

The reader extracts up to 30 local source windows containing economic terms.
Each window retains page, offsets and literal text. Stage words such as proposal,
approval, letter of intent, letter of award, agreement, commissioning and
completion are labelled MENTIONS, not affirmative verified events. Negations,
historical references and subsidiary/consortium boundaries still require reading.
Money literals are not assigned to issuer profit, normalized earnings, revenue,
cash, contract value or valuation. Currencies are not silently converted.

Every reading says UNREVIEWED, economic_event_verified=false and
live_capital_allowed=false. All financial effects remain unknown. An awarded
order does not prove revenue recognition or cash collection. No confidence score,
forecast probability or commercial data licence is inferred from a completed read.

## Selection and persistence

Selection rotates through disclosure families and distinct issuers rather than
hard-coding the earlier CONCOR/KRSNAA/UPL examples. Within a family, newer
announcements have priority. One older failed candidate may be retried before
new work. There are at most three attempts per code recipe. Successfully read
originals are not fetched again for the same recipe.

The new tables are `cc_news_readings` and `cc_news_attempts`. Source financial
extractions, reviews, the discovery queue and frozen H/AE/HG experiments are not
rewritten. A news attachment read does NOT decrement the old semantic-mapping
backlog or become an independently verified event.

Limits are explicit: 1..20 documents per invocation, four MiB per attachment,
12 MiB acquired per batch, and a storage-headroom check against the unchanged
active checkpoint cap. Excess or image-only attachments remain unresolved.
There is no OCR fallback that silently invents text, no model call and no API bill.
The existing provider adapter remains available elsewhere but is not configured
or invoked by this lane.

## Run

```bash
python -m marketlab.company_change_news \
  --workspace .marketlab/cc001 \
  --limit 4 \
  --output-prefix .marketlab/cc001-exports/news-inbox
```

The isolated live-source workflow restores a copy of the persisted state and
reads at most seven attachments across disclosure families. It cannot push state
or use model credentials. It retains exact code, original bytes and output for
replay. Completed reading is not independent semantic validation.

## Commercial boundary

This is an internal research component, not a licensed general-news wire or
multi-user recommendation service. A commercial launch still needs data-use
permissions, tenant isolation, provider configuration, service operations and
independently evaluated economic-event labels and investment performance.

Primary sources consulted:
- NSE corporate-announcement and original-XBRL publication pages.
- NSE corporate-filings disclaimer, which states submissions are disseminated
  without exchange verification of their adequacy, accuracy or veracity.
- SEBI circular dated 13 July 2023 on disclosure of material events. It is a
  historical source-format reference, not a statement of current legal compliance.

## Explicit assisted semantic review

`company_change_news_review` validates and admits an explicitly supplied review
package. An interpretation must reference the exact original URL, symbol, ISIN,
raw hash and text hash, with exact offset-bound quotations for event, stage and
economic actor. Missing evidence, wrong sources and additional forecast fields
are rejected. Atomic imports and deterministic identities make replay auditable.
The output retains who supplied the review and when. It is an assisted research
interpretation, not independently verified ground truth. No financial extraction,
source review, trading approval or frozen experiment is changed.

The four checked development cases are SEAMEC, Dhruv, Vikran and Prestige. They
were selected after inspecting their text and rendered original PDF pages. They
are seen development cases, not a blind evaluation set. The fixture is replayed
only in the read-only source smoke, not automatically applied to all new news.
Quoted source spans prevent fabricated evidence but do not themselves prove that
the interpretation is correct. Independent labels remain a separate requirement.

SEAMEC distinguishes an issuer-specific USD work award from consortium totals,
commencement and earnings. Dhruv separates incorporation from operations and
flags conflicting payment statements. Vikran distinguishes an outlook change
from a letter-grade downgrade. Prestige retains conflicting completion language
as UNRESOLVED instead of selecting the more optimistic sentence.

`review_packet` exports a provider-neutral evidence/schema packet. It does not
call a model, approve the response, send data externally or configure billing.
The running semantic path remains explicit assisted review until a provider and
its measured error rate are established.

The existing daily workflow now adds up to four announcement reads and persists
news-inbox.json/html. Its existing 40 financial-document batch, three-context
rotation, cadence and active storage cap remain unchanged. Partial news failures
are surfaced after checkpointing. Latest news status/hash are cleared on failure,
not populated from an older successful report.

The first live experiment planned twelve documents but reached its byte-budget
reserve after seven successful reads, so it correctly reported partial completion.
The reviewed smoke is explicitly seven documents. It does not enlarge the cap or
claim that the five deferred documents were read. It also connects SEAMEC to the
existing historical/price module without converting the award into forecast profit.
