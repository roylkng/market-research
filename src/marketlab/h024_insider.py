from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any
from xml.etree import ElementTree as ET

DISCLOSURE_AXIS = "ChangeInHoldingOfSecuritiesOfPromotersAxis"
DIRECT_ACTOR_CATEGORIES = frozenset(
    {"Promoter", "Promoter Group", "Director", "KMP", "Promoter and Director"}
)
PRIMARY_INSTRUMENT = "Equity"
PRIMARY_TRANSACTION_TYPE = "Buy"
PRIMARY_ACQUISITION_MODE = "Market Purchase"
PRIMARY_EXCHANGES = frozenset({"NSE", "BSE"})

TRANSACTION_CONCEPTS = (
    "CategoryOfPerson",
    "NameOfThePerson",
    "TypeOfInstrument",
    "SecuritiesHeldPriorToAcquisitionOrDisposalNumberOfSecurity",
    "SecuritiesHeldPriorToAcquisitionOrDisposalPercentageOfShareholding",
    "SecuritiesAcquiredOrDisposedNumberOfSecurity",
    "SecuritiesAcquiredOrDisposedValueOfSecurity",
    "SecuritiesAcquiredOrDisposedTransactionType",
    "SecuritiesHeldPostAcquistionOrDisposalNumberOfSecurity",
    "SecuritiesHeldPostAcquistionOrDisposalPercentageOfShareholding",
    "DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyFromDate",
    "DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyToDate",
    "ModeOfAcquisitionOrDisposal",
    "ExchangeOnWhichTheTradeWasExecuted",
    "DateOfIntimationToCompany",
)


class H024InsiderError(ValueError):
    """Raised when a current NSE PIT XBRL cannot be interpreted without guessing."""


@dataclass(frozen=True)
class PITTransaction:
    context_ref: str
    category: str
    person_name: str
    instrument: str
    prior_quantity: int
    prior_ownership_fraction: float
    transaction_quantity: int
    transaction_value_inr: float
    transaction_type: str
    post_quantity: int
    post_ownership_fraction: float
    transaction_from_date: str
    transaction_to_date: str
    acquisition_mode: str
    exchange: str
    intimation_date: str

    @property
    def prior_ownership_percentage(self) -> float:
        return self.prior_ownership_fraction * 100.0

    @property
    def post_ownership_percentage(self) -> float:
        return self.post_ownership_fraction * 100.0

    @property
    def ownership_delta_pp(self) -> float:
        return self.post_ownership_percentage - self.prior_ownership_percentage

    @property
    def is_direct_market_purchase(self) -> bool:
        return (
            self.category in DIRECT_ACTOR_CATEGORIES
            and self.instrument == PRIMARY_INSTRUMENT
            and self.transaction_type == PRIMARY_TRANSACTION_TYPE
            and self.acquisition_mode == PRIMARY_ACQUISITION_MODE
            and self.transaction_quantity > 0
            and self.transaction_value_inr > 0
            and self.exchange in PRIMARY_EXCHANGES
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["prior_ownership_percentage"] = self.prior_ownership_percentage
        payload["post_ownership_percentage"] = self.post_ownership_percentage
        payload["ownership_delta_pp"] = self.ownership_delta_pp
        payload["is_direct_market_purchase"] = self.is_direct_market_purchase
        return payload


@dataclass(frozen=True)
class PITDisclosure:
    symbol: str
    regulation: str
    revised_filing: bool
    date_of_filing: str
    transactions: tuple[PITTransaction, ...]

    @property
    def direct_market_purchases(self) -> tuple[PITTransaction, ...]:
        return tuple(row for row in self.transactions if row.is_direct_market_purchase)

    @property
    def direct_market_purchase_value_inr(self) -> float:
        return sum(row.transaction_value_inr for row in self.direct_market_purchases)

    @property
    def direct_market_purchase_quantity(self) -> int:
        return sum(row.transaction_quantity for row in self.direct_market_purchases)

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "regulation": self.regulation,
            "revised_filing": self.revised_filing,
            "date_of_filing": self.date_of_filing,
            "transaction_count": len(self.transactions),
            "transactions": [row.to_dict() for row in self.transactions],
            "direct_market_purchase_count": len(self.direct_market_purchases),
            "direct_market_purchase_value_inr": self.direct_market_purchase_value_inr,
            "direct_market_purchase_quantity": self.direct_market_purchase_quantity,
        }


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    if ":" in tag:
        return tag.rsplit(":", 1)[1]
    return tag


