# HG007-P014: Correct Acuité Original HTML Envelope Without Relaxing Financial Identity

Date: 2026-10-10. Reconciles failed source acquisition
run 38071158750 after successful PR #350 / HG007-P013.

## Initial official source outcome

- The exact May 20 NSE issuer presentation was fetched over HTTPS.
- HTTP status: 200; original 34-page PDF passed issuer/date, 103.46,
  36.55, 66.92 and Winston text identity.
- Original captured PDF SHA-256:
  2a3c319d7965a0c3c8602b65b6375bf5af63c0689dd5455ad05478724901a2a7
- Original source size: 5,537,004 bytes.
- The exact official Acuité Oct8 credit-rating URL returned HTTP 200,
  but the old collector rejected it before parsing because it did
  not begin literally with an HTML DOCTYPE or html tag.
- As designed, neither partial source was promoted to the two-source
  complete path; original PDF remained in GitHub run artifacts,
  not falsely labeled retained in main.

## Correction

The Acuité credit-report website can deliver HTML with comments,
byte-order mark or server fragments before the root. Require HTML
element structure plus the **full exact original credit rating report
content**, rather than a literal first-byte prefix.

The accepted page must still pass all of:
- original unchanged exact HTTPS Acuité issuer/rating URL,
- HTTP 200 and bounded original response bytes,
- substantial HTML page text with DOM elements,
- correct DEV ACCELERATOR LIMITED original issuer,
- October 08, 2026 report identity,
- ACUITE BBB / Stable and credit instruments,
- 3.11 lease-including debt/EBITDA and 1.32 lease-excluding ratio,
- original references to lease liabilities and Ahmedabad exposure.

Redirects, wrong actual URL, login pages, unrelated issuers, fake
200 HTML and 401/403/429 are not accepted. Neither source promotes
any return multiple, original current NCD balance, stock recommendation,
selected investment or live capital.

The existing workflow will retry the missing two-source bundle because
no complete bundle was ever anchored. A successful source capture must
preserve original bytes, SHA and UTC times in Git; another failure
remains an observable gap, not assumed success.
