# HG007-P044: Separate INOXGREEN Reporting Date from Public-Disclosure Date

**Dated source reconciliation prepared 13 October 2026.**
No current full diluted enterprise value, price target, payoff probability,
trade or alpha test is authorized.

## Critical correction

P008, frozen earlier, described the following as a *hypothetical*
post-QIP diluted count based on the March 31 outstanding option balance:

    419,602,518 post-QIP issued equity shares
  +   2,467,620 March outstanding potential dilutive shares
  = 422,070,138 illustrative shares.

P040 has since retained and parsed the exact official NSE *exceptional
shareholding report as of 29 September 2026*, verifying:

- 419,602,518 issued/basic shares.
- **422,070,138 reported fully diluted shares.**
- Difference 2,467,620 source-reported potential additional diluted shares.
- 225,317,291 net reported promoter-group shares.
- 4,900,000 reported pledged promoter shares as of the report date.
- No net change in promoter-group share count versus 30 June.

The report's recorded **first-public broadcast is 8 October 2026,
13:24:47 UTC (18:54:47 IST)**. That is not the same as the underlying
29 September reporting date. The original P008 historical *hypothesis*
is not rewritten; P044 records the subsequently verified original
September source with separate temporal authority.

Original NSE XBRL source:
https://nsearchives.nseindia.com/corporate/xbrl/SHP_1734551_08102026065442_WEB.xml

Exact original XML SHA-256:
6c58845fa1b3f17c9c72b2466978bf8c69cece2436b1a92f7d40c4410f8b1822

Existing source-backed P040 first-public/shareholding reconciliation:
research/hg007/hg007-p040-net-promoter-share-reconciliation-v1.json

## Two dated reference prices, unequal information sets

The original P008 price observations were:

| NSE session | Official historical close | Sep29 filing first public before this close? | Reported Sep29 FD shares x historical price |
|---|---:|---|---:|
| **1 Oct 2026** | ₹159.00 | **NO** | ₹6,710.915 crore (retrospective illustration ONLY) |
| **9 Oct 2026** | ₹128.92 | **YES** | ₹5,441.328 crore (publicly available as-of Sep29 source, not revalidated 9 Oct count) |

The 1 October result cannot enter any contemporaneously knowable
selection/performance claim, because its diluted share-count source
was first disseminated on 8 October.

At the 9 October price, the September 29 filing *had been made public*,
but it does not prove that no new shares, option exercises or capital
transactions happened during 30 September–9 October. The report is
historically dated, not an independently certified current October 13
fully diluted capitalization.

P008's independently calculated **post-QIP basic** capitalization
remains ₹6,671.68 crore at the Oct 1 price and ₹5,409.52 crore
at the Oct 9 price. Do not replace those basic results with a new
full diluted label in P008's original artifact.

## Governance interpretation

The original September filing also reports 4.9 million pledged
promoter shares, first publicly visible on 8 October. P040 shows
that the 56.12% to 53.70% promoter percentage decline is explained
arithmetically by QIP denominator growth with unchanged **net** group
shares. This does not prove zero gross promoter sales/transfers nor
the pledge's origination date, loan covenants or current status.

The exact composition of the source's fully diluted aggregate
(warrants versus outstanding options versus other securities) is
not decomposed in P044 merely because the difference equals the
previous March figure.

## Implementation and restrictions

- Model: src/marketlab/hg007_fd_publication_gate.py
- CLI: scripts/reconcile_hg007_fd_publication.py
- Tests: tests/test_hg007_fd_publication_gate.py
- Workflow: .github/workflows/hg007-fd-publication-gate.yml
- Append-only source-time result:
  research/hg007/hg007-p044-inoxgreen-publication-safe-fd-v1.json

P044 re-parses the original XBRL aggregate basic and fully diluted
concepts using HG005's already frozen parser, validates original
P008/P040 Git blobs and checks NSE dissemination time against the
observed price session closes. No source prices are fetched again.

## Real missing underwriting gates

- As-of-October-13 current equity and employee-option count.
- Any post-September-29 share issues, exercises or share actions.
- Current QIP cash deployment and true consolidated net debt.
- Verified WWIL transfer completion, EBITDA/FCF and Authum
  intercompany funding/minority rights.
- Current bid/ask depth, broker execution costs and position capacity.
- Unbiased forward source-matched return evidence after actual
  outcome horizons and pre-registered multiple-test thresholds.

**No investment recommendation, predicted return, corporate
action adjustment, portfolio eligibility or live capital.**
