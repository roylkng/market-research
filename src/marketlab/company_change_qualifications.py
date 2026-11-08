"""Read-only critical-source coverage diagnostic, never semantic certification.

The fixed source checklist is explicitly retrospective development annotation.
Coverage means the cited ranges contain the required original passages. It does
not mean the model understood them, mentioned them, or drew a correct conclusion.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sqlite3
from pathlib import Path

from marketlab.company_change import ChangeError, canonical_hash, public_url, strict_keys, timestamp
from marketlab.company_change_news_review import SOURCE_KEYS, validate_review
from marketlab.company_change_store import loads_unique

VERSION = "CC001-QUALIFICATIONS-v1"
PROVENANCE = "RETROSPECTIVE_SEEN_DEVELOPMENT_DIAGNOSTIC"
MAX_INPUT = 8 * 1024 * 1024


def exact_span(text: str, span: dict) -> tuple[int, int]:
    strict_keys(span, {"start", "end", "quote"}, "required source span")
    if set(span) != {"start", "end", "quote"}:
        raise ChangeError("incomplete source span")
    start, end = span["start"], span["end"]
    if (type(start) is not int or type(end) is not int or not 0 <= start < end <= len(text)
            or not isinstance(span["quote"], str) or len(span["quote"].strip()) < 10
            or text[start:end] != span["quote"]):
        raise ChangeError("required span is not exact original text")
    return start, end


def covered(target: tuple[int, int], ranges: list[tuple[int, int]]) -> bool:
    """Union of ranges may cover a clause, but no missing characters are bridged."""
    cursor, end = target
    for left, right in sorted(ranges):
        if right <= cursor:
            continue
        if left > cursor:
            return False
        cursor = right
        if cursor >= end:
            return True
    return False


def validate_manifest(manifest: dict) -> list[dict]:
    keys = {"schema_version", "provenance", "author", "independent_labels",
            "requirements_selected_after_predictions", "cases"}
    strict_keys(manifest, keys, "qualification manifest")
    if (set(manifest) != keys or type(manifest["schema_version"]) is not int
            or manifest["schema_version"] != 1 or manifest["provenance"] != PROVENANCE
            or manifest["independent_labels"] is not False
            or manifest["requirements_selected_after_predictions"] is not True
            or not isinstance(manifest["author"], str) or not manifest["author"].strip()
            or not isinstance(manifest["cases"], list) or not 1 <= len(manifest["cases"]) <= 100):
        raise ChangeError("retrospective annotation provenance or source denominator invalid")
    sources = set()
    for case in manifest["cases"]:
        strict_keys(case, {"source", "requirements"}, "source checklist")
        if (set(case) != {"source", "requirements"} or not isinstance(case["source"], dict)
                or set(case["source"]) != SOURCE_KEYS
                or not all(isinstance(v, str) and v for v in case["source"].values())):
            raise ChangeError("incomplete source-bound checklist")
        public_url(case["source"]["url"])
        key = canonical_hash(case["source"])
        if key in sources:
            raise ChangeError("duplicate checklist source")
        sources.add(key)
        requirements = case["requirements"]
        if not isinstance(requirements, list) or not 1 <= len(requirements) <= 30:
            raise ChangeError("source must retain one to thirty requirements")
        ids = set()
        for req in requirements:
            expected = {"id", "dimension", "reviewer_interpretation", "spans"}
            strict_keys(req, expected, "critical requirement")
            if (set(req) != expected or not all(isinstance(req[k], str) and req[k].strip()
                    for k in ("id", "dimension", "reviewer_interpretation"))
                    or req["id"] in ids or not isinstance(req["spans"], list)
                    or not 1 <= len(req["spans"]) <= 5):
                raise ChangeError("duplicate or malformed critical requirement")
            ids.add(req["id"])
    return manifest["cases"]


def verified_reading(db, root: Path, source: dict, attempt: dict | None, cutoff) -> dict | None:
    if attempt and attempt.get("reading_sha256"):
        rows = db.execute("SELECT id,payload FROM cc_news_readings WHERE id=?",
                          (attempt["reading_sha256"],)).fetchall()
    else:
        rows = db.execute("SELECT id,payload FROM cc_news_readings").fetchall()
    matches = []
    for row in rows:
        reading = loads_unique(row["payload"])
        if any(reading.get(k) != v for k, v in source.items()):
            if attempt and attempt.get("reading_sha256"):
                raise ChangeError("prediction and source reading identity differ")
            continue
        if timestamp(reading["published_at"]) > cutoff:
            raise ChangeError("source publication is after the prediction cutoff")
        if timestamp(reading["known_at"]) > cutoff:
            if attempt and attempt.get("reading_sha256"):
                raise ChangeError("prediction cites a reading observed after its cutoff")
            continue
        if (reading.get("reading_sha256") != row["id"]
                or canonical_hash({k: v for k, v in reading.items() if k != "reading_sha256"}) != row["id"]
                or hashlib.sha256(reading["text"].encode()).hexdigest() != source["text_sha256"]):
            raise ChangeError("reading integrity failure")
        capture = db.execute("SELECT raw_sha256 FROM captures WHERE id=?",
                             (reading["capture_id"],)).fetchone()
        if capture is None or capture[0] != source["raw_sha256"]:
            raise ChangeError("original capture is absent or differs")
        sha = source["raw_sha256"]
        if len(sha) != 64 or any(ch not in "0123456789abcdef" for ch in sha):
            raise ChangeError("invalid raw source digest")
        path = root / "blobs" / sha[:2] / sha
        if not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ChangeError("original source bytes failed verification")
        matches.append(reading)
    return max(matches, key=lambda r: timestamp(r["known_at"])) if matches else None


def diagnose(workspace: Path, predictions: dict, manifest: dict) -> dict:
    cases = validate_manifest(manifest)
    if canonical_hash({k: v for k, v in predictions.items() if k != "report_sha256"}) != predictions.get("report_sha256"):
        raise ChangeError("prediction report integrity failure")
    if (type(predictions.get("planned_cases")) is not int or predictions["planned_cases"] != len(cases)
            or not isinstance(predictions.get("attempts"), list)):
        raise ChangeError("full source denominator must be retained")
    cutoff = timestamp(predictions["as_of"])
    expected = {canonical_hash(c["source"]) for c in cases}
    attempts = {}
    for attempt in predictions["attempts"]:
        key = canonical_hash(attempt["source"])
        if key not in expected or key in attempts:
            raise ChangeError("duplicate or unlabelled prediction source")
        if attempt.get("status") not in {"PROPOSED", "ABSTAIN", "MISSING_SOURCE",
                                         "RUNNING", "FAILED_NO_AUTOMATIC_RETRY"}:
            raise ChangeError("unknown prediction status")
        attempts[key] = attempt
    root = workspace.resolve()
    database = root / "evidence.sqlite3"
    if not database.is_file() or database.is_symlink():
        raise ChangeError("existing evidence database required")
    journals = [Path(str(database) + suffix) for suffix in ("-wal", "-journal")]
    if any(p.exists() and p.stat().st_size for p in journals):
        raise ChangeError("use a closed checkpoint snapshot, not an active journal workspace")
    snapshot = (database.stat().st_size, database.stat().st_mtime_ns)
    # This offline diagnostic requires an immutable checkpoint. Unlike mode=ro
    # alone, immutable mode does not create WAL/SHM files in the evidence folder.
    db = sqlite3.connect(database.as_uri() + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    output = []
    try:
        for case in cases:
            attempt = attempts.get(canonical_hash(case["source"]))
            reading = verified_reading(db, root, case["source"], attempt, cutoff)
            ranges, proposals = [], []
            status = attempt["status"] if attempt else "MISSING_PREDICTION"
            if reading and status == "PROPOSED":
                proposals = attempt.get("proposals")
                if not isinstance(proposals, list) or not 1 <= len(proposals) <= 4:
                    raise ChangeError("proposed status has no bounded event records")
                for proposal in proposals:
                    validate_review(reading, proposal)  # Checks spans only, no approval.
                    for claim in proposal["claims"]:
                        ranges.append(exact_span(reading["text"], {k: claim[k] for k in ("start", "end", "quote")}))
            reqs = []
            for req in case["requirements"]:
                spans = []
                for span in req["spans"]:
                    target = exact_span(reading["text"], span) if reading else None
                    spans.append({**span, "present_in_selected_evidence": bool(target and covered(target, ranges))})
                reqs.append({**req, "spans": spans,
                    "all_required_passages_selected": all(s["present_in_selected_evidence"] for s in spans),
                    "source_checked": reading is not None,
                    "interpretation_entailment": "NOT_EVALUATED"})
            output.append({"source": case["source"], "prediction_status": status,
                "requirements": reqs, "requirements_covered": sum(r["all_required_passages_selected"] for r in reqs),
                "requirements_total": len(reqs), "reading_sha256": reading["reading_sha256"] if reading else None,
                "source_available": reading is not None,
                "model_interpretations": [p["interpretation"] for p in proposals],
                "decision": "HOLD_INTERPRETATION_REVIEW_REQUIRED", "model_output_approved": False})
    finally:
        db.close()
    if (snapshot != (database.stat().st_size, database.stat().st_mtime_ns)
            or any(p.exists() and p.stat().st_size for p in journals)):
        raise ChangeError("evidence snapshot changed during the diagnostic")
    total = sum(c["requirements_total"] for c in output)
    selected = sum(c["requirements_covered"] for c in output)
    result = {"engine": VERSION, "prediction_report_sha256": predictions["report_sha256"],
        "manifest_sha256": canonical_hash(manifest), "prediction_as_of": predictions["as_of"],
        "model_key": predictions.get("model_key"), "cases": output,
        "counts": {"source_cases": len(cases), "requirements": total,
                   "requirements_with_all_passages_selected": selected,
                   "documents_with_all_passages_selected": sum(c["requirements_covered"] == c["requirements_total"] for c in output),
                   "missing_predictions": sum(c["prediction_status"] == "MISSING_PREDICTION" for c in output),
                   "missing_sources": sum(not c["source_available"] for c in output)},
        "required_passage_coverage": selected / total,
        "metric_scope": "CITED_SOURCE_PASSAGE_COVERAGE_NOT_NARRATIVE_CORRECTNESS",
        "annotation_provenance": manifest["provenance"], "independent_labels": False,
        "requirements_selected_after_predictions": True, "model_output_approved": False,
        "live_capital_allowed": False, "validated_predictive_edge": False}
    result["report_sha256"] = canonical_hash(result)
    return result


def render(report: dict) -> str:
    def esc(value):
        return html.escape(str(value), quote=True)
    cards = []
    for case in report["cases"]:
        details = []
        for req in case["requirements"]:
            status = "Selected" if req["all_required_passages_selected"] else "Evidence omitted"
            spans = "".join(f"<blockquote>{esc(s['quote'])}</blockquote>" for s in req["spans"])
            details.append(f"<details><summary>{esc(status)}: {esc(req['dimension'])}</summary>"
                           f"<p>{esc(req['reviewer_interpretation'])}</p>{spans}</details>")
        narration = "".join(f"<blockquote>{esc(p)}</blockquote>" for p in case["model_interpretations"])
        cards.append(f"<article><h2>{esc(case['source']['symbol'])}</h2>"
            f"<p>{case['requirements_covered']}/{case['requirements_total']} required evidence groups selected.</p>"
            f"<p>Prediction status: {esc(case['prediction_status'])}</p>{''.join(details)}"
            f"<details><summary>Actual model interpretation, not approved</summary>{narration}</details></article>")
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Critical evidence diagnostic</title><style>*{box-sizing:border-box}body{font:16px system-ui;margin:0;background:#f3f6f5;color:#163440}main{max-width:1100px;padding:28px 22px;margin:auto}.banner{background:#163440;color:white;padding:24px;border-radius:12px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,340px),1fr));gap:18px;margin-top:24px}article{background:white;padding:22px;border:1px solid #cbd8d9;border-radius:12px;min-width:0}summary{cursor:pointer;font-weight:600;padding:12px 0}blockquote{border-left:3px solid #afc4c5;padding-left:12px;margin:12px 0;white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px}</style><main><h1>Did the analysis retain the decisive qualifications?</h1><div class="banner"><b>Correct citations do not certify a correct interpretation.</b><p>This retrospective checklist measures source passages selected, not narrative accuracy. Even complete evidence coverage leaves the model on HOLD.</p></div>""" + f"<p>{esc(report['model_key'])}: {report['counts']['requirements_with_all_passages_selected']}/{report['counts']['requirements']} required evidence groups selected.</p><div class='grid'>{''.join(cards)}</div></main></html>"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--output-prefix", type=Path, required=True)
    args = parser.parse_args(argv)
    for path in (args.predictions, args.requirements):
        if path.stat().st_size > MAX_INPUT:
            raise ChangeError("diagnostic input exceeds size bound")
    report = diagnose(args.workspace, loads_unique(args.predictions.read_bytes()), loads_unique(args.requirements.read_bytes()))
    args.output_prefix.parent.mkdir(parents=True, exist_ok=True)
    args.output_prefix.with_suffix(".json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    args.output_prefix.with_suffix(".html").write_text(render(report), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "report_sha256": report["report_sha256"], "model_output_approved": False}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
