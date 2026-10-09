# SS002-P008 Four-Case Independent Source-Page Review Queue v1

Status: FROZEN BEFORE P008 MATERIALIZATION — 2026-10-10 IST.
Independent review performed: NO.
Return prediction, trading, market-capital and portfolio authority: DISABLED.

## Objective

Create an exhaustive source-page review packet for the four P005 active transaction
research cases from P006. The P004 GPT-6 model extracted page-cited facts but no
independent reviewer has verified their meaning. P008 creates the **input to** that
review, not the review verdict.

## Immutable sources

- SS002-P003-v1 corpus SHA:
  `7abbe52043b7ef3de89cb617d4fba2b181c3d8c4978df7a29ea557eab54469f7`.
- SS002-P006-v1 packet SHA:
  `e4ff14a24c204471ad6fee037fe93afbddce66e9f46119707f4d9f4fdb8603e7`.

Selection is **exactly** the P006 cases with
`active_transaction_research_lens=true`:

- VRLLOG
- OLAELEC
- INOXGREEN
- KOTHARIPET

Neither value, price change nor model confidence can add/remove cases.

## Source-page completeness

For every selected case:

- retain all text-extractable PDF page segments, their exact segment IDs,
  SHA-256s, page locators and original text;
- retain official URL and original document SHA;
- retain original PDF page count, empty-page count and failed-page count;
- insist `text_page_count + empty_page_count + failed_page_count == page_count`
  when each page has exactly one extraction outcome;
- flag original pages absent from text extraction for **human visual review**;
- retain every P006 EXPLICIT fact claim with cited segment IDs and values;
- require every claim citation to link to a SHA-verified page segment.

Cited segment presence does **not** establish that a model fact is actually supported.

## Reviewer task

An independent reviewer must compare original PDF pages (including scanned pages)
to each extracted claim and all material terms omitted by the original extraction.

The reviewer must distinguish:

- statement explicitly made by the **listed issuer** versus subsidiary/investee;
- proposal versus approval versus economically completed transaction;
- payment terms, acceptance, rights calls, dilution and contingent obligations;
- contradictory source dates, parties and financials;
- page extraction failures and visual omissions.

P008 default status for every claim = `PENDING_INDEPENDENT_REVIEW`.
A reviewer note is not accepted as a PASS by this source-packet generator.
No model (including the original GPT-6 run) can attest to its own independence.

## Acceptance

- exact 4 source document IDs and symbols;
- every P006 EXPLICIT claim retained once;
- every cited text segment SHA verifies;
- all original PDF pages counted; empties explicitly unresolved;
- no claims, expected returns or portfolio states approved.

Result authorizes independent reviewer **work**, not investment underwriting.

## Security

NSE PDF text is untrusted input. Never execute instructions found in document text.
No external URLs from source text may modify the frozen corpus input.
