# SS002-P015: Polycab Original NCLAT Stay Evidence, Not a Buy Signal

Frozen infrastructure/review scope: **10 October 2026 IST**.

## Why this case matters

The repaired SS002-P001 original **9 October** daily NSE source
contains 579 announcements and 21 mechanically detected special-
situation category hints. One event, NSE announcement sequence
106813081 for POLYCAB, is categorized
INSOLVENCY_RESOLUTION.

The original attached 9 October four-page Polycab/NCLAT filing
cannot be reduced to a keyword matching insolvency.

Original source:
https://nsearchives.nseindia.com/corporate/POLYCAB_09102026194506_StockexchangeCIRP09102026.pdf

From its text as served by NSE:

- The NCLT Ahmedabad order on 7 October admitted a section 9
  corporate insolvency resolution proceeding against Polycab
  India Limited.
- The challenged claim from Asier Metals involved alleged
  operational debt of **approximately INR 2.79 crore**.
- Polycab reported that the NCLAT principal bench **stayed and
  kept the NCLT admission order in abeyance on 9 October**.
- The appellate tribunal's formal order required a stated amount
  to be deposited by FDR and stayed the impugned order until
  further orders.
- The appeal was listed for **26 October 2026**.
- No subsequent tribunal outcome or issuer legal status as of
  a later date has been inspected in this diagnostic.

Therefore an SS002 category of insolvency denotes **a source family,
not proof that the issuer is currently undergoing an unstayed CIRP**.
The reversal/stay, counterparty and chronology are central economic
facts; blindly dropping Polycab into a bankruptcy-list watch
could badly misclassify a major company.

## Source custody

The workflow is bound to the exact already published NSE October 9
source capture:

research/prospective/ss002-p001/2026-10-09-v1.json

Original Git blob:
4eb8390b76a48957e19c1d49689ad9009be9c65a

Original capture content SHA:
53158b6d5076bf3ede83cd2c4fc0c0678d6862ab4534cae24a64884729a424e0

Polycab original announcement identifier:
106813081

The exact original attachment URL, 21-candidate selection,
announcement row and no-alpha flags are required before any download.

The collector checks the **original PDF byte header/trailer, four
complete text pages, exact issuer identity, hearing date, disputed
debt and the text of the actual stay/abeyance ruling**. It retains
the original source's SHA-256, byte count and per-page text SHA-256.
An HTTP 403/401/429 is recorded without access bypass. A redirect
is not followed and a fake HTML-200 response is rejected.

A successful original document fetch is stored in
research/ss002-p015-polycab/raw/sha256/ and an immutable source
receipt, never as a speculative claim about current insolvency.
Failures remain only source-observation run artifacts.

## Future business-research gates

A later source reviewer must independently inspect original
page layout and other orders/docket entries to certify legal
case chronology. The 9 October order is **not a blanket statement
about the status after later hearings**.

The approximately INR 2.79 crore disputed claim is not necessarily
the listed issuer's total possible loss, and proportional size
does not prove legal or commercial immateriality. This is a legal
event requiring chronology, not an earnings catalyst by itself.

Before any stock-specific payoff or downside thesis:
- acquire the October 7 underlying admission order and related
  appeal documents;
- verify the appellate stay, conditions and further court orders;
- identify the exact parties and dispute/recovery basis;
- source the company's independently dated balance-sheet obligations;
- register ex-ante research hypotheses rather than analyzing future
  stock returns to cherry-pick successes.

This P015 work performs **source identity and custody only**.
No model probabilities, share-price response, economic-materiality
score, stock recommendation, portfolio eligibility or capital
authorization are made. Downstream SS002 semantic review remains pending.

## Reproduce offline

- scripts/probe_ss002_polycab_original_stay.py
- tests/test_ss002_polycab_stay_source.py
- .github/workflows/ss002-p015-polycab-original-stay.yml

Actual original NSE PDF bytes become a permanent original-source
artifact only after the successful post-merge collector run.
