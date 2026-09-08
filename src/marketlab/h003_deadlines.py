from __future__ import annotations

import calendar
import re
from dataclasses import asdict, dataclass
from datetime import date
from typing import Literal

DeadlineStatus = Literal[
    "NONE",
    "ISO_DATE",
    "FISCAL_YEAR",
    "FISCAL_QUARTER",
    "CALENDAR_YEAR",
    "MONTH_YEAR",
    "RELATIVE_CALENDAR",
    "RELATIVE_FISCAL",
    "DEFERRED_AMBIGUOUS",
    "DEFERRED_PAST",
    "DEFERRED_UNPARSED",
]

_MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


@dataclass(frozen=True)
class DeadlineResolution:
    raw_deadline: str | None
    source_date: str
    canonical_deadline: str | None
    status: DeadlineStatus
    note: str

    def to_dict(self) -> dict[str, str | None]:
        return asdict(self)


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


def _current_fiscal_year_end(source: date) -> date:
    # Indian financial year runs 1 April through 31 March.
    end_year = source.year + 1 if source.month >= 4 else source.year
    return date(end_year, 3, 31)


def _future_or_deferred(
    raw: str,
    source: date,
    candidate: date,
    status: DeadlineStatus,
    note: str,
) -> DeadlineResolution:
    if candidate < source:
        return DeadlineResolution(
            raw,
            source.isoformat(),
            None,
            "DEFERRED_PAST",
            f"deterministic interpretation {candidate.isoformat()} precedes source date",
        )
    return DeadlineResolution(raw, source.isoformat(), candidate.isoformat(), status, note)


def _fy_end_year(token: str) -> int:
    token = token.strip()
    if "-" in token:
        first, second = token.split("-", 1)
        if len(second) == 2:
            century = int(first[:2]) if len(first) == 4 else 20
            return century * 100 + int(second)
        return int(second)
    value = int(token)
    return 2000 + value if len(token) == 2 else value


