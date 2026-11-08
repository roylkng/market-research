"""Source-bound, independently tracked event facts for assisted research.

Signing, completion, payment and operations are different dimensions. A named
review is an attestation, not independent ground truth. Nothing here books
revenue, changes financial records, or authorizes trading.
"""
from __future__ import annotations

import copy
import json
import re
from decimal import Decimal

from marketlab.company_change import ChangeError, canonical_hash, public_url, timestamp
from marketlab.company_change_event_bridge import MONEY, SCALES, finite_contract
from marketlab.company_change_news_review import SOURCE_KEYS
from marketlab.company_change_semantics import checked_reading
from marketlab.company_change_store import loads_unique

VERSION = "CC001-EVENT-FACTS-v1"
DIMENSIONS = {
    "legal_recipient": {"ISSUER", "SUBSIDIARY", "CONSORTIUM", "COUNTERPARTY"},
    "investor": {"ISSUER", "SUBSIDIARY", "CONSORTIUM"},
    "operating_entity": {"ISSUER", "SUBSIDIARY", "TARGET"},
    "credit_obligor": {"ISSUER", "SUBSIDIARY"},
    "award": {"AWARDED", "PROPOSED", "CANCELLED"},
    "signing": {"SIGNED", "NOT_SIGNED"},
    "incorporation": {"INCORPORATED", "NOT_INCORPORATED"},
    "completion": {"COMPLETED", "PENDING"},
    "payment": {"PAID", "PENDING", "PARTIAL"},
    "operations": {"STARTED", "NOT_STARTED", "COMMENCEMENT_UNCONFIRMED"},
    "underlying_award_novelty": {"NEW_AWARD", "PREVIOUSLY_DISCLOSED"},
    "baseline_inclusion": {"ALREADY_INCLUDED", "NOT_INCLUDED", "PARTIALLY_INCLUDED"},
    "credit_grade": {"REAFFIRMED", "UPGRADED", "DOWNGRADED"},
    "credit_outlook": {"STABLE", "POSITIVE", "NEGATIVE"},
    "funding_pressure": {"REPORTED", "NOT_REPORTED"},
    "liquidity": {"RECEIVED", "EXPECTED"},
}
REQUIRED = {
    "ORDER": {"legal_recipient", "award", "signing", "completion", "payment",
              "operations", "baseline_inclusion"},
    "ACQUISITION": {"investor", "operating_entity", "signing", "incorporation", "completion",
                    "payment", "operations", "underlying_award_novelty"},
    "CREDIT": {"credit_obligor", "credit_grade", "credit_outlook",
               "funding_pressure", "liquidity"},
}
OWNERS = {"ISSUER_SCOPE", "CONSORTIUM_TOTAL", "SUBSIDIARY_SCOPE", "TARGET_SCOPE"}
QUALIFIERS = {"EXCLUDES_GST", "UPPER_LIMIT", "PAYABLE_IN_TRANCHES"}
PURPOSES = {"CONTRACT_VALUE", "SUBSCRIPTION_CONSIDERATION", "ACQUISITION_CONSIDERATION",
            "ISSUE_SIZE", "DEBT_FACILITY"}
PLAN_KEYS = {"source", "event_key", "category", "observations", "amounts", "next_checks"}


def keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ChangeError(f"{label}: exact required fields missing or unsupported fields supplied")


def exact_spans(text: str, evidence: list) -> list[dict]:
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= 5:
        raise ChangeError("one to five exact source spans required")
    result, seen = [], set()
    for span in evidence:
        keys(span, {"start", "end", "quote"}, "source span")
        start, end, quote = span["start"], span["end"], span["quote"]
        if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
                or not isinstance(quote, str) or not 10 <= len(quote.strip()) <= 4000
                or text[start:end] != quote or (start, end) in seen):
            raise ChangeError("source span differs, repeats, or exceeds bounds")
        seen.add((start, end))
        result.append(dict(span))
    return result


def assertions(text: str, values: list, allowed: set) -> list[dict]:
    if not isinstance(values, list) or len(values) > 8:
        raise ChangeError("bounded assertion list required, use [] for unknown")
    result, seen = [], set()
    for assertion in values:
        keys(assertion, {"value", "evidence"}, "assertion")
        if not isinstance(assertion["value"], str) or assertion["value"] not in allowed:
            raise ChangeError("unknown assertion value")
        checked = {"value": assertion["value"],
                   "evidence": exact_spans(text, assertion["evidence"])}
        digest = canonical_hash(checked)
        if digest in seen:
            raise ChangeError("duplicate assertion")
        seen.add(digest)
        result.append(checked)
    return result


