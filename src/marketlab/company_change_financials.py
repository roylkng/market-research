"""Original-XBRL cash and balance-sheet evidence. No source repair or imputation."""
from __future__ import annotations

import hashlib
import io
import re
import xml.etree.ElementTree as ET
from datetime import date
from decimal import Decimal, InvalidOperation

from marketlab.company_change import ChangeError, canonical_hash, finite, timestamp

NS = "http://www.xbrl.org/2003/instance"
ISO = "http://www.xbrl.org/2003/iso4217"
NIL = "{http://www.w3.org/2001/XMLSchema-instance}nil"
CRORE = Decimal(10_000_000)
DURATION = {
    "revenue": ("RevenueFromOperations",),
    "pbt": ("ProfitBeforeTax",),
    "group_pat": ("ProfitLossForPeriod", "ProfitLossForPeriodBeforeMinorityInterest"),
    "owner_pat": ("ProfitLossAttributableToOwnersOfParent", "ProfitOrLossAttributableToOwnersOfParent"),
    "minority_pat": ("ProfitLossAttributableToNonControllingInterests", "ProfitOrLossAttributableToNonControllingInterests"),
    "diluted_eps": ("DilutedEarningsLossPerShareFromContinuingAndDiscontinuedOperations",),
    "cfo": ("CashFlowsFromUsedInOperatingActivities",),
    "cfi": ("CashFlowsFromUsedInInvestingActivities",),
    "cff": ("CashFlowsFromUsedInFinancingActivities",),
    "fx_on_cash": ("EffectOfExchangeRateChangesOnCashAndCashEquivalents",),
    "cash_change": ("IncreaseDecreaseInCashAndCashEquivalents",),
    "ppe_purchases": ("PurchaseOfPropertyPlantAndEquipmentClassifiedAsInvestingActivities",),
    "intangible_purchases": ("PurchaseOfIntangibleAssetsClassifiedAsInvestingActivities",),
    "intangible_development": ("PurchaseOfIntangibleAssetsUnderDevelopment",),
    "investment_property_purchases": ("PurchaseOfInvestmentPropertyClassifiedAsInvestingActivities",),
    "other_long_term_purchases": ("PurchaseOfOtherLongTermAssetsClassifiedAsInvestingActivities",),
    "acquisitions": ("CashFlowsUsedInObtainingControlOfSubsidiariesOrOtherBusinessesClassifiedAsInvestingActivities",),
    "lease_payments": ("PaymentsOfLeaseLiabilitiesClassifiedAsFinancingActivities",),
    "financing_interest_paid": ("InterestPaidClassifiedAsFinancingActivities",),
    "new_borrowings": ("ProceedsFromBorrowingsClassifiedAsFinancingActivities",),
    "borrowings_repaid": ("RepaymentsOfBorrowingsClassifiedAsFinancingActivities",),
    "inventory_cash_adjustment": ("AdjustmentsForDecreaseIncreaseInInventories",),
    "receivables_cash_adjustment": ("AdjustmentsForDecreaseIncreaseInTradeReceivablesCurrent",),
    "payables_cash_adjustment": ("AdjustmentsForIncreaseDecreaseInTradePayablesCurrent",),
}
INSTANT = {
    "cash_equivalents": ("CashAndCashEquivalents",),
    "cash_flow_cash": ("CashAndCashEquivalentsCashFlowStatement",),
    "other_bank_balances": ("BankBalanceOtherThanCashAndCashEquivalents",),
    "borrowings_current": ("BorrowingsCurrent", "ShortTermBorrowings"),
    "borrowings_noncurrent": ("BorrowingsNoncurrent", "LongTermBorrowings"),
    "borrowings_total": ("Borrowings",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "equity": ("Equity",),
    "owner_equity": ("EquityAttributableToOwnersOfParent",),
    "equity_and_liabilities": ("EquityAndLiabilities",),
    "current_assets": ("CurrentAssets",),
    "current_liabilities": ("CurrentLiabilities",),
    "inventory": ("Inventories",),
    "current_receivables": ("TradeReceivablesCurrent",),
}


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parsed(raw: bytes):
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 16 * 1024 * 1024:
        raise ChangeError("invalid XBRL byte size")
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise ChangeError("only retained UTF-8 XBRL is supported") from exc
    if "\x00" in text or re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", text, re.IGNORECASE):
        raise ChangeError("XML entities and alternate encodings are unsupported")
    bindings, count = {}, 0
    try:
        parser = ET.iterparse(io.StringIO(text), events=("start-ns", "end"))
        for event, item in parser:
            if event == "start-ns":
                key, uri = item
                if key in bindings and bindings[key] != uri:
                    raise ChangeError("namespace prefix rebinding requires explicit review")
                bindings[key] = uri
            else:
                count += 1
                if count > 150_000:
                    raise ChangeError("XML element limit exceeded")
        root = parser.root
    except (ET.ParseError, ValueError) as exc:
        raise ChangeError(f"invalid XBRL: {exc}") from exc
    if root.tag != f"{{{NS}}}xbrl":
        raise ChangeError("retained bytes are not an XBRL instance")
    return root, bindings


def _qname(text: str, bindings: dict) -> tuple[str, str]:
    parts = (text or "").strip().split(":")
    if len(parts) == 2 and parts[0] in bindings:
        return bindings[parts[0]], parts[1]
    if len(parts) == 1 and "" in bindings:
        return bindings[""], parts[0]
    raise ChangeError("unresolved unit QName")


def extract_financials(raw: bytes, identity: dict, available_at: str) -> dict:
    """Read exact undimensioned durations/instants for one authenticated envelope.

    The byte hash ties facts to retained content, not to issuer truthfulness.
    Namespace-qualified units and context entity identities are checked explicitly.
    """
    clock = timestamp(available_at)
    root, bindings = _parsed(raw)
    source_sha = hashlib.sha256(raw).hexdigest()
    facts = [n for n in root if n.get("contextRef") is not None]
    anchors = [n for n in facts if _local(n.tag) == "Symbol"]
    if not anchors or {str(n.text).strip() for n in anchors} != {identity["symbol"]}:
        raise ChangeError("issuer symbol mismatch")
    namespaces = {n.tag.rsplit("}", 1)[0] + "}" for n in anchors}
    if len(namespaces) != 1:
        raise ChangeError("ambiguous issuer taxonomy")
    namespace = next(iter(namespaces))
    facts = [n for n in facts if n.tag.startswith(namespace)]
    isins = [n for n in facts if _local(n.tag) == "ISIN"]
    if {str(n.text).strip() for n in isins} != {identity["isin"]}:
        raise ChangeError("issuer ISIN mismatch")
    scopes = {str(n.text).strip().upper() for n in facts
              if _local(n.tag) == "NatureOfReportStandaloneConsolidated"}
    if scopes != {identity["scope"]} or identity["scope"] not in {"CONSOLIDATED", "STANDALONE"}:
        raise ChangeError("ambiguous or mismatched accounting scope")
    contexts, entities = {}, {}
    for node in root.findall(f"{{{NS}}}context"):
        cid = node.get("id")
        if not cid or cid in contexts:
            raise ChangeError("duplicate or missing context identity")
        entity = node.find(f"{{{NS}}}entity/{{{NS}}}identifier")
        if entity is None or not entity.text or not entity.get("scheme"):
            raise ChangeError("context entity identifier missing")
        entities[cid] = (entity.get("scheme"), entity.text.strip())
        if any(_local(n.tag) in {"segment", "scenario", "explicitMember", "typedMember"} for n in node.iter()):
            contexts[cid] = None
            continue
        begin = node.find(f"{{{NS}}}period/{{{NS}}}startDate")
        end = node.find(f"{{{NS}}}period/{{{NS}}}endDate")
        instant = node.find(f"{{{NS}}}period/{{{NS}}}instant")
        if begin is not None and end is not None and instant is None:
            b, e = date.fromisoformat(begin.text), date.fromisoformat(end.text)
            if b > e:
                raise ChangeError("reversed financial duration")
            key = ("duration", b.isoformat(), e.isoformat())
        elif instant is not None and begin is None and end is None:
            key = ("instant", date.fromisoformat(instant.text).isoformat())
        else:
            contexts[cid] = None
            continue
        contexts[cid] = key if date.fromisoformat(key[-1]) <= clock.date() else None
    anchor_entities = {entities.get(n.get("contextRef")) for n in anchors + isins}
    if len(anchor_entities) != 1 or None in anchor_entities:
        raise ChangeError("issuer identity contexts disagree")
    anchor_entity = next(iter(anchor_entities))
    groups = {}
    for cid, key in contexts.items():
        if key is not None and entities[cid] == anchor_entity:
            groups.setdefault(key, set()).add(cid)
    units = {}
    for unit in root.findall(f"{{{NS}}}unit"):
        uid = unit.get("id")
        if not uid or uid in units:
            raise ChangeError("duplicate or missing unit identity")
        direct = unit.findall(f"{{{NS}}}measure")
        divide = unit.find(f"{{{NS}}}divide")
        if len(direct) == 1 and divide is None:
            units[uid] = (_qname(direct[0].text, bindings),)
        elif not direct and divide is not None:
            num = divide.findall(f"{{{NS}}}unitNumerator/{{{NS}}}measure")
            den = divide.findall(f"{{{NS}}}unitDenominator/{{{NS}}}measure")
            if len(num) == len(den) == 1:
                units[uid] = (_qname(num[0].text, bindings), _qname(den[0].text, bindings))
    periods, instants = [], []
    for key, cids in sorted(groups.items()):
        aliases = DURATION if key[0] == "duration" else INSTANT
        extracted = {}
        for field, names in aliases.items():
            nodes = [n for n in facts if n.get("contextRef") in cids and _local(n.tag) in names]
            non_nil = [n for n in nodes if n.get(NIL) not in {"true", "1"}]
            if not non_nil:
                continue
            values = []
            for node in non_nil:
                per_share = field == "diluted_eps"
                expected_unit = ((ISO, "INR"), (NS, "shares")) if per_share else ((ISO, "INR"),)
                if units.get(node.get("unitRef")) != expected_unit:
                    raise ChangeError(f"{field}: missing or incompatible namespace-qualified unit")
                if node.get("scale") is not None or node.get("precision") is not None:
                    raise ChangeError("scaled/precision facts require an explicit adapter")
                literal = (node.text or "").strip()
                if not re.fullmatch(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)", literal):
                    raise ChangeError(f"{field}: nondecimal numeric literal")
                try:
                    value = Decimal(literal) / (Decimal(1) if per_share else CRORE)
                except InvalidOperation as exc:
                    raise ChangeError("invalid monetary amount") from exc
                finite(value, field)
                decimals = node.get("decimals")
                error = None
                if decimals == "INF":
                    error = Decimal(0)
                elif decimals is not None and re.fullmatch(r"-?\d{1,2}", decimals) and abs(int(decimals)) <= 18:
                    error = Decimal(5) * Decimal(10) ** (-int(decimals) - 1) / (Decimal(1) if per_share else CRORE)
                elif decimals is not None:
                    raise ChangeError("invalid XBRL decimals accuracy")
                values.append((value, error, node, literal))
            if len({v for v, _, _, _ in values}) != 1:
                raise ChangeError(f"conflicting same-period facts: {field}")
            value, error, node, literal = min(values, key=lambda x: x[1] if x[1] is not None else Decimal("Infinity"))
            extracted[field] = {"value": float(value), "decimal_value": str(value),
                "unit": "INR_per_share" if field == "diluted_eps" else "INR_crore",
                "rounding_error": float(error) if error is not None else None,
                "literal": literal, "concept": node.tag, "context_ref": node.get("contextRef"),
                "unit_ref": node.get("unitRef"), "decimals": node.get("decimals"),
                "raw_sha256": source_sha}
        if not extracted:
            continue
        entry = {"facts": extracted, "context_ids": sorted(cids)}
        if key[0] == "duration":
            entry.update(period_start=key[1], period_end=key[2])
            periods.append(entry)
        else:
            entry["date"] = key[1]
            instants.append(entry)
    result = {"identity": identity, "source_sha256": source_sha, "available_at": clock.isoformat(),
              "periods": periods, "instants": instants, "live_capital_allowed": False}
    result["facts_sha256"] = canonical_hash(result)
    return result
