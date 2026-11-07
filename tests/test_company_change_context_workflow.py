from pathlib import Path

import pytest
import yaml

from marketlab.company_change import ChangeError
from marketlab.company_change_context import build_card, parse_actions


def test_context_failure_keeps_original_checkpoint_and_existing_cadence():
    path = Path(__file__).resolve().parents[1] / '.github/workflows/cc001-daily-operations.yml'
    workflow = yaml.safe_load(path.read_text())
    steps = workflow['jobs']['refresh-research-workspace']['steps']
    export = next(s['run'] for s in steps if s.get('name') == 'Export research desk and checkpoint durable state')
    assert 'if ! python -m marketlab.company_change_context' in export
    assert '--limit 3 --output-prefix' in export
    assert export.index('company_change_checkpoint save') < export.index('test "$context_ok" = true')
    assert export.index('push origin HEAD:refs/heads/cc001-state') < export.index('test "$context_ok" = true')
    assert "'price_context_sha256': context['report_sha256'] if context else None" in export
    assert "- cron: '47 14 * * *'" in path.read_text()
    assert '--limit 40' in next(s['run'] for s in steps if s.get('id') == 'intake')


def test_action_before_annual_eps_end_is_not_adjusted_twice():
    identity = {"symbol": "TEST", "isin": "INE000A01001", "scope": "CONSOLIDATED"}
    now = "2026-11-07T12:00:00Z"
    annual = {"identity": identity, "period_start": "2025-04-01", "period_end": "2026-03-31",
              "facts": {"diluted_eps": {"value": 5, "unit": "INR_per_share"}},
              "raw_sha256": "a" * 64, "source_url": "https://issuer.test/source",
              "known_at": now, "published_at": "2026-05-01T10:00:00Z"}
    quote = {"identity": identity, "price": 70, "quoted_at": "2026-11-06T10:00:00Z", "observed_at": now}
    actions = parse_actions([{"symbol": "TEST", "exDate": "01-Jun-2025", "subject": "Bonus 1:1"}],
                            "TEST", "2025-03-31", "2026-11-07")
    result = build_card(identity, [annual], "2026-03-31", quote, actions, now)
    assert result["price_over_reported_annual_eps"] == 14
    assert result["reverse_hurdle_scenarios"]


def test_invalid_identity_is_rejected_before_assembling_history():
    with pytest.raises(ChangeError, match="identity"):
        build_card({"symbol": "TEST", "isin": "bad", "scope": "CONSOLIDATED"}, [],
                   "2026-09-30", None, None, "2026-11-07T12:00:00Z")
