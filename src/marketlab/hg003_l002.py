from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from marketlab.alpha import AlphaContractError, digest

SYNTHESIS_ID = "HG003-L002-v1"
EXPECTED_SELECTION_ID = "HG003-D001-v1"
EXPECTED_SELECTION_SHA = "ebc543464475ff9e409b1795c02272a818a3062cef8ad2bafcfafb5fcc30b536"
EXPECTED_L001_RUN_ID = "HG003-L001-GPT56SOL-NATIVE-v1"
EXPECTED_L001_RUN_SHA = "ce03af24e2bfa807f619a0db4db562d35cc96748cb0c5f75a1e1d7338c66809a"
EXPECTED_SYMBOL_COUNT = 28
EXPECTED_THREAD_COUNT = 35
EXPECTED_READY_COUNT = 34
EXPECTED_PENDING_THREAD = "HINDCOPPER::OFFER_FOR_SALE"

CURRENT_RELEVANCE = {
    "DIRECT_LISTED_SECURITY",
    "LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
}
INDIRECT_RELEVANCE = {"SUBSIDIARY_OR_INVESTEE_ONLY"}
CONTEXT_RELEVANCE = {"OTHER_CORPORATE_CONTEXT"}

ACTIVE_STAGES = {
    "PROPOSAL",
    "BOARD_APPROVED",
    "SHAREHOLDER_APPROVED",
    "REGULATORY_OR_COURT_APPROVED",
    "PUBLIC_ANNOUNCEMENT",
    "OFFER_OPEN",
    "RECORD_DATE_FIXED",
}
COMPLETED_STAGES = {
    "OFFER_CLOSED",
    "ALLOTMENT_COMPLETED",
    "TRANSACTION_COMPLETED",
}
CANCELLED_STAGES = {"CANCELLED_OR_WITHDRAWN"}
PROCEDURAL_STAGES = {"PROCEDURAL_UPDATE"}


def semantic_cluster(families: object) -> str:
    if not isinstance(families, list) or not families:
        raise AlphaContractError("HG003 L002 transaction families must be a non-empty list")
    values = {str(value) for value in families}
    if "BUYBACK" in values or "TENDER_OFFER" in values:
        return "BUYBACK_TENDER"
    if "INSOLVENCY_RESOLUTION" in values:
        return "INSOLVENCY_ACQUISITION"
    if "RIGHTS_ISSUE" in values:
        return "RIGHTS_ISSUE"
    if "PREFERENTIAL_WARRANT" in values:
        return "PREFERENTIAL_WARRANT"
    if "FUND_RAISE_OTHER" in values:
        return "FUND_RAISE_OTHER"
    if "SCHEME_REORGANISATION" in values:
        return "SCHEME_REORGANISATION"
    return "OTHER"


def stage_group(stage: str) -> str:
    if stage in ACTIVE_STAGES:
        return "ACTIVE_FORWARD_STAGE"
    if stage in COMPLETED_STAGES:
        return "COMPLETED_STAGE"
    if stage in CANCELLED_STAGES:
        return "CANCELLED_STAGE"
    if stage in PROCEDURAL_STAGES:
        return "PROCEDURAL_STAGE"
    raise AlphaContractError(f"HG003 L002 unsupported/unknown stage: {stage}")


def relevance_group(relevance: str) -> str:
    if relevance in CURRENT_RELEVANCE:
        return "CURRENT_ECONOMIC_RELEVANCE"
    if relevance in INDIRECT_RELEVANCE:
        return "INDIRECT_RELEVANCE"
    if relevance in CONTEXT_RELEVANCE:
        return "CONTEXT_ONLY"
    raise AlphaContractError(f"HG003 L002 unsupported relevance: {relevance}")


