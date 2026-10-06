from __future__ import annotations

from marketlab.alpha import digest
from marketlab.hg006_native_pilot import select_native_pilot


def _queue() -> dict:
    rows=[]
    for family,count in (
        ("PREFERENTIAL_WARRANT",738),
        ("SCHEME_REORGANISATION",710),
    ):
        prefix="A" if family=="PREFERENTIAL_WARRANT" else "B"
        for index in range(count):
            request_id=(f"{index:064x}" if prefix=="A" else f"{index+10000:064x}")
            rows.append({
                "request_id":request_id,
                "family":family,
                "document_id":"f"*64,
                "prompt_sha256":"a"*64,
            })
    q={
        "queue_id":"HG006-L001-P1-v1",
        "queue_sha256":"6732f5741ec6d9a2e1926a94d234c642871d454f0354d60dfa87cec3807ce934",
        "model_config_sha256":"043ec1f2d38aec7e72b24cfcbe864aebd83cda8b717d3c8c0fac2ecb3cafa51d",
        "request_count":1448,
        "requests":rows,
        "historical_terminal_labels_opened":False,
        "completion_probabilities_assigned":False,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    return q


def test_selects_first_ten_per_family_before_outputs() -> None:
    result=select_native_pilot(_queue())
    assert result["selected_request_count"]==20
    assert result["selected_counts_by_family"]=={
        "PREFERENTIAL_WARRANT":10,
        "SCHEME_REORGANISATION":10,
    }
    families=[row["family"] for row in result["rows"]]
    assert families.count("PREFERENTIAL_WARRANT")==10
    assert families.count("SCHEME_REORGANISATION")==10
    assert result["historical_terminal_labels_opened"] is False
    assert result["completion_probabilities_assigned"] is False


def test_selection_hash_is_deterministic() -> None:
    first=select_native_pilot(_queue())
    second=select_native_pilot(_queue())
    assert first["selection_sha256"]==second["selection_sha256"]
    assert first["selection_sha256"]==digest({
        key:value for key,value in first.items() if key!="selection_sha256"
    })
