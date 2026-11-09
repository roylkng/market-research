from __future__ import annotations

import runpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = runpy.run_path(str(ROOT / 'scripts/cc001_seamec_underwriting_capture.py'))


def test_discovery_does_not_substitute_other_issuer_or_voice_summary():
    choose = MODULE['selected_disclosures']
    rows = [
        {'symbol': 'OTHER', 'desc': 'Annual Report', 'attchmntFile': 'https://nsearchives.nseindia.com/a.pdf'},
        {'symbol': 'SEAMECLTD', 'desc': 'Routine', 'voiceSummary': 'Annual report', 'attchmntFile': 'https://nsearchives.nseindia.com/b.pdf'},
        {'symbol': 'SEAMECLTD', 'desc': 'Annual Report', 'attchmntFile': 'https://nsearchives.nseindia.com/c.pdf'},
    ]
    result = choose(rows)
    assert len(result) == 1
    assert result[0]['url'].endswith('c.pdf')
    assert len(result[0]['row_sha256']) == 64


def test_duplicate_or_already_listed_documents_not_fetched_twice():
    explicit = MODULE['FILES']['presentation_20261103']
    row = {'symbol': 'SEAMECLTD', 'desc': 'Annual Report Financial Results',
           'attchmntFile': 'https://nsearchives.nseindia.com/annual.pdf'}
    result = MODULE['selected_disclosures']([row, row, {'symbol': 'SEAMECLTD', 'desc': 'Annual Report', 'attchmntFile': explicit}])
    assert len(result) == 1


def test_malformed_rows_and_unsupported_formats_not_selected():
    assert MODULE['selected_disclosures']([None, 'bad', {'symbol': 'SEAMECLTD', 'desc': 'annual report', 'attchmntFile': None}, {'symbol': 'SEAMECLTD', 'desc': 'annual report', 'attchmntFile': 'https://nsearchives.nseindia.com/a.exe'}]) == []


def test_read_only_case_capture_does_not_activate_production_or_inference():
    text = (ROOT / '.github/workflows/cc001-underwriting-case.yml').read_text()
    assert 'contents: read' in text
    assert 'schedule:' not in text and 'push origin' not in text
    assert 'cc001_seamec_underwriting_capture.py' in text
    assert '--execute' not in text
    assert MODULE['IDENTITY']['isin'] == 'INE497B01018'
