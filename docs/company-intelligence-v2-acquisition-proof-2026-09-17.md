# V2 original-document acquisition proof

Date: 2026-09-17. Research integration only. Live capital remains disabled.

## Measured change

The original PR #107 source-access rehearsal collected zero original documents.
Diagnostic run 35196712194 then located all five failures at robots.txt, before
any company document request. L&T's policy response was 404. TCS and Infosys
returned policy-stage 403. The NSE archive policy request timed out.

The transport now permits unavailable robots policies only for 404/410, following
RFC 9309 section 2.3.1.3. It retains blocks for authorization errors, rate limits,
unreachable policy and server failures. Document 404 remains a failure. A narrow
Disallow cannot be defeated by an earlier broad Allow. This conservative parser
may overblock exceptions and is not advertised as full RFC conformance.

Standard: https://www.rfc-editor.org/rfc/rfc9309.html

## Actual successful acquisition checkpoint

Code: 93d85bfd5a058f15326bc6733b52e1a721931e6c
Run: https://github.com/roylkng/market-research/actions/runs/35198939717
Artifact ID: 10487138067
Artifact SHA-256: 8662eb6ef4635a56fb237cfc0212915fb603b0e42ea5cf0e5d65d2bf1ddc0d58
Report cutoff: 2026-09-17T08:19:25.376381+00:00
Report SHA-256: 15efdfda0e4147a3b90640170875270305b825980f4de8ba4735cfc21135a974
Full repository CI at this code: https://github.com/roylkng/market-research/actions/runs/35198943824

Fresh store, zero reviewed imports, nine configured source attempts:

| Source | Outcome | Extracted facts |
|---|---|---:|
| L&T official FY2026 board report | Original HTML downloaded and parsed | 5 |
| Infosys Q1 FY2027 issuer release via PRNewswire | Original HTML downloaded and parsed | 6 |
| HCLTech Q1 FY2027 issuer release via PRNewswire | Original HTML downloaded and parsed | 4 |
| TCS current and prior releases | Policy-stage 403, second attempt uses host-failure cache | 0 |
| Infosys index and Indore release | Policy-stage 403, later attempt uses host-failure cache | 0 |
| HCLTech own website | Policy-stage timeout | 0 |
| NSE announcement feed | Policy-stage timeout | 0 |

The job deliberately exits nonzero because six source attempts remain blocked.
A successful partial extraction does not make overall source health green.
The panel contains 100 identities, but this run covers only three companies with
15 extracted facts. No complete company dossier, news window, market scan or
investment forecast is claimed.

## Economic meaning preserved

Infosys: Q1 revenue USD 5,082 million, CC revenue growth 2.4%, operating margin
21.1%, signed large-deal TCV USD 3.6 billion, and FY2027 growth guidance bounds
1.5% and 3.0%. The guidance belongs to March 2027, not the June 2026 quarter.
Bookings are not recognised revenue. Guidance is not independent consensus.
Source: https://www.prnewswire.com/news-releases/infosys-ai-revenues-at-8-2-in-q1-resilient-operating-margin-of-21-1-302833364.html

HCLTech: Q1 revenue USD 3.65 billion, advanced-AI revenue USD 171 million, new
bookings USD 2.4 billion and proposed AI data-centre capex up to INR 3,500 crore.
The investment is a plan disclosed July 13, not completed spending in Q1.
Source: https://www.prnewswire.com/news-releases/hcltech-delivers-robust-q1-led-by-record-deal-bookings-of-2-4-billion-302824103.html

L&T: standalone income INR 161,038.62 crore, PBT excluding exceptional items
INR 16,262.95 crore, PAT excluding exceptional items INR 13,129.81 crore, capex
INR 2,241.73 crore, and agreed metro disposal consideration INR 1,461.47 crore.
Consideration is not profit or received cash. Disposal status on September 17
has not been established by this annual-report snapshot. The board's signoff
is not represented as its public dissemination time.
Source: https://investors.larsentoubro.com/board-report.aspx

## Integrity and repeat collection

The downloaded artifact hash was independently verified. All 15 quoted spans
match retained normalized text, which was reproduced from original HTTP bytes.
Rebuilding the report from its stored records at the same cutoff reproduced it
exactly. Replaying unchanged source bytes preserved the original facts and
first-seen times and did not alter the earlier report.

Two live downloads of the issuer-distribution pages also showed changed HTML
wrapper bytes but identical normalized text. The subsequent collector repair
retains each document observation without creating another copy of an unchanged
same-source, same-period, same-basis, same-role value. Changed values remain new
evidence and do not silently replace earlier records. The earliest evidence
and its explicit expiry are preserved. Refresh policy and sustained unattended
operation remain separate production work.

These checks establish acquisition and replay behavior, not stock-prediction
accuracy. The source templates and economic hypotheses remain manually reviewed
pilot configurations. Automated broad discovery, issuer mapping at scale,
consensus, current valuation, prices, macro exposures and public-social collection
are still unfinished. No legacy H-series protocol, ledger or schedule is modified.
