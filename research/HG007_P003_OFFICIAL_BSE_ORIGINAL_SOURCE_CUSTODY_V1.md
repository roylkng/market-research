# HG007-P003: Original BSE Attachment Provenance Probe for INOXGREEN/WWIL

Status: **SOURCE BYTE ACQUISITION, NOT SEMANTIC FINANCIAL REVIEW**.
Created 10 October 2026 before any independent verification of the
original 7 October 2026 BSE WWIL/Vibhav funding PDF.

## Why

HG007-P002 describes a provisionally reported ₹550 crore payment and
₹250/₹200/₹100 crore proposed funding bridge, but this comes from a
third-party HTML transcription while the exact original BSE PDF endpoint
returned HTTP 403 during review.

The report cannot be marked original-source-audited based on an
unverified copy or newspaper headline. We need its actual bytes and
original filing pages before accepting financing documents, executed
BTA conditions, loan conversion rights or legal transfer confirmation.

## Fixed original source

Exact original exchange attachment, *never a substituted document*:

https://www.bseindia.com/xml-data/corpfiling/AttachLive/d3241df5-32e2-4476-8075-bb5ed130e697.pdf

The Python probe has a single hardcoded HTTPS URL and performs bounded
retries on network/server failures only. HTTP 401/403/429 is preserved
as a blocked source status and is **not bypassed**. Redirects are not
followed, and changed HTTP destinations are not accepted.

A successful HTTP 200 is NOT enough to infer a PDF. Minimal content
byte validation requires a PDF header, EOF marker, and bounded byte
size. These are a lightweight envelope check, **not** comprehensive
structural parsing or page semantic verification.

Every genuine candidate file is retained unchanged under its SHA-256.
The receipt records exact URL, UTC capture timestamp, HTTP status,
original byte count, SHA-256, and all review/capital flags false.

If acquisition fails, no original document is fabricated, no branch
push marks the source as verified, and the run retains the blocked
receipt as a GitHub Actions artifact.

## Workflow

- Probe: scripts/probe_hg007_bse_wwil_original.py
- Regression: tests/test_hg007_bse_source_probe.py
- Scheduled/manual: .github/workflows/hg007-wwil-original-bse-source.yml

The workflow makes scheduled attempts during 10–31 October 2026
while no successful original receipt exists, with a manual trigger
also available. Later years are inactive by date gate.

On a valid byte acquisition only, the workflow anchors:
- original exact PDF bytes under research/hg007/wwil-bse-original/original-raw/sha256/
- matching source receipt at research/hg007/wwil-bse-original/official-source-receipt-v1.json

It verifies content hash after copying and refuses concurrent source
or protocol mutation. No receipt or file may be overwritten after
successful anchoring.

Run manually on a checkout with source access:

    python scripts/probe_hg007_bse_wwil_original.py \
      --out-dir /tmp/hg007-wwil-source \
      --attempts 2 \
      --sleep-seconds 3

The output is explicitly either source bytes captured/unread or
unavailable/blocked. GitHub CI exercises only synthetic tests and
does not access the real PDF as part of the PR review.

## Mandatory next stage

Even if raw bytes are captured, a second independent reviewer must
inspect the original PDF pages and BTA annexures, record evidence page
numbers and a semantic audit, verify conditions precedent and
conversion pricing/classes, and reconcile target normalized EBITDA
and parent diluted-share economics.

This P003 source probe **does not** approve the third-party
transcription, alter HG005/HG006 valuation stages, or assign
probability-weighted returns. All stock recommendations, orders,
portfolio permissions and live capital remain disabled.
