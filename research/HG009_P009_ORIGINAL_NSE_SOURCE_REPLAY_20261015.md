# HG009 P009: independent archived NSE FY26 issuer filing attestation

**Method:** independent raw-byte replay of earliest valid original NSE financial source receipts from P008. **Registration:** 15 October 2026, after original retrievals on 14 October. This is not a forward investment-signal preregistration.

The P008 source collection originally quarantined three NSE HTTP200 documents because cash-flow labels contain embedded newlines. The corrected parser matched nine reported FY26 consolidated statement fields in the original response. P009 creates a separate immutable **source-verification proof** of those archived originals, anchored to *the first successful* receipt for each issuer, not a later cherry-picked fetch.

| Issuer | First successful attempt | Original uncompressed HTML SHA-256 |
|---|---|---|
| ACUTAAS | 38617239523-1 | d2051e30328859b10f5e40a3161dd69ecbdfdce59f9cd73d8fd2e126a1149b57 |
| ACE | 38617239523-1 | 6e58fccb3104932bd45f5311cd5ff47ad59e47547066e2217e9b12fc68c05f72 |
| TRAVELFOOD | 38617239523-1 | 0c7173926ba43378626ce876ef417a7ea210a18fa731ab5d4b33f4d63b5dd2a9 |

Each attestation replays nine reported financial fields: pretax profit, operating CFO, PPE purchases, financing lease principal, financing interest paid, cash/equivalents, financial borrowing, current investments, and noncontrolling equity. It preserves actual first successful original-source retrieval UTC, exact byte count, SHA-256 and receipt SHA.

**Important epistemic boundary:** matching textual statement rows inside an NSE filing does **not** establish that the FY26 CFO-minus-PPE proxy is normalized, sustainable or wholly attributable to parent shareholders. It also does not establish current diluted share count, exact source column accounting regime for every possible section, future cashflow, executable stock purchase, or any positive expected return. All 10 dossier-level valuations remain ineligible, and live capital remains prohibited.

Adversarial tests attempt receipt-time modification, issuer substitution, and original file cash-amount tampering. These must fail closed. This P009 evidence does not update the October 14 P008 frozen company packet in place, and does not create T012 predictions or HG009 price returns.

Reproduce with:

    python scripts/materialize_hg009_p009.py --check
    pytest -q tests/test_hg009_p009_attestation.py

The signed result lives at research/hg009/hg009-p009-original-fy26-attestation-v1.json.
