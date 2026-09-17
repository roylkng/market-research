# Company intelligence v2: first acquisition evidence

## Observed automated result

The first source-access rehearsal on 2026-09-17, run 35186287613 at
commit d2c57f0a2812658c03a03301117aadcec7aa4d05, registered the real
100-name panel but acquired zero original documents. The TCS current/prior and
Infosys attempts encountered HTTP 403, L&T produced HTTPError, and the NSE RSS
attempt timed out. These are failures, not successful empty news windows.
The archive SHA-256 is
38eed90a7e07eb867927d1d824b4754fdf15a781328c738cf6989368028c31e0.

Run: https://github.com/roylkng/market-research/actions/runs/35186287613
Artifact ID: 10481773090.

## Reviewed-source integration

An additional reviewed-source import interface accepts short excerpts from
independently accessible rendered official pages. It explicitly retains
WEB_ASSISTED_EXCERPT, a hash of only the excerpts, null original-document hash,
actual import timestamps, source locators, semantic basis and reviewer identity.
It cannot turn a failed unattended collector into successful coverage, and cannot
backdate evidence. The reviewer is ChatGPT, not an independent human auditor.

The retained September 17 capture has three source excerpts and six claims for
TCS and L&T. It provides a real data integration case while preserving the
source-access problem. TCS reported-USD revenue arithmetic is +2.73548% year
over year. The 24.0% versus 24.5% margin comparison remains blocked because the
exceptional-item bases have not been reconciled. The AI run rate remains distinct
from incremental consolidated revenue. L&T's author/signoff date is not treated
as its publication date in the reviewed import.

Sources and brief audit excerpts are retained in:
research/company-intelligence-v2/reviewed-captures-2026-09-17.json.

After initializing a store, the reviewed import command is:

```bash
python scripts/import_company_research.py \
  --store .marketlab/company-intelligence-v2 \
  --capture research/company-intelligence-v2/reviewed-captures-2026-09-17.json \
  --output reports/company-intelligence-v2-reviewed
```

This replays retained research evidence, not a new live-source collection.
The observed local expanded suite has 67 passing tests, including checks that
reviewed excerpts cannot claim original bytes, complete coverage, a changed
number absent from the quoted text, or historical availability.

The complete local reviewed report, built on the downloaded real failed-run
store, is e86e4f4c5f23a4a19037c76bb17a108111741fef7cfdb943beaafde206852df5.
It retains all five failed source attempts alongside the six reviewed claims.
That report is an implementation case, not a validated company valuation,
complete 100-company research product or investment forecast.
