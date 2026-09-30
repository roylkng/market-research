from __future__ import annotations

import io
import math
import re
from bisect import bisect_left
from collections import Counter, defaultdict
from dataclasses import asdict
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pypdf
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from marketlab.alpha import AlphaContractError, FeatureDefinition, digest
from marketlab.alpha_market import DailyEquityObservation
from marketlab.events import sha256_bytes

T008_ID = "AE001-T008-v1"
SOURCE_LIST_ID = "AE001-T008-RATING-SOURCES-v1"
SOURCE_LIST_SHA256 = "abfc4d116f3a4a9ba362c124700a9e16ad0ae28540bf08a4d20e3a5fee623061"
PARENT_T007_PANEL_SHA256 = (
    "fc3be48ce09905b8d2ebef1ad0e75a7ed22815202abbd7d7b328fe6dfcd3957d"
)
EXPECTED_SOURCE_COUNT = 2552
PARSER_LIBRARY_VERSION = "6.17.0"
SEMANTIC_PAGE_LIMIT = 3
IST = ZoneInfo("Asia/Kolkata")
DECISION_TIME = time(18, 30)

UPGRADE_PATTERN = re.compile(r"\bupgrad(?:e|ed|ing)\b", re.IGNORECASE)
DOWNGRADE_PATTERN = re.compile(r"\bdowngrad(?:e|ed|ing)\b", re.IGNORECASE)
REAFFIRM_PATTERN = re.compile(
    r"\bre[ -]?affirm(?:ed|ation)?\b",
    re.IGNORECASE,
)
WATCH_POSITIVE_PATTERN = re.compile(
    r"(?:rating\s+watch|watch)\s+(?:with\s+)?positive\s+implications",
    re.IGNORECASE,
)
WATCH_NEGATIVE_PATTERN = re.compile(
    r"(?:rating\s+watch|watch)\s+(?:with\s+)?negative\s+implications",
    re.IGNORECASE,
)
WATCH_DEVELOPING_PATTERN = re.compile(
    r"(?:rating\s+watch|watch)\s+(?:with\s+)?developing\s+implications",
    re.IGNORECASE,
)
WATCH_REMOVED_PATTERNS = (
    re.compile(r"removed\s+from\s+(?:the\s+)?rating\s+watch", re.IGNORECASE),
    re.compile(r"rating\s+watch.{0,50}\bremoved\b", re.IGNORECASE),
)
NONCOOPERATION_PATTERN = re.compile(
    r"issuer\s+(?:not\s+cooperating|non[- ]cooperating)|"
    r"non[- ]cooperation",
    re.IGNORECASE,
)
WITHDRAW_PATTERN = re.compile(r"\bwithdraw(?:n|al)?\b", re.IGNORECASE)
WITHDRAW_BOILERPLATE = (
    "reserves the right to withdraw",
    "reserve the right to withdraw",
    "right to withdraw",
    "may withdraw",
)
AGENCY_OR_RATING_CONTEXT = re.compile(
    r"\b(?:crisil|icra|care|acu[ií]te|fitch|infomerics|brickwork|"
    r"india ratings|ind-ra|bwr|rating|outlook)\b",
    re.IGNORECASE,
)
POSITIVE_TOKEN = re.compile(
    r"(?:\boutlook\b.{0,60}\bpositive\b|"
    r"\bpositive\b.{0,60}\boutlook\b|"
    r"[/\(]\s*positive\b)",
    re.IGNORECASE,
)
NEGATIVE_TOKEN = re.compile(
    r"(?:\boutlook\b.{0,60}\bnegative\b|"
    r"\bnegative\b.{0,60}\boutlook\b|"
    r"[/\(]\s*negative\b)",
    re.IGNORECASE,
)