def _qname_local(value: object) -> str:
    return str(value or "").rsplit(":", 1)[-1]


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def _context_ids(root: ET.Element) -> tuple[str, ...]:
    ids: list[str] = []
    for context in root.iter():
        if _local_name(context.tag).casefold() != "context":
            continue
        context_id = _clean(context.attrib.get("id"))
        if not context_id:
            continue
        axes = [
            _qname_local(nested.attrib.get("dimension"))
            for nested in context.iter()
            if _local_name(nested.tag).casefold() == "typedmember"
        ]
        if axes == [DISCLOSURE_AXIS]:
            ids.append(context_id)
        elif DISCLOSURE_AXIS in axes:
            raise H024InsiderError(
                f"{context_id}: disclosure context contains unexpected additional typed axes"
            )
    if not ids:
        raise H024InsiderError("PIT XBRL contains no transaction disclosure contexts")
    if len(ids) != len(set(ids)):
        raise H024InsiderError("PIT XBRL contains duplicate disclosure context ids")
    return tuple(ids)


def _facts_by_context(root: ET.Element) -> dict[str, dict[str, list[ET.Element]]]:
    result: dict[str, dict[str, list[ET.Element]]] = {}
    for element in root.iter():
        context_ref = _clean(
            element.attrib.get("contextRef") or element.attrib.get("contextref")
        )
        if not context_ref:
            continue
        concept = _local_name(element.tag)
        result.setdefault(context_ref, {}).setdefault(concept, []).append(element)
    return result


def _one_text(facts: dict[str, list[ET.Element]], concept: str, *, context: str) -> str:
    matches = facts.get(concept, [])
    if len(matches) != 1:
        raise H024InsiderError(
            f"{context}: expected exactly one {concept} fact, found {len(matches)}"
        )
    value = _clean(matches[0].text)
    if not value:
        raise H024InsiderError(f"{context}: {concept} is empty")
    return value


def _one_numeric(
    facts: dict[str, list[ET.Element]],
    concept: str,
    *,
    context: str,
    unit: str,
) -> Decimal:
    matches = facts.get(concept, [])
    if len(matches) != 1:
        raise H024InsiderError(
            f"{context}: expected exactly one {concept} fact, found {len(matches)}"
        )
    element = matches[0]
    observed_unit = _clean(element.attrib.get("unitRef") or element.attrib.get("unitref"))
    if observed_unit != unit:
        raise H024InsiderError(
            f"{context}: {concept} unit changed: expected={unit} observed={observed_unit}"
        )
    raw = _clean(element.text).replace(",", "")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise H024InsiderError(f"{context}: {concept} is not numeric: {raw}") from exc
    if not value.is_finite():
        raise H024InsiderError(f"{context}: {concept} is non-finite")
    return value


def _integer(value: Decimal, *, field: str, context: str) -> int:
    if value < 0 or value != value.to_integral_value():
        raise H024InsiderError(f"{context}: {field} must be a non-negative integer")
    return int(value)


def _fraction(value: Decimal, *, field: str, context: str) -> float:
    if value < 0 or value > 1:
        raise H024InsiderError(f"{context}: {field} fraction out of range: {value}")
    result = float(value)
    if not math.isfinite(result):
        raise H024InsiderError(f"{context}: {field} fraction is non-finite")
    return result


