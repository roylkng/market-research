"""Freeze one future original-exchange first-seen corporate-event forecast.

Usage requires a real, independent stage-review receipt and exact original
source bytes. The resulting file MUST be Git-committed before any terminal
announcement. Merely creating a local JSON never proves prospectivity.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.hg008_event_forecast import freeze_new_event_forecast
from scripts.build_hg008_event_baselines import build


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root",type=Path,default=Path("."))
    parser.add_argument("--event",type=Path,required=True)
    parser.add_argument("--original-source",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    event=json.loads(args.event.read_text(encoding="utf-8"))
    if not isinstance(event,dict):
        raise TypeError("new event must be structured original-source record")
    original=args.original_source.read_bytes()
    baseline=build(args.repo_root)
    event_forecast=freeze_new_event_forecast(
        baseline,
        event=event,
        original_notice_bytes=original,
        forecast_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"),
    )
    if args.out.exists():
        raise FileExistsError("first-seen source forecast cannot be overwritten")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("x",encoding="utf-8") as stream:
        json.dump(event_forecast,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "forecast_id":event_forecast["forecast_id"],
        "symbol":event_forecast["symbol"],
        "track":event_forecast["track"],
        "horizon":event_forecast["horizon_days"],
        "probability":event_forecast["probability"],
        "forecast_record_sha256":event_forecast["packet_sha256"],
        "git_commit_before_outcome_verified":False,
        "current_stock_return_prediction":False,
        "live_capital_allowed":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