def reduce_assertions(values: list[dict]) -> dict:
    alternatives = sorted({v["value"] for v in values})
    return {"status": "UNKNOWN" if not alternatives else "REVIEWED_ASSERTION" if len(alternatives) == 1 else "CONFLICT",
            "value": alternatives[0] if len(alternatives) == 1 else None,
            "alternatives": alternatives, "evidence": copy.deepcopy(values)}


def parse_amount(text: str, item: dict) -> dict:
    keys(item, {"id", "purpose", "literal", "evidence", "owner", "qualifiers"}, "amount")
    if (not isinstance(item["id"], str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", item["id"])
            or not isinstance(item["purpose"], str) or item["purpose"] not in PURPOSES
            or not isinstance(item["literal"], str)):
        raise ChangeError("invalid amount identity or purpose")
    match = MONEY.fullmatch(item["literal"])
    if match is None:
        raise ChangeError("unsupported monetary literal")
    evidence = exact_spans(text, item["evidence"])
    if not any(any(m[0].strip() == item["literal"] for m in MONEY.finditer(s["quote"])) for s in evidence):
        raise ChangeError("amount literal not present as a complete source monetary expression")
    currency = match[1].upper()
    currency = "INR" if currency in {"RS", "RS.", "₹"} else currency
    scale = match[3].lower().rstrip("s") if match[3] else "unit"
    units = Decimal(match[2].replace(",", "")) * SCALES[scale]
    if not units.is_finite() or not 0 < units <= Decimal("1e18"):
        raise ChangeError("amount must be positive, finite and bounded")
    owner = assertions(text, item["owner"], OWNERS)
    qualifiers = assertions(text, item["qualifiers"], QUALIFIERS)
    return {**copy.deepcopy(item), "evidence": evidence, "owner": owner, "qualifiers": qualifiers,
            "currency": currency, "amount_units": str(units),
            "inr_crore": str(units / 10_000_000) if currency == "INR" else None}


def validate(reading: dict, proposal: dict) -> dict:
    keys(proposal, PLAN_KEYS, "fact review")
    keys(proposal["source"], SOURCE_KEYS, "source reference")
    if any(proposal["source"][k] != reading[k] for k in SOURCE_KEYS):
        raise ChangeError("fact review belongs to another source")
    public_url(reading["url"])
    if (not isinstance(proposal["event_key"], str)
            or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,99}", proposal["event_key"])
            or not isinstance(proposal["category"], str) or proposal["category"] not in REQUIRED):
        raise ChangeError("unsupported event identity/category")
    observations = proposal["observations"]
    if (not isinstance(observations, dict) or not set(observations) <= DIMENSIONS.keys()
            or not REQUIRED[proposal["category"]] <= observations.keys()):
        raise ChangeError("all category questions must be addressed, explicitly [] when unknown")
    checked = {k: assertions(reading["text"], v, DIMENSIONS[k]) for k, v in observations.items()}
    if not isinstance(proposal["amounts"], list) or len(proposal["amounts"]) > 10:
        raise ChangeError("at most ten source amounts permitted")
    amounts = [parse_amount(reading["text"], a) for a in proposal["amounts"]]
    if len({a["id"] for a in amounts}) != len(amounts):
        raise ChangeError("duplicate amount ID")
    checks = proposal["next_checks"]
    if (not isinstance(checks, list) or not 1 <= len(checks) <= 6
            or not all(isinstance(c, str) and 10 <= len(c) <= 600 for c in checks)):
        raise ChangeError("specific bounded diligence questions required")
    return {**copy.deepcopy(proposal), "observations": checked, "amounts": amounts,
            "reading_sha256": reading["reading_sha256"],
            "source_published_at": reading["published_at"], "source_known_at": reading["known_at"]}


def setup(store):
    store.db.execute("""CREATE TABLE IF NOT EXISTS cc_event_fact_reviews(
        id TEXT PRIMARY KEY, source_key TEXT NOT NULL, recorded_at TEXT NOT NULL, payload TEXT NOT NULL)""")
    store.db.commit()


