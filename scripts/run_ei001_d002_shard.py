from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from marketlab.ei001_context_audit import EI001ContextError, parse_single_quarter_source
from marketlab.ei001_full_market import build_comparable_from_fa_current
from marketlab.events import sha256_bytes
from marketlab.fa001_facts import SHARD_COUNT, deterministic_shard
from marketlab.fa001_schema_audit import FA001SchemaError, filing_candidates
from marketlab.nse import NSEAcquisitionError, NSEClient

PRIOR_END="2025-06-30"


def _load(path:Path)->dict:
    p=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(p,dict): raise TypeError(f"JSON payload must be object: {path}")
    return p


def _retain(root:Path,raw:bytes,url:str)->tuple[str,str]:
    sha=sha256_bytes(raw)
    suffix=Path(urlparse(url).path).suffix.lower() or ".bin"
    path=root/"filings"/"sha256"/f"{sha}{suffix}"
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=raw: raise RuntimeError(f"EI001 collision: {path}")
    path.write_bytes(raw)
    return sha,str(path)


def _earliest_unique(candidates):
    if not candidates: return None
    rows=sorted(candidates,key=lambda x:(x.exchange_published_at_utc,x.source_url))
    t=rows[0].exchange_published_at_utc
    first=[x for x in rows if x.exchange_published_at_utc==t]
    if len({x.source_url for x in first})!=1:
        raise EI001ContextError("same-timestamp prior source is ambiguous")
    return first[0]


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument("--fa-panel",type=Path,required=True)
    p.add_argument("--shard-index",type=int,required=True)
    p.add_argument("--shard-count",type=int,default=SHARD_COUNT)
    p.add_argument("--raw-dir",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--timeout-seconds",type=float,default=25.0)
    p.add_argument("--attempts",type=int,default=4)
    p.add_argument("--pause-seconds",type=float,default=0.01)
    return p.parse_args()


def main()->int:
    args=parse_args()
    if args.shard_count!=SHARD_COUNT: raise ValueError(f"EI001 D002 requires shard_count={SHARD_COUNT}")
    fa=_load(args.fa_panel)
    if fa.get("panel_sha256")!="cb8a408b6904799750a5aa08210f909ae8b285005273b5588fb1f8b7a6019124":
        raise ValueError("EI001 D002 frozen FA panel mismatch")
    rows=fa.get("rows")
    if not isinstance(rows,list) or len(rows)!=2319: raise TypeError("EI001 D002 FA rows unavailable")
    assigned=[r for r in rows if isinstance(r,dict) and deterministic_shard(str(r.get("symbol") or ""))==args.shard_index]
    client=NSEClient(timeout=args.timeout_seconds,attempts=args.attempts)
    output=[]
    for i,base in enumerate(sorted(assigned,key=lambda x:str(x["symbol"])),1):
        symbol=str(base["symbol"]).upper()
        q=base.get("quarter")
        current_ready=isinstance(q,dict) and q.get("status")=="READY" and isinstance(q.get("parsed"),dict)
        row={
            "symbol":symbol,
            "status":"CURRENT_UNAVAILABLE" if not current_ready else "PRIOR_UNAVAILABLE",
            "reason":"CURRENT_Q1_NOT_READY" if not current_ready else None,
            "prior_candidate_available":False,
            "current":None,
            "prior":None,
            "comparable":None,
        }
        if current_ready:
            current_parsed=q["parsed"]
            current_facts=current_parsed.get("facts")
            candidate=q.get("candidate")
            if not isinstance(current_facts,dict) or not isinstance(candidate,dict):
                raise TypeError(f"{symbol}: current FA quarter incomplete")
            row["current"]={
                "source_url":current_parsed.get("source_url"),
                "raw_sha256":current_parsed.get("raw_sha256"),
                "accounting_basis":current_parsed.get("accounting_basis"),
                "period_end":current_parsed.get("period_end"),
                "facts":{k:current_facts.get(k) for k in ("revenue","pat","pbt","finance_costs","depreciation","basic_eps")},
            }
            try:
                payload,_=client.integrated_financial_filings_with_raw(symbol)
                prior=_earliest_unique(filing_candidates(
                    payload,
                    symbol=symbol,
                    period_end=PRIOR_END,
                    accounting_basis=str(candidate["accounting_basis"]),
                ))
                if prior is None:
                    row["reason"]="NO_SAME_BASIS_PRIOR_Q1_CANDIDATE"
                else:
                    row["prior_candidate_available"]=True
                    raw=client.archive_bytes(prior.source_url)
                    sha,path=_retain(args.raw_dir,raw,prior.source_url)
                    parsed=parse_single_quarter_source(raw,candidate=prior,expected_period_end=PRIOR_END)
                    if parsed["raw_sha256"]!=sha: raise EI001ContextError("prior raw SHA mismatch")
                    row.update({
                        "status":"PAIR_READY",
                        "reason":None,
                        "prior":{**parsed,"raw_path":path},
                        "comparable":build_comparable_from_fa_current(current_facts=current_facts,prior=parsed),
                    })
            except (NSEAcquisitionError,FA001SchemaError,EI001ContextError) as exc:
                row["status"]="FAILED"
                row["reason"]=f"{type(exc).__name__}: {exc}"
        output.append(row)
        if i==1 or i%50==0 or i==len(assigned):
            print(f"[ei001-d002:{args.shard_index}] {i:03d}/{len(assigned)} {symbol} {row['status']}",flush=True)
        if args.pause_seconds: time.sleep(args.pause_seconds)
    payload={
        "schema_version":1,
        "panel_id":"EI001-D002-v1",
        "shard_index":args.shard_index,
        "shard_count":SHARD_COUNT,
        "assigned_identity_count":len(assigned),
        "captured_at_utc":datetime.now(UTC).isoformat().replace("+00:00","Z"),
        "rows":output,
        "return_outcomes_opened":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/f"ei001-d002-shard-{args.shard_index}.json"
    path.write_text(json.dumps(payload,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",encoding="utf-8")
    return 0


if __name__=="__main__": raise SystemExit(main())
