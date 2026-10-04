from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlparse

from marketlab.alpha import AlphaContractError, digest
from marketlab.events import sha256_bytes

AUDIT_ID = "FA001-D001-v1"
ANNUAL_PERIOD_END = "2026-03-31"
QUARTER_PERIOD_END = "2026-06-30"
BASIS_PREFERENCE = ("Consolidated", "Standalone")
APPROVED_HOSTS = frozenset(
    {"nsearchives.nseindia.com", "archives.nseindia.com"}
)

ANNUAL_ALIASES: dict[str, tuple[str, ...]] = {
    "total_assets": ("TotalAssets", "Assets"),
    "total_equity": ("TotalEquity", "Equity"),
    "cash": ("CashAndCashEquivalents",),
    "bank_balances_other": ("BankBalancesOtherThanCashAndCashEquivalents",),
    "current_investments": ("CurrentInvestments", "InvestmentsCurrent"),
    "noncurrent_investments": (
        "NoncurrentInvestments",
        "NonCurrentInvestments",
        "InvestmentsNoncurrent",
        "InvestmentsNonCurrent",
    ),
    "other_current_financial_assets": ("OtherCurrentFinancialAssets",),
    "other_noncurrent_financial_assets": ("OtherNoncurrentFinancialAssets",),
    "borrowings_current": ("BorrowingsCurrent", "CurrentBorrowings"),
    "borrowings_noncurrent": (
        "BorrowingsNoncurrent",
        "BorrowingsNonCurrent",
        "NoncurrentBorrowings",
        "NonCurrentBorrowings",
    ),
    "lease_liabilities_current": ("LeaseLiabilitiesCurrent",),
    "lease_liabilities_noncurrent": (
        "LeaseLiabilitiesNoncurrent",
        "LeaseLiabilitiesNonCurrent",
    ),
    "current_liabilities": ("TotalCurrentLiabilities", "CurrentLiabilities"),
    "noncurrent_liabilities": (
        "TotalNoncurrentLiabilities",
        "TotalNonCurrentLiabilities",
        "NoncurrentLiabilities",
        "NonCurrentLiabilities",
    ),
    "ppe": ("PropertyPlantAndEquipment",),
    "capital_work_in_progress": ("CapitalWorkInProgress",),
    "investment_property": ("InvestmentProperty",),
    "goodwill": ("Goodwill",),
    "other_intangibles": (
        "OtherIntangibleAssets",
        "IntangibleAssetsOtherThanGoodwill",
    ),
    "inventories": ("Inventories",),
    "trade_receivables": (
        "TradeReceivablesCurrent",
        "TradeReceivables",
    ),
    "other_current_assets": ("OtherCurrentAssets",),
    "other_noncurrent_assets": (
        "OtherNoncurrentAssets",
        "OtherNonCurrentAssets",
    ),
    "paid_up_equity": ("PaidUpValueOfEquityShareCapital",),
    "face_value_equity": ("FaceValueOfEquityShareCapital",),
    "basic_eps": (
        "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        "BasicEarningsLossPerShareFromContinuingOperations",
    ),
    "operating_cash_flow": (
        "NetCashFlowsFromUsedInOperatingActivities",
        "CashFlowsFromUsedInOperatingActivities",
    ),
    "purchase_ppe": (
        "PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
        "PurchaseOfPropertyPlantAndEquipment",
        "PaymentsToAcquirePropertyPlantAndEquipment",
    ),
    "sale_ppe": (
        "ProceedsFromSaleOfPropertyPlantAndEquipment",
        "ProceedsFromSaleOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",
    ),
    "purchase_investments": (
        "PurchaseOfInvestmentsClassifiedAsInvestingActivities",
        "PaymentsToAcquireInvestments",
    ),
    "sale_investments": (
        "ProceedsFromSaleOfInvestmentsClassifiedAsInvestingActivities",
        "ProceedsFromSaleOfInvestments",
    ),
}

