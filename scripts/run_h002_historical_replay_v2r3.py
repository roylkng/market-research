from __future__ import annotations

from typing import Any

import run_h002_historical_replay_v2r2 as base

from marketlab.h002_historical_identity import historical_isins_equivalent
from marketlab.marketdata import MarketDataError

# Retained official NSE XBRL for this exact Coforge filing has:
#   Symbol=NUCLEUS
#   ISIN=INE591G01025
#   NameOfTheCompany=COFORGE LIMITED
# Discovery itself is correctly bound to COFORGE.  Constrain the compatibility
# exception to this one official source URL and quarter so NUCLEUS never becomes
# a discovery alias for Coforge.
_COFORGE_FY26_Q3_SOURCE = (
    "https://nsearchives.nseindia.com/corporate/xbrl/"
    "INTEGRATED_FILING_INDAS_1608772_22012026114610_WEB.xml"
)

_ORIGINAL_PROCESS_PAIR = base._process_pair
_ORIGINAL_SYMBOLS_EQUIVALENT = base.symbols_equivalent
_ORIGINAL_PARSE_UDIFF = base.parse_udiff_equity


def _coforge_source_defect_symbols_equivalent(
    canonical_symbol: str,
    observed_symbol: str,
) -> bool:
    canonical = canonical_symbol.strip().upper()
    observed = observed_symbol.strip().upper()
    if canonical == "COFORGE" and observed == "NUCLEUS":
        return True
    return _ORIGINAL_SYMBOLS_EQUIVALENT(canonical_symbol, observed_symbol)


def _persistent_udiff_with_registered_historical_isin(
    raw_zip: bytes,
    *,
    symbol: str,
    session_date: Any,
    series: str = "EQ",
    expected_isin: str | None = None,
):
    try:
        return _ORIGINAL_PARSE_UDIFF(
            raw_zip,
            symbol=symbol,
            session_date=session_date,
            series=series,
            expected_isin=expected_isin,
        )
    except MarketDataError as exc:
        if "ISIN mismatch" not in str(exc):
            raise
        parsed = _ORIGINAL_PARSE_UDIFF(
            raw_zip,
            symbol=symbol,
            session_date=session_date,
            series=series,
            expected_isin=None,
        )
        if not historical_isins_equivalent(symbol, expected_isin, parsed.isin):
            raise
        return parsed


def _process_pair_v3(**kwargs: Any) -> dict[str, Any]:
    member = kwargs["member"]
    quarter = kwargs["quarter"]
    pair = kwargs["pair"]

    patch_coforge = (
        member.symbol.upper() == "COFORGE"
        and quarter["id"] == "FY26-Q3"
        and pair.target.source_url == _COFORGE_FY26_Q3_SOURCE
    )
    patch_persistent = (
        member.symbol.upper() == "PERSISTENT" and quarter["id"] == "FY26-Q1"
    )

    previous_symbols = base.symbols_equivalent
    previous_parse = base.parse_udiff_equity
    if patch_coforge:
        base.symbols_equivalent = _coforge_source_defect_symbols_equivalent
    if patch_persistent:
        base.parse_udiff_equity = _persistent_udiff_with_registered_historical_isin

    try:
        try:
            return _ORIGINAL_PROCESS_PAIR(**kwargs)
        except base.PhaseAV2Error as exc:
            # TMPV is the post-restructure company.  A retained target filing that
            # still identifies TATAMOTORS is predecessor history, not an identity
            # acquisition failure and not a comparable H002 observation.
            if (
                member.symbol.upper() == "TMPV"
                and "target symbol mismatch: canonical=TMPV, observed=TATAMOTORS" in str(exc)
            ):
                return base._record(
                    member=member,
                    quarter=quarter,
                    status="SKIPPED",
                    reason="non_comparable_predecessor_target_after_corporate_restructure",
                    freeze_at_utc=kwargs["freeze_at_utc"],
                    pair=pair,
                    discovery_evidence=kwargs["discovery_evidence"],
                    action_evidence=kwargs["action_evidence"],
                )
            raise
    finally:
        base.symbols_equivalent = previous_symbols
        base.parse_udiff_equity = previous_parse


def main() -> None:
    base._process_pair = _process_pair_v3
    base.main()


if __name__ == "__main__":
    main()
