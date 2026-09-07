from __future__ import annotations

from datetime import date, datetime
from typing import Any

import run_h002_historical_v2_phase_b_shard as base

from marketlab.h002_historical_identity import historical_symbol_variants
from marketlab.marketdata import MarketDataMissingRow

_COFORGE_FY26_Q3_SOURCE = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "INTEGRATED_FILING_INDAS_1608772_22012026114610_WEB.xml"
)
_LTM_SYMBOL_CHANGE_DATE = date(2026, 2, 27)

_ORIGINAL_TRADING_SYMBOL = base._trading_symbol
_ORIGINAL_PARSE_HISTORICAL_EQUITY = base._parse_historical_equity


def _publication_day(record: dict[str, Any]) -> date | None:
    target = record.get("target_event")
    if not isinstance(target, dict):
        return None
    provenance = target.get("provenance")
    if not isinstance(provenance, dict):
        return None
    value = provenance.get("exchange_published_at_utc")
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _point_in_time_trading_symbol(record: dict[str, Any], member: Any) -> str:
    canonical = member.symbol.strip().upper()
    candidate = record.get("target_candidate")
    observed = ""
    source_url = ""
    if isinstance(candidate, dict):
        observed = str(candidate.get("symbol") or "").strip().upper()
        source_url = str(candidate.get("source_url") or "")

    # Exact retained NSE XBRL defect. The issuer name and ISIN identify Coforge,
    # while the filing's Symbol field incorrectly says NUCLEUS. Never expose
    # NUCLEUS as a Coforge market-data alias.
    if canonical == "COFORGE" and observed == "NUCLEUS" and source_url == _COFORGE_FY26_Q3_SOURCE:
        return "COFORGE"

    # LTM was LTIM on NSE before the evidence-backed 27-Feb-2026 symbol change.
    # Resolve by publication date before any outcome price lookup.
    if canonical == "LTM":
        publication_day = _publication_day(record)
        if publication_day is not None and publication_day < _LTM_SYMBOL_CHANGE_DATE:
            return "LTIM"
        return "LTM"

    # BAJAJAUTO appears in some filing metadata, but the exchange trading symbol
    # is BAJAJ-AUTO. This exact spelling pair is already registered as equivalent.
    if canonical == "BAJAJ-AUTO" and observed == "BAJAJAUTO":
        return "BAJAJ-AUTO"

    return _ORIGINAL_TRADING_SYMBOL(record, member)


def _parse_with_registered_alias_fallback(
    raw_zip: bytes,
    *,
    canonical_symbol: str,
    trading_symbol: str,
    session_date: date,
    series: str,
    expected_isin: str | None,
):
    try:
        return _ORIGINAL_PARSE_HISTORICAL_EQUITY(
            raw_zip,
            canonical_symbol=canonical_symbol,
            trading_symbol=trading_symbol,
            session_date=session_date,
            series=series,
            expected_isin=expected_isin,
        )
    except MarketDataMissingRow as first_error:
        # Fallback is restricted to explicitly registered symbol equivalence.
        # Every successful row still has to pass the frozen ISIN check inside the
        # original parser, so this cannot drift into fuzzy ticker matching.
        for variant in historical_symbol_variants(canonical_symbol):
            if variant == trading_symbol:
                continue
            try:
                return _ORIGINAL_PARSE_HISTORICAL_EQUITY(
                    raw_zip,
                    canonical_symbol=canonical_symbol,
                    trading_symbol=variant,
                    session_date=session_date,
                    series=series,
                    expected_isin=expected_isin,
                )
            except MarketDataMissingRow:
                continue
        raise first_error


def main() -> None:
    base._trading_symbol = _point_in_time_trading_symbol
    base._parse_historical_equity = _parse_with_registered_alias_fallback
    base.main()


if __name__ == "__main__":
    main()