def _iso_date(value: str, *, field: str, context: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise H024InsiderError(f"{context}: invalid {field}: {value}") from exc
    if parsed.isoformat() != value:
        raise H024InsiderError(f"{context}: non-canonical {field}: {value}")
    return value


def _main_fact(root: ET.Element, concept: str) -> str:
    matches = [
        element
        for element in root.iter()
        if _local_name(element.tag) == concept
        and _clean(element.attrib.get("contextRef") or element.attrib.get("contextref"))
        in {"MainI", "MainD"}
    ]
    if len(matches) != 1:
        raise H024InsiderError(f"expected exactly one main {concept} fact, found {len(matches)}")
    value = _clean(matches[0].text)
    if not value:
        raise H024InsiderError(f"main {concept} fact is empty")
    return value


def parse_pit_xml(raw: bytes, *, expected_symbol: str | None = None) -> PITDisclosure:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise H024InsiderError(f"invalid PIT XBRL XML: {exc}") from exc

    symbol = _main_fact(root, "Symbol").upper()
    if expected_symbol is not None and symbol != expected_symbol.strip().upper():
        raise H024InsiderError(
            f"PIT XML symbol mismatch: expected={expected_symbol.strip().upper()} observed={symbol}"
        )
    regulation = _main_fact(root, "DisclosureUnderRegulation")
    if regulation != "Regulation 7 (2)":
        raise H024InsiderError(f"unexpected PIT regulation: {regulation}")
    revised_raw = _main_fact(root, "RevisedFilling").casefold()
    if revised_raw not in {"true", "false"}:
        raise H024InsiderError(f"unexpected RevisedFilling value: {revised_raw}")
    date_of_filing = _iso_date(
        _main_fact(root, "DateOfFiling"), field="DateOfFiling", context="MainI"
    )

    facts_by_context = _facts_by_context(root)
    transactions: list[PITTransaction] = []
    for context_ref in _context_ids(root):
        facts = facts_by_context.get(context_ref, {})
        missing = sorted(set(TRANSACTION_CONCEPTS) - set(facts))
        if missing:
            raise H024InsiderError(
                f"{context_ref}: transaction context is missing concepts: {missing}"
            )
        prior_quantity = _integer(
            _one_numeric(
                facts,
                "SecuritiesHeldPriorToAcquisitionOrDisposalNumberOfSecurity",
                context=context_ref,
                unit="shares",
            ),
            field="prior quantity",
            context=context_ref,
        )
        prior_fraction = _fraction(
            _one_numeric(
                facts,
                "SecuritiesHeldPriorToAcquisitionOrDisposalPercentageOfShareholding",
                context=context_ref,
                unit="pure",
            ),
            field="prior ownership",
            context=context_ref,
        )
        transaction_quantity = _integer(
            _one_numeric(
                facts,
                "SecuritiesAcquiredOrDisposedNumberOfSecurity",
                context=context_ref,
                unit="shares",
            ),
            field="transaction quantity",
            context=context_ref,
        )
        transaction_value = _one_numeric(
            facts,
            "SecuritiesAcquiredOrDisposedValueOfSecurity",
            context=context_ref,
            unit="INR",
        )
        if transaction_value < 0:
            raise H024InsiderError(f"{context_ref}: transaction value must be non-negative")
        post_quantity = _integer(
            _one_numeric(
                facts,
                "SecuritiesHeldPostAcquistionOrDisposalNumberOfSecurity",
                context=context_ref,
                unit="shares",
            ),
            field="post quantity",
            context=context_ref,
        )
        post_fraction = _fraction(
            _one_numeric(
                facts,
                "SecuritiesHeldPostAcquistionOrDisposalPercentageOfShareholding",
                context=context_ref,
                unit="pure",
            ),
            field="post ownership",
            context=context_ref,
        )
        transactions.append(
            PITTransaction(
                context_ref=context_ref,
                category=_one_text(facts, "CategoryOfPerson", context=context_ref),
                person_name=_one_text(facts, "NameOfThePerson", context=context_ref),
                instrument=_one_text(facts, "TypeOfInstrument", context=context_ref),
                prior_quantity=prior_quantity,
                prior_ownership_fraction=prior_fraction,
                transaction_quantity=transaction_quantity,
                transaction_value_inr=float(transaction_value),
                transaction_type=_one_text(
                    facts, "SecuritiesAcquiredOrDisposedTransactionType", context=context_ref
                ),
                post_quantity=post_quantity,
                post_ownership_fraction=post_fraction,
                transaction_from_date=_iso_date(
                    _one_text(
                        facts,
                        "DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyFromDate",
                        context=context_ref,
                    ),
                    field="transaction from date",
                    context=context_ref,
                ),
                transaction_to_date=_iso_date(
                    _one_text(
                        facts,
                        "DateOfAllotmentAdviceOrAcquisitionOfSharesOrSaleOfSharesSpecifyToDate",
                        context=context_ref,
                    ),
                    field="transaction to date",
                    context=context_ref,
                ),
                acquisition_mode=_one_text(
                    facts, "ModeOfAcquisitionOrDisposal", context=context_ref
                ),
                exchange=_one_text(
                    facts, "ExchangeOnWhichTheTradeWasExecuted", context=context_ref
                ),
                intimation_date=_iso_date(
                    _one_text(facts, "DateOfIntimationToCompany", context=context_ref),
                    field="intimation date",
                    context=context_ref,
                ),
            )
        )

    transactions.sort(key=lambda row: row.context_ref)
    return PITDisclosure(
        symbol=symbol,
        regulation=regulation,
        revised_filing=revised_raw == "true",
        date_of_filing=date_of_filing,
        transactions=tuple(transactions),
    )


def parser_contract() -> dict[str, Any]:
    return {
        "regulation": "Regulation 7 (2)",
        "transaction_axis": DISCLOSURE_AXIS,
        "required_transaction_concepts": list(TRANSACTION_CONCEPTS),
        "quantity_unit": "shares",
        "transaction_value_unit": "INR",
        "ownership_unit": "pure",
        "ownership_semantics": "fraction_of_shareholding; multiply by 100 for percentage",
        "primary_candidate_actor_categories": sorted(DIRECT_ACTOR_CATEGORIES),
        "primary_candidate_instrument": PRIMARY_INSTRUMENT,
        "primary_candidate_transaction_type": PRIMARY_TRANSACTION_TYPE,
        "primary_candidate_acquisition_mode": PRIMARY_ACQUISITION_MODE,
        "primary_candidate_quantity_rule": "strictly_positive",
        "primary_candidate_value_rule": "strictly_positive_INR",
        "primary_candidate_exchanges": sorted(PRIMARY_EXCHANGES),
    }