RATING_DEFINITIONS = [
    FeatureDefinition(
        "rating_event_current",
        "announcement_events",
        "v1",
        "Frozen T008 rating announcements mapped to current decision interval.",
        1,
    ),
    FeatureDefinition(
        "rating_new_current",
        "announcement_events",
        "v1",
        "Current rating announcements with NSE description Credit Rating- New.",
        1,
    ),
    FeatureDefinition(
        "rating_upgrade_current",
        "announcement_events",
        "v1",
        "Current rating PDF attachments containing explicit upgrade action language.",
        1,
    ),
    FeatureDefinition(
        "rating_downgrade_current",
        "announcement_events",
        "v1",
        "Current rating PDF attachments containing explicit downgrade action language.",
        1,
    ),
    FeatureDefinition(
        "rating_reaffirmed_current",
        "announcement_events",
        "v1",
        "Current rating PDF attachments containing explicit reaffirmation language.",
        1,
    ),
    FeatureDefinition(
        "rating_outlook_positive_current",
        "announcement_events",
        "v1",
        "Current rating attachments showing positive outlook language.",
        1,
    ),
    FeatureDefinition(
        "rating_outlook_negative_current",
        "announcement_events",
        "v1",
        "Current rating attachments showing negative outlook language.",
        1,
    ),
    FeatureDefinition(
        "rating_watch_positive_current",
        "announcement_events",
        "v1",
        "Current rating attachments showing positive rating-watch implications.",
        1,
    ),
    FeatureDefinition(
        "rating_watch_negative_current",
        "announcement_events",
        "v1",
        "Current rating attachments showing negative rating-watch implications.",
        1,
    ),
    FeatureDefinition(
        "rating_watch_developing_current",
        "announcement_events",
        "v1",
        "Current rating attachments showing developing rating-watch implications.",
        1,
    ),
    FeatureDefinition(
        "rating_watch_removed_current",
        "announcement_events",
        "v1",
        "Current rating attachments explicitly removing rating watch.",
        1,
    ),
    FeatureDefinition(
        "rating_noncooperation_current",
        "announcement_events",
        "v1",
        "Current rating attachments containing issuer non-cooperation language.",
        1,
    ),
    FeatureDefinition(
        "rating_withdrawn_current",
        "announcement_events",
        "v1",
        "Current rating attachments with non-boilerplate withdrawal action language.",
        1,
    ),
    FeatureDefinition(
        "rating_upgrade_20",
        "announcement_events",
        "v1",
        "Upgrade-event count over twenty decision sessions including current.",
        20,
    ),
    FeatureDefinition(
        "rating_downgrade_20",
        "announcement_events",
        "v1",
        "Downgrade-event count over twenty decision sessions including current.",
        20,
    ),
    FeatureDefinition(
        "rating_sessions_since_directional_cap60",
        "announcement_events",
        "v1",
        "Decision sessions since latest directional rating event, capped at sixty.",
        60,
    ),
    FeatureDefinition(
        "rating_text_unavailable_current",
        "announcement_events",
        "v1",
        "Current frozen rating events whose PDF body could not yield semantic text.",
        1,
    ),
]

RATING_ACTION_RULE_SHA256 = digest(
    {
        "parser_library": "pypdf",
        "parser_library_version": PARSER_LIBRARY_VERSION,
        "semantic_page_limit": SEMANTIC_PAGE_LIMIT,
        "upgrade": UPGRADE_PATTERN.pattern,
        "downgrade": DOWNGRADE_PATTERN.pattern,
        "reaffirm": REAFFIRM_PATTERN.pattern,
        "watch_positive": WATCH_POSITIVE_PATTERN.pattern,
        "watch_negative": WATCH_NEGATIVE_PATTERN.pattern,
        "watch_developing": WATCH_DEVELOPING_PATTERN.pattern,
        "watch_removed": [pattern.pattern for pattern in WATCH_REMOVED_PATTERNS],
        "noncooperation": NONCOOPERATION_PATTERN.pattern,
        "withdraw": WITHDRAW_PATTERN.pattern,
        "withdraw_boilerplate": list(WITHDRAW_BOILERPLATE),
        "positive": POSITIVE_TOKEN.pattern,
        "negative": NEGATIVE_TOKEN.pattern,
        "agency_context": AGENCY_OR_RATING_CONTEXT.pattern,
    }
)
RATING_FEATURE_DEFINITION_SHA256 = digest(
    sorted(
        (asdict(definition) for definition in RATING_DEFINITIONS),
        key=lambda row: row["name"],
    )
)