def admit(store, package: list, reviewer: str) -> list[dict]:
    """Explicit assisted attestation. It is not authentication or automatic model approval."""
    if not isinstance(reviewer, str) or not 1 <= len(reviewer.strip()) <= 200:
        raise ChangeError("named research reviewer required")
    if not isinstance(package, list) or not 1 <= len(package) <= 20:
        raise ChangeError("one to twenty explicit fact reviews required")
    setup(store)
    readings = []
    for row in store.db.execute("SELECT id,payload FROM cc_news_readings"):
        reading = loads_unique(row["payload"])
        if row["id"] != reading.get("reading_sha256"):
            raise ChangeError("reading identity mismatch")
        readings.append(reading)
    prepared, seen = [], set()
    for proposal in package:
        keys(proposal, PLAN_KEYS, "fact review")
        keys(proposal["source"], SOURCE_KEYS, "source reference")
        matches = [r for r in readings if all(r.get(k) == v for k, v in proposal["source"].items())]
        if not matches:
            raise ChangeError("exact source reading unavailable")
        reading = max(matches, key=lambda r: (timestamp(r["known_at"]), r["reading_sha256"]))
        checked_reading(store, reading)
        validated = validate(reading, proposal)
        source_key = canonical_hash([proposal["source"], proposal["event_key"]])
        identity = canonical_hash([source_key, proposal, reviewer])
        if identity in seen:
            raise ChangeError("duplicate review in atomic package")
        seen.add(identity)
        row = store.db.execute("SELECT payload FROM cc_event_fact_reviews WHERE id=?", (identity,)).fetchone()
        if row:
            record = loads_unique(row[0])
            check_record(record)
        else:
            record = {**validated, "id": identity, "source_key": source_key,
                      "reviewer": reviewer, "recorded_at": timestamp(store.clock()).isoformat(),
                      "review_status": "ASSISTED_RESEARCH_ATTESTATION", "independently_verified": False,
                      "live_capital_allowed": False}
            if timestamp(record["recorded_at"]) < max(timestamp(reading[k]) for k in ("known_at", "published_at")):
                raise ChangeError("review clock moved before source availability")
            record["record_sha256"] = canonical_hash(record)
        prepared.append(record)
    with store.transaction():
        for record in prepared:
            store.db.execute("INSERT OR IGNORE INTO cc_event_fact_reviews VALUES (?,?,?,?)", (
                record["id"], record["source_key"], record["recorded_at"], json.dumps(record, allow_nan=False)))
    return prepared


def check_record(record: dict) -> None:
    if (record.get("review_status") != "ASSISTED_RESEARCH_ATTESTATION"
            or canonical_hash({k: v for k, v in record.items() if k != "record_sha256"}) != record.get("record_sha256")
            or record.get("independently_verified") is not False or record.get("live_capital_allowed") is not False):
        raise ChangeError("fact review integrity or authority mismatch")


def compile_state(records: list[dict], as_of: str) -> dict:
    """Append-only aggregation. Repeated reviews cannot vote away a contradiction."""
    if not records:
        raise ChangeError("at least one reviewed fact record required")
    for record in records:
        check_record(record)
        if max(timestamp(record[k]) for k in ("recorded_at", "source_known_at", "source_published_at")) > timestamp(as_of):
            raise ChangeError("review unavailable at cutoff")
    first = records[0]
    if any(r["source_key"] != first["source_key"] or r["source"] != first["source"]
           or r["event_key"] != first["event_key"] for r in records):
        raise ChangeError("cannot mix source revisions or events")
    records = sorted(records, key=lambda r: r["id"])
    def unique(seq):
        mapping = {canonical_hash(v): v for v in seq}
        return [mapping[k] for k in sorted(mapping)]
    facts = {k: reduce_assertions(unique(v for r in records for v in r["observations"].get(k, [])))
             for k in DIMENSIONS}
    amounts = {}
    for record in records:
        for item in record["amounts"]:
            amounts.setdefault(item["id"], []).append(item)
    compiled_amounts = []
    for ident, variants in sorted(amounts.items()):
        variants = unique(variants)
        identities = {(a["purpose"], a["currency"], a["amount_units"], a["literal"]) for a in variants}
        owner = reduce_assertions(unique(v for a in variants for v in a["owner"]))
        compiled_amounts.append({"id": ident, "status": "REVIEWED_ASSERTION" if len(identities) == 1 else "CONFLICT",
            "purpose": variants[0]["purpose"] if len(identities) == 1 else None,
            "currency": variants[0]["currency"] if len(identities) == 1 else None,
            "amount_units": variants[0]["amount_units"] if len(identities) == 1 else None,
            "inr_crore": variants[0]["inr_crore"] if len(identities) == 1 else None,
            "owner": owner, "variants": copy.deepcopy(variants)})
    categories = sorted({r["category"] for r in records})
    result = {"engine": VERSION, "source": first["source"], "event_key": first["event_key"],
              "category": categories[0] if len(categories) == 1 else None, "category_alternatives": categories,
              "as_of": as_of, "reviewed_at": max(timestamp(r["recorded_at"]) for r in records).isoformat(),
              "source_known_at": max(timestamp(r["source_known_at"]) for r in records).isoformat(),
              "source_published_at": max(timestamp(r["source_published_at"]) for r in records).isoformat(),
              "facts": facts, "amounts": compiled_amounts,
              "review_ids": sorted(r["id"] for r in records),
              "reviewers": sorted({r["reviewer"] for r in records}),
              "next_checks": list(dict.fromkeys(c for r in records for c in r["next_checks"])),
              "conflicts": [k for k, v in facts.items() if v["status"] == "CONFLICT"],
              "financial_facts_written": False, "model_accuracy_claimed": False,
              "independently_verified": False, "buy_approved": False, "live_capital_allowed": False}
    result["state_sha256"] = canonical_hash(result)
    return result


