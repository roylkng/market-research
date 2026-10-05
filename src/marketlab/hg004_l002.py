from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest

SYNTHESIS_ID = "HG004-L002-v1"
EXPECTED_RUN_ID = "HG004-L001-GPT56SOL-NATIVE-v1"
EXPECTED_RUN_SHA = "a402b39a8890cd2fac3218bb94673f8b9c00b1f325315f9ec93863c22d9a1d12"
EXPECTED_SYMBOLS = {
    "ANANTRAJ",
    "AXITA",
    "DATAMATICS",
    "DEVX",
    "FCL",
    "INOXGREEN",
    "NPST",
    "SAMBHV",
    "SANDESH",
    "SUVIDHAA",
    "TREL",
}

STATE_PRECEDENCE = (
    "READY_ACQUISITION_ECONOMICS",
    "READY_DEMERGER_ENTITLEMENT",
    "READY_DILUTION_FINANCING",
    "READY_RIGHTS_PAYOFF",
    "READY_CAPITAL_DEPLOYMENT_MONITOR",
    "PARTIAL_ACQUISITION_TERMS_REQUIRED",
    "PARTIAL_RIGHTS_TERMS_REQUIRED",
    "HISTORICAL_FINANCING_MONITOR",
    "PROCEDURAL_INTERNAL_REORGANISATION",
)

EXPECTED_PRIMARY = {
    "ANANTRAJ": "READY_DEMERGER_ENTITLEMENT",
    "AXITA": "PARTIAL_ACQUISITION_TERMS_REQUIRED",
    "DATAMATICS": "PROCEDURAL_INTERNAL_REORGANISATION",
    "DEVX": "READY_DILUTION_FINANCING",
    "FCL": "HISTORICAL_FINANCING_MONITOR",
    "INOXGREEN": "READY_ACQUISITION_ECONOMICS",
    "NPST": "READY_CAPITAL_DEPLOYMENT_MONITOR",
    "SAMBHV": "READY_DILUTION_FINANCING",
    "SANDESH": "PROCEDURAL_INTERNAL_REORGANISATION",
    "SUVIDHAA": "PARTIAL_RIGHTS_TERMS_REQUIRED",
    "TREL": "PROCEDURAL_INTERNAL_REORGANISATION",
}

ALLOWED_MISSING = {
    "CURRENT_MARKET_PRICE",
    "CURRENT_MARKET_CAP",
    "CURRENT_FULLY_DILUTED_SHARE_COUNT",
    "SEPARATED_BUSINESS_EARNINGS",
    "SEPARATED_BUSINESS_VALUATION_REFERENCE",
    "ACQUISITION_FUNDING_STRUCTURE",
    "TARGET_NORMALIZED_EARNINGS_OR_CASH_FLOW",
    "FINAL_PURCHASE_PRICE_OR_ADJUSTMENTS",
    "RIGHTS_ISSUE_PRICE",
    "RIGHTS_ENTITLEMENT_RATIO",
    "RIGHTS_RECORD_DATE",
    "TRANSACTION_EFFECTIVE_DATE",
    "CURRENT_CAPITAL_DEPLOYMENT_UPDATE",
    "OTHER_EXPLICIT_SOURCE_REQUIRED",
}


def _explicit(extraction: dict[str, Any], family: str, field: str) -> Any | None:
    fact = extraction["facts"][family][field]
    if fact.get("status") == "EXPLICIT":
        return fact.get("value")
    return None


def _texts(extraction: dict[str, Any]) -> str:
    pieces: list[str] = []
    for block in extraction.get("facts", {}).values():
        if not isinstance(block, dict):
            continue
        for fact in block.values():
            if isinstance(fact, dict) and fact.get("status") == "EXPLICIT":
                pieces.append(str(fact.get("value") or ""))
    pieces.extend(str(x) for x in extraction.get("extraction_caveats", []))
    return " ".join(pieces).casefold()


