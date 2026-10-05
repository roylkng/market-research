from __future__ import annotations

from marketlab.hg003_l002 import (
    build_company_event_synthesis,
    relevance_group,
    semantic_cluster,
    stage_group,
)


def _selection_and_run() -> tuple[dict, dict]:
    symbols = ["HINDCOPPER"] + [f"S{index:02d}" for index in range(27)]
    selection_rows = []
    l001_rows = []

    def add(
        symbol: str,
        category: str,
        timestamp: str,
        *,
        relevance: str = "DIRECT_LISTED_SECURITY",
        families: list[str] | None = None,
        stage: str = "TRANSACTION_COMPLETED",
        state: str = "TEXT_READY",
    ) -> None:
        thread_id = f"{symbol}::{category}"
        selection_rows.append(
            {
                "thread_id": thread_id,
                "symbol": symbol,
                "category": category,
                "selection_state": state,
                "selected_exchange_published_at_utc": (
                    timestamp if state == "TEXT_READY" else None
                ),
                "selected_announcement_id": (
                    f"A-{thread_id}" if state == "TEXT_READY" else None
                ),
                "selected_document_id": (
                    f"D-{thread_id}" if state == "TEXT_READY" else None
                ),
            }
        )
        if state == "TEXT_READY":
            l001_rows.append(
                {
                    "thread_id": thread_id,
                    "validated_extraction": {
                        "economic_relevance": relevance,
                        "transaction_families": families or [category],
                        "transaction_stage": stage,
                        "extraction_caveats": [],
                    },
                }
            )

    add(
        "HINDCOPPER",
        "OFFER_FOR_SALE",
        "",
        state="TEXT_UNAVAILABLE",
    )

    for index, symbol in enumerate(symbols[1:]):
        add(
            symbol,
            "SCHEME_REORGANISATION",
            f"2026-10-{(index % 20) + 1:02d}T10:00:00Z",
            families=["SCHEME_REORGANISATION"],
        )

    # Seven extra threads bring the frozen total from 28 to 35.
    # S00: later completion must supersede older OFFER_OPEN in the same BUYBACK_TENDER cluster.
    add(
        "S00",
        "BUYBACK",
        "2026-10-04T12:00:00Z",
        families=["BUYBACK", "TENDER_OFFER"],
        stage="TRANSACTION_COMPLETED",
    )
    add(
        "S00",
        "TENDER_OFFER",
        "2026-10-03T12:00:00Z",
        families=["BUYBACK", "TENDER_OFFER"],
        stage="OFFER_OPEN",
    )

    # S01: completed scheme must not erase independent active CIRP/acquisition cluster.
    add(
        "S01",
        "INSOLVENCY_RESOLUTION",
        "2026-10-04T12:00:00Z",
        relevance="LISTED_COMPANY_AS_ACQUIRER_OR_INVESTOR",
        families=["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT"],
        stage="REGULATORY_OR_COURT_APPROVED",
    )

    # S02: equal timestamps in one cluster exercise frozen thread_id ascending tie break.
    add(
        "S02",
        "BUYBACK",
        "2026-10-04T12:00:00Z",
        families=["BUYBACK", "TENDER_OFFER"],
        stage="TRANSACTION_COMPLETED",
    )
    add(
        "S02",
        "TENDER_OFFER",
        "2026-10-04T12:00:00Z",
        families=["BUYBACK", "TENDER_OFFER"],
        stage="OFFER_OPEN",
    )

    add(
        "S03",
        "RIGHTS_ISSUE",
        "2026-10-04T12:00:00Z",
        relevance="SUBSIDIARY_OR_INVESTEE_ONLY",
        families=["RIGHTS_ISSUE"],
        stage="ALLOTMENT_COMPLETED",
    )
    add(
        "S04",
        "PREFERENTIAL_WARRANT",
        "2026-10-04T12:00:00Z",
        families=["PREFERENTIAL_WARRANT"],
        stage="CANCELLED_OR_WITHDRAWN",
    )

    assert len(selection_rows) == 35
    assert len(l001_rows) == 34

    selection = {
        "selection_id": "HG003-D001-v1",
        "selection_sha256": (
            "ebc543464475ff9e409b1795c02272a818a3062cef8ad2bafcfafb5fcc30b536"
        ),
        "thread_count": 35,
        "symbol_count": 28,
        "rows": selection_rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    run = {
        "run_id": "HG003-L001-GPT56SOL-NATIVE-v1",
        "run_sha256": (
            "ce03af24e2bfa807f619a0db4db562d35cc96748cb0c5f75a1e1d7338c66809a"
        ),
        "validated_output_count": 34,
        "rows": l001_rows,
        "return_outcomes_opened": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    return selection, run


def test_semantic_cluster_and_stage_groups_are_frozen() -> None:
    assert semantic_cluster(["BUYBACK", "TENDER_OFFER"]) == "BUYBACK_TENDER"
    assert semantic_cluster(
        ["INSOLVENCY_RESOLUTION", "ACQUISITION_INVESTMENT"]
    ) == "INSOLVENCY_ACQUISITION"
    assert stage_group("BOARD_APPROVED") == "ACTIVE_FORWARD_STAGE"
    assert stage_group("TRANSACTION_COMPLETED") == "COMPLETED_STAGE"
    assert relevance_group("SUBSIDIARY_OR_INVESTEE_ONLY") == "INDIRECT_RELEVANCE"


def test_later_completion_supersedes_older_offer_open_within_cluster() -> None:
    selection, run = _selection_and_run()
    result = build_company_event_synthesis(selection=selection, l001_run=run)
    row = next(item for item in result["rows"] if item["symbol"] == "S00")
    cluster = next(
        item for item in row["clusters"] if item["semantic_cluster"] == "BUYBACK_TENDER"
    )
    assert cluster["latest_thread_id"] == "S00::BUYBACK"
    assert cluster["stage_group"] == "COMPLETED_STAGE"


def test_independent_active_cirp_survives_completed_scheme() -> None:
    selection, run = _selection_and_run()
    result = build_company_event_synthesis(selection=selection, l001_run=run)
    row = next(item for item in result["rows"] if item["symbol"] == "S01")
    assert row["company_catalyst_state"] == "ACTIVE_DIRECT_CATALYST"
    assert row["direct_active_cluster_count"] == 1
    assert row["completed_direct_cluster_count"] == 1


def test_equal_timestamp_uses_thread_id_ascending_tie_break() -> None:
    selection, run = _selection_and_run()
    result = build_company_event_synthesis(selection=selection, l001_run=run)
    row = next(item for item in result["rows"] if item["symbol"] == "S02")
    cluster = next(
        item for item in row["clusters"] if item["semantic_cluster"] == "BUYBACK_TENDER"
    )
    assert cluster["latest_thread_id"] == "S02::BUYBACK"
    assert cluster["stage_group"] == "COMPLETED_STAGE"


def test_indirect_thread_does_not_create_direct_catalyst() -> None:
    selection, run = _selection_and_run()
    result = build_company_event_synthesis(selection=selection, l001_run=run)
    row = next(item for item in result["rows"] if item["symbol"] == "S03")
    # S03 still has its base direct completed scheme, so the company remains completed-only;
    # the indirect rights issue is retained but does not become an active direct catalyst.
    assert row["company_catalyst_state"] == "COMPLETED_DIRECT_EVENT_ONLY"
    assert row["indirect_or_context_cluster_count"] == 1


def test_hindcopper_stays_explicitly_text_pending_and_all_threads_account() -> None:
    selection, run = _selection_and_run()
    result = build_company_event_synthesis(selection=selection, l001_run=run)
    row = next(item for item in result["rows"] if item["symbol"] == "HINDCOPPER")
    assert row["company_catalyst_state"] == "TEXT_PENDING"
    assert row["pending_thread_ids"] == ["HINDCOPPER::OFFER_FOR_SALE"]
    assert result["symbol_count"] == 28
    assert result["thread_count"] == 35
    assert result["validated_thread_count"] == 34
    assert all(result["threshold_passes"].values())
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
