from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path

from marketlab.events import sha256_bytes
from marketlab.nse import NSEAcquisitionError, NSEClient
from marketlab.ss001_size import (
    SS001SizeError,
    build_company_size_panel,
    parse_trade_info_market_cap,
)


def _load(path: Path) -> dict:
    payload=json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload,dict):
        raise TypeError(f"JSON payload must be an object: {path}")
    return payload


def _retain(root:Path,raw:bytes)->tuple[str,str]:
    sha=sha256_bytes(raw)
    path=root/"quote-trade-info"/"sha256"/f"{sha}.json"
    path.parent.mkdir(parents=True,exist_ok=True)
    if path.exists() and path.read_bytes()!=raw:
        raise RuntimeError(f"SS001 D003 content-addressed collision: {path}")
    path.write_bytes(raw)
    return sha,str(path)


def parse_args()->argparse.Namespace:
    parser=argparse.ArgumentParser()
    parser.add_argument("--d001-census",type=Path,required=True)
    parser.add_argument("--raw-dir",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    parser.add_argument("--timeout-seconds",type=float,default=20.0)
    parser.add_argument("--attempts",type=int,default=3)
    parser.add_argument("--pause-seconds",type=float,default=0.02)
    return parser.parse_args()


def main()->int:
    args=parse_args()
    census=_load(args.d001_census)
    rows=census.get("rows")
    if not isinstance(rows,list):
        raise TypeError("SS001 D003 D001 rows must be a list")

    client=NSEClient(timeout=args.timeout_seconds,attempts=args.attempts)
    acquired=[]
    total=len(rows)

    for index,row in enumerate(rows,start=1):
        if not isinstance(row,dict):
            raise TypeError("SS001 D003 D001 row must be an object")
        symbol=str(row.get("symbol") or "").strip().upper()
        if not symbol:
            raise ValueError("SS001 D003 D001 row lacks symbol")
        try:
            payload,raw=client.quote_equity_trade_info_with_raw(symbol)
            raw_sha,raw_path=_retain(args.raw_dir,raw)
            parsed=parse_trade_info_market_cap(
                payload,
                symbol=symbol,
                raw=raw,
            )
            if parsed["raw_sha256"]!=raw_sha:
                raise SS001SizeError("trade-info raw SHA mismatch")
            acquired.append({
                **parsed,
                "raw_path":raw_path,
            })
        except (NSEAcquisitionError,SS001SizeError) as exc:
            acquired.append({
                "symbol":symbol,
                "status":"SOURCE_UNAVAILABLE",
                "total_market_cap_inr_crore":None,
                "free_float_market_cap_inr_crore":None,
                "free_float_fraction":None,
                "raw_sha256":None,
                "raw_path":None,
                "error":f"{type(exc).__name__}: {exc}",
            })

        if index==1 or index%50==0 or index==total:
            print(
                f"[size] {index:04d}/{total} {symbol} "
                f"status={acquired[-1]['status']}",
                flush=True,
            )
        if args.pause_seconds:
            time.sleep(args.pause_seconds)

    panel=build_company_size_panel(
        d001_census=census,
        acquired_rows=acquired,
        captured_at_utc=datetime.now(UTC).isoformat().replace("+00:00","Z"),
    )

    args.output.mkdir(parents=True,exist_ok=True)
    (args.output/"ss001-d003-size-panel.json").write_text(
        json.dumps(panel,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    summary={key:value for key,value in panel.items() if key!="rows"}
    (args.output/"summary.json").write_text(
        json.dumps(summary,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+"\n",
        encoding="utf-8",
    )
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
