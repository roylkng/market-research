"""Executable CC001 research intake: original bytes, extraction, persistence, inbox.

No trades, automatic investment approval, or claim of predictive performance.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import io
import ipaddress
import json
import os
import re
import socket
import sys
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from marketlab.company_change import (
    ChangeError,
    SourceDocument,
    analyze_bundle,
    canonical_hash,
    extract_event,
    extraction_request,
    public_url,
    strict_keys,
)
from marketlab.company_change_store import EvidenceStore, loads_unique, now_utc
from marketlab.company_change_tables import META, METRICS, PERIOD, clean, extract_statement

VERSION = "CC001-PIPELINE-v1"
MAX_BYTES = 16 * 1024 * 1024
MAX_TEXT = 120_000
DEFAULT_HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com", "www.nseindia.com"}


def code_fingerprint() -> str:
    names = ("company_change.py", "company_change_tables.py", "company_change_store.py",
             "company_change_pipeline.py")
    return canonical_hash({n: hashlib.sha256(Path(__file__).with_name(n).read_bytes()).hexdigest()
                           for n in names})


def check_url(url: str, hosts: set[str], *, resolve: bool = True) -> None:
    public_url(url)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.port not in (None, 443) or parsed.hostname not in hosts:
        raise ChangeError("source URL is not on the explicit HTTPS host allowlist")
    if parsed.fragment or parsed.query:
        raise ChangeError("source URL must not carry query credentials or fragments")
    if resolve:
        try:
            addresses = socket.getaddrinfo(parsed.hostname, 443, type=socket.SOCK_STREAM)
        except OSError as exc:
            raise ChangeError("source DNS resolution failed") from exc
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise ChangeError("source resolves to a non-public address")


def fetch_original(url: str, hosts: set[str], *, session=None, resolve: bool = True) -> tuple[bytes, str]:
    """Bounded fetch. Never follows an unchecked redirect or executes a document."""
    client = session or requests.Session()
    owned = session is None
    current = url
    try:
        for _ in range(4):
            check_url(current, hosts, resolve=resolve)
            with client.get(current, timeout=(10, 45), stream=True, allow_redirects=False,
                            headers={"User-Agent": "MarketLab-CC001/1.0 internal research"}) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    current = urljoin(current, response.headers.get("Location", ""))
                    continue
                response.raise_for_status()
                if int(response.headers.get("Content-Length", "0")) > MAX_BYTES:
                    raise ChangeError("document exceeds byte limit")
                chunks, size = [], 0
                for chunk in response.iter_content(65536):
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise ChangeError("document exceeds byte limit")
                    chunks.append(chunk)
                raw = b"".join(chunks)
                if not raw:
                    raise ChangeError("empty document")
                return raw, current
        raise ChangeError("too many source redirects")
    except requests.RequestException as exc:
        # Response bodies and headers may contain sensitive service details.
        raise ChangeError(f"source HTTP request failed ({type(exc).__name__})") from exc
    finally:
        if owned:
            client.close()


def project_html(raw: bytes) -> tuple[list, dict]:
    """Expand bounded HTML spans, select values by period-header columns.

    Projection retains raw DOM origins. It does not infer dates or discard blanks.
    Nested wrapper rows are skipped, but their child tables are read independently.
    """
    if len(raw) > MAX_BYTES:
        raise ChangeError("document exceeds byte limit")
    soup = BeautifulSoup(raw.decode("utf-8-sig", errors="strict"), "html.parser")
    tables, origins = [], {}
    meta_rows, meta_origins = [], []
    alias = {v.casefold() for values in META.values() for v in values}
    concepts = {v.casefold() for values in METRICS.values() for v in values} | {
        v.casefold() for v in PERIOD.values()}
    for ti, table in enumerate(soup.find_all("table")):
        rows, locations, occupied = [], [], {}
        trs = [tr for tr in table.find_all("tr") if tr.find_parent("table") is table]
        if len(trs) > 10000:
            raise ChangeError("table row limit exceeded")
        for ri, tr in enumerate(trs):
            cells = tr.find_all(["td", "th"], recursive=False)
            if any(c.find("table") is not None for c in cells):
                rows.append([])
                locations.append([])
                continue
            ci = 0
            for di, cell in enumerate(cells):
                while (ri, ci) in occupied:
                    ci += 1
                try:
                    rs, cs = int(cell.get("rowspan", 1)), int(cell.get("colspan", 1))
                except (TypeError, ValueError) as exc:
                    raise ChangeError("invalid table span") from exc
                if not 1 <= rs <= 100 or not 1 <= cs <= 100 or ci + cs > 256:
                    raise ChangeError("table span limit exceeded")
                text = clean(cell.get_text(" ", strip=True))
                origin = {"table": ti, "row": ri, "cell": di, "text": text}
                for r in range(ri, ri + rs):
                    for c in range(ci, ci + cs):
                        if (r, c) in occupied:
                            raise ChangeError("overlapping table spans")
                        occupied[r, c] = (text, origin)
                ci += cs
            width = max((c + 1 for r, c in occupied if r == ri), default=0)
            rows.append([occupied.get((ri, c), ("", None))[0] for c in range(width)])
            locations.append([occupied.get((ri, c), ("", None))[1] for c in range(width)])
        for ri, row in enumerate(rows):
            # Metadata may have a merged label. The next distinct DOM cell is its value.
            for ci, text in enumerate(row):
                if text.casefold() not in alias or (ci and locations[ri][ci] == locations[ri][ci - 1]):
                    continue
                rest = [c for c in range(ci + 1, len(row)) if locations[ri][c] != locations[ri][ci]]
                if rest:
                    value_col = rest[0]
                    meta_rows.append([text, row[value_col]])
                    meta_origins.append([locations[ri][ci], locations[ri][value_col]])
        start_rows = [(ri, row) for ri, row in enumerate(rows)
                      if PERIOD["start"].casefold() in [v.casefold() for v in row]]
        if not start_rows:
            continue
        if len(start_rows) != 1:
            raise ChangeError("multiple reporting headers in one table require explicit segmentation")
        ri, start_row = start_rows[0]
        value_cols = [c for c, text in enumerate(start_row) if re.fullmatch(r"\d{2}-\d{2}-\d{4}", text)]
        if not value_cols:
            continue
        projected, mapped = [], []
        for ri, row in enumerate(rows):
            found = sorted({v for v in row[:min(value_cols)] if v.casefold() in concepts})
            if not found:
                continue
            if len(found) != 1:
                raise ChangeError("ambiguous financial row label")
            label = found[0]
            label_col = row.index(label)
            if max(value_cols) >= len(row):
                raise ChangeError("financial row lacks requested value columns")
            projected.append(["", label] + [row[c] for c in value_cols])
            mapped.append([None, locations[ri][label_col]] + [locations[ri][c] for c in value_cols])
        if projected:
            tables.append(projected)
            origins[str(len(tables))] = mapped
    if not meta_rows or not tables:
        raise ChangeError("no supported statement with identity and reporting headers")
    origins["0"] = meta_origins
    return [meta_rows] + tables, origins


def document_text(raw: bytes, format_name: str) -> str:
    if format_name == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        if reader.is_encrypted or len(reader.pages) > 200:
            raise ChangeError("encrypted or oversized PDF requires manual intake")
        text = "\n".join(f"[PAGE {i + 1}]\n{page.extract_text() or ''}"
                         for i, page in enumerate(reader.pages))
    elif format_name == "html":
        soup = BeautifulSoup(raw.decode("utf-8-sig", errors="strict"), "html.parser")
        for element in soup(["script", "style", "noscript"]):
            element.decompose()
        text = soup.get_text("\n", strip=True)
    elif format_name == "text":
        text = raw.decode("utf-8-sig", errors="strict")
    else:
        raise ChangeError("unsupported document format")
    if not text.strip() or len(text) > MAX_TEXT:
        raise ChangeError("empty or oversized text requires an explicit chunking/review policy")
    return text


def model_config() -> dict:
    url, model = os.environ.get("CC001_MODEL_URL"), os.environ.get("CC001_MODEL_NAME")
    if not url or not model:
        raise ChangeError("MODEL_NOT_CONFIGURED: set CC001_MODEL_URL and CC001_MODEL_NAME")
    public_url(url)
    parsed = urlsplit(url)
    local = parsed.hostname in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (local and os.environ.get("CC001_ALLOW_LOCAL_MODEL") == "1"):
        raise ChangeError("model endpoint requires HTTPS or explicitly permitted loopback")
    if parsed.query or parsed.fragment:
        raise ChangeError("model endpoint must not contain query credentials")
    if not parsed.path.endswith("/chat/completions"):
        raise ChangeError("CC001_MODEL_URL must be a full chat-completions endpoint")
    return {"url": url, "model": model, "max_tokens": 4096, "temperature": 0}


def call_extractor(source: SourceDocument, config: dict, *, session=None) -> tuple[dict, bytes]:
    """One explicit request, no automatic paid retries and no model tool permissions."""
    request = extraction_request(source)
    fields = list(request["allowed_fields"])
    item = {"type": "object", "properties": {
        "field": {"type": "string", "enum": fields}, "quote": {"type": "string"},
        "literal": {"type": "string"}}, "required": ["field", "quote", "literal"],
        "additionalProperties": False}
    schema = {"type": "object", "properties": {"facts": {"type": "array", "items": item}},
              "required": ["facts"], "additionalProperties": False}
    payload = {"model": config["model"], "temperature": 0, "max_tokens": config["max_tokens"],
        "messages": [
            {"role": "system", "content": request["system"] +
             " For this adapter return {facts:[{field,quote,literal}]}. "
             "Return a unique exact quote. The client computes offsets. Do not infer missing facts."},
            {"role": "user", "content": json.dumps({"scope": source.scope,
                "period_start": source.period_start, "period_end": source.period_end,
                "allowed_fields": request["allowed_fields"], "untrusted_source": source.text})}],
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "financial_facts", "strict": True, "schema": schema}}}
    headers = {"Content-Type": "application/json"}
    if os.environ.get("CC001_MODEL_API_KEY"):
        headers["Authorization"] = "Bearer " + os.environ["CC001_MODEL_API_KEY"]
    client, owned = session or requests.Session(), session is None
    try:
        with client.post(config["url"], json=payload, headers=headers, timeout=(10, 120),
                         stream=True, allow_redirects=False) as response:
            if response.status_code != 200:
                raise ChangeError(f"model request failed with HTTP {response.status_code}")
            chunks, size = [], 0
            for chunk in response.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise ChangeError("model response exceeds byte limit")
                chunks.append(chunk)
            raw = b"".join(chunks)
        body = loads_unique(raw)
        choice = body["choices"][0]
        if choice.get("finish_reason") != "stop" or choice["message"].get("refusal"):
            raise ChangeError("model response is incomplete or refused")
        parsed = loads_unique(choice["message"]["content"])
        strict_keys(parsed, {"facts"}, "model response")
        if not isinstance(parsed.get("facts"), list):
            raise ChangeError("model facts must be a list")
        proposals = {}
        for fact in parsed["facts"]:
            strict_keys(fact, {"field", "quote", "literal"}, "model fact")
            if set(fact) != {"field", "quote", "literal"}:
                raise ChangeError("incomplete model fact")
            field, quote, literal = fact["field"], fact["quote"], fact["literal"]
            if field not in fields or field in proposals:
                raise ChangeError("unknown or duplicate model field")
            if not isinstance(quote, str) or not quote or source.text.count(quote) != 1:
                raise ChangeError("model quote must occur exactly once in source text")
            if not isinstance(literal, str) or not literal or literal not in quote:
                raise ChangeError("model literal is not in its cited source passage")
            start = source.text.index(quote)
            proposals[field] = {"start": start, "end": start + len(quote),
                                "quote": quote, "literal": literal}
        return {"proposed_facts": proposals, "usage": body.get("usage", {}),
                "model": body.get("model", config["model"]),
                "request_sha256": canonical_hash(payload)}, raw
    except requests.RequestException as exc:
        raise ChangeError(f"model transport failed ({type(exc).__name__})") from exc
    finally:
        if owned:
            client.close()


def validate_spec(spec: dict) -> None:
    required = {"source_id", "url", "symbol", "isin", "kind", "event_key", "scope",
                "period_start", "period_end", "format", "extractor", "rights"}
    allowed = required | {"local_file", "published_at", "contract_assumptions"}
    strict_keys(spec, allowed, "source spec")
    if not required <= spec.keys():
        raise ChangeError(f"source spec missing {sorted(required - spec.keys())}")
    if spec["rights"] not in {"INTERNAL_RESEARCH", "REDISTRIBUTABLE"}:
        raise ChangeError("source usage must be authorized before ingestion")
    if spec["extractor"] not in {"statement", "labels", "llm"}:
        raise ChangeError("unsupported extractor")
    if spec["extractor"] == "statement" and (spec["format"] != "html" or spec["kind"] != "earnings_quality"):
        raise ChangeError("statement extraction requires earnings HTML")
    public_url(spec["url"])
    # Reuse the v1 identity/scope/period checks without fabricating financial data.
    clock = spec.get("published_at", now_utc())
    SourceDocument.from_dict({"source_id": spec["source_id"], "symbol": spec["symbol"],
        "isin": spec["isin"], "kind": spec["kind"], "event_key": spec["event_key"],
        "scope": spec["scope"], "period_start": spec["period_start"], "period_end": spec["period_end"],
        "published_at": clock, "first_observed_at": clock, "text_recorded_at": clock,
        "url": spec["url"], "authority": "ISSUER", "rights": spec["rights"],
        "evidence_mode": "HISTORICAL_RECONSTRUCTION", "text": "validation",
        "text_sha256": hashlib.sha256(b"validation").hexdigest()})


def process_capture(store: EvidenceStore, capture: dict, spec: dict, *, model_session=None) -> dict:
    config = model_config() if spec["extractor"] == "llm" else None
    recipe = canonical_hash({"code": code_fingerprint(), "spec": spec, "model": config})
    cached = store.cached(capture["id"], recipe)
    if cached is not None:
        return cached
    raw = store.read_blob(capture["raw_sha256"])
    selector = {k: spec[k] for k in ("scope", "period_start", "period_end")}
    result = {"source_id": spec["source_id"], "symbol": spec["symbol"], "isin": spec["isin"],
              "url": spec["url"], "kind": spec["kind"], "selector": selector,
              "identity": {k: spec[k] for k in ("symbol", "isin", "scope", "kind", "event_key")},
              "evidence_mode": "HISTORICAL_RECONSTRUCTION", "requires_review": True}
    if spec["extractor"] == "statement":
        tables, origins = project_html(raw)
        manifest = {"source_id": spec["source_id"], "url": spec["url"],
            "captured_at": capture["captured_at"], "representation": "CAPTURED_HTML_TABLES",
            "payload_sha256": canonical_hash(tables), "usage": "INTERNAL_DEVELOPMENT",
            "symbol": spec["symbol"], "isin": spec["isin"]}
        statement = extract_statement(tables, manifest, selector, store.clock())
        for fact in statement["facts"].values():
            fact["original_dom_cell"] = origins[str(fact["table"])][fact["row"]][fact["column"]]
        result.update(facts=statement["facts"], bridge=statement["bridge"],
                      blockers=statement["blockers"], source_document=None)
        result["projection_sha256"] = canonical_hash({"tables": tables, "origins": origins})
    else:
        text = document_text(raw, spec["format"])
        recorded = store.clock()
        source = SourceDocument.from_dict({
            **{k: spec[k] for k in ("source_id", "symbol", "isin", "kind", "event_key", "scope",
                                    "period_start", "period_end", "url", "rights")},
            "published_at": spec.get("published_at", capture["captured_at"]),
            "first_observed_at": capture["captured_at"], "text_recorded_at": recorded,
            "authority": "ISSUER", "evidence_mode": "HISTORICAL_RECONSTRUCTION",
            "text": text, "text_sha256": hashlib.sha256(text.encode()).hexdigest()})
        if config:
            response, response_raw = call_extractor(source, config, session=model_session)
            result["model_response_sha256"] = store.put_blob(response_raw)
            result["model_usage"] = response["usage"]
            result["model_request_sha256"] = response["request_sha256"]
            source = SourceDocument.from_dict({**asdict(source),
                "proposed_facts": response["proposed_facts"], "proposed_facts_at": store.clock()})
        event = extract_event(source)
        if not event["facts"]:
            raise ChangeError("no supported facts extracted")
        bundle = {"schema_version": 1, "as_of": store.clock(), "sources": [asdict(source)]}
        if "contract_assumptions" in spec:
            bundle["contract_assumptions"] = {source.source_id: spec["contract_assumptions"]}
        analyzed = analyze_bundle(bundle)["events"][0]
        result.update(facts=event["facts"], bridge=analyzed["bridge"],
                      blockers=["Financial interpretation requires review."], source_document=asdict(source))
    if not result["facts"]:
        raise ChangeError("extraction produced no supported facts")
    result["facts_sha256"] = canonical_hash({k: {"value": v["value"], "unit": v["unit"]}
                                           for k, v in result["facts"].items()})
    return store.record_extraction(capture, recipe, result)


def ingest(manifest: dict, store: EvidenceStore, *, base: Path, allow_network=False,
           fetcher=fetch_original, model_session=None) -> dict:
    strict_keys(manifest, {"schema_version", "allowed_hosts", "sources"}, "manifest")
    if type(manifest.get("schema_version")) is not int or manifest["schema_version"] != 1:
        raise ChangeError("unsupported intake schema")
    specs = manifest.get("sources")
    if not isinstance(specs, list) or not 1 <= len(specs) <= 1000:
        raise ChangeError("manifest requires 1..1000 sources")
    hosts = manifest.get("allowed_hosts", sorted(DEFAULT_HOSTS))
    if not isinstance(hosts, list) or not all(isinstance(h, str) and h for h in hosts):
        raise ChangeError("allowed_hosts must be explicit hostname strings")
    ids = set()
    for spec in specs:
        validate_spec(spec)
        if spec["source_id"] in ids:
            raise ChangeError("duplicate source_id in manifest")
        ids.add(spec["source_id"])
    successes, failures, fetched = [], [], {}
    for spec in specs:
        try:
            if "local_file" in spec:
                path = (base / spec["local_file"]).resolve()
                if not path.is_relative_to(base.resolve()) or path.stat().st_size > MAX_BYTES:
                    raise ChangeError("local input escapes manifest directory or exceeds byte limit")
                raw = path.read_bytes()
                origin, final_url = "LOCAL_IMPORT_NOT_ATTESTED_ORIGINAL", spec["url"]
            else:
                if not allow_network:
                    raise ChangeError("NETWORK_DISABLED: supply --fetch for explicit source retrieval")
                if spec["url"] not in fetched:
                    fetched[spec["url"]] = fetcher(spec["url"], set(hosts))
                raw, final_url = fetched[spec["url"]]
                origin = "HTTP_RESPONSE_BYTES"
            if not raw or len(raw) > MAX_BYTES:
                raise ChangeError("invalid document size")
            metadata = {"spec": spec, "origin": origin, "final_url": final_url,
                        "publication_time_verified": False}
            capture = store.capture(raw, metadata)
            extracted = process_capture(store, capture, spec, model_session=model_session)
            successes.append({"source_id": spec["source_id"], "extraction_id": extracted["extraction_id"],
                "raw_sha256": capture["raw_sha256"], "facts": len(extracted["facts"]), "origin": origin})
            store.attempt(spec["source_id"], "EXTRACTED", extracted["extraction_id"])
        except (ValueError, TypeError, KeyError, OSError) as exc:
            message = str(exc)[:600]
            failures.append({"source_id": spec["source_id"], "reason": message})
            store.attempt(spec["source_id"], "FAILED", message)
    snapshot = store.snapshot()
    report = {"engine": VERSION, "manifest_sha256": canonical_hash(manifest),
              "code_sha256": code_fingerprint(), "successes": successes, "failures": failures,
              "snapshot": snapshot, "live_capital_allowed": False, "trained_predictor": False}
    report["report_sha256"] = canonical_hash(report)
    return report


def render_inbox(report: dict) -> str:
    def esc(value):
        return html.escape(str(value), quote=True)
    cards = []
    for result in report["snapshot"]["active"]:
        rows = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v['value'])}</td><td>{esc(v['unit'])}</td></tr>"
                       for k, v in result["facts"].items())
        cards.append(f"<article><div class='tag'>{esc(result['review_status'])} / RESEARCH ONLY</div>"
            f"<h2>{esc(result['symbol'])}</h2><p>{esc(result['selector']['scope'])} · "
            f"{esc(result['selector']['period_end'])}</p><table>{rows}</table>"
            f"<details><summary>Calculation and provenance</summary><pre>{esc(json.dumps(result['bridge'], indent=2))}</pre>"
            f"<p>Original-byte SHA-256</p><code>{esc(result['raw_sha256'])}</code>"
            f"<p>Known at {esc(result['known_at'])}</p><a href='{esc(result['url'])}'>Source reference</a></details></article>")
    failures = "".join(f"<li>{esc(f['source_id'])}: {esc(f['reason'])}</li>" for f in report["failures"])
    return """<!doctype html><html lang='en'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<title>Company-change research inbox</title><style>
