"""Recover only the original 2026-10-30 H021 machine seal from GitHub Actions.

Incident workflow run 41104775260 completed the frozen acquisition and sealing
before an unrelated downstream Git race prevented the original anchor. This is
not an alternative collector. It never contacts forecast/market providers,
changes the original timestamp, or opens H021 outcomes.
"""
from __future__ import annotations

import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = "roylkng/market-research"
RUN = 41104775260
ARTIFACT = 13000832780
ZIP_SHA = "24828411e22ac7f44981ecf60ef59dcf94134d265ef7e33a905b46ce123f264e"
GZIP_SHA = "38261b07b9081fe9e21a5a6800f6731464db465820f6944d4025d14aac0d9abc"
JSON_SHA = "b48bd8ec00075e4d8fc74a1ec5a575d8f8f3c44b061c2f70fb8a12bc737842f4"
UNIVERSE_SHA = "8026e81faee3e913d2fba1dba72d60603b69fa07"
SOURCE = "H021-public-stockanalysis-spgi-plus-trendlyne-secondary-v1"
DATE = "2026-10-30"
STATES = {"OBSERVED", "PARTIAL", "NO_COVERAGE", "SOURCE_BLOCKED", "IDENTITY_UNRESOLVED"}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def demand(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def load_original_actions_zip() -> bytes:
    """Fetch only the already-produced original GitHub Actions artifact."""
    token = os.environ["GITHUB_TOKEN"]

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    url = f"https://api.github.com/repos/{REPO}/actions/artifacts/{ARTIFACT}/zip"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}",
                 "Accept": "application/vnd.github+json",
                 "User-Agent": "H021-original-machine-seal-recovery"},
    )
    try:
        urllib.request.build_opener(NoRedirect()).open(req, timeout=30)
        raise ValueError("Expected GitHub artifact redirect")
    except urllib.error.HTTPError as exc:
        if exc.code not in (301, 302, 303, 307, 308):
            raise
        location = exc.headers.get("Location")
        demand(bool(location), "GitHub did not provide original artifact location")
    parsed = urllib.parse.urlsplit(location)
    demand(parsed.scheme == "https" and parsed.hostname != "api.github.com",
           "Artifact redirect must be HTTPS and must not reuse GitHub token")
    # The bearer token is NOT forwarded to the blob host.
    with urllib.request.urlopen(location, timeout=60) as response:
        return response.read()


