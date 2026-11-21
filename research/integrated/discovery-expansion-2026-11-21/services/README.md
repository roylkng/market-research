# Services discovery expansion, 21 November 2026

| Completed decision | Official 20 November close | Five-year dividend-inclusive scenarios | Reconsideration conditions |
|---|---:|---:|---|
| NEWGEN, full integrated case | ₹413.55 | −7.1% / 8.3% / 18.9% | ₹325–350 if the business evidence does not deteriorate, or stronger growth and collection evidence near current price |
| NUCLEUS, compact treasury and recovery case | ₹611.45 | −11.3% / 7.8% / 23.7% | ₹475–500 with treasury protection, receivable reversal and margin stabilization |

The numbers are scenarios, not probabilities or price targets. Neither is an unconditional current-price buy. The original-source work explains why the apparent cheapness is incomplete and preserves the favorable counter-cases. The screen adds MPS, REDINGTON, EMUDHRA and INTELLECT as differentiated comparisons.

## Files

- `screening_log.md` and `screen_prices_2026-11-20.json` document actual breadth and original EQ/ISIN price matches.
- `newgen_case.md`, `newgen_inputs.json`, `newgen_outputs.json` and `newgen_calculator.py` hold the full case.
- `nucleus_cash_review.md`, `nucleus_inputs.json`, `nucleus_outputs.json` and `nucleus_calculator.py` hold the additional bounded case.
- `case_summary.json` is the compact parent/report handoff.
- `source_manifest.json` records original bytes, hashes, scope and inspection limits. Original-byte files are in the referenced evidence directory for packaging by the parent.
- `services_scenarios.svg` is a static visual of conditional modeled returns.

Run with Python 3 and no external packages:

```bash
python3 newgen_calculator.py
python3 nucleus_calculator.py
```

Keep both calculator files together. The NUCLEUS entry point uses the same funded cash engine, with different inputs and explicit cash-funded share awards. Outputs include every annual cash allocation, operating working-capital change, liquidity reserve, cash award/dilution treatment, treasury retention, funding gap, terminal valuation, IRR and entry-price sensitivity.

This folder is a new dated research increment. It does not alter earlier case decisions, frozen protocols, live-capital rules or schedules.
