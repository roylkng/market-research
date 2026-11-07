"""Historical identity and profit-attribution checks, without repairing source facts."""
from __future__ import annotations

import copy
import csv
import hashlib
import io
import re
from datetime import date, datetime
from decimal import Decimal

from marketlab.company_change import ChangeError, finite, timestamp
from marketlab.company_change_financials import _parsed
from marketlab.company_change_pipeline import fetch_original

SYMBOL_CHANGES_URL = "https://nsearchives.nseindia.com/content/equities/symbolchange.csv"
ATTRIBUTION_FIELDS = ("owner_pat", "minority_pat", "group_pat")


def attribution_check(period: dict) -> dict:
    """A failed identity withholds attribution, not revenue or group cash flow.

    Unknown rounding never receives a made-up tolerance. Source values remain
    unchanged and are still shown in evidence, including contradictory zeroes.
    """
    facts = period["facts"]
    check = {"name": "owner_plus_minority_equals_group_pat", "status": "MISSING_INPUT",
             "residual_crore": None, "tolerance_crore": None, "withheld_fields": []}
    if not all(key in facts for key in ATTRIBUTION_FIELDS):
        return check
    amounts, errors = [], []
    for key in ATTRIBUTION_FIELDS:
        fact = facts[key]
        if fact.get("unit") != "INR_crore":
            raise ChangeError("attribution check requires INR crore")
        finite(fact["value"], key)
        value = Decimal(str(fact.get("decimal_value", fact["value"])))
        finite(value, key)
        if value != Decimal(str(fact["value"])):
            # Float conversion of an exact decimal can round its last digits.
            if float(value) != finite(fact["value"], key):
                raise ChangeError("attribution decimal and exposed value disagree")
        amounts.append(value)
        error = fact.get("rounding_error")
        if error is not None:
            finite(error, "rounding_error", minimum=0)
        errors.append(Decimal(str(error)) if error is not None else None)
    residual = amounts[0] + amounts[1] - amounts[2]
    tolerance = sum(errors, Decimal(0)) if all(e is not None for e in errors) else None
    status = ("EXACT" if residual == 0 else "ROUNDING_UNKNOWN" if tolerance is None else
              "WITHIN_REPORTED_ROUNDING" if abs(residual) <= tolerance else "FAIL")
    check.update(status=status, residual_crore=finite(residual, "residual"),
                 tolerance_crore=finite(tolerance, "tolerance") if tolerance is not None else None)
    if status in {"FAIL", "ROUNDING_UNKNOWN"}:
        check["withheld_fields"] = ["owner_pat", "minority_pat"]
    return check


def guarded_periods(periods: list[dict]) -> list[dict]:
    """Recompute derived checks. Never trust caller-supplied pass/approval flags."""
    result = copy.deepcopy(periods)
    for period in result:
        check = attribution_check(period)
        period["context_quality"] = {"attribution": check,
                                     "withheld_fields": check["withheld_fields"]}
    return result


def direct_symbol_change(raw: bytes, old: str, new: str, published_at: str,
                         observed_at: str) -> dict:
    """Require one original exchange row and ordered dates. No fuzzy aliases."""
    if not isinstance(raw, bytes) or not 0 < len(raw) <= 4 * 1024 * 1024:
        raise ChangeError("invalid symbol-change registry size")
    if not all(re.fullmatch(r"[A-Z0-9&._-]{1,30}", symbol) for symbol in (old, new)) or old == new:
        raise ChangeError("invalid historical symbol pair")
    published, observed = timestamp(published_at), timestamp(observed_at)
    if published > observed:
        raise ChangeError("symbol mapping is not yet observed")
    matches = []
    for line, fields in enumerate(csv.reader(io.StringIO(raw.decode("utf-8-sig"))), 1):
        if not fields or not any(v.strip() for v in fields):
            continue
        # The exchange publishes this as four fields, with or without a header.
        if len(fields) != 4:
            raise ChangeError("unexpected symbol-change registry shape")
        company, prior, current, effective_text = [v.strip() for v in fields]
        if prior == old and current == new:
            effective = None
            for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d", "%d-%B-%Y"):
                try:
                    effective = datetime.strptime(effective_text, fmt).date()
                    break
                except ValueError:
                    continue
            if effective is None or not company:
                raise ChangeError("invalid symbol-change row")
            matches.append({"old_symbol": prior, "new_symbol": current,
                            "effective_date": effective.isoformat(), "company_name": company,
                            "source_line": line, "source_fields": fields})
    if len(matches) != 1:
        raise ChangeError("exact historical symbol mapping is absent or ambiguous")
    selected = matches[0]
    effective = date.fromisoformat(selected["effective_date"])
    if not published.date() < effective <= observed.date():
        raise ChangeError("historical symbol dates do not cover source publication and observation")
    return {**selected, "source_url": SYMBOL_CHANGES_URL,
            "registry_sha256": hashlib.sha256(raw).hexdigest(),
            "observed_at": observed.isoformat(), "resolution": "OFFICIAL_DIRECT_SYMBOL_CHANGE_WITH_IDENTICAL_ISIN"}


def resolve_xml_identity(raw: bytes, identity: dict, published_at: str, store,
                         *, fetcher=fetch_original) -> tuple[dict, dict | None]:
    """Preserve original XML, parse with its own verified historical symbol.

    The security's ISIN must already match exactly. The current issuer identity
    is not changed. Mergers, ISIN changes, chains and undocumented aliases abstain.
    """
    root, _ = _parsed(raw)
    facts = [n for n in root if n.get("contextRef") is not None]
    symbols = {str(n.text).strip() for n in facts if n.tag.rsplit("}", 1)[-1] == "Symbol"}
    isins = {str(n.text).strip() for n in facts if n.tag.rsplit("}", 1)[-1] == "ISIN"}
    if isins != {identity["isin"]}:
        raise ChangeError("historical source ISIN mismatch, symbol mapping is not allowed")
    if symbols == {identity["symbol"]}:
        return dict(identity), None
    if len(symbols) != 1:
        raise ChangeError("historical source symbol is ambiguous")
    source_symbol = next(iter(symbols))
    registry, final_url = fetcher(SYMBOL_CHANGES_URL, {"nsearchives.nseindia.com"})
    capture = store.capture(registry, {"url": SYMBOL_CHANGES_URL, "final_url": final_url,
                                      "origin": "HTTP_RESPONSE_BYTES", "lane": "CC001-SYMBOL-IDENTITY-v1"})
    resolution = direct_symbol_change(registry, source_symbol, identity["symbol"],
                                      published_at, capture["captured_at"])
    return {**identity, "symbol": source_symbol}, resolution
