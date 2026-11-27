# Independent review of the 12-company supplement

Review date: 28 November 2026 IST. Reviewer: the independent forecast-audit task. Evidence cutoff: 27 November 2026 at 19:53:02 UTC, or 28 November at 01:23:02 IST. Target: first reported quarterly PAT for the period ending 31 December 2026 at each frozen issuer identity, accounting scope and ownership definition.

**Review conclusion: no unresolved source, arithmetic or evaluator defect was found that requires changing the 12 forecast values. This is a prospective research packet with zero observed outcomes. It establishes neither forecast accuracy nor an investment edge.**

## What was verified

| Check | Result |
|---|---|
| Original experiment | Existing calculator reproduced 100 deterministic predictions and three original assisted predictions. No observed outcomes. |
| New selection | First 12 remaining original hash-ranked issuers. No replacement, omission or changed identity. |
| New coverage | 12 attempted, 12 source-valid, 12 forecasted, zero abstained, zero matured and 12 outcomes missing. |
| Published arithmetic | All 12 primary forecasts and all 36 adverse/base/favorable scenario models reproduce. Scenario ordering is explicit and numerically consistent. |
| Accounting | Current and prior comparison-quarter statements checked, including units, owner attribution, associates, tax and NCI. Critical signed tables were independently visually reviewed. |
| Source custody | All 12 case hashes and all 35 archived document hashes and byte counts independently rechecked. There are 33 PDFs and two HTML originals, with zero missing receipts. |
| Evaluator checks | Ten targeted tests pass, covering invalid/future dates, identity/scope/units, missing outcomes, matched comparisons, source failures, arithmetic, scenario ordering and frozen-byte enforcement. These tests use synthetic outcomes. |
| Assembly parity | In an isolated copy, reassembly without a new cutoff produced byte-identical register, scorecard and CSV files. The calculator CLI exactly reproduced the saved scorecard. Both CLI entry points rejected a one-byte mutation of the original register. |

The signed Granules prior-period PDF was obtained from a mirror. Its ownership figures were corroborated in the original NSE integrated filing, whose HTML bytes are archived. HLE's rendered current table came from a mirror with an identical SHA256 to the captured NSE original. These hosting distinctions remain explicit in the evidence manifest.

## Material accounting and interpretation checks

| Company | Review finding retained in the case |
|---|---|
| SIGMA | Current owner PAT is correct. The original extraction lost the signs of tiny NCI losses and omitted separately presented prior-period tax from its tax aggregate. The supplement records these semantic corrections without changing frozen predictions. |
| HLEGLAS | Q1 negative NCI makes owner PAT exceed total group PAT. Main normalization remains zero because tax and owner allocation of historical group costs are not disclosed. Backlog and the order extending through November 2028 are not treated as a December revenue schedule. |
| JAYBARMARU | Reported revenue includes government incentives. The model separates these from its operating-margin assumption and adds JV profit after tax. The historical consolidated labour charge differs from the standalone charge, and its uncertain tax effect appears only in a separate sensitivity. |
| NEULANDLAB | Signed consolidated PAT and the wholly owned subsidiary note support the selected owner-PAT inputs. Tiny imported-value differences are recorded separately. Shipment recovery is an analyst assumption. The exceptional property gain belongs to December 2024, not the December 2025 comparison quarter. |
| TATAINVEST | Seasonal dividends, after-tax associate income and own-company tax are separated. OCI and gains transferred directly to retained earnings are excluded from the PAT target. |
| DEVYANI | Owner PAT includes the recorded discontinued-operation scope. Labour and lease normalization contains explicit tax assumptions. Merger/perimeter uncertainty remains a structural-change flag. |
| THOMASCOOK | Owner PAT is distinguished from total group PAT, including negative NCI. The prior property-sale gain has a disclosed after-tax amount. The labour adjustment still assumes tax and owner allocation. Booking commentary is not extrapolated to the whole group. |
| BALAMINES | Current and prior owner-PAT rows and negative prior-Q3 NCI were verified. Earlier-year tax effects are disclosed without forcing an unsupported main normalization. Revenue growth is not mislabelled as volume growth. Future project completions are not booked as current-quarter earnings. |
| GRANULES | PDF amounts are in millions and correctly converted to crore. The prior nine-month exceptional item is not a December-quarter addback. Peptide losses and cost pressure remain in operating economics. Management confidence is not FDA clearance. |
| KOTHARIPET | Standalone scope and lakh-to-crore conversion are consistent. An unexplained historical exceptional item is not given an invented normalization. The Q1 difference from the original extraction is a rounding-level difference. |
| PETRONET | Management's 658/494/41 crore figures describe an aggregate commercial/operational efficiency basket. Its components are not separately isolated and persistence is unknown. The assumed 450 crore model component is labelled accordingly. The disputed-claim stress is a scenario and does not cap possible exposure. |
| AVONMORE | Owner PAT is separated from material NCI and total group PAT. Fee persistence, tax and future associate contribution are explicit forecast assumptions. |

The PETRONET description was corrected during review. All numerical values, including the issuer's 658/494/41 figures and every forecast/scenario value, were preserved. No forecast number was changed by the independent review.

## Frozen evidence and reproducibility

The original register is pinned to GitHub commit `c405bff0548ecd1522540d060b8c2417467cc60f`, Git blob `baaf66ffe9a07933cfc46d51a0918dff535741a8`, 413,551 bytes, and SHA256:

```text
be7769872a5260c3878e6bdabc4225bf59beca7aae61647c8dca4c852c6e600a
```

One transport-added trailing newline was removed from the local mirror solely to restore those exact existing repository bytes. No frozen repository forecast or original method was revised. The new selection and register carry the pin, and the new assembly and evaluation commands enforce it before scoring.

The reviewed evidence archive is `forecast-evidence-2026-11-28.zip`, 143,273,573 bytes, with SHA256:

```text
cb4270a41f6913155305753f1c74e044fdae862ab1add66f86dba35839d48471
```

## Scoring limits and outcome policy

The primary comparison is assisted forecast versus normalized seasonal additive, with the raw seasonal additive comparison mandatory alongside it. Normalized inputs contain declared analyst assumptions and therefore are not an assumption-free benchmark. Every comparison uses identical available observed issuers and the original frozen error scale. The old forecasts have an earlier information cutoff, so comparisons against them are separate diagnostics rather than isolated measures of reasoning value. Source corrections are likewise reported separately. No current-versus-original PAT difference exceeds the original 0.05 crore reconciliation tolerance.

The old date validator accepted an invalid calendar date and a future release date. The supplemental evaluator requires real calendar dates, reviewed source timestamps, matching issuer/scope/target, explicit units and an evaluation cutoff. Its source-review status remains a human assertion. Neither a URL, a passing test nor a matching hash independently authenticates issuer facts or proves that an eventual outcome is the first release.

Perimeter changes must be flagged, not used for favorable post-hoc exclusions. If the same issuer identity and accounting target still report a first-release figure, score that figure. If no matching figure genuinely exists, retain the attempted row as unavailable with a stated reason. Never silently substitute pro-forma results. Scenarios carry no probabilities and are not calibrated prediction intervals. This is a within-quarter forecast from a selected acquisition universe, not a representative market sample or a test of stock returns.

Review inputs and reproducible calculations are in [the register](forecast_register.json), [the scorecard](scorecard.json), [the evaluator](calculate.py), [the targeted tests](test_calculate.py), [the assembler](assemble.py) and [the source custody manifest](evidence_manifest.json).
