"""Score one mature first-seen official transaction event, never stock returns.

Resolution is a separate independently source-reviewed attestation. Outcome
not observed is censored, NOT negative unless continuous official coverage
and independent omission review are documented.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

from marketlab.hg008_event_score import score_matured_event


def main() -> None:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--forecast",type=Path,required=True)
    parser.add_argument("--terminal-evidence",type=Path,required=True)
    parser.add_argument("--out",type=Path,required=True)
    args=parser.parse_args()
    forecast=json.loads(args.forecast.read_text(encoding="utf-8"))
    evidence=json.loads(args.terminal_evidence.read_text(encoding="utf-8"))
    if not isinstance(forecast,dict) or not isinstance(evidence,dict):
        raise TypeError("forecast and terminal evidence require JSON objects")
    scored=score_matured_event(
        forecast,evidence,
        evaluated_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z")
    )
    if args.out.exists():
        raise FileExistsError("scored forecast evidence may not be overwritten")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    with args.out.open("x",encoding="utf-8") as stream:
        json.dump(scored,stream,indent=2,sort_keys=True,allow_nan=False)
        stream.write("\n")
    print(json.dumps({
        "score_id":scored["score_id"],
        "episode":scored["issuer_episode_id"],
        "state":scored["score_state"],
        "brier_score":scored["brier_score"],
        "validated_company_out_of_sample_skill":False,
        "stock_return_prediction":False,
        "live_capital_allowed":False,
    },sort_keys=True))


if __name__=="__main__":
    main()
