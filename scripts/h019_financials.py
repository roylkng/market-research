"""Strict point-in-time financial primitives for H019.

This module parses only source facts frozen by the pre-outcome H019 source audit.
It does not calculate H019 scores or returns.
"""

from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date


class H019FinancialError(ValueError):
    """An official filing cannot satisfy the frozen H019 source contract."""


@dataclass(frozen=True)
class QuarterlyFinancials:
    quarter_end: date
    revenue: float
    profit_after_tax: float
    pre_exception_pretax_profit: float
    basic_eps: float
    paid_up_equity_share_capital: float
    face_value_per_share: float
    share_count: float

    @property
    def net_margin(self) -> float:
        return self.profit_after_tax / self.revenue

    @property
    def pre_exception_pretax_margin(self) -> float:
        return self.pre_exception_pretax_profit / self.revenue

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["quarter_end"] = self.quarter_end.isoformat()
        payload["net_margin"] = self.net_margin
        payload["pre_exception_pretax_margin"] = self.pre_exception_pretax_margin
        return payload


_FACTS = {
    "revenue": ("RevenueFromOperations", "INR"),
    "profit_after_tax": ("ProfitLossForPeriod", "INR"),
    "pre_exception_pretax_profit": ("ProfitBeforeExceptionalItemsAndTax", "INR"),
    "basic_eps": ("BasicEarningsLossPerShareFromContinuingOperations", "INRPerShare"),
    "paid_up_equity_share_capital": ("PaidUpValueOfEquityShareCapital", "INR"),
    "face_value_per_share": ("FaceValueOfEquityShareCapital", "INRPerShare"),
}


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _finite_number(text: str, concept: str) -> float:
    try:
        value = float(text.replace(",", "").strip())
    except ValueError as exc:
        raise H019FinancialError(f"non-numeric H019 fact: {concept}") from exc
    if not math.isfinite(value):
        raise H019FinancialError(f"non-finite H019 fact: {concept}")
    return value


def _one_d_fact(root: ET.Element, concept: str, unit: str) -> float:
    matches: list[float] = []
    for element in root.iter():
        if _local_name(element.tag) != concept:
            continue
        if str(element.attrib.get("contextRef") or "").strip() != "OneD":
            continue
        if str(element.attrib.get("unitRef") or "").strip() != unit:
            continue
        text = (element.text or "").strip()
        if not text:
            continue
        matches.append(_finite_number(text, concept))
    if len(matches) != 1:
        raise H019FinancialError(
            f"expected exactly one {concept} fact at contextRef=OneD unit={unit}; "
            f"found {len(matches)}"
        )
    return matches[0]


def parse_quarterly_financials(raw_xml: bytes, quarter_end: date) -> QuarterlyFinancials:
    """Parse the exact current-quarter source facts permitted by H019-v1 design."""
    if not isinstance(raw_xml, bytes) or not raw_xml:
        raise H019FinancialError("H019 XBRL source must be nonempty bytes")
    if not isinstance(quarter_end, date):
        raise H019FinancialError("quarter_end must be a date")
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError as exc:
        raise H019FinancialError(f"invalid H019 XBRL: {exc}") from exc
    if _local_name(root.tag).casefold() != "xbrl":
        raise H019FinancialError("H019 source root is not XBRL")

    values = {
        field: _one_d_fact(root, concept, unit)
        for field, (concept, unit) in _FACTS.items()
    }
    if values["revenue"] <= 0:
        raise H019FinancialError("H019 revenue must be strictly positive")
    if values["paid_up_equity_share_capital"] <= 0:
        raise H019FinancialError("H019 paid-up equity share capital must be strictly positive")
    if values["face_value_per_share"] <= 0:
        raise H019FinancialError("H019 face value per share must be strictly positive")

    share_count = values["paid_up_equity_share_capital"] / values["face_value_per_share"]
    if not math.isfinite(share_count) or share_count <= 0:
        raise H019FinancialError("H019 derived share count must be finite and positive")

    return QuarterlyFinancials(
        quarter_end=quarter_end,
        revenue=values["revenue"],
        profit_after_tax=values["profit_after_tax"],
        pre_exception_pretax_profit=values["pre_exception_pretax_profit"],
        basic_eps=values["basic_eps"],
        paid_up_equity_share_capital=values["paid_up_equity_share_capital"],
        face_value_per_share=values["face_value_per_share"],
        share_count=share_count,
    )
