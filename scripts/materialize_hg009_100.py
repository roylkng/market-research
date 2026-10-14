"""Freeze or verify the distinct 100-name NSE full-market development cohort."""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
from pathlib import Path

from marketlab.hg009_100 import (
    FROZEN_SOURCE_SHA,
    build_hg009_100,
    load_hg001_router,
    validate_hg009_100,
)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--source", type=Path, default=Path(
            "research/hg009/original-hg001-d001-router-20261005.json.gz"
        ),
    )
    p.add_argument(
        "--archived-original", type=Path, default=Path(
            "research/hg009/original-hg001-d001-router-20261005.json.gz"
        ),
    )
    p.add_argument(
        "--output", type=Path, default=Path(
            "research/hg009/hg009-d001-100-experimental-companies-v1.json"
        ),
    )
    p.add_argument("--check", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    source = load_hg001_router(args.source)
    cohort = build_hg009_100(source)
    validate_hg009_100(cohort, source=source)
    original_bytes = (
        gzip.decompress(args.source.read_bytes())
        if args.source.suffix == ".gz"
        else args.source.read_bytes()
    )
    source_sha256 = hashlib.sha256(original_bytes).hexdigest()
    canonical_source = (
        json.dumps(source, sort_keys=True, separators=(",", ":"),
                   ensure_ascii=False, allow_nan=False).encode("utf-8")
    )
    # Retain the ORIGINAL exact source bytes, rather than replacing original
    # formatting with a later canonical dump.
    if source_sha256 != hashlib.sha256(original_bytes).hexdigest():
        raise SystemExit("Original source bytes changed while materializing")
    if not canonical_source:
        raise SystemExit("Original canonical HG001 source is empty")
    source_zip = gzip.compress(original_bytes, compresslevel=9, mtime=0)
    report = (
        json.dumps(
            cohort, sort_keys=True, indent=2,
            ensure_ascii=False, allow_nan=False,
        ) + "\n"
    )
    if args.check:
        if (
            not args.archived_original.is_file()
            or args.archived_original.read_bytes() != source_zip
        ):
            raise SystemExit("HG009 permanent original source gzip drifted")
        if not args.output.exists() or args.output.read_text("utf-8") != report:
            raise SystemExit("HG009 signed 100-company cohort differs")
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.archived_original.parent.mkdir(parents=True, exist_ok=True)
        if (
            args.archived_original.exists()
            and args.archived_original.read_bytes() != source_zip
        ):
            raise SystemExit("HG009 original source archive cannot be overwritten")
        if args.output.exists() and args.output.read_text("utf-8") != report:
            raise SystemExit("HG009 signed company cohort cannot be overwritten")
        args.archived_original.write_bytes(source_zip)
        args.output.write_text(report, encoding="utf-8")

    print(json.dumps({
        "state": "VERIFIED" if args.check else "MATERIALIZED",
        "trial": cohort["cohort_id"],
        "source_router_sha256": FROZEN_SOURCE_SHA,
        "original_router_bytes_sha256": source_sha256,
        "selected": cohort["selected_count"],
        "three_lane": cohort["selected_3lane_count"],
        "two_lane": cohort["selected_2lane_count"],
        "cohort_sha256": cohort["cohort_sha256"],
        "live_capital_allowed": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