def states(store, as_of: str | None = None) -> list[dict]:
    cutoff = as_of or store.clock()
    if not store.db.execute("SELECT name FROM sqlite_master WHERE name='cc_event_fact_reviews'").fetchone():
        return []
    groups = {}
    for row in store.db.execute("SELECT * FROM cc_event_fact_reviews ORDER BY recorded_at,id"):
        record = loads_unique(row["payload"])
        check_record(record)
        if (row["id"] != record["id"] or row["source_key"] != record["source_key"]
                or timestamp(row["recorded_at"]) != timestamp(record["recorded_at"])):
            raise ChangeError("fact review index/payload mismatch")
        if timestamp(record["recorded_at"]) > timestamp(cutoff):
            continue
        r = store.db.execute("SELECT payload FROM cc_news_readings WHERE id=?", (record["reading_sha256"],)).fetchone()
        if r is None:
            raise ChangeError("review lost its original reading")
        reading = loads_unique(r[0])
        checked_reading(store, reading)
        proposal = {k: record[k] for k in PLAN_KEYS}
        proposal["amounts"] = [{k: a[k] for k in ("id", "purpose", "literal", "evidence", "owner", "qualifiers")}
                               for a in record["amounts"]]
        revalidated = validate(reading, proposal)
        if any(record[k] != revalidated[k] for k in revalidated):
            raise ChangeError("stored fact review differs from original-source reconstruction")
        groups.setdefault(record["source_key"], []).append(record)
    return [compile_state(groups[k], cutoff) for k in sorted(groups)]


def order_scenarios(state: dict, plan: dict) -> dict:
    """Allow only explicitly hypothetical finite cash, never realized earnings."""
    if canonical_hash({k: v for k, v in state.items() if k != "state_sha256"}) != state.get("state_sha256"):
        raise ChangeError("compiled state integrity failure")
    keys(plan, {"source_raw_sha256", "event_key", "amount_id", "scenarios", "rationale"}, "fact scenario plan")
    if (plan["source_raw_sha256"] != state["source"]["raw_sha256"]
            or plan["event_key"] != state["event_key"] or state["category"] != "ORDER"):
        raise ChangeError("plan/source/event type mismatch")
    if state["facts"]["award"]["value"] != "AWARDED" or state["conflicts"]:
        raise ChangeError("unawarded or conflicted event cannot enter finite cash scenarios")
    matches = [a for a in state["amounts"] if a["id"] == plan["amount_id"]]
    if (len(matches) != 1 or matches[0]["status"] != "REVIEWED_ASSERTION"
            or matches[0]["purpose"] != "CONTRACT_VALUE"
            or matches[0]["owner"]["status"] != "REVIEWED_ASSERTION"
            or matches[0]["owner"]["value"] not in {"ISSUER_SCOPE", "CONSORTIUM_TOTAL"}):
        raise ChangeError("contract amount/owner unresolved")
    if (not isinstance(plan["scenarios"], list) or not 1 <= len(plan["scenarios"]) <= 20
            or not isinstance(plan["rationale"], str) or not 20 <= len(plan["rationale"]) <= 2000):
        raise ChangeError("bounded explicit assumptions and rationale required")
    amount = matches[0]
    normalized = {"currency": amount["currency"], "amount_units": amount["amount_units"],
                  "amount_scope": amount["owner"]["value"]}
    return {"state_sha256": state["state_sha256"], "amount_id": amount["id"],
            "legal_recipient": state["facts"]["legal_recipient"], "amount_owner": amount["owner"],
            "scenarios": [finite_contract(normalized, s) for s in plan["scenarios"]],
            "rationale": plan["rationale"], "recognized_revenue": None, "collected_cash": None,
            "per_share_value": None, "buy_approved": False, "live_capital_allowed": False}
