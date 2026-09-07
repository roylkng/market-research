from __future__ import annotations

from dataclasses import replace

from marketlab.events import FinancialEvent

# Deliberately narrow, evidence-backed equivalence. No fuzzy ticker matching.
# BAJAJ-AUTO appears as BAJAJAUTO in some official financial XBRL instances.
# LTIM changed its NSE trading symbol to LTM effective 27-Feb-2026.
# ZOMATO changed its NSE name/symbol to ETERNAL in Apr-2025 with the same ISIN
# INE758T01015. This is a rename, not a change in the economic company.
_SYMBOL_EQUIVALENCE: dict[str, frozenset[str]] = {
    "BAJAJ-AUTO": frozenset({"BAJAJ-AUTO", "BAJAJAUTO"}),
    "ETERNAL": frozenset({"ETERNAL", "ZOMATO"}),
    "LTM": frozenset({"LTM", "LTIM"}),
}

# This lineage is not a rename. TMPV emerged from the Tata Motors demerger/merger
# scheme, so predecessor TATAMOTORS EPS is not a valid same-company baseline.
_NON_COMPARABLE_PREDECESSORS: frozenset[tuple[str, str]] = frozenset(
    {
        ("TMPV", "TATAMOTORS"),
    }
)


def symbols_equivalent(canonical_symbol: str, observed_symbol: str) -> bool:
    canonical = canonical_symbol.strip().upper()
    observed = observed_symbol.strip().upper()
    if canonical == observed:
        return True
    return observed in _SYMBOL_EQUIVALENCE.get(canonical, frozenset())


def is_non_comparable_predecessor(
    canonical_symbol: str,
    observed_baseline_symbol: str,
) -> bool:
    return (
        canonical_symbol.strip().upper(),
        observed_baseline_symbol.strip().upper(),
    ) in _NON_COMPARABLE_PREDECESSORS


def normalize_symbol_for_h002(
    event: FinancialEvent,
    *,
    canonical_symbol: str,
) -> FinancialEvent:
    """Return a calculation-only symbol-normalized view of retained evidence."""

    return replace(event, symbol=canonical_symbol.strip().upper())
