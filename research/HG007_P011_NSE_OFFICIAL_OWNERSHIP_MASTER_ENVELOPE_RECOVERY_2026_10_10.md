# HG007-P011: Preserve Official NSE Master Response Before Interpreting Ownership

Status: **SOURCE ENVELOPE DIAGNOSTIC AND RECOVERY**, outcome-blind,
10 October 2026. No company eligibility, trade or portfolio action.

## What the first official probe found

Source-only workflow run 38055404082 (10 October 2026) queried
INOXGREEN's exact NSE corporate-share-holdings-master endpoint.

It received an HTTP 200 payload that JSON-decoded to an OBJECT,
whereas the original H023-derived source selector expected a LIST.
The original P010 code failed closed with:

    NSE_MASTER_SOURCE_UNAVAILABLE
    TypeError: original NSE master must return a list, not error envelope

Therefore the initial source attempt did not verify **any** September
shareholding, pledged-share quantity, current option count or governance
change. P010 did **not** silently substitute Trendlyne or mark a
company as questionable solely from a secondary vendor.

However, the original version discarded even the 200 response bytes
when its structure was unexpected. This made it impossible to
distinguish an authentic NSE JSON data envelope from an NSE error
object with confidence.

## P011 changes

- Root arrays remain accepted under the existing dated-filing checks.
- Root objects are accepted **only** if they expose an explicit
  data or records ARRAY and contain no error/exception or failed
  status. The same strict report/broadcast/issuer identity, approved
  archive and ambiguous revision guards apply.
- Any other object, malformed data, future-dated or contradictory
  source remains blocked, not interpreted as zero company filings.
- The exact original master response from HTTP 200 is retained,
  SHA-256 addressable, with the JSON root type and top-level
  field names recorded, even when the parser cannot approve it.
- Raw NSE XBRL ownership files are fetched only after an accepted
  dated source is identified, and official issuer/share count and
  promoter-pledge boolean checks must pass before success is anchored.
- Original source and failure artifacts remain immutable and
  separately dated; a successful later probe does not retroactively
  pretend that the first failed probe was valid.

## Why this is important

This is a source protocol recovery, **not a scored alpha trial**.
It prevents a change in NSE API packaging from making a verified
special-date filing permanently invisible while retaining the
correct fail-closed behavior for denial or error JSON.

It does not bypass access controls or assert the third-party
29 September **4.9 million pledged shares** amount. Even if
the exact original XBRL eventually supports a YES pledge boolean,
P011 cannot infer pledge quantity from YES.

The certified issued share count and QIP capitalization correction
from P007-P009 remain unchanged. Current options, loan claims,
borrower/creditor priority, minority value and company-specific
transaction completion probability remain separate evidence gates.

To reproduce regression tests without contacting the exchange:

    pytest -q tests/test_hg007_ownership_source.py

The on-merge official source workflow from P010 is triggered by
these code changes and preserves a new independent HTTP response
receipt. Portfolio and live-capital permissions remain disabled.