QUARTER_ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": ("RevenueFromOperations",),
    "total_income": ("TotalIncome",),
    "pbeit": ("ProfitBeforeExceptionalItemsAndTax",),
    "exceptional_items": ("ExceptionalItemsBeforeTax", "ExceptionalItems"),
    "pbt": ("ProfitBeforeTax",),
    "pat": ("ProfitLossForPeriod",),
    "finance_costs": ("FinanceCosts", "FinanceCost"),
    "depreciation": (
        "DepreciationDepletionAndAmortisationExpense",
        "DepreciationAndAmortisationExpense",
    ),
    "employee_benefits": ("EmployeeBenefitExpense", "EmployeeBenefitsExpense"),
    "materials": ("CostOfMaterialsConsumed",),
    "stock_in_trade": ("PurchasesOfStockInTrade",),
    "inventory_change": (
        "ChangesInInventoriesOfFinishedGoodsWorkInProgressAndStockInTrade",
    ),
    "other_expenses": ("OtherExpenses",),
    "basic_eps": (
        "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations",
        "BasicEarningsLossPerShareFromContinuingOperations",
    ),
}

DISCOVERY_TYPE = "integrated filing- financials"


class FA001SchemaError(ValueError):
    """Raised when FA001 source semantics cannot be resolved without guessing."""


@dataclass(frozen=True)
class FilingCandidate:
    symbol: str
    accounting_basis: str
    period_end: str
    exchange_published_at_utc: str
    source_url: str
    discovery_row_sha256: str


@dataclass(frozen=True)
class Context:
    context_id: str
    start_date: str | None
    end_date: str | None
    instant: str | None
    dimensional: bool


def _clean(value: object) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split()).strip()


def _parse_date(value: object) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d-%B-%Y"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=UTC).date().isoformat()
        except ValueError:
            continue
    return None


