from __future__ import annotations

import pytest

from marketlab.h003_deadlines import canonicalize_target_deadline


@pytest.mark.parametrize(
    ("raw", "source", "expected"),
    [
        ("FY26", "2025-07-10", "2026-03-31"),
        ("FY27 year-end", "2026-05-01", "2027-03-31"),
        ("end of FY25", "2024-08-01", "2025-03-31"),
        ("FY2025-26 year-end", "2025-06-01", "2026-03-31"),
        ("Q3 FY26", "2025-08-01", "2025-12-31"),
        ("2030", "2025-01-01", "2030-12-31"),
        ("end of 2025", "2025-01-01", "2025-12-31"),
        ("end of calendar 2026", "2025-01-01", "2026-12-31"),
        ("December 2026", "2025-01-01", "2026-12-31"),
        ("end of March 2028", "2025-01-01", "2028-03-31"),
        ("2026-06", "2025-01-01", "2026-06-30"),
        ("September 2025", "2025-01-01", "2025-09-30"),
        ("end of next calendar year", "2025-06-01", "2026-12-31"),
        ("end of this year", "2025-06-01", "2025-12-31"),
        ("end of current fiscal year", "2025-06-01", "2026-03-31"),
        ("current financial year-end", "2026-02-01", "2026-03-31"),
        ("December", "2025-06-01", "2025-12-31"),
        ("end of June", "2025-07-01", "2026-06-30"),
        ("1 April", "2025-04-02", "2026-04-01"),
        ("June of current year", "2025-02-01", "2025-06-30"),
        ("2026-04-30", "2025-01-01", "2026-04-30"),
    ],
)
def test_deterministic_deadline_forms(raw: str, source: str, expected: str) -> None:
    resolution = canonicalize_target_deadline(raw, source)
    assert resolution.canonical_deadline == expected
    assert not resolution.status.startswith("DEFERRED_")


@pytest.mark.parametrize("raw", ["year-end", "mid-2027", "sometime next cycle"])
def test_ambiguous_deadlines_fail_closed(raw: str) -> None:
    resolution = canonicalize_target_deadline(raw, "2025-05-01")
    assert resolution.canonical_deadline is None
    assert resolution.status.startswith("DEFERRED_")


def test_past_interpretation_is_not_silently_rewritten() -> None:
    resolution = canonicalize_target_deadline("December 2024", "2025-01-15")
    assert resolution.canonical_deadline is None
    assert resolution.status == "DEFERRED_PAST"


def test_none_is_preserved() -> None:
    resolution = canonicalize_target_deadline(None, "2025-05-01")
    assert resolution.canonical_deadline is None
    assert resolution.status == "NONE"