def _verify_hashed_payload(
    payload: dict[str, Any],
    *,
    hash_field: str,
    name: str,
) -> None:
    stored = str(payload.get(hash_field) or "")
    unsigned = dict(payload)
    unsigned.pop(hash_field, None)
    if len(stored) != 64 or digest(unsigned) != stored:
        raise AlphaContractError(f"{name} hash mismatch")


def validate_rating_source_list(source_list: dict[str, Any]) -> None:
    _verify_hashed_payload(
        source_list,
        hash_field="source_list_sha256",
        name="T008 rating source list",
    )
    if (
        source_list.get("source_list_id") != SOURCE_LIST_ID
        or source_list.get("source_list_sha256") != SOURCE_LIST_SHA256
        or source_list.get("parent_t007_announcement_panel_sha256")
        != PARENT_T007_PANEL_SHA256
        or source_list.get("source_count") != EXPECTED_SOURCE_COUNT
        or source_list.get("market_return_outcomes_attached") is not False
        or source_list.get("live_capital_allowed") is not False
    ):
        raise AlphaContractError("T008 frozen rating source-list contract changed")
    records = source_list.get("records")
    if not isinstance(records, list) or len(records) != EXPECTED_SOURCE_COUNT:
        raise AlphaContractError("T008 source-list record count mismatch")
    ids = [str(row.get("announcement_id") or "") for row in records]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise AlphaContractError("T008 source-list announcement IDs are invalid")


def _normalise_line(value: str) -> str:
    return " ".join(value.replace("\x00", " ").split())


def _text_flags(lines: list[str]) -> dict[str, bool]:
    upgrade = False
    downgrade = False
    reaffirmed = False
    outlook_positive = False
    outlook_negative = False
    watch_positive = False
    watch_negative = False
    watch_developing = False
    watch_removed = False
    noncooperation = False
    withdrawn = False

    for line in lines:
        lowered = line.casefold()
        upgrade = upgrade or bool(UPGRADE_PATTERN.search(line))
        downgrade = downgrade or bool(DOWNGRADE_PATTERN.search(line))
        reaffirmed = reaffirmed or bool(REAFFIRM_PATTERN.search(line))
        watch_positive = watch_positive or bool(
            WATCH_POSITIVE_PATTERN.search(line)
        )
        watch_negative = watch_negative or bool(
            WATCH_NEGATIVE_PATTERN.search(line)
        )
        watch_developing = watch_developing or bool(
            WATCH_DEVELOPING_PATTERN.search(line)
        )
        watch_removed = watch_removed or any(
            pattern.search(line) for pattern in WATCH_REMOVED_PATTERNS
        )
        noncooperation = noncooperation or bool(
            NONCOOPERATION_PATTERN.search(line)
        )
        context = bool(AGENCY_OR_RATING_CONTEXT.search(line))
        if context:
            outlook_positive = outlook_positive or bool(
                POSITIVE_TOKEN.search(line)
            )
            outlook_negative = outlook_negative or bool(
                NEGATIVE_TOKEN.search(line)
            )
        if WITHDRAW_PATTERN.search(line) and not any(
            phrase in lowered for phrase in WITHDRAW_BOILERPLATE
        ):
            withdrawn = True

    return {
        "upgrade": upgrade,
        "downgrade": downgrade,
        "reaffirmed": reaffirmed,
        "outlook_positive": outlook_positive,
        "outlook_negative": outlook_negative,
        "watch_positive": watch_positive,
        "watch_negative": watch_negative,
        "watch_developing": watch_developing,
        "watch_removed": watch_removed,
        "noncooperation": noncooperation,
        "withdrawn": withdrawn,
    }


