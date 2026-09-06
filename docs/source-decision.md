# Source decision v1: Indian earnings filings

## Decision

For prospective H002 observations, the **National Stock Exchange of India (NSE) corporate filing is the primary source of record** when the issuer is NSE-listed and the filing is available there.

For modern results, use NSE **Integrated Filing - Financials**, including its Details/XBRL documents and exchange broadcast timestamps.

Issuer investor-relations pages and BSE disclosures are corroboration/fallback sources. A fallback must be recorded explicitly and must never silently replace missing NSE provenance.

## Discovery versus source of record

The collector may use an NSE web-facing JSON endpoint to discover filings and symbols. Discovery metadata is not itself the immutable source document.

The retained event record points to the original exchange filing/XBRL URL and preserves its raw content hash, exchange timestamps, and capture timestamp.

Third-party libraries may help discover endpoint shapes during development, but no third-party wrapper is treated as the source of record.

## Current NSE paths

Primary human-facing page:

`https://www.nseindia.com/companies-listing/corporate-integrated-filing?integratedType=integratedfilingfinancials`

Observed web-facing JSON path used by the NSE site:

`https://www.nseindia.com/api/integrated-filing-results`

Observed index/metadata paths used for universe construction:

- `https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20200`
- `https://www.nseindia.com/api/quote-equity?symbol=<SYMBOL>`

These are web-facing interfaces, not a contractual public API. They can change, require browser-style cookies/headers, throttle, or fail. The client therefore treats endpoint availability as an acquisition concern rather than a research assumption.

## Acquisition policy

For each event:

1. Record discovery response and its capture timestamp.
2. Select the original filing and preserve exchange broadcast/revision metadata.
3. Fetch and hash original Details/XBRL bytes.
4. Store source URL, content SHA-256, capture timestamp, parser version, and reporting basis.
5. Keep consolidated and standalone filings distinct.
6. Prefer consolidated results for H002 when both are available, as frozen by the future H002 signal specification.
7. A revised/corrected filing creates a new version linked to the original. It never overwrites it.

## Retry and failure behavior

- Retry transient network errors and HTTP 429/5xx with bounded exponential backoff.
- Refresh NSE session cookies once after 401/403 and retry.
- Do not retry permanent schema/validation failures indefinitely.
- If source capture cannot be completed, record `SOURCE_CAPTURE_FAILED`; do not infer values from news articles or current screeners.
- Corroboration from BSE/company IR may identify a missing source, but use of a fallback is explicit in provenance.

## Historical reconstruction

Older filings and historical news can be used to develop extraction and company-intelligence features. They are labelled `HISTORICAL_RECONSTRUCTION` and do not become prospective evidence.

A transcript published after the financial result is a later event. It cannot be attached to the result-time information set as though it were already public.

## Licensing and repository storage

Do not commit large/licensed raw market datasets by default. Store public small fixtures only when redistribution is appropriate. For larger source files, preserve URL, timestamp, hash, acquisition metadata, and local immutable storage instructions.
