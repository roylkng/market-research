"""Rebuild original-source HG009 evidence from pinned GitHub Actions ZIP artifacts.

Run after downloading immutable artifact IDs in l001_p004_original_replay. Does
not mutate any frozen prospective experiment or emit investment recommendations.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from marketlab.l001_p004_original_replay import ARTIFACT_IDS, replay_frozen_100

ROOT = Path(__file__).resolve().parents[1]
COHORT = ROOT / "research/hg009/hg009-d001-100-experimental-companies-v1.json"


def _artifact_path(directory: Path, artifact: int) -> Path:
    path = directory / f"github-actions-artifact-{artifact}.zip"
    if not path.is_file():
        raise FileNotFoundError(f"pinned source artifact not downloaded: {artifact}")
    return path


def _panel(directory: Path, artifact: int, filename: str) -> dict:
    with zipfile.ZipFile(_artifact_path(directory, artifact)) as archive:
        return json.loads(archive.read(filename))


def _source_xml(directory: Path, required_financial: set[str],
                required_shareholding: set[str]) -> dict[str, bytes]:
    originals: dict[str, bytes] = {}
    for artifact in ARTIFACT_IDS["fa001_shard_raw"]:
        with zipfile.ZipFile(_artifact_path(directory, artifact)) as archive:
            for name in archive.namelist():
                if not name.startswith("filings/sha256/") or not name.endswith(".xml"):
                    continue
                digest = name.rsplit("/", 1)[-1].removesuffix(".xml")
                if digest not in required_financial:
                    continue
                blob = archive.read(name)
                if hashlib.sha256(blob).hexdigest() != digest:
                    raise ValueError("original financial XBRL hash mismatch")
                existing = originals.get(digest)
                if existing is not None and existing != blob:
                    raise ValueError("duplicate hash changed issuer source bytes")
                originals[digest] = blob
    with zipfile.ZipFile(_artifact_path(directory, ARTIFACT_IDS["gf001"])) as archive:
        for digest in required_shareholding:
            path = f"raw/xbrl/sha256/{digest}.xml"
            blob = archive.read(path)
            if hashlib.sha256(blob).hexdigest() != digest:
                raise ValueError("original shareholder XBRL hash mismatch")
            existing = originals.get(digest)
            if existing is not None and existing != blob:
                raise ValueError("conflicting original source bytes")
            originals[digest] = blob
    missing = (required_financial | required_shareholding) - originals.keys()
    if missing:
        raise ValueError("original XBRL source files missing")
    return originals


def materialize(directory: Path) -> tuple[dict, dict[str, bytes]]:
    cohort = json.loads(COHORT.read_text(encoding="utf-8"))
    census = _panel(directory, ARTIFACT_IDS["census"], "ss001-d001-census.json")
    financial = _panel(directory, ARTIFACT_IDS["fa001"], "fa001-d002-panel.json")
    shares = _panel(directory, ARTIFACT_IDS["ss001"], "ss001-d004-panel.json")
    governance = _panel(directory, ARTIFACT_IDS["gf001"], "gf001-d002-panel.json")
    selected = {r["symbol"] for r in cohort["selected"]}
    by_financial = {r["symbol"]: r for r in financial["rows"] if r["symbol"] in selected}
    by_shares = {r["symbol"]: r for r in shares["rows"] if r["symbol"] in selected}
    financial_shas = {
        by_financial[symbol][period]["parsed"]["raw_sha256"]
        for symbol in selected for period in ("annual", "quarter")
    }
    share_shas = {by_shares[symbol]["raw_sha256"] for symbol in selected}
    originals = _source_xml(directory, financial_shas, share_shas)
    report = replay_frozen_100(cohort, census, financial, shares, governance, originals)
    return report, {k: v for k, v in originals.items() if k in financial_shas | share_shas}


def _write_source_pack(path: Path, originals: dict[str, bytes]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, mode="w", compression=zipfile.ZIP_DEFLATED,
                         compresslevel=9) as archive:
        for name, raw in sorted(originals.items()):
            info = zipfile.ZipInfo(f"sha256/{name}.xml", date_time=(2026, 10, 18, 0, 0, 0))
            archive.writestr(
                info, raw, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9
            )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--original-pack", type=Path)
    args = parser.parse_args()
    report, sources = materialize(args.zip_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    if args.original_pack:
        _write_source_pack(args.original_pack, sources)
    print(json.dumps({
        "company_count": report["company_count"],
        "xml_sha_verified": report["original_xml_sha256_checked"],
        "numeric_facts_replayed": report["original_numeric_xbrl_values_replayed"],
        "reported_issued_shares": report["issued_share_count_ready"],
        "source_cap_eligible": report["share_count_cap_source_eligible"],
        "owner_cash_complete": report["sector_specific_valuation_ready_count"],
        "report_sha256": report["report_sha256"],
        "source_pack_sha256": (
            hashlib.sha256(args.original_pack.read_bytes()).hexdigest()
            if args.original_pack else None
        ),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
