"""Audit future SEBI CAS clock divergence without changing a frozen trial."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.calendar_snapshot import load_calendar_snapshot
from marketlab.rm001_cas_future import audit_2026_frozen_cas_transition

DEFAULT = Path(
    "research/prospective/calendars/FY27-Q2-2026-09-06/"
    "NSE-CM-FY27Q2-v1.json"
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--calendar", type=Path, default=DEFAULT)
    args = p.parse_args()
    report = audit_2026_frozen_cas_transition(
        load_calendar_snapshot(args.calendar)
    )
    print(json.dumps({
        "audit": report["audit_id"],
        "source": report["sebi_original_document_url"],
        "effective": report["future_regime_effective_date"],
        "iceberg_rule_effective": report["future_iceberg_rule_effective_date"],
        "affected_2026_sessions": report["affected_frozen_2026_session_count"],
        "prospective_amendment_required": report[
            "prospective_amendment_required_before_new_rule_is_used"
        ],
        "frozen_trial_changed": report["active_scoring_or_decision_protocol_changed"],
        "audit_sha256": report["audit_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