def _parse_exchange_time(value: object) -> str | None:
    raw = _clean(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            return parsed.astimezone(UTC).isoformat()
    except ValueError:
        pass
    for fmt in (
        "%d-%b-%Y %H:%M:%S",
        "%d-%b-%Y %H:%M",
        "%d-%b-%Y",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
    ):
        try:
            parsed = datetime.strptime(f"{raw} +0530", f"{fmt} %z")
            return parsed.astimezone(UTC).isoformat()
        except ValueError:
            continue
    return None


def _payload_rows(payload: object) -> list[dict[str, Any]]:
    rows = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise AlphaContractError("FA001 discovery payload lacks data list")
    return [row for row in rows if isinstance(row, dict)]


def _approved_url(value: object) -> str | None:
    raw = _clean(value)
    if not raw or raw in {"-", "--"}:
        return None
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in APPROVED_HOSTS:
        return None
    return raw


def filing_candidates(
    payload: object,
    *,
    symbol: str,
    period_end: str,
    accounting_basis: str,
) -> list[FilingCandidate]:
    wanted_symbol = symbol.strip().upper()
    wanted_basis = accounting_basis.casefold()
    result: list[FilingCandidate] = []
    for row in _payload_rows(payload):
        if _clean(row.get("type")).casefold() != DISCOVERY_TYPE:
            continue
        if _clean(row.get("symbol")).upper() != wanted_symbol:
            continue
        if _clean(row.get("consolidated")).casefold() != wanted_basis:
            continue
        if _parse_date(row.get("qe_Date")) != period_end:
            continue
        url = _approved_url(row.get("xbrl"))
        published = _parse_exchange_time(
            row.get("broadcast_Date")
            or row.get("revised_Date")
            or row.get("creation_Date")
        )
        if url is None or published is None:
            continue
        result.append(
            FilingCandidate(
                symbol=wanted_symbol,
                accounting_basis=accounting_basis,
                period_end=period_end,
                exchange_published_at_utc=published,
                source_url=url,
                discovery_row_sha256=digest(row),
            )
        )
    return sorted(result, key=lambda row: (row.exchange_published_at_utc, row.source_url))


def _select_earliest(candidates: list[FilingCandidate]) -> FilingCandidate | None:
    if not candidates:
        return None
    timestamp = candidates[0].exchange_published_at_utc
    rows = [row for row in candidates if row.exchange_published_at_utc == timestamp]
    urls = {row.source_url for row in rows}
    if len(urls) != 1:
        raise FA001SchemaError("same-timestamp filing source URL is ambiguous")
    return rows[0]


def select_audit_filings(
    payload: object,
    *,
    symbol: str,
) -> tuple[FilingCandidate | None, FilingCandidate | None]:
    annual = None
    for basis in BASIS_PREFERENCE:
        candidate = _select_earliest(
            filing_candidates(
                payload,
                symbol=symbol,
                period_end=ANNUAL_PERIOD_END,
                accounting_basis=basis,
            )
        )
        if candidate is not None:
            annual = candidate
            break

    quarter = None
    quarter_basis_order = (
        (annual.accounting_basis,) + tuple(
            basis for basis in BASIS_PREFERENCE if annual is None or basis != annual.accounting_basis
        )
        if annual is not None
        else BASIS_PREFERENCE
    )
    for basis in quarter_basis_order:
        candidate = _select_earliest(
            filing_candidates(
                payload,
                symbol=symbol,
                period_end=QUARTER_PERIOD_END,
                accounting_basis=basis,
            )
        )
        if candidate is not None:
            quarter = candidate
            break
    return annual, quarter


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def _contexts(root: ET.Element) -> dict[str, Context]:
    result: dict[str, Context] = {}
    for element in root.iter():
        if _local_name(element.tag).casefold() != "context":
            continue
        context_id = element.attrib.get("id")
        if not context_id:
            continue
        start = None
        end = None
        instant = None
        dimensional = False
        for child in element.iter():
            name = _local_name(child.tag)
            if name == "startDate":
                start = _parse_date(child.text)
            elif name == "endDate":
                end = _parse_date(child.text)
            elif name == "instant":
                instant = _parse_date(child.text)
            elif name in {"explicitMember", "typedMember"}:
                dimensional = True
        result[context_id] = Context(
            context_id=context_id,
            start_date=start,
            end_date=end,
            instant=instant,
            dimensional=dimensional,
        )
    return result


def _numeric(value: object) -> float | None:
    raw = _clean(value).replace(",", "").replace("₹", "")
    if not raw or raw.casefold() in {"na", "n/a", "-", "--", "null"}:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    if negative:
        raw = raw[1:-1]
    try:
        parsed = float(raw)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return -parsed if negative else parsed


def parse_schema_inventory(raw: bytes, *, candidate: FilingCandidate) -> dict[str, Any]:
    try:
        document = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FA001SchemaError("XBRL is not UTF-8") from exc
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        raise FA001SchemaError(f"XBRL is not well formed: {exc}") from exc
    if _local_name(root.tag).casefold() != "xbrl":
        raise FA001SchemaError("source root is not XBRL")

    contexts = _contexts(root)
    fact_rows = []
    concept_names: set[str] = set()
    symbol_values: set[str] = set()
    for element in root.iter():
        context_ref = element.attrib.get("contextRef")
        if context_ref is None:
            continue
        name = _local_name(element.tag)
        value = _clean(element.text)
        if not value:
            continue
        concept_names.add(name)
        if name.casefold() == "symbol":
            symbol_values.add(value.upper())
        context = contexts.get(context_ref)
        fact_rows.append(
            {
                "concept": name,
                "context_ref": context_ref,
                "unit_ref": element.attrib.get("unitRef"),
                "numeric": _numeric(value) is not None,
                "start_date": context.start_date if context else None,
                "end_date": context.end_date if context else None,
                "instant": context.instant if context else None,
                "dimensional": context.dimensional if context else None,
            }
        )

    if symbol_values and candidate.symbol not in symbol_values:
        raise FA001SchemaError(
            f"filing symbol mismatch: expected {candidate.symbol}, observed {sorted(symbol_values)}"
        )

    period_end = date.fromisoformat(candidate.period_end)
    annual_contexts = {
        ctx.context_id
        for ctx in contexts.values()
        if not ctx.dimensional
        and ctx.start_date
        and ctx.end_date == candidate.period_end
        and 350 <= (period_end - date.fromisoformat(ctx.start_date)).days + 1 <= 380
    }
    instant_contexts = {
        ctx.context_id
        for ctx in contexts.values()
        if not ctx.dimensional and ctx.instant == candidate.period_end
    }
    quarter_contexts = {
        ctx.context_id
        for ctx in contexts.values()
        if not ctx.dimensional
        and ctx.start_date
        and ctx.end_date == candidate.period_end
        and 80 <= (period_end - date.fromisoformat(ctx.start_date)).days + 1 <= 100
    }

    aliases = ANNUAL_ALIASES if candidate.period_end == ANNUAL_PERIOD_END else QUARTER_ALIASES
    context_scope = {
        "annual": annual_contexts,
        "instant": instant_contexts,
        "quarter": quarter_contexts,
    }

    family_status: dict[str, dict[str, Any]] = {}
    for family, names in aliases.items():
        observed = sorted(name for name in names if name in concept_names)
        applicable_contexts: set[str] = set()
        if candidate.period_end == ANNUAL_PERIOD_END:
            duration_families = {
                "basic_eps",
                "operating_cash_flow",
                "purchase_ppe",
                "sale_ppe",
                "purchase_investments",
                "sale_investments",
            }
            applicable_contexts = (
                annual_contexts if family in duration_families else instant_contexts
            )
        else:
            applicable_contexts = quarter_contexts

        exact_rows = [
            row
            for row in fact_rows
            if row["concept"] in names and row["context_ref"] in applicable_contexts
        ]
        family_status[family] = {
            "candidate_aliases": list(names),
            "observed_aliases": observed,
            "deterministic_context_fact_count": len(exact_rows),
            "deterministic_numeric_fact_count": sum(row["numeric"] for row in exact_rows),
            "ready": len(exact_rows) > 0,
        }

    keyword_tokens = (
        "cash",
        "investment",
        "borrow",
        "lease",
        "property",
        "plant",
        "equipment",
        "capitalwork",
        "goodwill",
        "intangible",
        "inventor",
        "receiv",
        "equitysharecapital",
        "revenue",
        "profit",
        "financecost",
        "depreci",
    )
    keyword_concepts = sorted(
        name
        for name in concept_names
        if any(token in name.casefold() for token in keyword_tokens)
    )

    return {
        "symbol": candidate.symbol,
        "accounting_basis": candidate.accounting_basis,
        "period_end": candidate.period_end,
        "exchange_published_at_utc": candidate.exchange_published_at_utc,
        "source_url": candidate.source_url,
        "raw_sha256": sha256_bytes(raw),
        "context_counts": {
            key: len(value) for key, value in context_scope.items()
        },
        "family_status": family_status,
        "keyword_concepts": keyword_concepts,
        "fact_count": len(fact_rows),
        "context_count": len(contexts),
    }


def build_schema_audit(
    *,
    sample: dict[str, Any],
    observations: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    sample_rows = sample.get("symbols")
    if not isinstance(sample_rows, list) or len(sample_rows) != 48:
        raise AlphaContractError("FA001 D001 requires frozen 48-symbol sample")
    expected_symbols = {str(row["symbol"]).upper() for row in sample_rows}
    if len(expected_symbols) != 48:
        raise AlphaContractError("FA001 D001 sample symbols must be unique")

    by_symbol: dict[str, dict[str, Any]] = {}
    for row in observations:
        if not isinstance(row, dict):
            raise TypeError("FA001 D001 observations must be objects")
        symbol = str(row.get("symbol") or "").upper()
        if symbol not in expected_symbols or symbol in by_symbol:
            raise AlphaContractError("FA001 D001 observation identity mismatch")
        by_symbol[symbol] = row
    if set(by_symbol) != expected_symbols:
        raise AlphaContractError("FA001 D001 observations do not cover frozen sample")

    annual_ready = 0
    quarter_ready = 0
    annual_core_assets = 0
    annual_borrowings = 0
    annual_investments = 0
    quarter_revenue_pat = 0
    annual_family_counts: Counter[str] = Counter()
    quarter_family_counts: Counter[str] = Counter()
    keyword_concept_counts: Counter[str] = Counter()
    states: Counter[str] = Counter()

    for symbol in sorted(expected_symbols):
        row = by_symbol[symbol]
        annual = row.get("annual")
        quarter = row.get("quarter")
        if isinstance(annual, dict) and annual.get("status") == "READY":
            annual_ready += 1
            audit = annual["audit"]
            families = audit["family_status"]
            for family, state in families.items():
                if state["ready"]:
                    annual_family_counts[family] += 1
            if all(families[name]["ready"] for name in ("total_assets", "total_equity", "cash")):
                annual_core_assets += 1
            if families["borrowings_current"]["ready"] and families["borrowings_noncurrent"]["ready"]:
                annual_borrowings += 1
            if families["current_investments"]["ready"] or families["noncurrent_investments"]["ready"]:
                annual_investments += 1
            for name in audit.get("keyword_concepts", []):
                keyword_concept_counts[name] += 1
        else:
            states[str((annual or {}).get("reason") or "ANNUAL_UNAVAILABLE")] += 1

        if isinstance(quarter, dict) and quarter.get("status") == "READY":
            quarter_ready += 1
            audit = quarter["audit"]
            families = audit["family_status"]
            for family, state in families.items():
                if state["ready"]:
                    quarter_family_counts[family] += 1
            if families["revenue"]["ready"] and families["pat"]["ready"]:
                quarter_revenue_pat += 1
            for name in audit.get("keyword_concepts", []):
                keyword_concept_counts[name] += 1
        else:
            states[str((quarter or {}).get("reason") or "QUARTER_UNAVAILABLE")] += 1

    annual_denom = max(annual_ready, 1)
    quarter_denom = max(quarter_ready, 1)
    gates = {
        "minimum_quarter_xbrl_40_of_48": quarter_ready >= 40,
        "minimum_annual_xbrl_32_of_48": annual_ready >= 32,
        "annual_core_assets_80pct": annual_core_assets / annual_denom >= 0.80,
        "annual_borrowings_70pct": annual_borrowings / annual_denom >= 0.70,
        "annual_investments_70pct": annual_investments / annual_denom >= 0.70,
        "quarter_revenue_pat_85pct": quarter_revenue_pat / quarter_denom >= 0.85,
    }

    output = {
        "schema_version": 1,
        "audit_id": AUDIT_ID,
        "classification": "FULL_MARKET_FINANCIAL_ASSET_XBRL_SCHEMA_AUDIT_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "sample_count": 48,
        "sample_sha256": digest(sample),
        "annual_ready_count": annual_ready,
        "quarter_ready_count": quarter_ready,
        "annual_core_assets_ready_count": annual_core_assets,
        "annual_borrowings_ready_count": annual_borrowings,
        "annual_investments_ready_count": annual_investments,
        "quarter_revenue_pat_ready_count": quarter_revenue_pat,
        "annual_family_counts": dict(sorted(annual_family_counts.items())),
        "quarter_family_counts": dict(sorted(quarter_family_counts.items())),
        "keyword_concept_file_counts": dict(sorted(keyword_concept_counts.items())),
        "source_state_counts": dict(sorted(states.items())),
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_full_market_fact_parser": all(gates.values()),
        "observations": sorted(observations, key=lambda row: row["symbol"]),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["audit_sha256"] = digest(output)
    return output