def _document_rows(run: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    rows = run.get("rows")
    if not isinstance(rows, list) or len(rows) != 19:
        raise AlphaContractError("HG004 L002 requires exactly 19 L001 rows")
    result: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise TypeError("HG004 L002 L001 rows must be objects")
        symbols = row.get("symbols")
        extraction = row.get("validated_extraction")
        if (
            not isinstance(symbols, list)
            or len(symbols) != 1
            or not isinstance(extraction, dict)
        ):
            raise AlphaContractError("HG004 L002 row identity is not deterministic")
        symbol = str(symbols[0]).upper()
        if symbol not in EXPECTED_SYMBOLS:
            raise AlphaContractError(f"HG004 L002 unexpected symbol: {symbol}")
        result[symbol].append(row)
    if set(result) != EXPECTED_SYMBOLS:
        raise AlphaContractError("HG004 L002 exact 11-symbol set is unavailable")
    return result


def _lane(
    *,
    state: str,
    family: str,
    document_ids: list[str],
    explicit_terms: dict[str, Any],
    missing_inputs: list[str],
    notes: list[str],
) -> dict[str, Any]:
    if any(item not in ALLOWED_MISSING for item in missing_inputs):
        raise AlphaContractError("HG004 L002 contains unregistered missing-input code")
    return {
        "readiness_state": state,
        "economic_family": family,
        "evidence_document_ids": sorted(set(document_ids)),
        "explicit_terms": explicit_terms,
        "missing_inputs": sorted(set(missing_inputs)),
        "notes": notes,
    }


def _has_historical_monitor(extractions: list[dict[str, Any]]) -> bool:
    text = " ".join(_texts(x) for x in extractions)
    return (
        "final monitoring" in text
        or "final monitoring-agency" in text
        or "not a fresh 2026" in text
        or "not a fresh warrant" in text
    )


def _scheme_internal(extraction: dict[str, Any]) -> bool:
    text = _texts(extraction)
    no_consideration = _explicit(
        extraction, "consideration", "non_cash_consideration_description"
    )
    exchange = _explicit(extraction, "ratios_entitlement", "exchange_ratio_text")
    return (
        "wholly owned" in text
        and no_consideration is not None
        and exchange is not None
        and ("no share" in str(exchange).casefold() or "no exchange ratio" in str(exchange).casefold())
    )


def _is_demerger(extraction: dict[str, Any]) -> bool:
    if "SCHEME_REORGANISATION" not in extraction.get("transaction_families", []):
        return False
    exchange = _explicit(extraction, "ratios_entitlement", "exchange_ratio_text")
    text = _texts(extraction)
    return exchange is not None and (
        "demerg" in text
        or "two focused listed" in text
        or "two listed entit" in text
    )


def _synthesize_symbol(symbol: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    docs = [str(row["document_id"]) for row in rows]
    extractions = [row["validated_extraction"] for row in rows]
    lanes: list[dict[str, Any]] = []

    # Acquisition/CIRP economics.
    acquisition_docs = [
        row
        for row in rows
        if "ACQUISITION_INVESTMENT"
        in row["validated_extraction"].get("transaction_families", [])
    ]
    if acquisition_docs:
        explicit_price = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "consideration",
                    "total_consideration",
                )
                for row in acquisition_docs
                if _explicit(
                    row["validated_extraction"],
                    "consideration",
                    "total_consideration",
                )
                is not None
            ),
            None,
        )
        asset = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "asset_or_business_description",
                )
                for row in acquisition_docs
                if _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "asset_or_business_description",
                )
                is not None
            ),
            None,
        )
        capacity = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                )
                for row in acquisition_docs
                if _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                )
                is not None
            ),
            None,
        )
        state = (
            "READY_ACQUISITION_ECONOMICS"
            if explicit_price is not None and asset is not None
            else "PARTIAL_ACQUISITION_TERMS_REQUIRED"
        )
        missing = [
            "CURRENT_MARKET_PRICE",
            "CURRENT_MARKET_CAP",
            "ACQUISITION_FUNDING_STRUCTURE",
            "TARGET_NORMALIZED_EARNINGS_OR_CASH_FLOW",
        ]
        if explicit_price is None:
            missing.append("FINAL_PURCHASE_PRICE_OR_ADJUSTMENTS")
        elif isinstance(explicit_price, (int, float)) and any(
            "subject" in _texts(row["validated_extraction"])
            for row in acquisition_docs
        ):
            # The Inox term is a maximum price subject to adjustments.
            missing.append("FINAL_PURCHASE_PRICE_OR_ADJUSTMENTS")
        lanes.append(
            _lane(
                state=state,
                family="ACQUISITION_ECONOMICS",
                document_ids=[str(row["document_id"]) for row in acquisition_docs],
                explicit_terms={
                    "stated_total_consideration": explicit_price,
                    "asset_or_business_description": asset,
                    "operating_metric": capacity,
                },
                missing_inputs=missing,
                notes=[
                    "Acquisition lane is routed from explicit source terms only; no completion probability is assigned."
                ],
            )
        )

    # Demerger entitlement economics.
    demerger_docs = [
        row
        for row in rows
        if _is_demerger(row["validated_extraction"])
    ]
    if demerger_docs:
        ratio = next(
            _explicit(
                row["validated_extraction"],
                "ratios_entitlement",
                "exchange_ratio_text",
            )
            for row in demerger_docs
            if _explicit(
                row["validated_extraction"],
                "ratios_entitlement",
                "exchange_ratio_text",
            )
            is not None
        )
        asset = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "asset_or_business_description",
                )
                for row in demerger_docs
                if _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "asset_or_business_description",
                )
                is not None
            ),
            None,
        )
        operating = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                )
                for row in demerger_docs
                if _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                )
                is not None
            ),
            None,
        )
        lanes.append(
            _lane(
                state="READY_DEMERGER_ENTITLEMENT",
                family="DEMERGER_ENTITLEMENT",
                document_ids=[str(row["document_id"]) for row in demerger_docs],
                explicit_terms={
                    "exchange_ratio_text": ratio,
                    "asset_or_business_description": asset,
                    "operating_metric": operating,
                },
                missing_inputs=[
                    "CURRENT_MARKET_PRICE",
                    "CURRENT_MARKET_CAP",
                    "SEPARATED_BUSINESS_EARNINGS",
                    "SEPARATED_BUSINESS_VALUATION_REFERENCE",
                    "TRANSACTION_EFFECTIVE_DATE",
                ],
                notes=[
                    "Entitlement is explicit; separated-business valuation remains an independent downstream research task."
                ],
            )
        )

    # Preferential/warrant financing.
    pref_docs = [
        row
        for row in rows
        if "PREFERENTIAL_WARRANT"
        in row["validated_extraction"].get("transaction_families", [])
    ]
    if pref_docs:
        if _has_historical_monitor(
            [row["validated_extraction"] for row in pref_docs]
        ) and all(
            row["validated_extraction"].get("transaction_stage")
            == "PROCEDURAL_UPDATE"
            for row in pref_docs
        ):
            lanes.append(
                _lane(
                    state="HISTORICAL_FINANCING_MONITOR",
                    family="DILUTION_FINANCING",
                    document_ids=[str(row["document_id"]) for row in pref_docs],
                    explicit_terms={
                        "monitoring_document_count": len(pref_docs),
                    },
                    missing_inputs=[],
                    notes=[
                        "Source documents are final/historical utilization or forfeiture reports rather than a new forward financing catalyst."
                    ],
                )
            )
        else:
            issue_price = next(
                (
                    _explicit(
                        row["validated_extraction"],
                        "security_economics",
                        "issue_price_per_share",
                    )
                    for row in pref_docs
                    if _explicit(
                        row["validated_extraction"],
                        "security_economics",
                        "issue_price_per_share",
                    )
                    is not None
                ),
                None,
            )
            count = next(
                (
                    _explicit(
                        row["validated_extraction"],
                        "security_economics",
                        "number_of_securities",
                    )
                    for row in pref_docs
                    if _explicit(
                        row["validated_extraction"],
                        "security_economics",
                        "number_of_securities",
                    )
                    is not None
                ),
                None,
            )
            if issue_price is not None and count is not None:
                lanes.append(
                    _lane(
                        state="READY_DILUTION_FINANCING",
                        family="DILUTION_FINANCING",
                        document_ids=[str(row["document_id"]) for row in pref_docs],
                        explicit_terms={
                            "issue_price_per_security": issue_price,
                            "security_count": count,
                        },
                        missing_inputs=[
                            "CURRENT_MARKET_PRICE",
                            "CURRENT_MARKET_CAP",
                            "CURRENT_FULLY_DILUTED_SHARE_COUNT",
                        ],
                        notes=[
                            "Dilution mechanics are explicit; current market and fully diluted capital structure remain deterministic downstream inputs."
                        ],
                    )
                )

    # Capital-deployment monitoring.
    fund_docs = [
        row
        for row in rows
        if "FUND_RAISE_OTHER"
        in row["validated_extraction"].get("transaction_families", [])
        and _explicit(
            row["validated_extraction"],
            "business_economics",
            "stated_use_of_proceeds",
        )
        is not None
    ]
    if fund_docs and not (
        symbol == "FCL"
        and _has_historical_monitor(
            [row["validated_extraction"] for row in fund_docs]
        )
    ):
        amount = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "consideration",
                    "total_consideration",
                )
                for row in fund_docs
                if _explicit(
                    row["validated_extraction"],
                    "consideration",
                    "total_consideration",
                )
                is not None
            ),
            None,
        )
        use = next(
            _explicit(
                row["validated_extraction"],
                "business_economics",
                "stated_use_of_proceeds",
            )
            for row in fund_docs
            if _explicit(
                row["validated_extraction"],
                "business_economics",
                "stated_use_of_proceeds",
            )
            is not None
        )
        progress = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                )
                for row in fund_docs
                if _explicit(
                    row["validated_extraction"],
                    "business_economics",
                    "capacity_or_operating_metric_disclosed",
                )
                is not None
            ),
            None,
        )
        missing = ["CURRENT_MARKET_PRICE", "CURRENT_MARKET_CAP"]
        if symbol == "NPST":
            missing.append("CURRENT_CAPITAL_DEPLOYMENT_UPDATE")
        if symbol == "DEVX":
            missing.append("OTHER_EXPLICIT_SOURCE_REQUIRED")
        lanes.append(
            _lane(
                state="READY_CAPITAL_DEPLOYMENT_MONITOR",
                family="CAPITAL_DEPLOYMENT_MONITOR",
                document_ids=[str(row["document_id"]) for row in fund_docs],
                explicit_terms={
                    "stated_raise_or_consideration": amount,
                    "stated_use_of_proceeds": use,
                    "deployment_or_operating_metric": progress,
                },
                missing_inputs=missing,
                notes=[
                    "Capital deployment is explicit; downstream payoff work must connect deployment to operating economics without assuming realization."
                ],
            )
        )

    # Rights issue.
    rights_docs = [
        row
        for row in rows
        if "RIGHTS_ISSUE"
        in row["validated_extraction"].get("transaction_families", [])
    ]
    if rights_docs:
        price = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "security_economics",
                    "issue_price_per_share",
                )
                for row in rights_docs
                if _explicit(
                    row["validated_extraction"],
                    "security_economics",
                    "issue_price_per_share",
                )
                is not None
            ),
            None,
        )
        ratio = next(
            (
                _explicit(
                    row["validated_extraction"],
                    "ratios_entitlement",
                    "exchange_ratio_text",
                )
                for row in rights_docs
                if _explicit(
                    row["validated_extraction"],
                    "ratios_entitlement",
                    "exchange_ratio_text",
                )
                is not None
            ),
            None,
        )
        state = (
            "READY_RIGHTS_PAYOFF"
            if price is not None and ratio is not None
            else "PARTIAL_RIGHTS_TERMS_REQUIRED"
        )
        missing = ["CURRENT_MARKET_PRICE", "CURRENT_MARKET_CAP"]
        if price is None:
            missing.append("RIGHTS_ISSUE_PRICE")
        if ratio is None:
            missing.append("RIGHTS_ENTITLEMENT_RATIO")
        record_date = next(
            (
                _explicit(
                    row["validated_extraction"], "dates", "record_date"
                )
                for row in rights_docs
                if _explicit(
                    row["validated_extraction"], "dates", "record_date"
                )
                is not None
            ),
            None,
        )
        if record_date is None:
            missing.append("RIGHTS_RECORD_DATE")
        lanes.append(
            _lane(
                state=state,
                family="RIGHTS_TERMS",
                document_ids=[str(row["document_id"]) for row in rights_docs],
                explicit_terms={
                    "issue_price_per_share": price,
                    "entitlement_ratio": ratio,
                    "record_date": record_date,
                },
                missing_inputs=missing,
                notes=[
                    "Rights payoff cannot be modeled until explicit price and entitlement terms exist."
                ],
            )
        )

    # Internal wholly-owned reorganisations.
    internal_docs = [
        row
        for row in rows
        if _scheme_internal(row["validated_extraction"])
    ]
    if internal_docs and not demerger_docs:
        lanes.append(
            _lane(
                state="PROCEDURAL_INTERNAL_REORGANISATION",
                family="INTERNAL_REORGANISATION",
                document_ids=[str(row["document_id"]) for row in internal_docs],
                explicit_terms={
                    "document_count": len(internal_docs),
                    "no_consideration_or_exchange_ratio": True,
                },
                missing_inputs=[],
                notes=[
                    "No standalone event-payoff model is justified from the current documents because the scheme is an internal wholly owned reorganisation."
                ],
            )
        )

    if not lanes:
        raise AlphaContractError(f"{symbol}: no registered L002 lane")

    states = {lane["readiness_state"] for lane in lanes}
    primary = next(state for state in STATE_PRECEDENCE if state in states)
    return {
        "symbol": symbol,
        "source_document_count": len(docs),
        "source_document_ids": sorted(docs),
        "payoff_model_lanes": sorted(
            lanes, key=lambda lane: STATE_PRECEDENCE.index(lane["readiness_state"])
        ),
        "primary_readiness_state": primary,
        "payoff_model_ready": any(
            lane["readiness_state"].startswith("READY_") for lane in lanes
        ),
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }


