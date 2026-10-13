"""Resolve actual SC001 market observation window before source acquisition.

The timestamp is taken from the running GitHub runner, not the upstream
event time or an exchange report filename. Workflow_run is an independent
wake-up only. This command does not fetch a market source.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path

from marketlab.ae001_sc001_window import resolve_sc001_source_window


def main() -> None:
    event = os.environ.get("GITHUB_EVENT_NAME", "workflow_dispatch")
    upstream_branch = os.environ.get("SC001_UPSTREAM_HEAD_BRANCH") or None
    result = resolve_sc001_source_window(
        observed_at_utc=datetime.now(UTC),
        event_name=event,
        upstream_head_branch=upstream_branch,
    )
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with Path(output).open("a", encoding="utf-8") as stream:
            stream.write(f"date={result['date_ist']}\n")
            stream.write(f"state={result['state']}\n")
    print(json.dumps(result, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
