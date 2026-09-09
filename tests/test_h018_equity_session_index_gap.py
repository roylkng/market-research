import json
import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import h018_checkpoint_market as market
import run_h018_low_volatility_50 as h018


def test_equity_session_index_gap_is_a_complete_checkpoint(tmp_path):
    day = date(2015, 3, 12)
    path = tmp_path / "checkpoints" / f"{day.isoformat()}.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": market.CHECKPOINT_SCHEMA,
                "date": day.isoformat(),
                "status": "EQUITY_SESSION_INDEX_GAP",
                "bhavcopy": {"raw_path": "raw/example", "sha256": "example"},
            }
        )
    )
    assert market._complete_checkpoint(tmp_path, day)["status"] == "EQUITY_SESSION_INDEX_GAP"


def test_unknown_checkpoint_status_still_fails_closed(tmp_path):
    day = date(2015, 3, 12)
    path = tmp_path / "checkpoints" / f"{day.isoformat()}.json"
    path.parent.mkdir(parents=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": market.CHECKPOINT_SCHEMA,
                "date": day.isoformat(),
                "status": "EQUITY_SESSION_GUESSED",
            }
        )
    )
    assert market._complete_checkpoint(tmp_path, day) is None


def test_required_benchmark_endpoint_gate_accepts_real_rows():
    cohorts = [{"entry_date": "2014-12-01", "exit_date": "2015-05-29"}]
    index = {
        date(2014, 12, 1): {"open": 1.0, "close": 1.0},
        date(2015, 5, 29): {"open": 1.0, "close": 1.0},
    }
    assert h018.require_outcome_benchmark_dates(cohorts, index) == [
        date(2014, 12, 1),
        date(2015, 5, 29),
    ]


def test_required_benchmark_endpoint_gate_rejects_gap():
    cohorts = [{"entry_date": "2014-12-01", "exit_date": "2015-05-29"}]
    with pytest.raises(ValueError, match="2015-05-29"):
        h018.require_outcome_benchmark_dates(
            cohorts, {date(2014, 12, 1): {"open": 1.0, "close": 1.0}}
        )
