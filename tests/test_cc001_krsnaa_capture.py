from __future__ import annotations

import runpy
from pathlib import Path

M = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/cc001_krsnaa_capture.py'))


def test_locator_requires_exact_issuer_and_unique_original_pdf():
    row = {'symbol':'KRSNAA','desc':'Annual Report','attchmntFile':'https://nsearchives.nseindia.com/corporate/a.pdf'}
    assert len(M['selected_disclosures']([row, row, {**row,'symbol':'OTHER'}])) == 1
    assert M['selected_disclosures']([{**row,'attchmntFile':'https://example.test/a.html'}]) == []


def test_locator_is_bounded_and_voice_summary_cannot_select_an_event():
    rows = [{'symbol':'KRSNAA','desc':'General Updates','attchmntText':'warrant equipment annual report',
             'attchmntFile':f'https://nsearchives.nseindia.com/corporate/{i}.pdf'} for i in range(100)]
    assert len(M['selected_disclosures'](rows)) <= 8
    assert not M['selected_disclosures']([{'symbol':'KRSNAA','desc':'Unrelated','voiceSummary':'annual report',
        'attchmntFile':'https://nsearchives.nseindia.com/corporate/a.pdf'}])


def test_case_identity_and_read_only_workflow():
    assert M['IDENTITY'] == {'symbol':'KRSNAA','isin':'INE08LI01020','scope':'CONSOLIDATED'}
    path = Path(__file__).resolve().parents[1] / '.github/workflows/cc001-krsnaa-underwriting.yml'
    text = path.read_text()
    assert 'contents: read' in text and 'schedule:' not in text and 'push origin' not in text
    assert 'CC001_MODEL_API_KEY' not in text
