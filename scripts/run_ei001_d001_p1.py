from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from marketlab.ei001_context_audit import (
    EI001ContextError,
    build_p1_context_audit,
    build_source_pair_comparable,
    parse_single_quarter_source,
)
from marketlab.events import sha256_bytes
from marketlab.fa001_schema_audit import (
    FA001SchemaError,
    filing_candidates,
    select_audit_filings,
)
from marketlab.nse import NSEAcquisitionError, NSEClient

CURRENT_END="2026-06-30"
PRIOR_END="2025-06-30"


def _load(path:Path)->dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _retain(root:Path,*,kind:str,raw:bytes,url:str)->tuple[str,str]:
    sha=sha256_bytes(raw)
    suffix=Path(urlparse(url).path).suffix.lower() or ".bin"
    path=root/kind/"sha256"/f"{sha}{suffix}"
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=raw:
        raise RuntimeError(f"EI001 P1 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha,str(path)


def _earliest_unique(candidates):
    if not candidates:
        return None
    first_time=candidates[0].exchange_published_at_utc
    same=[row for row in candidates if row.exchange_published_at_utc==first_time]
    if len({row.source_url for row in same})!=1:
        raise EI001ContextError("same-timestamp prior-year source URL is ambiguous")
    return same[0]


def parse_args()->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--sample",type=Path,required=True)
    parser.add_argument("--raw-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--timeout-seconds",type=float,default=25.0)
    parser.add_argument("--attempts",type=int,default=4)
    parser.add_argument("--pause-seconds",type=float,default=0.03)
    return parser.parse_args()


def main()->int:
    args=parse_args()
    sample=_load(args.sample)
    rows=sample.get("symbols")
    if not isinstance(rows,list) or len(rows)!=48:
        raise TypeError("EI001 P1 sample must contain exactly 48 rows")

    client=NSEClient(timeout=args.timeout_seconds,attempts=args.attempts)
    observations=[]

    for index,row in enumerate(rows,start=1):
        symbol=str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("EI001 P1 sample row lacks symbol")
        observation={
            "symbol":symbol,
            "status":"PAIR_UNAVAILABLE",
            "reason":None,
            "current_source_available":False,
            "prior_candidate_available":False,
            "current":None,
            "prior":None,
            "comparable":None,
        }
        try:
            payload,discovery_raw=client.integrated_financial_filings_with_raw(symbol)
            discovery_sha,discovery_path=_retain(
                args.raw_dir,
                kind="discovery",
                raw=discovery_raw,
                url=NSEClient.INTEGRATED_FILING_ENDPOINT.url,
            )
            _,current_candidate=select_audit_filings(payload,symbol=symbol)
            if current_candidate is None:
                observation["reason"]="NO_CURRENT_Q1_CANDIDATE"
            else:
                observation["current_source_available"]=True
                prior_candidates=filing_candidates(
                    payload,
                    symbol=symbol,
                    period_end=PRIOR_END,
                    accounting_basis=current_candidate.accounting_basis,
                )
                prior_candidate=_earliest_unique(prior_candidates)
                if prior_candidate is None:
                    observation["reason"]="NO_SAME_BASIS_PRIOR_Q1_CANDIDATE"
                else:
                    observation["prior_candidate_available"]=True
                    current_raw=client.archive_bytes(current_candidate.source_url)
                    prior_raw=client.archive_bytes(prior_candidate.source_url)
                    current_sha,current_path=_retain(
                        args.raw_dir,kind="filings",raw=current_raw,
                        url=current_candidate.source_url,
                    )
                    prior_sha,prior_path=_retain(
                        args.raw_dir,kind="filings",raw=prior_raw,
                        url=prior_candidate.source_url,
                    )
                    current=parse_single_quarter_source(
                        current_raw,
                        candidate=current_candidate,
                        expected_period_end=CURRENT_END,
                    )
                    prior=parse_single_quarter_source(
                        prior_raw,
                        candidate=prior_candidate,
                        expected_period_end=PRIOR_END,
                    )
                    if current["raw_sha256"]!=current_sha or prior["raw_sha256"]!=prior_sha:
                        raise EI001ContextError("filing raw SHA mismatch")
                    comparable=build_source_pair_comparable(
                        current=current,
                        prior=prior,
                    )
                    observation.update({
                        "status":"PAIR_READY",
                        "reason":None,
                        "discovery_raw_sha256":discovery_sha,
                        "discovery_raw_path":discovery_path,
                        "current":{**current,"raw_path":current_path},
                        "prior":{**prior,"raw_path":prior_path},
                        "comparable":comparable,
                    })
        except (NSEAcquisitionError,FA001SchemaError,EI001ContextError) as exc:
            observation["status"]="FAILED"
            observation["reason"]=f"{type(exc).__name__}: {exc}"

        observations.append(observation)
        if index==1 or index%8==0 or index==len(rows):
            print(
                f"[ei001-p1] {index:02d}/48 {symbol} "
                f"status={observation['status']}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    audit=build_p1_context_audit(
        sample=sample,
        observations=observations,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"),
    )
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"ei001-d001-p1-audit.json").write_text(
        json.dumps(audit,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    summary={key:value for key,value in audit.items() if key!="observations"}
    (args.output/"summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
