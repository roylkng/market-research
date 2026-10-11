# HG007-P038: Historical full-market GF001 governance evidence for the 28 hidden gems

Freeze: **11 October 2026 IST**, before Monday's first H021 observation.
Classification: *archived source/governance facts only, not 11 Oct live facts or alpha*.

## Source routing correction

The H023 prospective mutual-fund ownership hypothesis has a
frozen 100-company U001 nonfinancial Nifty200 universe. All 28 HG002
candidate names were intentionally selected *outside U001*. H023
therefore does **NOT** certify HG002 promoter shares, mutual-fund
ownership or pledges.

A separate original **GF001-D002 full-market** NSE shareholding parser
had already verified 1,999 core-ready filings out of 2,050
latest-quarter source candidates, across a 2,319-company NSE census.
Original 4 October run:

- GF001 full ownership panel: run 37202941712, artifact 11303742567.
- GF001 original panel SHA256:
  dd338cd91f44396278300e27e8cdac1506dae11b63dd31ce827505fe62e8abe7.
- SS001 original source census: run 37198355430, artifact 11302177421.
- Original SS001 source census SHA256:
  214c1172491d58800dcded126303e7a2844967e75da57e0e6f666abc3b311293.

P038 reuses the original GitHub Actions artifacts and selectively
extracts the original XBRL source for the *28 HG002 names*. It does
not request new NSE data and does not substitute the H023 U001 source.

## Source verification and fields

The builder:

1. Git-blob-rechecks frozen HG002 28 names and frozen U001 100
   members. The intersection MUST remain zero.
2. Independently re-hashes the complete 2,319-identity GF001-D002
   full-market panel and verifies the signed SS001 source census.
3. Joins by **exact NSE symbol**, retaining the source report date
   and separately recorded NSE broadcast/availability timestamp.
4. Rejects an XBRL first broadcast after GF001's real historical
   capture timestamp, including any later information that was not
   observable in the original 4 October snapshot.
5. For each core-ready company, retrieves exact bytes from the
   original GF001 artifact, independently verifies the raw SHA256
   and reruns the existing GF001 original XBRL ownership parser.
6. Records promoter-group, public and MF percentages **only when
   the original XBRL parser produced exact usable facts**.
7. Keeps an absent MF context as *unknown/not represented*, not zero.
8. Keeps pledge/NDU/other encumbrance source flags as **booleans**,
   never invents the pledged-share number, security or collateral.
9. Leaves all unavailable/failed companies as explicitly missing
   or parser-failed, not cleared as low-risk.

Current Oct11 share count, options, latest pledge status, overall
promoter quality, governance score, intrinsic company valuation,
company-specific success probability and capital authorization
remain unverified by an Oct4 panel.

The INOXGREEN Sep29 exceptional QIP/pledge XBRL first broadcast on
8 Oct 2026 is separately source-reviewed in HG007-P013. A GF001
source snapshot from 4 Oct **cannot** silently incorporate that
newer filing, even though the exceptional filing's reporting date
was earlier.

## Reproduction and output

Code: src/marketlab/hg007_gf001_governance.py

CLI: scripts/build_hg007_gf001_governance.py

Tests: tests/test_hg007_gf001_governance.py

Workflow: .github/workflows/hg007-28-governance-gf001.yml

Immutable generated source packet:
research/hg007/outside-u001-governance-2026-10-04/28-original-governance-v1.json

Retained original selected XBRL bytes:
research/hg007/outside-u001-governance-2026-10-04/raw/sha256/

Artifact acquisition occurs on GitHub Actions using read-only access
to the user's **already existing** original full-market GF001 and
SS001 artifacts, rather than paying for another data source or making
2,319 new exchange requests.

These source archives have finite GitHub Actions retention. The
28-case source extract and underlying original selected XBRL files
are therefore explicitly committed to Git after passing all
cryptographic/identity checks.

## Investment significance and limits

A single historical pledge flag or MF ownership percentage is
context, not an independent company return forecast. This
pre-entry historical governance scan is **not a new trial**, not a
stock screener fitted to recent returns and not a revision to
HG002's mechanical selection.

Newer corporate filings, promoter pledge releases/increases,
share conversions, company net debt, post-QIP option counts
and legally completed transactions must still be independently
verified before any current-case underwriting or expected return.

**No stock recommendations, future returns, portfolio authorization,
live capital, or company-specific completion probabilities.**