def main() -> None:
    root = Path.cwd()
    capture_dir = root / "research/prospective/h021/captures"
    name = "2026-10-30-full-u001-v1"
    output = {
        "sealed-capture.json.gz": capture_dir / (name + ".json.gz"),
        "sealed-capture.manifest.json": capture_dir / (name + ".manifest.json"),
        "sealed-capture.md": capture_dir / (name + ".md"),
    }
    comp_path = root / "research/prospective/h021/comparisons/2026-10-30-primary-revision-v1.json"
    for path in (*output.values(), comp_path):
        demand(not path.exists(), f"Never overwrite or duplicate a dated observation: {path}")
    archive = load_original_actions_zip()
    demand(digest(archive) == ZIP_SHA, "Original workflow artifact ZIP SHA mismatch")
    with zipfile.ZipFile(io.BytesIO(archive)) as z:
        expected = {"capture-draft.json", "sealed-capture.json.gz",
                    "sealed-capture.manifest.json", "sealed-capture.md",
                    "session-decision.json", "source-evidence.json"}
        demand(set(z.namelist()) == expected, "Original workflow artifact member set drift")
        original = {key: z.read(key) for key in expected}
    gz = original["sealed-capture.json.gz"]
    canonical = gzip.decompress(gz)
    capture = json.loads(canonical)
    manifest = json.loads(original["sealed-capture.manifest.json"])
    evidence = json.loads(original["source-evidence.json"])
    decision = json.loads(original["session-decision.json"])
    demand(digest(gz) == GZIP_SHA == manifest["payload_gzip_sha256"],
           "Original machine-sealed gzip SHA mismatch")
    demand(digest(canonical) == JSON_SHA == manifest["payload_uncompressed_sha256"],
           "Original machine-sealed JSON SHA mismatch")
    demand(len(gz) == manifest["payload_gzip_bytes"] and
           len(canonical) == manifest["payload_uncompressed_bytes"], "Original seal size drift")
    demand(canonical == (json.dumps(capture, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False) + "\n").encode("utf-8"),
           "Original sealed JSON is not canonical")
    demand(capture["logical_capture_id"] == manifest["logical_capture_id"] == name,
           "Logical observation identity mismatch")
    for key in ("capture_date_ist", "captured_at_utc", "universe_path",
                "universe_git_blob_sha", "source_version"):
        demand(capture[key] == manifest[key], "Manifest/capture identity disagreement: " + key)
    demand(capture["capture_date_ist"] == DATE and
           capture["universe_git_blob_sha"] == UNIVERSE_SHA and
           capture["source_version"] == SOURCE, "Frozen universe/source identity changed")
    demand(decision["state"] == "CAPTURE" and decision["final_session_date"] == DATE,
           "Original NSE final-session gate not satisfied")
    timestamp = datetime.fromisoformat(capture["captured_at_utc"])
    demand(timestamp.astimezone(ZoneInfo("Asia/Kolkata")).date().isoformat() == DATE
           and timestamp.hour >= 10, "Attempt to backdate or use pre-close capture")
    demand(capture["outcomes_opened"] is False and capture["live_capital_allowed"] is False
           and evidence["outcomes_opened"] is False and evidence["live_capital_allowed"] is False,
           "Research-only firewall broken")
    demand(evidence["completed_at_utc"] == capture["captured_at_utc"]
           and evidence["robots"]["status_code"] == 200, "Source/time evidence invalid")
    members = sorted(json.loads((root / "research/prospective/universes/FY27-Q2-2026-09-06.json")
                                .read_text())["members"], key=lambda member: member["rank"])
    rows = capture["observations"]
    source_rows = evidence["rows"]
    demand(len(members) == len(rows) == len(source_rows) == 100, "Missing frozen U001 rows")
    demand(len({row["symbol"] for row in rows}) == 100, "Duplicate frozen symbols")
    counts = {name: 0 for name in STATES}
    for i, (member, row, src) in enumerate(zip(members, rows, source_rows, strict=True), 1):
        demand(member["symbol"] == row["symbol"] == src["symbol"] and
               member["isin"] == row["isin"] and row["universe_rank"] == i == member["rank"],
               "Frozen symbol/ISIN/order substitution")
        demand(row["batch_id"] == ("B01" if i <= 50 else "B02"), "Frozen batch mismatch")
        demand(row["data_state"] in STATES and row["data_state"] == src["capture_state"],
               "Coverage state invalid")
        counts[row["data_state"]] += 1
        demand(row["source_url"].startswith("https://stockanalysis.com/quote/nse/") and
               src["forecast_http"]["status_code"] == 200,
               "Unpermitted source or HTTP control event")
        demand(row["source_observed_market_date"] is None, "Do not infer source date")
        if row["consensus_eps"] is not None:
            demand(row["fiscal_period"] and row["period_ending"] and row["eps_currency"] and
                   src["parser_pass"] and src["parsed"]["provider"] == "S&P Global Market Intelligence"
                   and src["parsed"]["consensus_eps"] == row["consensus_eps"],
                   "Explicit same-period EPS/source evidence invalid")
    demand(all(counts[state] == manifest["coverage_summary"][state] for state in STATES),
           "Manifest state accounting mismatch")
    demand(counts["PARTIAL"] == 100 and
           sum(row["consensus_eps"] is not None for row in rows) == 99 and
           sum((row["analyst_count"] or 0) >= 5 for row in rows) == 93,
           "Original 100/99/93 coverage changed")
    demand({row["symbol"] for row in rows if row["consensus_eps"] is None} == {"SIEMENS"},
           "Missing EPS identity changed")
    # Only byte-identical original machine seal and original evidence are preserved.
    for source_name, path in output.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original[source_name])
    evidence_dir = root / "reports/h021-weekly-acquisition/recovered-2026-10-30-run-41104775260"
    demand(not evidence_dir.exists(), "Original recovery provenance already recorded")
    evidence_dir.mkdir(parents=True)
    (evidence_dir / "original-workflow-artifact.zip").write_bytes(archive)
    (evidence_dir / "source-evidence.json").write_bytes(original["source-evidence.json"])
    (evidence_dir / "session-decision.json").write_bytes(original["session-decision.json"])
    (evidence_dir / "recovery-provenance.json").write_text(
        json.dumps({
            "hypothesis_id": "H021", "original_capture_date": DATE,
            "original_captured_at_utc": capture["captured_at_utc"],
            "original_workflow_run_id": RUN, "original_artifact_id": ARTIFACT,
            "original_zip_sha256": ZIP_SHA,
            "original_gzip_sha256": GZIP_SHA,
            "original_canonical_json_sha256": JSON_SHA,
            "original_source_evidence_sha256": digest(original["source-evidence.json"]),
            "recovery": "original Actions machine seal, no reacquisition or resealing",
            "failure": "unrelated downstream H021 future-cohort packet Git race",
            "outcomes_opened": False, "live_capital_allowed": False,
        }, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    # Run only the unmodified, frozen, EPS-only comparator against immutable Sept25.
    subprocess.run([sys.executable, "scripts/compare_h021_captures.py",
                    "--capture-dir", str(capture_dir),
                    "--current", str(output["sealed-capture.json.gz"]),
                    "--out", str(comp_path)], check=True)
    comparison = json.loads(comp_path.read_text())
    demand(comparison["prior_capture_date_ist"] == "2026-09-25" and
           comparison["capture_interval_days"] == 35 and
           comparison["primary_signal_available_count"] == 92 and
           comparison["primary_top_decile_count"] == 10,
           "Frozen 35-day 92/10 comparator does not match original workflow log")
    demand(comparison["outcomes_opened"] is False and comparison["live_capital_allowed"] is False
           and comparison["source_version"] == SOURCE and
           comparison["universe_git_blob_sha"] == UNIVERSE_SHA,
           "EPS comparison violated source/universe/research boundary")
    print("Original Oct30 seal and evidence recovered, frozen 35-day EPS-only 92/10 confirmed")


if __name__ == "__main__":
    main()