def build_transaction_term_synthesis(run: dict[str, Any]) -> dict[str, Any]:
    if run.get("run_id") != EXPECTED_RUN_ID:
        raise AlphaContractError("HG004 L002 requires frozen L001 run")
    if run.get("run_sha256") != EXPECTED_RUN_SHA:
        raise AlphaContractError("HG004 L002 L001 run SHA mismatch")
    if run.get("validated_output_count") != 19:
        raise AlphaContractError("HG004 L002 requires 19 validated outputs")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if run.get(field) is not False:
            raise AlphaContractError(f"HG004 L002 requires L001 {field}=false")

    grouped = _document_rows(run)
    rows = [
        _synthesize_symbol(symbol, grouped[symbol])
        for symbol in sorted(EXPECTED_SYMBOLS)
    ]

    observed_primary = {
        row["symbol"]: row["primary_readiness_state"] for row in rows
    }
    if observed_primary != EXPECTED_PRIMARY:
        raise AlphaContractError(
            f"HG004 L002 primary-state mismatch: {observed_primary}"
        )

    primary_counts = Counter(row["primary_readiness_state"] for row in rows)
    lane_counts = Counter(
        lane["readiness_state"]
        for row in rows
        for lane in row["payoff_model_lanes"]
    )
    ready_symbols = [
        row["symbol"] for row in rows if row["payoff_model_ready"]
    ]
    partial_symbols = [
        row["symbol"]
        for row in rows
        if row["primary_readiness_state"].startswith("PARTIAL_")
    ]
    procedural_symbols = [
        row["symbol"]
        for row in rows
        if row["primary_readiness_state"]
        in {"HISTORICAL_FINANCING_MONITOR", "PROCEDURAL_INTERNAL_REORGANISATION"}
    ]

    output = {
        "schema_version": 1,
        "synthesis_id": SYNTHESIS_ID,
        "classification": "DETERMINISTIC_TRANSACTION_TERM_SYNTHESIS_NOT_ALPHA",
        "source_run_id": EXPECTED_RUN_ID,
        "source_run_sha256": EXPECTED_RUN_SHA,
        "symbol_count": len(rows),
        "primary_readiness_state_counts": dict(sorted(primary_counts.items())),
        "lane_readiness_state_counts": dict(sorted(lane_counts.items())),
        "payoff_model_ready_symbol_count": len(ready_symbols),
        "payoff_model_ready_symbols": ready_symbols,
        "partial_terms_symbol_count": len(partial_symbols),
        "partial_terms_symbols": partial_symbols,
        "procedural_or_historical_symbol_count": len(procedural_symbols),
        "procedural_or_historical_symbols": procedural_symbols,
        "rows": rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["synthesis_sha256"] = digest(output)
    return output
