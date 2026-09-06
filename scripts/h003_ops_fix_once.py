from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected one target in {path}, found {text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "src/marketlab/h003_review.py",
    '''DECISION_TIMESTAMP_UTC = "2026-09-06T12:21:06.431463Z"\nIST = ZoneInfo("Asia/Kolkata")\n''',
    '''DECISION_TIMESTAMP_UTC = "2026-09-06T12:21:06.431463Z"\nEXPECTED_COHORT_COMPANY_COUNT = 100\nEXPECTED_SOURCE_BEARING_COMPANY_COUNT = 97\nFROZEN_ZERO_SOURCE_SYMBOLS = ("BHEL", "ITC", "TRENT")\nIST = ZoneInfo("Asia/Kolkata")\n''',
)
replace_once(
    "src/marketlab/h003_review.py",
    '''        or document.get("expected_member_count") != 100\n        or document.get("processed_company_count") != 100\n''',
    '''        or document.get("expected_member_count") != EXPECTED_COHORT_COMPANY_COUNT\n        or document.get("processed_company_count") != EXPECTED_SOURCE_BEARING_COMPANY_COUNT\n''',
)

path = Path("tests/test_h003_review_operations.py")
text = path.read_text(encoding="utf-8")
text += '''\n\ndef test_frozen_h003_source_denominator_is_100_cohort_97_source_bearing():
    from marketlab.h003_review import (
        EXPECTED_COHORT_COMPANY_COUNT,
        EXPECTED_SOURCE_BEARING_COMPANY_COUNT,
        FROZEN_ZERO_SOURCE_SYMBOLS,
    )

    source_path = Path(
        "research/prospective/h003/FY27-Q2-2026-09-06/source-coverage-v1.json"
    )
    document = json.loads(source_path.read_text(encoding="utf-8"))
    records = document["records"]
    source_bearing = [record for record in records if record["source_count"] > 0]
    zero_source = sorted(
        record["symbol"] for record in records if record["source_count"] == 0
    )
    assert len(records) == EXPECTED_COHORT_COMPANY_COUNT == 100
    assert len(source_bearing) == EXPECTED_SOURCE_BEARING_COMPANY_COUNT == 97
    assert zero_source == sorted(FROZEN_ZERO_SOURCE_SYMBOLS) == ["BHEL", "ITC", "TRENT"]
'''
path.write_text(text, encoding="utf-8")
