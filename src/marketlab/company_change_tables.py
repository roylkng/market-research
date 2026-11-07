"""CC001 statement-table intake and explicitly developmental real-filing replay.

Reads preserved HTML tables or a source-derived row matrix. No network, inference,
portfolio decisions or writes to frozen experiments. Missing cells stay missing.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

from bs4 import BeautifulSoup

from marketlab.company_change import (
    ChangeError,
    canonical_hash,
    earnings_bridge,
    public_url,
    strict_keys,
    timestamp,
)

VERSION = "CC001-TABLES-v1"
# The aliases are financial concepts, not company-specific values or row positions.
METRICS = {
    "revenue": ("Revenue from operations",),
    "other_income": ("Other income",),
    "pbt": ("Total profit before tax", "Profit before tax"),
    "pretax_exceptional_items": ("Exceptional items",),
    "tax_expense": ("Total tax expenses",),
    "reported_pat": ("Total profit (loss) for period",),
    "owner_pat": ("Profit or loss, attributable to owners of parent",),
    "noncontrolling_pat": ("Total profit or loss, attributable to non-controlling interests",),
    "basic_eps": ("Basic earnings (loss) per share from continuing and discontinued operations",),
    "diluted_eps": ("Diluted earnings (loss) per share from continuing and discontinued operations",),
    "paid_up_capital": ("Paid-up equity share capital",),
    "face_value": ("Face value of equity share capital",),
}
META = {
    "symbol": ("NSE Symbol",), "isin": ("ISIN",),
    "currency": ("Description of presentation currency",),
    "rounding": ("Level of rounding used in financial results", "Level of rounding"),
}
PERIOD = {
    "start": "Date of start of reporting period",
    "end": "Date of end of reporting period",
    "scope": "Nature of report standalone or consolidated",
}
SCALES = {"lakhs": Decimal("0.01"), "lakh": Decimal("0.01"),
          "crores": Decimal(1), "crore": Decimal(1), "millions": Decimal("0.1"),
          "million": Decimal("0.1"), "rupees": Decimal("0.0000001")}
NUMBER = re.compile(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d{1,2}(?:,\d{2})+,\d{3}|\d+)(?:\.\d+)?")


def clean(value: str) -> str:
    if not isinstance(value, str):
        raise ChangeError("table cells must be strings")
    return " ".join(value.replace("\xa0", " ").split())


def html_tables(raw: bytes) -> list[list[list[str]]]:
    """Retain blank cells. Refuse merged/nested layouts rather than shift columns."""
    try:
        text = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        raise ChangeError("HTML must be UTF-8") from exc
    soup = BeautifulSoup(text, "html.parser")
    tables = []
    for table in soup.find_all("table"):
        if table.find("table") is not None:
            raise ChangeError("nested tables require a reviewed layout adapter")
        rows = []
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"], recursive=False)
            if not cells:
                continue
            if any(c.get("rowspan", "1") != "1" or c.get("colspan", "1") != "1" for c in cells):
                raise ChangeError("merged table cells require a reviewed layout adapter")
            rows.append([clean(c.get_text(" ", strip=True)) for c in cells])
        if rows:
            tables.append(rows)
    if not tables:
        raise ChangeError("no HTML tables found")
    return tables


def _hits(rows: list[list[str]], labels: tuple[str, ...]) -> list[tuple[int, int]]:
    wanted = {x.casefold() for x in labels}
    return [(r, c) for r, row in enumerate(rows) for c, cell in enumerate(row)
            if clean(cell).casefold() in wanted]


def _number(cell: str) -> Decimal | None:
    token = clean(cell)
    if token.casefold() in {"", "null", "na", "n/a", "-", "—"}:
        return None
    negative = token.startswith("(") and token.endswith(")")
    if negative:
        token = token[1:-1]
        if token.startswith(("+", "-")):
            raise ChangeError("ambiguous accounting sign")
    if not NUMBER.fullmatch(token):
        raise ChangeError(f"invalid financial number: {cell!r}")
    try:
        number = Decimal(token.replace(",", ""))
    except InvalidOperation as exc:
        raise ChangeError("invalid financial number") from exc
    return -number if negative else number


def _date(cell: str) -> str:
    try:
        return datetime.strptime(clean(cell), "%d-%m-%Y").date().isoformat()
    except ValueError as exc:
        raise ChangeError(f"invalid reporting-period date: {cell!r}") from exc


def validate_source(source: dict, tables: list, cutoff: str) -> tuple[datetime, str]:
    required = {"source_id", "url", "captured_at", "representation", "payload_sha256",
                "usage", "symbol", "isin"}
    strict_keys(source, required, "table source")
    if set(source) != required:
        raise ChangeError("incomplete table-source manifest")
    if not all(isinstance(source[k], str) and source[k] for k in required):
        raise ChangeError("source manifest values must be nonempty strings")
    public_url(source["url"])
    if source["usage"] != "INTERNAL_DEVELOPMENT":
        raise ChangeError("this adapter is limited to internal development, not redistribution")
    if source["representation"] not in {"SOURCE_DERIVED_ROWS", "CAPTURED_HTML_TABLES"}:
        raise ChangeError("unsupported source representation")
    if canonical_hash(tables) != source["payload_sha256"]:
        raise ChangeError("source table payload hash mismatch")
    clock = timestamp(source["captured_at"])
    if clock > timestamp(cutoff):
        raise ChangeError("table source is unavailable at the decision cutoff")
    if not re.fullmatch(r"[A-Z0-9&._-]{1,30}", source["symbol"]):
        raise ChangeError("invalid expected symbol")
    if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}[0-9]", source["isin"]):
        raise ChangeError("invalid expected ISIN")
    return clock, source["payload_sha256"]


def extract_statement(tables: list, source: dict, selector: dict, cutoff: str) -> dict:
    """Select a full period and scope, never first nonempty number or guessed unit."""
    strict_keys(selector, {"period_start", "period_end", "scope"}, "selector")
    if set(selector) != {"period_start", "period_end", "scope"}:
        raise ChangeError("selector requires start, end and scope")
    if selector["scope"] not in {"STANDALONE", "CONSOLIDATED"}:
        raise ChangeError("invalid accounting scope")
    start, end = date.fromisoformat(selector["period_start"]), date.fromisoformat(selector["period_end"])
    if start > end:
        raise ChangeError("reversed period")
    if not isinstance(tables, list) or not tables:
        raise ChangeError("tables must be a nonempty list")
    for table in tables:
        if not isinstance(table, list) or not table:
            raise ChangeError("invalid table matrix")
        for row in table:
            if not isinstance(row, list) or not row or not all(isinstance(x, str) for x in row):
                raise ChangeError("invalid table row")
    available, digest = validate_source(source, tables, cutoff)
    if end > available.date():
        raise ChangeError("reported results cannot end after observation")
    metadata = {}
    context = {}
    for key, aliases in META.items():
        observations = []
        for t, rows in enumerate(tables):
            for r, c in _hits(rows, aliases):
                if c + 1 < len(rows[r]):
                    observations.append((clean(rows[r][c + 1]), t, r, c + 1))
        if not observations or any(not x[0] for x in observations):
            raise ChangeError(f"missing statement context: {key}")
        if len({x[0].casefold() for x in observations}) != 1:
            raise ChangeError(f"conflicting statement context: {key}")
        value, t, r, c = observations[0]
        metadata[key] = value
        context[key] = {"table": t, "row": r, "column": c, "text": value}
    for key in ("symbol", "isin"):
        if metadata[key] != source[key]:
            raise ChangeError(f"statement {key} differs from expected identity")
    if metadata["currency"] != "INR" or metadata["rounding"].casefold() not in SCALES:
        raise ChangeError("unsupported currency or monetary rounding")
    scale = SCALES[metadata["rounding"].casefold()]
    candidates = []
    for t, rows in enumerate(tables):
        # Balance-sheet and segment tables may also have dates. Income concepts
        # must coexist in the SAME table before it is a candidate statement.
        if not _hits(rows, METRICS["revenue"]) or not _hits(rows, METRICS["reported_pat"]):
            continue
        period_rows = {}
        for key, label in PERIOD.items():
            hits = _hits(rows, (label,))
            if len(hits) != 1:
                raise ChangeError(f"ambiguous or absent statement header: {key}")
            r, c = hits[0]
            period_rows[key] = (r, c, rows[r][c + 1:])
        lengths = {len(x[2]) for x in period_rows.values()}
        if len(lengths) != 1 or not next(iter(lengths)):
            raise ChangeError("reporting-period columns are misaligned")
        for col in range(len(period_rows["start"][2])):
            starts = _date(period_rows["start"][2][col])
            ends = _date(period_rows["end"][2][col])
            scope = clean(period_rows["scope"][2][col]).upper()
            if scope not in {"STANDALONE", "CONSOLIDATED"}:
                raise ChangeError("missing accounting scope for table column")
            if (starts, ends, scope) == (selector["period_start"], selector["period_end"], selector["scope"]):
                candidates.append((t, col, period_rows))
    if not candidates:
        raise ChangeError("no exact statement column for requested period and scope")
    extracted = []
    for t, col, periods in candidates:
        facts, missing = {}, []
        rows = tables[t]
        count = len(periods["start"][2])
        for key, aliases in METRICS.items():
            hits = _hits(rows, aliases)
            if len(hits) > 1:
                raise ChangeError(f"ambiguous repeated financial concept: {key}")
            if not hits:
                missing.append(key)
                continue
            r, c = hits[0]
            cells = rows[r][c + 1:]
            if len(cells) != count:
                raise ChangeError(f"misaligned data columns for {key}")
            number = _number(cells[col])
            if number is None:
                missing.append(key)
                continue
            per_share = key in {"basic_eps", "diluted_eps", "face_value"}
            converted = number if per_share else number * scale
            facts[key] = {"value": float(converted), "unit": "INR_per_share" if per_share else "INR_crore",
                "source_id": source["source_id"], "table": t, "row": r,
                "column": c + 1 + col, "literal": cells[col], "label": rows[r][c],
                "quote": " | ".join(rows[r]), "source_payload_sha256": digest,
                "context": context,
                "period_context": {k: {"row": v[0], "column": v[1] + 1 + col,
                                       "text": v[2][col]} for k, v in periods.items()}}
        extracted.append((facts, missing, t, col))
    signatures = [canonical_hash({"values": {k: (v["value"], v["unit"]) for k, v in f.items()},
                                   "missing": m}) for f, m, _, _ in extracted]
    if len(set(signatures)) != 1:
        raise ChangeError("conflicting columns for identical accounting period")
    facts, missing, t, col = extracted[0]
    # Reported total group PAT is intentionally never substituted for owner PAT.
    bridge = earnings_bridge({"facts": facts})
    blockers = ["No verified after-tax owner-attributable normalization.",
                "Reported EPS is not automatically sustainable owner EPS.",
                "No price, investment recommendation or predictive outcome is supplied."]
    if "owner_pat" not in facts:
        blockers.append("Owner-attributable PAT is absent. Total profit was not substituted.")
    if (end - start).days + 1 < 360:
        blockers.append("Interim results were not annualized.")
    if "pretax_exceptional_items" in facts:
        blockers.append("Pretax exceptional items were not used as after-tax owner adjustments.")
    warnings = []
    if {"pbt", "tax_expense", "reported_pat"} <= facts.keys():
        residual = facts["pbt"]["value"] - facts["tax_expense"]["value"] - facts["reported_pat"]["value"]
        if abs(residual) > 0.03:
            warnings.append("PBT minus tax differs from group PAT. Other profit components need review.")
    result = {"symbol": source["symbol"], "isin": source["isin"], **selector,
              "source_id": source["source_id"], "available_at": available.isoformat(),
              "selected_table": t, "selected_value_column": col,
              "equivalent_column_count": len(candidates), "facts": facts,
              "missing_fields": missing, "bridge": bridge, "warnings": warnings,
              "blockers": blockers, "evidence_mode": "HISTORICAL_RECONSTRUCTION",
              "disposition": "DEVELOPMENT_ONLY", "live_capital_allowed": False}
    result["statement_sha256"] = canonical_hash(result)
    return result


def evaluate_corpus(corpus: dict) -> dict:
    """Expected labels are used ONLY after extraction, never by the extractor."""
    strict_keys(corpus, {"schema_version", "as_of", "sources", "cases"}, "corpus")
    if type(corpus.get("schema_version")) is not int or corpus["schema_version"] != 1:
        raise ChangeError("unsupported corpus schema")
    cutoff = corpus["as_of"]
    timestamp(cutoff)
    sources = {}
    for item in corpus["sources"]:
        strict_keys(item, {"manifest", "tables", "observation_note"}, "corpus source")
        source_id = item["manifest"]["source_id"]
        if source_id in sources:
            raise ChangeError("duplicate corpus source")
        sources[source_id] = item
    cases, seen = [], set()
    for case in corpus["cases"]:
        strict_keys(case, {"case_id", "source_id", "selector", "expected"}, "replay case")
        if case["case_id"] in seen:
            raise ChangeError("duplicate replay case")
        seen.add(case["case_id"])
        item = sources[case["source_id"]]
        actual = extract_statement(item["tables"], item["manifest"], case["selector"], cutoff)
        strict_keys(case["expected"], set(METRICS), "expected labels")
        checks = []
        for key, expected in case["expected"].items():
            value = actual["facts"].get(key, {}).get("value")
            passed = value is None if expected is None else value == expected
            checks.append({"field": key, "expected": expected, "actual": value, "passed": passed})
        # Score accidental extra fields too. An unlabeled extracted field is not a success.
        for key in actual["facts"].keys() - case["expected"].keys():
            checks.append({"field": key, "expected": "UNLABELED", "actual": actual["facts"][key]["value"],
                           "passed": False})
        cases.append({"case_id": case["case_id"], "statement": actual, "checks": checks,
                      "passed": all(c["passed"] for c in checks) and bool(checks)})
    checks = [c for case in cases for c in case["checks"]]
    report = {"engine": VERSION, "as_of": cutoff, "corpus_sha256": canonical_hash(corpus),
              "sources": [v["manifest"] for v in sources.values()], "cases": cases,
              "counts": {"sources": len(sources), "cases": len(cases), "checks": len(checks),
                         "passed_checks": sum(c["passed"] for c in checks),
                         "failed_checks": sum(not c["passed"] for c in checks)},
              "status": "PASS" if cases and all(c["passed"] for c in cases) else "FAIL",
              "live_capital_allowed": False, "trained_predictor": False,
              "evaluation_class": "SEEN_DEVELOPMENT_REPLAY_NOT_BLIND_ACCURACY",
              "renderer_version": "cc001-replay-html-v1",
              "limitations": ["Source-derived rows are not original HTML/PDF byte custody.",
                  "Two-source development examples do not establish market-wide extraction accuracy.",
                  "Expected labels and rules were developed together. No held-out performance is claimed.",
                  "No learned model was invoked and no investment-return outcomes were opened."]}
    report["report_sha256"] = canonical_hash(report)
    return report


def render_replay(report: dict) -> str:
    esc = html.escape
    cards = []
    for case in report["cases"]:
        s = case["statement"]
        rows = "".join(f"<tr><td>{esc(c['field'])}</td><td>{esc(str(c['actual']))}</td>"
                       f"<td>{'PASS' if c['passed'] else 'FAIL'}</td></tr>" for c in case["checks"])
        blockers = "".join(f"<li>{esc(b)}</li>" for b in s["blockers"])
        cards.append(f"<article><div class='tag'>{esc(s['scope'])} / DEVELOPMENT ONLY</div>"
            f"<h2>{esc(s['symbol'])}</h2><p>{esc(s['period_start'])} to {esc(s['period_end'])}</p>"
            f"<table><tr><th>Metric</th><th>Extracted value</th><th>Replay</th></tr>{rows}</table>"
            f"<details><summary>Decision blockers</summary><ul>{blockers}</ul></details></article>")
    counts = report["counts"]
    sources = "".join(
        f"<li><a href='{esc(source['url'], quote=True)}' rel='noopener noreferrer'>{esc(source['symbol'])} original NSE reference</a>"
        f". Representation: {esc(source['representation'])}. Reconstruction recorded {esc(source['captured_at'])}.</li>"
        for source in report["sources"]
    )
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>CC001 real-filing development replay</title><style>
body{font-family:system-ui,sans-serif;background:#f2f5f6;color:#203440;margin:0}main{max-width:1160px;padding:36px 24px;margin:auto}
h1{font-size:34px}.tag{font-size:11px;letter-spacing:.08em;color:#556d76}.banner{background:#203440;color:white;padding:20px;border-radius:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:18px;margin:24px 0}article{background:white;border:1px solid #d4dfe4;border-radius:12px;padding:20px}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{text-align:left;border-bottom:1px solid #e3e9ec;padding:9px 4px}
li{margin:12px 0}summary{cursor:pointer;margin-top:16px;font-weight:600}footer{font-size:12px;overflow-wrap:anywhere;color:#556d76}
</style><main><div class="tag">MARKETLAB / REAL-FILING INTAKE</div><h1>From statement columns to evidence</h1>
<div class="banner"><b>Development replay, not validated prediction.</b><p>Real disclosed numbers in source-derived table reconstructions. No original-byte archive or blind extraction accuracy is claimed.</p></div>
""" + f"<p><b>{counts['sources']} disclosures · {counts['cases']} accounting-period cases · " \
        f"{counts['passed_checks']}/{counts['checks']} labelled checks passed</b></p>" \
        "<p>Monetary statement values are ₹ crore. EPS and face value remain ₹ per share. Blank cells remain unknown.</p>" \
        f"<div class='grid'>{''.join(cards)}</div><h2>What is deliberately not inferred</h2>" \
        "<p>No group-to-owner profit substitution. No pretax-to-after-tax adjustment. No annualization of a quarter. " \
        "No share count manufactured from rounded capital or EPS. No buy rating.</p>" \
        f"<h2>Evidence references</h2><ul>{sources}</ul><footer>{esc(report['evaluation_class'])}<br>Report SHA-256: {esc(report['report_sha256'])}</footer></main></html>"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = evaluate_corpus(json.loads(args.corpus.read_text(encoding="utf-8")))
        if any(p in {"hypotheses", "registry", "experiments", "prospective"} or
               re.fullmatch(r"(?:h|hg|ae)\d+", p, re.IGNORECASE) for p in args.out.resolve().parts):
            raise ChangeError("output cannot target frozen experiment namespaces")
        args.out.mkdir(parents=True, exist_ok=True)
        for ext, payload in (("json", json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)),
                             ("html", render_replay(report))):
            path = args.out / f"{report['report_sha256']}.{ext}"
            raw = payload.encode("utf-8")
            try:
                with path.open("xb") as stream:
                    stream.write(raw)
            except FileExistsError:
                if path.read_bytes() != raw:
                    raise ChangeError("refusing to overwrite a different replay artifact")
        print(json.dumps({"status": report["status"], **report["counts"], "report_sha256": report["report_sha256"]}))
        return 0 if report["status"] == "PASS" else 1
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"CC001-TABLES: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
