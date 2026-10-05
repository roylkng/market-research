from __future__ import annotations

import argparse
import json
from pathlib import Path

from marketlab.hg006_calibration import build_calibration_cohort


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--census",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    census=json.loads(args.census.read_text(encoding="utf-8"))
    output=build_calibration_cohort(census)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(
        json.dumps(output,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "selection_sha256":output["selection_sha256"],
        "selected_chronology_count":output["selected_chronology_count"],
        "selected_chronology_counts_by_family":output[
            "selected_chronology_counts_by_family"
        ],
        "selected_attachment_ready_counts_by_family":output[
            "selected_attachment_ready_counts_by_family"
        ],
        "selected_event_link_count":output["selected_event_link_count"],
    },sort_keys=True))


if __name__=="__main__":
    main()