def extract_rating_semantics(
    raw_pdf: bytes,
) -> dict[str, Any]:
    if not raw_pdf:
        raise AlphaContractError("T008 rating PDF bytes are empty")
    if pypdf.__version__ != PARSER_LIBRARY_VERSION:
        raise AlphaContractError(
            "T008 pypdf version changed: "
            f"{pypdf.__version__} != {PARSER_LIBRARY_VERSION}"
        )
    raw_sha = sha256_bytes(raw_pdf)
    try:
        reader = PdfReader(io.BytesIO(raw_pdf), strict=False)
        if reader.is_encrypted:
            raise AlphaContractError("T008 encrypted rating PDF is unsupported")
        page_count = len(reader.pages)
        lines = []
        for page in reader.pages[:SEMANTIC_PAGE_LIMIT]:
            text = page.extract_text() or ""
            lines.extend(
                normalised
                for raw_line in text.splitlines()
                if (normalised := _normalise_line(raw_line))
            )
    except (PdfReadError, OSError, KeyError, TypeError, ValueError) as exc:
        return {
            "status": "PARSE_ERROR",
            "raw_sha256": raw_sha,
            "page_count": None,
            "first3_text_sha256": None,
            "first3_text_char_count": None,
            "flags": {},
            "failure_reason": str(exc),
        }
    canonical = "\n".join(lines)
    if not canonical.strip():
        return {
            "status": "NO_TEXT",
            "raw_sha256": raw_sha,
            "page_count": page_count,
            "first3_text_sha256": sha256_bytes(b""),
            "first3_text_char_count": 0,
            "flags": {},
            "failure_reason": "pypdf extracted no non-whitespace text from first three pages",
        }
    return {
        "status": "TEXT_READY",
        "raw_sha256": raw_sha,
        "page_count": page_count,
        "first3_text_sha256": sha256_bytes(canonical.encode("utf-8")),
        "first3_text_char_count": len(canonical),
        "flags": _text_flags(lines),
        "failure_reason": None,
    }


def build_rating_semantic_record(
    source: dict[str, Any],
    *,
    raw_pdf: bytes | None,
    fetch_error: str | None = None,
) -> dict[str, Any]:
    announcement_id = str(source.get("announcement_id") or "")
    if not announcement_id:
        raise AlphaContractError("T008 semantic source is missing announcement_id")
    if raw_pdf is None:
        if not str(fetch_error or "").strip():
            raise AlphaContractError("T008 fetch failure requires a reason")
        semantic = {
            "status": "FETCH_ERROR",
            "raw_sha256": None,
            "page_count": None,
            "first3_text_sha256": None,
            "first3_text_char_count": None,
            "flags": {},
            "failure_reason": str(fetch_error),
        }
    else:
        semantic = extract_rating_semantics(raw_pdf)

    flags = {
        key: bool(value)
        for key, value in (semantic.get("flags") or {}).items()
    }
    record = {
        "announcement_id": announcement_id,
        "symbol": str(source["symbol"]).upper(),
        "seq_id": str(source["seq_id"]),
        "exchange_published_at_utc": str(source["exchange_published_at_utc"]),
        "description": str(source["description"]),
        "attachment_url": str(source["attachment_url"]),
        **{key: value for key, value in semantic.items() if key != "flags"},
        "flags": flags,
        "directional": any(
            flags.get(name, False)
            for name in (
                "upgrade",
                "downgrade",
                "outlook_positive",
                "outlook_negative",
                "watch_positive",
                "watch_negative",
                "noncooperation",
            )
        ),
    }
    record["record_sha256"] = digest(record)
    return record


