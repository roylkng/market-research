# H003 source coverage v1

## Objective

H003 asks whether prior management delivery credibility predicts future returns. Before extracting or scoring claims, the source corpus must be complete enough that the feature measures management delivery rather than which companies happened to receive manual research attention.

The frozen source contract is `H003-C001` in `registry/h003_source_rule.yaml`.

This contract does not change the H003 feature formula. The feature remains `MET / (MET + PARTIAL + MISSED + LATE)` with at least three resolved claims required. H003 remains independent from H002 and live capital remains disabled.

## Point-in-time boundary

The H003 source cutoff is bound to the exact frozen U001 timestamp:

`2026-09-06T12:21:06.431463Z`

Announcement inclusion is determined from the official NSE exchange publication timestamp, not from the date the source was reconstructed. An attachment published later on 6-Sep-2026 is therefore excluded even though its calendar date matches the cohort decision date.

The source window begins 1-Sep-2024.

## Source of record

Coverage uses symbol-scoped NSE Corporate Announcements discovery and original NSE archive attachments. Exact discovery response bytes are retained and hashed.

A completeness probe compared a single two-year response with the union of four six-month windows for INFY, RELIANCE, LT and HINDUNILVR. The full and sliced sets matched exactly for all four, including INFY's 490 announcement rows. This provides evidence that the symbol-scoped two-year response was not silently truncated for these high-volume representative histories.

## Transcript classification

The first prototype incorrectly required metadata to contain phrases such as `earnings call` or `financial results`. NSE frequently labels genuine quarterly call transcripts more generically:

- description: `Analysts/Institutional Investor Meet/Con. Call Updates`
- attachment text: `<issuer> has informed the Exchange about Transcript`
- attachment filename: issuer-specific transcript PDF

That brittle filter falsely classified companies such as HCLTECH, LT, MARUTI and HINDALCO as having zero sources despite approximately eight to nine official transcripts each.

The frozen v1 rule therefore classifies a source as a `MANAGEMENT_CALL_TRANSCRIPT` when it contains a transcript attachment and either uses NSE's official analyst/institutional-investor/conference-call update category or contains an explicit earnings/results-call marker. AGM transcripts, investor-day/AI-day material, investor presentations, meeting schedules and one-on-one notices are excluded.

This is a coverage correction made before claim extraction and before H003 forward outcomes. It is not a return-driven factor change.

## Final measured coverage

The final 100-company scan completed with no acquisition or classification failures:

- frozen U001 members: 100
- companies with one or more qualifying transcripts: 97
- companies with zero qualifying transcripts: 3
- companies with at least 3 transcripts: 93
- companies with at least 6 transcripts: 92
- qualifying management-call transcript sources: 794
- incomplete source-coverage records: 0

The three complete-zero-source companies are BHEL, ITC and TRENT. They remain in the cohort denominator. Source availability is not used as an excuse to substitute issuer websites or add a discretionary alternate source after seeing the company.

Final source-coverage bundle SHA-256:

`583af88b3c070e15fe94a7782962c9e1fb1ce167e1412a08fd5c7b2f2dcaf7ee`

H003-C001 SHA-256:

`a48e9cd1e1d56b69429696168fb1a2097b288d3179c7830ac79cbd8582835f0e`

The final scan was anchored by GitHub Actions run `34051346751` on 6-Sep-2026. The exact discovery-byte artifact is `9994668607`, with artifact digest `sha256:ab282da63d86c572fd9fca755cc1e60c5f886640486e088d486d6b8df9cc43ec`.

## Claim-extraction gate

Source coverage is necessary but not sufficient for an H003 score.

The next stage must preserve every generated claim candidate and assign an explicit `ACCEPTED` or `REJECTED` disposition. Accepted claims must be genuine future management commitments with a measurable metric or explicit deadline. Outcome resolution may use only evidence available by the same point-in-time cutoff. Post-decision price returns are forbidden from claim review.

A company cannot receive a numeric H003 credibility score merely because it has three transcript files. It still needs at least three accepted and resolved claims under the frozen H003 feature rule.