def canonicalize_target_deadline(
    raw_deadline: str | None,
    source_date: str,
) -> DeadlineResolution:
    """Canonicalize blind-review deadline text without using company or outcome data.

    The only contextual input is the immutable source publication date. Ambiguous
    language is deliberately deferred instead of guessed. A deterministic
    interpretation that lands before the source date is also deferred.
    """

    source = date.fromisoformat(source_date)
    if raw_deadline is None or not raw_deadline.strip():
        return DeadlineResolution(None, source.isoformat(), None, "NONE", "no deadline text")

    raw = " ".join(raw_deadline.strip().split())
    lowered = raw.casefold().replace("–", "-").replace("—", "-")

    try:
        exact = date.fromisoformat(raw)
    except ValueError:
        exact = None
    if exact is not None:
        return _future_or_deferred(raw, source, exact, "ISO_DATE", "already ISO date")

    # Fiscal-quarter phrases are resolved before generic fiscal-year phrases.
    quarter_match = re.fullmatch(
        r"q([1-4])\s+fy\s*((?:20)?\d{2}(?:-\d{2,4})?)(?:\s+year-end)?",
        lowered,
    )
    if quarter_match:
        quarter = int(quarter_match.group(1))
        end_year = _fy_end_year(quarter_match.group(2))
        if quarter == 1:
            candidate = date(end_year - 1, 6, 30)
        elif quarter == 2:
            candidate = date(end_year - 1, 9, 30)
        elif quarter == 3:
            candidate = date(end_year - 1, 12, 31)
        else:
            candidate = date(end_year, 3, 31)
        return _future_or_deferred(
            raw, source, candidate, "FISCAL_QUARTER", "Indian fiscal-quarter end"
        )

    fiscal = lowered
    fiscal = re.sub(r"^end of\s+", "", fiscal)
    fiscal = re.sub(r"\s+year-end$", "", fiscal)
    fiscal_match = re.fullmatch(r"fy\s*((?:20)?\d{2}(?:-\d{2,4})?)", fiscal)
    if fiscal_match:
        end_year = _fy_end_year(fiscal_match.group(1))
        return _future_or_deferred(
            raw,
            source,
            date(end_year, 3, 31),
            "FISCAL_YEAR",
            "Indian fiscal-year end",
        )

    if lowered in {"end of current fiscal year", "current financial year-end"}:
        return _future_or_deferred(
            raw,
            source,
            _current_fiscal_year_end(source),
            "RELATIVE_FISCAL",
            "current Indian fiscal-year end from immutable source date",
        )

    if lowered == "end of next calendar year":
        return _future_or_deferred(
            raw,
            source,
            date(source.year + 1, 12, 31),
            "RELATIVE_CALENDAR",
            "next calendar-year end from immutable source date",
        )

    if lowered in {"end of this year", "end of current year", "current calendar year-end"}:
        return _future_or_deferred(
            raw,
            source,
            date(source.year, 12, 31),
            "RELATIVE_CALENDAR",
            "current calendar-year end from immutable source date",
        )

    if lowered in {"year-end", "year end"}:
        return DeadlineResolution(
            raw,
            source.isoformat(),
            None,
            "DEFERRED_AMBIGUOUS",
            "bare year-end does not specify calendar versus fiscal year",
        )

    if re.fullmatch(r"mid-\d{4}", lowered):
        return DeadlineResolution(
            raw,
            source.isoformat(),
            None,
            "DEFERRED_AMBIGUOUS",
            "mid-year has no exact day under the frozen review rule",
        )

    # YYYY-MM means the end of the stated month.
    numeric_month = re.fullmatch(r"(\d{4})-(\d{2})", lowered)
    if numeric_month:
        year, month = map(int, numeric_month.groups())
        if 1 <= month <= 12:
            return _future_or_deferred(
                raw,
                source,
                _month_end(year, month),
                "MONTH_YEAR",
                "end of stated month",
            )

    # Month-name plus year, optionally prefixed by 'end of'.
    month_year_text = re.sub(r"^end of\s+", "", lowered)
    month_year = re.fullmatch(r"([a-z]+)\s+(\d{4})", month_year_text)
    if month_year and month_year.group(1) in _MONTHS:
        month = _MONTHS[month_year.group(1)]
        year = int(month_year.group(2))
        return _future_or_deferred(
            raw,
            source,
            _month_end(year, month),
            "MONTH_YEAR",
            "end of stated month",
        )

    # A bare four-digit year is interpreted conservatively as no later than that
    # calendar-year end. This is the widest deterministic bound consistent with
    # phrases such as 'by 2030'.
    if re.fullmatch(r"\d{4}", lowered):
        year = int(lowered)
        return _future_or_deferred(
            raw,
            source,
            date(year, 12, 31),
            "CALENDAR_YEAR",
            "calendar-year end for bare year target",
        )

    # Month-only expressions use the nearest occurrence on or after source date.
    month_only_text = re.sub(r"^end of\s+", "", lowered)
    if month_only_text in _MONTHS:
        month = _MONTHS[month_only_text]
        year = source.year
        candidate = _month_end(year, month)
        if candidate < source:
            candidate = _month_end(year + 1, month)
        return _future_or_deferred(
            raw,
            source,
            candidate,
            "RELATIVE_CALENDAR",
            "nearest future end of named month",
        )

    current_year_month = re.fullmatch(r"([a-z]+) of current year", lowered)
    if current_year_month and current_year_month.group(1) in _MONTHS:
        month = _MONTHS[current_year_month.group(1)]
        return _future_or_deferred(
            raw,
            source,
            _month_end(source.year, month),
            "RELATIVE_CALENDAR",
            "named month in source calendar year",
        )

    day_month = re.fullmatch(r"(\d{1,2})\s+([a-z]+)", lowered)
    if day_month and day_month.group(2) in _MONTHS:
        day = int(day_month.group(1))
        month = _MONTHS[day_month.group(2)]
        year = source.year
        try:
            candidate = date(year, month, day)
        except ValueError:
            candidate = None
        if candidate is not None:
            if candidate < source:
                candidate = date(year + 1, month, day)
            return _future_or_deferred(
                raw,
                source,
                candidate,
                "RELATIVE_CALENDAR",
                "nearest future named calendar day",
            )

    return DeadlineResolution(
        raw,
        source.isoformat(),
        None,
        "DEFERRED_UNPARSED",
        "deadline text has no frozen deterministic interpretation",
    )
