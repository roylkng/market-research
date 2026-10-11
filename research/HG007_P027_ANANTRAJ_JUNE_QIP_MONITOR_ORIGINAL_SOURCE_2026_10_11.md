# HG007 P027: ANANTRAJ June 2026 Original QIP Monitoring Report Custody

Source acquisition protocol prepared **11 October 2026 IST**. This
is an **original-exchange-document acquisition**, not an approval
of transferred cash, future demerger value or returns.

## Why this is the next important gap

HG007 P026 established from the full 48-page Anant Raj / Ashok
Cloud proposed scheme that the demerged undertaking may include
certain QIP-sourced cash, deposits, assets, and loans attributable
to its data-centre/cloud operations. The scheme does **not**
assign actual rupee values to all those transfers. Counting the
same QIP money once at ARL and again as Ashok Cloud equity would
create false upside.

Anant Raj filed on **8 August 2026** an Infomerics Valuation and
Rating Limited monitoring report for the QIP quarter ending
30 June 2026.

Exact original BSE attachment URL:

https://www.bseindia.com/xml-data/corpfiling/AttachLive/8d34184b-45a6-4317-b98d-02b4d60e7b25.pdf

A publicly accessible document transcription reports:

- QIP gross proceeds: **₹1,100 crore**.
- Related issue expenses: **₹27.80 crore**.
- Net issue proceeds: **₹1,072.20 crore**.
- Gross proceeds spent through 30 June: around **₹410.01 crore**.
- The monitoring agency reported no deviation from stated issue
  objectives in its report.

**These figures remain provisional until the retrieved original
pages and the object-by-object monitoring tables are verified.**
In particular, gross 1,100 minus gross proceeds usage 410.01 equals
689.99 crore, but it is invalid to call this amount free,
unencumbered ARL cash or eligible cloud assets. It must be
reconciled to earmarking, expenses, object categories, committed
but unspent project invoices, deposits, restricted investments
and legal demerger allocation.

The monitoring report explicitly disclaims that the monitoring
agency performs an independent audit of all issuer information.

## Safe source acquisition

Code: scripts/probe_hg007_anantraj_june_qip_monitor.py

Workflow:
.github/workflows/hg007-anantraj-qip-monitor-source.yml

Tests:
tests/test_hg007_anantraj_qip_monitor_source.py

The probe has exactly one approved original BSE PDF URL and
no alternate host, no redirected access, no cookie bypass.
It requires genuine PDF original bytes, plausible page
count, the Anant Raj issuer, Infomerics and the June quarter
identity. An HTTP 401/403/429 is logged as blocked, not
a completed source. Every true original is anchored once by
raw SHA-256 with HTTP status, time, original bytes and page
text hashes.

The PR tests are entirely synthetic and access no market
source. After successful merger, a GitHub Action makes the
first original source attempt. It saves access failures as
workflow artifacts. If acquired, bytes and provenance are
retained in:

research/hg007/anantraj-qip-monitor-june2026/

## Further analysis, separately gated

1. Extract **all original pages** and check the monitoring
   agency's object-wise cumulative and quarterly utilization,
   interest earned, deviations, audit certificate and any
   deployment at subsidiaries or related parties.
2. Verify exact as-of-30-June unused allocation by object,
   and independently compare to bank/deposit records and
   dated financial statements.
3. Join money-use objects to the 48-page demerger's clause
   1.13, non-dedicated debt and legal transfer-date rules;
   do **not** assume remaining QIP balances all move to
   Ashok Cloud or all remain at Anant Raj.
4. Obtain a pro-forma undertaking balance sheet with
   transferred liabilities and cash, and separately track
   minority holdings to avoid double counting.

This tool adds zero expected return, zero company completion
probability and zero portfolio/live-capital authority.
