from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from marketlab.ei001_context_audit import (
    EI001ContextError,
    build_context_audit,
    parse_comparative_quarter,
)
from marketlab.events import sha256_bytes
from marketlab.fa001_schema_audit import FA001SchemaError, select_audit_filings
from marketlab.nse import NSEAcquisitionError, NSEClient


def _load(path: Path) -> dict:
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
        raise RuntimeError(f"EI001 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha,str(path)


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
        raise TypeError("EI001 D001 sample must contain exactly 48 rows")
    client=NSEClient(timeout=args.timeout_seconds,attempts=args.attempts)
    observations=[]

    for index,row in enumerate(rows,start=1):
        symbol=str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("EI001 D001 sample row lacks symbol")
        try:
            payload,discovery_raw=client.integrated_financial_filings_with_raw(symbol)
            discovery_sha,discovery_path=_retain(
                args.raw_dir,
                kind="discovery",
                raw=discovery_raw,
                url=NSEClient.INTEGRATED_FILING_ENDPOINT.url,
            )
            _,candidate=select_audit_filings(payload,symbol=symbol)
            if candidate is None:
                observations.append({
                    "symbol":symbol,
                    "status":"UNAVAILABLE",
                    "reason":"NO_2026_06_30_CANDIDATE",
                    "discovery_raw_sha256":discovery_sha,
                    "discovery_raw_path":discovery_path,
                    "parsed":None,
                })
            else:
                raw=client.archive_bytes(candidate.source_url)
                raw_sha,raw_path=_retain(
                    args.raw_dir,kind="filings",raw=raw,url=candidate.source_url
                )
                parsed=parse_comparative_quarter(raw,candidate=candidate)
                if parsed["raw_sha256"]!=raw_sha:
                    raise EI001ContextError("filing raw SHA mismatch")
                observations.append({
                    "symbol":symbol,
                    "status":"READY",
                    "reason":None,
                    "discovery_raw_sha256":discovery_sha,
                    "discovery_raw_path":discovery_path,
                    "raw_path":raw_path,
                    "parsed":parsed,
                })
        except (NSEAcquisitionError,FA001SchemaError,EI001ContextError) as exc:
            observations.append({
                "symbol":symbol,
                "status":"FAILED",
                "reason":f"{type(exc).__name__}: {exc}",
                "parsed":None,
            })
        if index==1 or index%8==0 or index==len(rows):
            print(
                f"[ei001] {index:02d}/48 {symbol} status={observations[-1]['status']}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    audit=build_context_audit(
        sample=sample,
        observations=observations,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"),
    )
    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"ei001-d001-audit.json").write_text(
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
