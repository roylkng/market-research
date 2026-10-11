from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from marketlab.h021_p011_dividend_alert import (
    EXPECTED_SELECTION,
    RISK_ID,
    build_preentry_risk,
    replay_first_cohort,
)


def _source():
    intent=json.loads(Path(
        "research/prospective/h021/intents/2026-10-09-primary-entry-intent-v1.json"
    ).read_text(encoding="utf-8"))
    universe=json.loads(Path(
        "research/prospective/universes/FY27-Q2-2026-09-06.json"
    ).read_text(encoding="utf-8"))
    return intent,universe


def test_known_cash_dividend_flag_does_not_modify_frozen_h021_primary() -> None:
    intent,universe=_source()
    original=deepcopy(intent)
    result=build_preentry_risk(intent,universe)
    assert result["risk_id"]==RISK_ID
    assert result["frozen_selected_symbols"]==list(EXPECTED_SELECTION)
    assert result["publicly_identified_pre_entry_dividend_count"]==1
    assert result["publicly_identified_pre_entry_dividend_symbols"]==["VEDL"]
    by_symbol={row["symbol"]:row for row in result["source_risk_rows"]}
    assert by_symbol["VEDL"]["known_preentry_dividend_event"][
        "issuer_reported_per_share_inr"
    ]==5.0
    assert by_symbol["VEDL"]["known_preentry_dividend_event"][
        "reported_record_date_ist"
    ]=="2026-10-14"
    assert by_symbol["VEDL"]["known_preentry_dividend_event"][
        "official_exchange_dividend_terms_semantically_audited"
    ] is False
    assert all(
        row["20_session_total_return_comparable"] is False
        and row["60_session_total_return_comparable"] is False
        for row in result["source_risk_rows"]
    )
    assert all(by_symbol[s]["known_preentry_dividend_event"] is None
               for s in EXPECTED_SELECTION if s!="VEDL")
    assert result["original_h021_selection_unchanged"] is True
    assert result["other_symbols_complete_corporate_action_audit_performed"] is False
    assert result["stock_dividend_cashflows_accounted_for"] is False
    assert result["return_outcomes_opened"] is False
    assert result["portfolio_eligibility_allowed"] is False
    assert result["live_capital_allowed"] is False
    assert intent==original


def test_rejects_changes_to_frozen_cohort_and_universe() -> None:
    intent,universe=_source()
    intent["selected_observations"][0]["symbol"]="TRENT"
    with pytest.raises(ValueError,match="selection"):
        build_preentry_risk(intent,universe)
    intent,universe=_source()
    universe["members"][0]["isin"]="BAD"
    with pytest.raises(ValueError,match="invalid symbol or ISIN"):
        build_preentry_risk(intent,universe)


def test_replay_original_sources_and_output_do_not_claim_pnl(tmp_path:Path) -> None:
    original=replay_first_cohort(Path("."))
    output=tmp_path/"risk.json"
    base=[sys.executable,"scripts/build_h021_p011_dividend_alert.py","--output",str(output)]
    result=subprocess.run(base,check=True,capture_output=True,text=True)
    assert json.loads(output.read_text(encoding="utf-8"))==original
    assert json.loads(result.stdout)["live_capital_allowed"] is False
    subprocess.run(base+["--verify-existing"],check=True,capture_output=True,text=True)
    output.write_text(output.read_text(encoding="utf-8")+"garbage",encoding="utf-8")
    failed=subprocess.run(base+["--verify-existing"],check=False,capture_output=True,text=True)
    assert failed.returncode!=0
    assert "event warning changed" in failed.stderr
