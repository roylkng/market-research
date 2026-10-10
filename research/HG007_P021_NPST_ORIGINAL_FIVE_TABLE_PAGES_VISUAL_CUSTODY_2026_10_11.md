# HG007-P021: Original NPST Financial/Reg32 Table-Layout Review Images

**Source visual custody only, not yet independent semantic approval.**
Frozen 11 October 2026 before any underlying source was reinterpreted
from images. All earlier issuer-source PDF bytes and page texts are pinned.

## Source motivation

HG007-P020 reconciled NPST Q1 FY27 and Reg32 original PDF text pages,
but the investor-presentation graphic on page 18 disagrees with the
two financial tables on pages 19–20:

- Graphic Q1 EBITDA: ₹18.78 crore; tables: ₹18.79 crore.
- Graphic net profit appears ₹11.04 crore; tables: ₹11.05 crore.

Both source tables do reconcile to Q1 total income/expenses while
the original Reg32 fundraising purposes are laid out across
continuation pages 2–3. Text extraction alone does not establish
complete column alignment, notes or issuer financial consistency.

## Exact original source pages

1. August 11, 2026 NPST investor presentation, original PDF
   SHA-256
   5afd8b272e7bd2f7f3fad549aa1270e4899e1d24c8d982268cab16a17bbe2225.
   - original page 18: bar-chart Q1 summary.
   - original page 19: Q1 consolidated key finance table.
   - original page 20: consolidated finance line-by-line table.
2. August 11, 2026 NPST June Reg32 source, original PDF SHA-256
   79010c968b0fe8359f685d27a203c891a8e35f684a73b86a67cf78ee46b54013.
   - original page 2: ₹300.0041cr purpose allocations and most uses.
   - original page 3: third purpose, ₹35.6409cr utilization total.

Exactly these five pages are rendered by the Poppler PDF rendering
tool into independent grayscale PNG source images, while refusing any
file not matched to the original Git/SHA-pinned P019 source custody.

The machine-readable manifest records for each page:

- independent original PDF SHA-256;
- original PDF page index and previous extracted-page-text SHA-256;
- complete rendered PNG SHA-256, dimensions and retained filename;
- all semantic approval, bank-cash availability, investment-return,
  valuation and portfolio flags FALSE.

No document is cropped/rearranged, and PDF originals are unchanged.

## Reproducibility

- Renderer: scripts/render_hg007_npst_original_tables.py
- Tests: tests/test_hg007_npst_original_visuals.py
- Workflow: .github/workflows/hg007-npst-source-visuals.yml
- Source images after merge:
  research/hg007/npst-aug2026-originals/june-source-financial-visuals/

Reproduce source-only images:

    python scripts/render_hg007_npst_original_tables.py \
      --output-dir /tmp/npst-original-source-review

## Mandatory separate audit

A reviewer must inspect all five original page images before resolving
the graphic-vs-table one-paisa-of-a-crore differences and before
claiming that all three Reg32 objects have been assigned to the
correct spending columns.

The source HTML/Reg32 statement confirms usage reporting, not
actual bank statements, equity proceeds net of cost or incremental
recurring EBITDA. No historical quarter-times-four figure is a
forward annual earnings estimate.

Next research still requires standalone/consolidated audited quarterly
financial-statement consistency, the monitoring agency June
report, current post-preferential fully diluted shares, QIP cash/credit
deployment, client concentrations, contract margins, receivables and
maintenance capital.

This is infrastructure and evidence transparency, **not** positive
stock upside or permission to trade.
