# Evidence package for the 18 November discovery review

Start with the [session synthesis](../discovery-upgrade-2026-11-18.md) and [current decision register](decision_register.json). The company subdirectories retain complete notes, source receipts, calculations and explicit limitations. This package contains two completed company underwritings and three bounded additional reviews, not five fully certified investment recommendations.

## Reproduction

- `datamatics/calculate.py` reproduces its inputs and valuation outputs with Python's standard library.
- `cmsinfo/calculate_cmsinfo.py` reproduces the historical cash bridge and reverse cash requirements.
- `replay/audit_hg009_h20.py --repo /path/to/repository --output /path/to/separate/output` reproduces the frozen H20 source-price diagnostic. Use repository source commit `1e27acfa719ee3ff4615f8c105eaa0ae870420bf` or the original input subset in the user evidence bundle. It does not write original ledgers.
- `breadth/reproduce_breadth_review.py` verifies the hashes of the pinned financial export and the dated NSE ZIP before routing 196 issuers. Exact commands and the financial export URL are in `breadth/README.md`. Apply `primary_review_overrides.json` before considering company-specific cash figures.
- Cosmo, GESHIP and Sandesh JSON files contain their source inputs, assumptions, intermediate cash/debt/NAV calculations and scenario results. Cosmo's independent review contains a separately recalculated arithmetic record.

The user evidence ZIP contains the immutable financial export, dated price ZIP, and the original archived market-input subset needed for the H20 reproduction. Original issuer annual reports are linked and their downloaded bytes hashed in company manifests, but the large PDFs are not duplicated in this research PR. A hash is custody evidence, not approval of financial meaning.

## Boundaries

Raw historical price changes are not economic returns. Current scenario values are not predictions or floors. The user's required return and portfolio weights remain unspecified. Original decisions, experiment definitions, source ledgers and live-capital restrictions are preserved. No order, new data service or schedule change is included.

The delivery record in the accompanying user bundle records the actual remote commit, PR and daily-watch update. An open research branch is not a main-branch merge.