def _validate_selection(selection: dict[str, Any]) -> list[dict[str, Any]]:
    if selection.get("selection_id") != EXPECTED_SELECTION_ID:
        raise AlphaContractError("HG003 L002 requires frozen D001 selection")
    if selection.get("selection_sha256") != EXPECTED_SELECTION_SHA:
        raise AlphaContractError("HG003 L002 selection SHA mismatch")
    if selection.get("thread_count") != EXPECTED_THREAD_COUNT:
        raise AlphaContractError("HG003 L002 thread count mismatch")
    if selection.get("symbol_count") != EXPECTED_SYMBOL_COUNT:
        raise AlphaContractError("HG003 L002 symbol count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if selection.get(field) is not False:
            raise AlphaContractError(f"HG003 L002 requires selection {field}=false")
    rows = selection.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_THREAD_COUNT:
        raise AlphaContractError("HG003 L002 selection rows unavailable")
    return rows


def _validate_l001(run: dict[str, Any]) -> list[dict[str, Any]]:
    if run.get("run_id") != EXPECTED_L001_RUN_ID:
        raise AlphaContractError("HG003 L002 requires frozen L001 run")
    if run.get("run_sha256") != EXPECTED_L001_RUN_SHA:
        raise AlphaContractError("HG003 L002 L001 run SHA mismatch")
    if run.get("validated_output_count") != EXPECTED_READY_COUNT:
        raise AlphaContractError("HG003 L002 validated output count mismatch")
    for field in (
        "return_outcomes_opened",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if run.get(field) is not False:
            raise AlphaContractError(f"HG003 L002 requires L001 {field}=false")
    rows = run.get("rows")
    if not isinstance(rows, list) or len(rows) != EXPECTED_READY_COUNT:
        raise AlphaContractError("HG003 L002 L001 rows unavailable")
    return rows


def _company_state(cluster_rows: list[dict[str, Any]], pending_count: int) -> str:
    current = [
        row
        for row in cluster_rows
        if row["relevance_group"] == "CURRENT_ECONOMIC_RELEVANCE"
    ]
    if any(row["stage_group"] == "ACTIVE_FORWARD_STAGE" for row in current):
        return "ACTIVE_DIRECT_CATALYST"
    if any(row["stage_group"] == "PROCEDURAL_STAGE" for row in current):
        return "PROCEDURAL_DIRECT_REVIEW"
    if any(row["stage_group"] == "COMPLETED_STAGE" for row in current):
        return "COMPLETED_DIRECT_EVENT_ONLY"
    if any(row["stage_group"] == "CANCELLED_STAGE" for row in current):
        return "CANCELLED_DIRECT_EVENT_ONLY"
    if cluster_rows:
        return "INDIRECT_OR_CONTEXT_ONLY"
    if pending_count:
        return "TEXT_PENDING"
    raise AlphaContractError("HG003 L002 company has no thread evidence")


def build_company_event_synthesis(
    *,
    selection: dict[str, Any],
    l001_run: dict[str, Any],
) -> dict[str, Any]:
    selection_rows = _validate_selection(selection)
    l001_rows = _validate_l001(l001_run)

    selection_by_thread: dict[str, dict[str, Any]] = {}
    symbols: set[str] = set()
    for row in selection_rows:
        if not isinstance(row, dict):
            raise TypeError("HG003 L002 selection rows must be objects")
        thread_id = str(row.get("thread_id") or "")
        symbol = str(row.get("symbol") or "").upper()
        if not thread_id or not symbol or thread_id in selection_by_thread:
            raise AlphaContractError("HG003 L002 selection thread identity invalid")
        selection_by_thread[thread_id] = row
        symbols.add(symbol)
    if len(symbols) != EXPECTED_SYMBOL_COUNT:
        raise AlphaContractError("HG003 L002 unique symbol count mismatch")

    l001_by_thread: dict[str, dict[str, Any]] = {}
    for row in l001_rows:
        if not isinstance(row, dict):
            raise TypeError("HG003 L002 L001 rows must be objects")
        thread_id = str(row.get("thread_id") or "")
        if thread_id not in selection_by_thread or thread_id in l001_by_thread:
            raise AlphaContractError("HG003 L002 L001 thread identity mismatch")
        l001_by_thread[thread_id] = row

    ready_threads = {
        thread_id
        for thread_id, row in selection_by_thread.items()
        if row.get("selection_state") == "TEXT_READY"
    }
    pending_threads = {
        thread_id
        for thread_id, row in selection_by_thread.items()
        if row.get("selection_state") == "TEXT_UNAVAILABLE"
    }
    if ready_threads != set(l001_by_thread):
        raise AlphaContractError("HG003 L002 TEXT_READY/L001 accounting mismatch")
    if pending_threads != {EXPECTED_PENDING_THREAD}:
        raise AlphaContractError("HG003 L002 unresolved thread mismatch")

    per_symbol_threads: dict[str, list[dict[str, Any]]] = defaultdict(list)
    per_symbol_pending: Counter[str] = Counter()

    for thread_id, source in selection_by_thread.items():
        symbol = str(source["symbol"]).upper()
        if thread_id in pending_threads:
            per_symbol_pending[symbol] += 1
            continue

        lrow = l001_by_thread[thread_id]
        extraction = lrow.get("validated_extraction")
        if not isinstance(extraction, dict):
            raise AlphaContractError(f"{thread_id}: validated extraction unavailable")
        relevance = str(extraction.get("economic_relevance") or "")
        families = extraction.get("transaction_families")
        stage = str(extraction.get("transaction_stage") or "")
        cluster = semantic_cluster(families)

        per_symbol_threads[symbol].append(
            {
                "thread_id": thread_id,
                "upstream_category": source.get("category"),
                "selected_exchange_published_at_utc": source.get(
                    "selected_exchange_published_at_utc"
                ),
                "selected_announcement_id": source.get("selected_announcement_id"),
                "selected_document_id": source.get("selected_document_id"),
                "economic_relevance": relevance,
                "relevance_group": relevance_group(relevance),
                "corrected_transaction_families": list(families),
                "transaction_stage": stage,
                "stage_group": stage_group(stage),
                "semantic_cluster": cluster,
                "extraction_caveats": extraction.get("extraction_caveats", []),
            }
        )

    company_rows = []
    state_counts: Counter[str] = Counter()
    cluster_state_counts: Counter[str] = Counter()
    direct_active_total = 0

    for symbol in sorted(symbols):
        thread_rows = per_symbol_threads.get(symbol, [])
        cluster_members: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in thread_rows:
            cluster_members[row["semantic_cluster"]].append(row)

        cluster_rows = []
        for cluster, members in sorted(cluster_members.items()):
            ordered = sorted(
                members,
                key=lambda row: str(row["thread_id"]),
            )
            ordered.sort(
                key=lambda row: str(
                    row["selected_exchange_published_at_utc"] or ""
                ),
                reverse=True,
            )
            latest = ordered[0]
            cluster_state = latest["stage_group"]
            cluster_state_counts[cluster_state] += 1
            cluster_rows.append(
                {
                    "semantic_cluster": cluster,
                    "latest_thread_id": latest["thread_id"],
                    "latest_exchange_published_at_utc": latest[
                        "selected_exchange_published_at_utc"
                    ],
                    "latest_relevance": latest["economic_relevance"],
                    "relevance_group": latest["relevance_group"],
                    "latest_transaction_families": latest[
                        "corrected_transaction_families"
                    ],
                    "latest_transaction_stage": latest["transaction_stage"],
                    "stage_group": latest["stage_group"],
                    "member_thread_ids": sorted(
                        member["thread_id"] for member in members
                    ),
                    "superseded_thread_ids": [
                        member["thread_id"] for member in ordered[1:]
                    ],
                }
            )

        pending_count = int(per_symbol_pending[symbol])
        state = _company_state(cluster_rows, pending_count)
        state_counts[state] += 1

        active_direct = sum(
            row["relevance_group"] == "CURRENT_ECONOMIC_RELEVANCE"
            and row["stage_group"] == "ACTIVE_FORWARD_STAGE"
            for row in cluster_rows
        )
        completed_direct = sum(
            row["relevance_group"] == "CURRENT_ECONOMIC_RELEVANCE"
            and row["stage_group"] == "COMPLETED_STAGE"
            for row in cluster_rows
        )
        indirect_context = sum(
            row["relevance_group"] != "CURRENT_ECONOMIC_RELEVANCE"
            for row in cluster_rows
        )
        direct_active_total += active_direct

        company_rows.append(
            {
                "symbol": symbol,
                "company_catalyst_state": state,
                "semantic_cluster_count": len(cluster_rows),
                "direct_active_cluster_count": active_direct,
                "completed_direct_cluster_count": completed_direct,
                "indirect_or_context_cluster_count": indirect_context,
                "text_pending_thread_count": pending_count,
                "clusters": cluster_rows,
                "threads": sorted(thread_rows, key=lambda row: row["thread_id"]),
                "pending_thread_ids": sorted(
                    thread_id
                    for thread_id in pending_threads
                    if str(selection_by_thread[thread_id]["symbol"]).upper() == symbol
                ),
                "portfolio_eligibility_allowed": False,
                "live_capital_allowed": False,
            }
        )

    accounted_threads = sum(
        len(row["threads"]) + len(row["pending_thread_ids"])
        for row in company_rows
    )
    threshold_passes = {
        "exact_28_symbols": len(company_rows) == EXPECTED_SYMBOL_COUNT,
        "exact_35_thread_accounting": accounted_threads == EXPECTED_THREAD_COUNT,
        "exact_34_validated_threads": sum(len(row["threads"]) for row in company_rows)
        == EXPECTED_READY_COUNT,
        "exact_hindcopper_pending_thread": pending_threads == {EXPECTED_PENDING_THREAD},
        "every_cluster_has_latest_authority": all(
            cluster["latest_thread_id"]
            for row in company_rows
            for cluster in row["clusters"]
        ),
    }

    output = {
        "schema_version": 1,
        "synthesis_id": SYNTHESIS_ID,
        "classification": "HG002_COMPANY_SPECIAL_SITUATION_SYNTHESIS_NOT_ALPHA",
        "source_selection_sha256": EXPECTED_SELECTION_SHA,
        "source_l001_run_sha256": EXPECTED_L001_RUN_SHA,
        "symbol_count": len(company_rows),
        "thread_count": accounted_threads,
        "validated_thread_count": EXPECTED_READY_COUNT,
        "pending_thread_count": len(pending_threads),
        "company_catalyst_state_counts": dict(sorted(state_counts.items())),
        "cluster_stage_group_counts": dict(sorted(cluster_state_counts.items())),
        "direct_active_cluster_count": direct_active_total,
        "rows": company_rows,
        "threshold_passes": threshold_passes,
        "feasibility_pass": all(threshold_passes.values()),
        "promotion_allowed_to_detailed_term_extraction": all(
            threshold_passes.values()
        ),
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["synthesis_sha256"] = digest(output)
    return output
