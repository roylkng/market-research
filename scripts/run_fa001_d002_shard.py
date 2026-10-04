from __future__ import annotations

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse

from marketlab.events import sha256_bytes
from marketlab.fa001_facts import (
    EXPECTED_SS001_CENSUS_SHA,
    SHARD_COUNT,
    FA001FactError,
    deterministic_shard,
    parse_filing_facts,
    validate_d001_census,
)
from marketlab.fa001_schema_audit import FilingCandidate, select_audit_filings
from marketlab.nse import NSEAcquisitionError, NSEClient


def _load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _payload_rows(payload: object) -> list[dict]:
    if isinstance(payload,list):
        return [row for row in payload if isinstance(row,dict)]
    if isinstance(payload,dict):
        data=payload.get("data")
        if data is None:
            return []
        if not isinstance(data,list):
            raise TypeError("FA001 D002 discovery payload.data must be a list")
        return [row for row in data if isinstance(row,dict)]
    raise TypeError("FA001 D002 discovery payload must be object or list")


def _discovery_index(root: Path) -> tuple[dict[str,list[dict]], list[str]]:
    files=sorted((root/"raw"/"integrated-filing-discovery"/"sha256").glob("*"))
    if not files:
        raise FileNotFoundError("FA001 D002 preserved discovery pages are unavailable")
    index: dict[str,list[dict]]=defaultdict(list)
    hashes=[]
    for path in files:
        raw=path.read_bytes()
        sha=sha256_bytes(raw)
        if not path.name.startswith(sha):
            raise RuntimeError(f"FA001 D002 discovery filename/hash mismatch: {path}")
        hashes.append(sha)
        payload=json.loads(raw.decode("utf-8"))
        for row in _payload_rows(payload):
            symbol=str(row.get("symbol") or "").strip().upper()
            if symbol:
                index[symbol].append(row)
    return dict(index), sorted(hashes)


def _candidate_dict(candidate: FilingCandidate | None) -> dict | None:
    if candidate is None:
        return None
    return {
        "symbol":candidate.symbol,
        "accounting_basis":candidate.accounting_basis,
        "period_end":candidate.period_end,
        "exchange_published_at_utc":candidate.exchange_published_at_utc,
        "source_url":candidate.source_url,
        "discovery_row_sha256":candidate.discovery_row_sha256,
    }


def _retain(root: Path, raw: bytes, source_url: str) -> tuple[str,str]:
    sha=sha256_bytes(raw)
    suffix=Path(urlparse(source_url).path).suffix.lower() or ".bin"
    path=root/"filings"/"sha256"/f"{sha}{suffix}"
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=raw:
        raise RuntimeError(f"FA001 D002 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha,str(path)


def _acquire(
    *,
    client:NSEClient,
    candidate:FilingCandidate | None,
    filing_kind:str,
    raw_dir:Path,
) -> dict:
    if candidate is None:
        return {
            "status":"NO_CANDIDATE",
            "candidate":None,
            "raw_path":None,
            "parsed":None,
            "error":"NO_EXACT_PERIOD_CANDIDATE",
        }
    candidate_payload=_candidate_dict(candidate)
    try:
        raw=client.archive_bytes(candidate.source_url)
        sha,path=_retain(raw_dir,raw,candidate.source_url)
    except NSEAcquisitionError as exc:
        return {
            "status":"FETCH_FAILED",
            "candidate":candidate_payload,
            "raw_path":None,
            "parsed":None,
            "error":f"{type(exc).__name__}: {exc}",
        }
    try:
        parsed=parse_filing_facts(
            raw,
            candidate=candidate,
            filing_kind=filing_kind,
        )
        if parsed["raw_sha256"]!=sha:
            raise FA001FactError("raw SHA mismatch")
    except FA001FactError as exc:
        return {
            "status":"PARSE_FAILED",
            "candidate":candidate_payload,
            "raw_path":path,
            "parsed":None,
            "error":f"{type(exc).__name__}: {exc}",
        }
    return {
        "status":"READY",
        "candidate":candidate_payload,
        "raw_path":path,
        "parsed":parsed,
        "error":None,
    }


def parse_args()->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--d001-root",type=Path,required=True)
    parser.add_argument("--shard-index",type=int,required=True)
    parser.add_argument("--shard-count",type=int,default=SHARD_COUNT)
    parser.add_argument("--raw-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--timeout-seconds",type=float,default=25.0)
    parser.add_argument("--attempts",type=int,default=4)
    parser.add_argument("--pause-seconds",type=float,default=0.02)
    return parser.parse_args()


def main()->int:
    args=parse_args()
    if args.shard_count!=SHARD_COUNT:
        raise ValueError(f"FA001 D002 frozen shard_count must equal {SHARD_COUNT}")
    if not 0<=args.shard_index<SHARD_COUNT:
        raise ValueError("FA001 D002 shard_index out of range")

    census=_load(args.d001_root/"ss001-d001-census.json")
    rows=validate_d001_census(census)
    discovery, page_hashes=_discovery_index(args.d001_root)

    assigned=[
        row for row in rows
        if deterministic_shard(str(row["symbol"]))==args.shard_index
    ]
    client=NSEClient(timeout=args.timeout_seconds,attempts=args.attempts)
    output_rows=[]

    for index,row in enumerate(sorted(assigned,key=lambda x:str(x["symbol"])),start=1):
        symbol=str(row["symbol"]).upper()
        payload={"data":discovery.get(symbol,[])}
        annual_candidate,quarter_candidate=select_audit_filings(payload,symbol=symbol)
        annual=_acquire(
            client=client,
            candidate=annual_candidate,
            filing_kind="ANNUAL",
            raw_dir=args.raw_dir,
        )
        quarter=_acquire(
            client=client,
            candidate=quarter_candidate,
            filing_kind="QUARTER",
            raw_dir=args.raw_dir,
        )
        output_rows.append({
            "symbol":symbol,
            "isin":row.get("isin"),
            "company_name":row.get("company_name"),
            "in_existing_u001":bool(row.get("in_existing_u001")),
            "annual":annual,
            "quarter":quarter,
            "return_outcomes_opened":False,
            "portfolio_eligibility_allowed":False,
            "live_capital_allowed":False,
        })
        if index==1 or index%40==0 or index==len(assigned):
            print(
                f"[fa001-d002:{args.shard_index}] {index:03d}/{len(assigned)} "
                f"{symbol} annual={annual['status']} quarter={quarter['status']}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    result={
        "schema_version":1,
        "shard_index":args.shard_index,
        "shard_count":SHARD_COUNT,
        "source_census_sha256":EXPECTED_SS001_CENSUS_SHA,
        "discovery_page_sha256":page_hashes,
        "assigned_identity_count":len(assigned),
        "rows":output_rows,
        "return_outcomes_opened":False,
        "model_fitted":False,
        "portfolio_eligibility_allowed":False,
        "live_capital_allowed":False,
    }
    args.output.mkdir(parents=True,exist_ok=True)
    path=args.output/f"fa001-d002-shard-{args.shard_index}.json"
    path.write_text(
        json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(path)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