body{margin:0;background:#f1f5f5;color:#17323d;font:15px system-ui}main{max-width:1160px;margin:auto;padding:32px 24px}h1{font-size:36px}
.banner{background:#17323d;color:white;padding:20px;border-radius:14px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,320px),1fr));gap:18px;margin:24px 0}
article{min-width:0;background:white;border:1px solid #d4e0e3;border-radius:14px;padding:20px}.tag{font-size:11px;letter-spacing:.08em}table{width:100%;border-collapse:collapse;font-size:12px}
td{border-bottom:1px solid #e0e9eb;padding:9px 3px;overflow-wrap:anywhere}td:first-child{width:45%}pre,code{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}summary{cursor:pointer;margin-top:16px}
</style><main><div class='tag'>MARKETLAB / PERSISTENT EVIDENCE WORKSPACE</div><h1>Company-change inbox</h1>
<div class='banner'><b>Original documents → verified facts → economic consequences</b><p>Research outputs require review. No trades or validated predictive advantage are implied.</p></div>
""" + f"<p>{len(report['successes'])} source analyses completed · {len(report['failures'])} failed · " \
        f"{len(report['snapshot']['history'])} retained extraction versions</p><div class='grid'>{''.join(cards)}</div>" \
        f"<h2>Unresolved intake</h2><ul>{failures or '<li>None in this run.</li>'}</ul>" \
        f"<p>Report fingerprint <code>{esc(report['report_sha256'])}</code></p></main></html>"


def write_outputs(store: EvidenceStore, report: dict) -> list[str]:
    folder = store.root / "reports"
    folder.mkdir(exist_ok=True)
    paths = []
    for ext, contents in (("json", json.dumps(report, indent=2, allow_nan=False)),
                          ("html", render_inbox(report))):
        path = folder / f"{report['report_sha256']}.{ext}"
        raw = contents.encode()
        try:
            with path.open("xb") as stream:
                stream.write(raw)
        except FileExistsError:
            if path.read_bytes() != raw:
                raise ChangeError("refusing inconsistent report overwrite")
        paths.append(str(path))
    return paths



def economic_features(snapshot: dict) -> dict:
    """Export reviewed, source-timestamped numbers only. No outcomes or buy scores."""
    rows = []
    for result in snapshot["active"]:
        if result["review_status"] != "ACCEPT":
            continue
        facts = {key: value["value"] for key, value in result["facts"].items()}
        def ratio(numerator, denominator, facts=facts):
            n, d = facts.get(numerator), facts.get(denominator)
            return n / d if isinstance(n, (int, float)) and isinstance(d, (int, float)) and d > 0 else None
        values = {"cc_pbt_margin": ratio("pbt", "revenue"),
                  "cc_other_income_to_sales": ratio("other_income", "revenue"),
                  "cc_effective_tax_rate": ratio("tax_expense", "pbt"),
                  "cc_cfo_to_owner_pat": ratio("cfo", "owner_pat"),
                  "cc_reported_diluted_eps": facts.get("diluted_eps"),
                  "cc_owner_dilution": result["bridge"].get("existing_owner_dilution_fraction")}
        known = max(result["known_at"], result["review"]["recorded_at"])
        rows.append({"symbol": result["symbol"], "isin": result["isin"],
            "scope": result["selector"]["scope"], "period_start": result["selector"]["period_start"],
            "period_end": result["selector"]["period_end"], "extraction_id": result["extraction_id"],
            "features": values, "known_at": {key: known for key in values},
            "raw_sha256": result["raw_sha256"], "outcomes_attached": False})
    return {"engine": VERSION, "rows": rows, "snapshot_sha256": snapshot["snapshot_sha256"],
            "live_capital_allowed": False, "outcomes_attached": False,
            "limitations": ["Reviewed accounting features are not predictive signals by themselves.",
                            "Join to the existing point-in-time universe and baseline by identity and cutoff."]}


def record_decision(store: EvidenceStore, specification: dict) -> dict:
    """Join a reviewed extraction to explicit valuation assumptions, without orders."""
    snapshot = store.snapshot()
    matches = [r for r in snapshot["active"] if r["kind"] == "earnings_quality" and
               all(r["identity"].get(k) == specification.get(k)
                   for k in ("symbol", "isin", "scope", "event_key"))]
    if len(matches) != 1:
        raise ChangeError("decision requires one unambiguous active earnings record")
    result = matches[0]
    blockers = []
    if result["review_status"] != "ACCEPT":
        blockers.append("Latest extraction has not been accepted by a reviewer.")
    if result["source_document"] is None:
        blockers.append("Table facts do not yet establish normalized owner earnings and diluted shares.")
    # Company-level decisions must include capital events in the persistent state,
    # not just the selected earnings document. An unreviewed issuance cannot be
    # silently ignored to preserve an otherwise attractive stale EPS denominator.
    issues = [r for r in snapshot["active"] if r["kind"] == "capital_allocation"
              and r["symbol"] == result["symbol"] and r["isin"] == result["isin"]
              and r["selector"]["period_end"] >= result["selector"]["period_start"]
              and r["facts"].get("status", {}).get("value") != "CANCELLED"]
    if issues:
        blockers.append("Reconcile normalized EPS to the capital events in company history.")
    if blockers:
        card = {"disposition": "WAIT", "symbol": result["symbol"], "blockers": blockers,
                "assumptions": specification, "extraction_id": result["extraction_id"],
                "live_capital_allowed": False}
    else:
        source = {**result["source_document"], "reviewed_by": result["review"]["reviewer"],
                  "reviewed_at": result["review"]["recorded_at"]}
        report = analyze_bundle({"schema_version": 1, "as_of": store.clock(), "sources": [source],
                                 "valuations": [specification]})
        card = report["decision_cards"][0]
        card["extraction_id"] = result["extraction_id"]
    card["snapshot_sha256"] = snapshot["snapshot_sha256"]
    card["decision_id"] = store.decision(card)
    return card


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true")
    parser.add_argument("--review")
    parser.add_argument("--reviewer")
    parser.add_argument("--verdict", choices=("ACCEPT", "REJECT"))
    parser.add_argument("--rationale")
    parser.add_argument("--decision-file", type=Path)
    parser.add_argument("--export-features", action="store_true")
    parser.add_argument("--require-extracted", type=int, default=0)
    args = parser.parse_args(argv)
    try:
        with EvidenceStore(args.workspace) as store:
            if args.review:
                if not all((args.reviewer, args.verdict, args.rationale)):
                    raise ChangeError("review requires reviewer, verdict and rationale")
                print(store.review(args.review, args.reviewer, args.verdict, args.rationale))
                return 0
            if args.decision_file:
                card = record_decision(store, loads_unique(args.decision_file.read_text(encoding="utf-8")))
                print(json.dumps(card, allow_nan=False))
                return 0
            if args.export_features:
                print(json.dumps(economic_features(store.snapshot()), allow_nan=False))
                return 0
            if args.manifest is None:
                raise ChangeError("manifest required for ingestion")
            manifest = loads_unique(args.manifest.read_text(encoding="utf-8"))
            report = ingest(manifest, store, base=args.manifest.parent, allow_network=args.fetch)
            paths = write_outputs(store, report)
            print(json.dumps({"successes": report["successes"], "failures": report["failures"],
                              "artifacts": paths, "live_capital_allowed": False}))
        return 1 if report["failures"] or len(report["successes"]) < args.require_extracted else 0
    except (ValueError, TypeError, KeyError, OSError) as exc:
        print(f"CC001 pipeline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