def build_rating_semantic_panel(
    *,
    source_list: dict[str, Any],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    validate_rating_source_list(source_list)
    by_id = {
        str(record.get("announcement_id") or ""): record
        for record in records
    }
    if len(by_id) != len(records):
        raise AlphaContractError("T008 semantic records contain duplicate IDs")
    expected_ids = [
        str(source["announcement_id"])
        for source in source_list["records"]
    ]
    if set(by_id) != set(expected_ids):
        raise AlphaContractError(
            "T008 semantic records do not exactly cover frozen source list"
        )
    ordered = []
    status_counts: Counter[str] = Counter()
    for source in source_list["records"]:
        record = by_id[str(source["announcement_id"])]
        unsigned = dict(record)
        stored = str(unsigned.pop("record_sha256", ""))
        if stored != digest(unsigned):
            raise AlphaContractError("T008 semantic record hash mismatch")
        for field in (
            "symbol",
            "seq_id",
            "exchange_published_at_utc",
            "description",
            "attachment_url",
        ):
            expected = (
                str(source[field]).upper()
                if field == "symbol"
                else str(source[field])
            )
            if str(record[field]) != expected:
                raise AlphaContractError(
                    f"T008 semantic/source identity mismatch: {field}"
                )
        status_counts[str(record["status"])] += 1
        ordered.append(record)

    if status_counts.get("FETCH_ERROR", 0):
        raise AlphaContractError(
            "T008 semantic panel has unresolved FETCH_ERROR sources"
        )

    panel = {
        "schema_version": 1,
        "panel_id": "AE001-T008-RATING-SEMANTICS-v1",
        "trial_id": T008_ID,
        "evidence_class": "HISTORICAL_RECONSTRUCTION_DEVELOPMENT",
        "source_list_sha256": source_list["source_list_sha256"],
        "source_count": len(ordered),
        "status_counts": dict(sorted(status_counts.items())),
        "action_rule_sha256": RATING_ACTION_RULE_SHA256,
        "feature_definition_sha256": RATING_FEATURE_DEFINITION_SHA256,
        "records": ordered,
        "market_return_outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel


def _verify_panel(panel: dict[str, Any], *, name: str) -> None:
    _verify_hashed_payload(panel, hash_field="panel_sha256", name=name)


def _cutoff(day_text: str) -> datetime:
    day = date.fromisoformat(day_text)
    return datetime.combine(day, DECISION_TIME, IST).astimezone(UTC)


def augment_feature_panel_with_rating_semantics(
    *,
    feature_panel: dict[str, Any],
    market_panel: dict[str, Any],
    semantic_panel: dict[str, Any],
) -> dict[str, Any]:
    _verify_panel(feature_panel, name="T008 base feature")
    _verify_panel(market_panel, name="T008 market")
    _verify_panel(semantic_panel, name="T008 semantic")
    if feature_panel.get("outcomes_attached") is not False:
        raise AlphaContractError("T008 base feature panel contains outcomes")
    if semantic_panel.get("market_return_outcomes_attached") is not False:
        raise AlphaContractError("T008 semantic panel contains outcomes")
    if (
        semantic_panel.get("source_list_sha256") != SOURCE_LIST_SHA256
        or semantic_panel.get("action_rule_sha256") != RATING_ACTION_RULE_SHA256
        or semantic_panel.get("feature_definition_sha256")
        != RATING_FEATURE_DEFINITION_SHA256
    ):
        raise AlphaContractError("T008 semantic panel does not match frozen contract")

    market_sessions = market_panel.get("sessions")
    if not isinstance(market_sessions, list) or not market_sessions:
        raise AlphaContractError("T008 market sessions are required")
    session_dates = [str(row["session_date"]) for row in market_sessions]
    if session_dates != sorted(session_dates):
        raise AlphaContractError("T008 market sessions must be chronological")
    cutoffs = [_cutoff(day) for day in session_dates]

    identity_by_session_symbol: list[dict[str, tuple[str, str]]] = []
    for session in market_sessions:
        mapping = {}
        for raw in session.get("equities", []):
            row = (
                raw
                if isinstance(raw, DailyEquityObservation)
                else DailyEquityObservation(**raw)
            )
            if row.symbol in mapping:
                raise AlphaContractError(
                    f"{row.session_date}: duplicate T008 market symbol"
                )
            mapping[row.symbol] = (row.symbol, row.isin)
        identity_by_session_symbol.append(mapping)

    current_counts: dict[tuple[int, tuple[str, str]], Counter[str]] = defaultdict(Counter)
    upgrades: dict[tuple[str, str], list[int]] = defaultdict(
        lambda: [0] * len(session_dates)
    )
    downgrades: dict[tuple[str, str], list[int]] = defaultdict(
        lambda: [0] * len(session_dates)
    )
    directional: dict[tuple[str, str], list[int]] = defaultdict(
        lambda: [0] * len(session_dates)
    )
    excluded_no_identity = 0
    excluded_after_last_cutoff = 0
    mapped_event_count = 0

    for record in semantic_panel["records"]:
        published = datetime.fromisoformat(
            str(record["exchange_published_at_utc"]).replace("Z", "+00:00")
        ).astimezone(UTC)
        index = bisect_left(cutoffs, published)
        if index >= len(cutoffs):
            excluded_after_last_cutoff += 1
            continue
        symbol = str(record["symbol"]).upper()
        identity = identity_by_session_symbol[index].get(symbol)
        if identity is None:
            excluded_no_identity += 1
            continue
        counts = current_counts[(index, identity)]
        counts["event"] += 1
        if str(record["description"]).strip().casefold() == "credit rating- new":
            counts["new"] += 1
        if record["status"] != "TEXT_READY":
            counts["text_unavailable"] += 1
        flags = record.get("flags") or {}
        for name in (
            "upgrade",
            "downgrade",
            "reaffirmed",
            "outlook_positive",
            "outlook_negative",
            "watch_positive",
            "watch_negative",
            "watch_developing",
            "watch_removed",
            "noncooperation",
            "withdrawn",
        ):
            if bool(flags.get(name)):
                counts[name] += 1
        if bool(flags.get("upgrade")):
            upgrades[identity][index] += 1
        if bool(flags.get("downgrade")):
            downgrades[identity][index] += 1
        if bool(record.get("directional")):
            directional[identity][index] += 1
        mapped_event_count += 1

    upgrade_prefix: dict[tuple[str, str], list[int]] = {}
    downgrade_prefix: dict[tuple[str, str], list[int]] = {}
    last_directional: dict[tuple[str, str], list[int | None]] = {}
    all_identities = set(upgrades) | set(downgrades) | set(directional)
    for identity in all_identities:
        up_values = upgrades[identity]
        down_values = downgrades[identity]
        dir_values = directional[identity]
        up_run = [0]
        down_run = [0]
        latest = None
        latest_by_session = []
        for index in range(len(session_dates)):
            up_run.append(up_run[-1] + up_values[index])
            down_run.append(down_run[-1] + down_values[index])
            if dir_values[index] > 0:
                latest = index
            latest_by_session.append(latest)
        upgrade_prefix[identity] = up_run
        downgrade_prefix[identity] = down_run
        last_directional[identity] = latest_by_session

    base_definitions = feature_panel.get("feature_definitions")
    if not isinstance(base_definitions, list):
        raise AlphaContractError("T008 base feature definitions are missing")
    definitions = list(base_definitions) + [
        asdict(definition) for definition in RATING_DEFINITIONS
    ]
    names = [str(row["name"]) for row in definitions]
    if len(names) != len(set(names)):
        raise AlphaContractError("T008 rating features collide with base features")
    definitions.sort(key=lambda row: row["name"])
    feature_set_sha256 = digest(definitions)
    index_by_date = {day: index for index, day in enumerate(session_dates)}

    rows = []
    per_session: dict[str, int] = defaultdict(int)
    for base in feature_panel.get("rows", []):
        day = str(base["feature_session"])
        index = index_by_date.get(day)
        if index is None:
            raise AlphaContractError(
                f"T008 base feature session absent from market panel: {day}"
            )
        identity = (str(base["symbol"]), str(base["isin"]))
        counts = current_counts.get((index, identity), Counter())

        up_prefix = upgrade_prefix.get(identity)
        down_prefix = downgrade_prefix.get(identity)
        if up_prefix is None:
            up20 = 0
        else:
            up20 = up_prefix[index + 1] - up_prefix[max(0, index - 19)]
        if down_prefix is None:
            down20 = 0
        else:
            down20 = down_prefix[index + 1] - down_prefix[max(0, index - 19)]

        latest_rows = last_directional.get(identity)
        latest = None if latest_rows is None else latest_rows[index]
        since = 60 if latest is None else min(60, index - latest)

        new_values = {
            "rating_event_current": float(counts.get("event", 0)),
            "rating_new_current": float(counts.get("new", 0)),
            "rating_upgrade_current": float(counts.get("upgrade", 0)),
            "rating_downgrade_current": float(counts.get("downgrade", 0)),
            "rating_reaffirmed_current": float(counts.get("reaffirmed", 0)),
            "rating_outlook_positive_current": float(
                counts.get("outlook_positive", 0)
            ),
            "rating_outlook_negative_current": float(
                counts.get("outlook_negative", 0)
            ),
            "rating_watch_positive_current": float(
                counts.get("watch_positive", 0)
            ),
            "rating_watch_negative_current": float(
                counts.get("watch_negative", 0)
            ),
            "rating_watch_developing_current": float(
                counts.get("watch_developing", 0)
            ),
            "rating_watch_removed_current": float(
                counts.get("watch_removed", 0)
            ),
            "rating_noncooperation_current": float(
                counts.get("noncooperation", 0)
            ),
            "rating_withdrawn_current": float(
                counts.get("withdrawn", 0)
            ),
            "rating_upgrade_20": float(up20),
            "rating_downgrade_20": float(down20),
            "rating_sessions_since_directional_cap60": float(since),
            "rating_text_unavailable_current": float(
                counts.get("text_unavailable", 0)
            ),
        }
        if any(
            not math.isfinite(float(value))
            for value in new_values.values()
        ):
            raise AlphaContractError("T008 generated nonfinite rating feature")

        rows.append(
            {
                **base,
                "feature_set_sha256": feature_set_sha256,
                "values": {**base["values"], **new_values},
            }
        )
        per_session[day] += 1

    panel = {
        **{
            key: value
            for key, value in feature_panel.items()
            if key not in {
                "panel_sha256",
                "feature_definitions",
                "feature_set_sha256",
                "rows",
                "sessions",
                "feature_row_count",
                "session_count",
            }
        },
        "panel_id": "AE001-T008-CORE44-v1",
        "base_feature_panel_sha256": feature_panel["panel_sha256"],
        "rating_semantic_panel_sha256": semantic_panel["panel_sha256"],
        "rating_source_list_sha256": SOURCE_LIST_SHA256,
        "rating_action_rule_sha256": RATING_ACTION_RULE_SHA256,
        "feature_definitions": definitions,
        "feature_set_sha256": feature_set_sha256,
        "rating_feature_count": len(RATING_DEFINITIONS),
        "rating_mapped_event_count": mapped_event_count,
        "rating_excluded_no_same_session_eq_identity": excluded_no_identity,
        "rating_excluded_after_last_decision_cutoff": excluded_after_last_cutoff,
        "session_count": len(per_session),
        "feature_row_count": len(rows),
        "sessions": [
            {"session_date": day, "eligible_count": count}
            for day, count in sorted(per_session.items())
        ],
        "rows": rows,
        "outcomes_attached": False,
        "live_capital_allowed": False,
    }
    panel["panel_sha256"] = digest(panel)
    return panel
