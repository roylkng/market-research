from __future__ import annotations

from dataclasses import replace

from marketlab.events import FinancialEvent

# Deliberately narrow, evidence-backed equivalence. No fuzzy ticker matching.
# BAJAJ-AUTO appears as BAJAJAUTO in some official financial XBRL instances.
# LTIM changed its NSE trading symbol to LTM effective 27-Feb-2026.
# ZOMATO changed its NSE name/symbol to ETERNAL in Apr-2025 with the same ISIN
# INE758T01015. These groups are pure identity-preserving aliases. Membership in
# a group is symmetric so a point-in-time ticker can discover a filing published
# after a later rename, or vice versa. The dictionary key is also the stable
# research-cluster identity used across quarters.
_SYMBOL_EQUIVALENCE: dict[str, frozenset[str]] = {
    "BAJAJ-AUTO": frozenset({"BAJAJ-AUTO", "BAJAJAUTO"}),
    "ETERNAL": frozenset({"ETERNAL", "ZOMATO"}),
    "LTM": frozenset({"LTM", "LTIM"}),
}

# Retrieval-only aliases are not economic identity equivalence. They exist only
# because today's NSE discovery endpoint may stop answering a retired ticker even
# though it still returns that ticker's historical filings when queried through a
# successor/current endpoint. Candidate selection must still require the exact
# point-in-time filing ticker. In particular, TATAMOTORS and TMPV are NOT treated
# as comparable companies across the demerger/restructure.
_DISCOVERY_QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "TATAMOTORS": ("TMPV",),
}

# Exact official-source defects observed in retained NSE XBRL evidence. These are
# not aliases and must never broaden discovery. They only permit an already
# selected filing to remain attributable to its canonical company when the XBRL
# embeds a demonstrably wrong ticker but the company name and ISIN identify the
# canonical issuer exactly.
_KNOWN_FILING_SYMBOL_DEFECTS: frozenset[tuple[str, str, str, str]] = frozenset(
    {
        (
            "COFORGE",
            "NUCLEUS",
            "INE591G01025",
            "COFORGE LIMITED",
        ),
    }
)

# Exact historical ISIN inconsistencies observed across official NSE sources.
# These are source-record inconsistencies, not broad ISIN aliases. They are used
# only after an exact/registered ticker identity match. Separate corporate-action
# and baseline/target checks remain authoritative for economic share-basis
# comparability.
_HISTORICAL_ISIN_EQUIVALENCE: dict[str, frozenset[str]] = {
    "PERSISTENT": frozenset({"INE262H01016", "INE262H01021"}),
    # NSE July-2025 OBEROIRLTY financial XBRL transposes the leading 093 to 903;
    # older/current exchange security records use INE093I01010.
    "OBEROIRLTY": frozenset({"INE093I01010", "INE903I01010"}),
    # TATATECH 2025 financial XBRL uses ...01017 while contemporaneous NSE prior
    # intimation and bhavcopy identity use ...01025. No share-basis transformation
    # is inferred from this source inconsistency.
    "TATATECH": frozenset({"INE142M01017", "INE142M01025"}),
}

# This lineage is not a rename. TMPV emerged from the Tata Motors demerger/merger
# scheme, so predecessor TATAMOTORS EPS is not a valid same-company baseline or
# target for a TMPV historical replay.
_NON_COMPARABLE_PREDECESSORS: frozenset[tuple[str, str]] = frozenset(
    {
        ("TMPV", "TATAMOTORS"),
    }
)


def _registered_symbol_group(symbol: str) -> frozenset[str]:
    normalized = symbol.strip().upper()
    matches = [group for group in _SYMBOL_EQUIVALENCE.values() if normalized in group]
    if len(matches) > 1:
        raise ValueError(f"historical symbol alias belongs to multiple groups: {normalized}")
    return matches[0] if matches else frozenset({normalized})


def canonical_historical_symbol(symbol: str) -> str:
    """Return a stable company-cluster ticker for identity-preserving renames only."""

    normalized = symbol.strip().upper()
    matches = [
        canonical
        for canonical, group in _SYMBOL_EQUIVALENCE.items()
        if normalized in group
    ]
    if len(matches) > 1:
        raise ValueError(f"historical symbol alias belongs to multiple canonical groups: {normalized}")
    return matches[0] if matches else normalized


def historical_symbol_variants(canonical_symbol: str) -> tuple[str, ...]:
    """Return the ticker plus only explicitly registered identity-preserving aliases."""

    canonical = canonical_symbol.strip().upper()
    variants = _registered_symbol_group(canonical)
    return tuple(sorted(variants, key=lambda item: (item != canonical, item)))


def historical_discovery_query_symbols(point_in_time_symbol: str) -> tuple[str, ...]:
    """Return retrieval queries without widening economic identity equivalence."""

    symbol = point_in_time_symbol.strip().upper()
    ordered = list(historical_symbol_variants(symbol))
    for alias in _DISCOVERY_QUERY_ALIASES.get(symbol, ()):
        normalized = alias.strip().upper()
        if normalized not in ordered:
            ordered.append(normalized)
    return tuple(ordered)


def symbols_equivalent(canonical_symbol: str, observed_symbol: str) -> bool:
    canonical = canonical_symbol.strip().upper()
    observed = observed_symbol.strip().upper()
    if canonical == observed:
        return True
    return observed in _registered_symbol_group(canonical)


def filing_identity_matches(canonical_symbol: str, event: FinancialEvent) -> bool:
    """Accept exact aliases or a specifically registered official-XBRL defect."""

    canonical = canonical_symbol.strip().upper()
    if symbols_equivalent(canonical, event.symbol):
        return True
    identity = (
        canonical,
        event.symbol.strip().upper(),
        (event.isin or "").strip().upper(),
        " ".join(event.company_name.upper().split()),
    )
    return identity in _KNOWN_FILING_SYMBOL_DEFECTS


def historical_isins_equivalent(
    canonical_symbol: str,
    expected_isin: str | None,
    observed_isin: str | None,
) -> bool:
    """Compare exact ISINs, allowing only registered official-source inconsistencies."""

    expected = (expected_isin or "").strip().upper()
    observed = (observed_isin or "").strip().upper()
    if not expected or not observed:
        return expected == observed
    if expected == observed:
        return True
    registered = _HISTORICAL_ISIN_EQUIVALENCE.get(
        canonical_symbol.strip().upper(), frozenset()
    )
    return expected in registered and observed in registered


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
