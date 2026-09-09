"""Outcome-blind numeric extraction audit for the frozen H019 annual-report corpus."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import time
import zipfile
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse
from xml.etree import ElementTree as ET

import requests
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from marketlab.nse import NSEAcquisitionError, NSEClient, NSEEndpoint

LEGACY = NSEEndpoint(
    "legacy_financials",
    "https://www.nseindia.com/api/corporates-financial-results",
)
ARCHIVE_HOSTS = {"nsearchives.nseindia.com", "archives.nseindia.com"}
REPORT_CORPUS_STATUS = "H019_ANNUAL_REPORT_SOURCE_FEASIBILITY_ONLY"
REPORT_COUNT = 12
MAX_PAGES = 500
BALANCE_TOLERANCE = 0.005
XBRL_REL_TOLERANCE = 0.01
EPS_ABS_TOLERANCE = 0.02

NUMBER_RE = re.compile(r"(?<![\w.])\(?-?\d[\d,]*(?:\.\d+)?\)?")

FACT_PATTERNS = {
    "revenue": (
        r"\brevenue from operations\b",
        r"\btotal revenue from operations\b",
    ),
    "pat": (
        r"\bprofit\s*/?\s*\(?loss\)?\s+for the (?:year|period)\b",
        r"\bprofit for the year\b",
        r"\bnet profit after tax\b",
        r"\bprofit\s*/?\s*\(?loss\)?\s+after tax\b",
    ),
    "assets": (r"^\s*total assets\b",),
    "equity": (r"^\s*total equity\b(?!\s+and\s+liabil)",),
    "equity_and_liabilities": (r"^\s*total equity and liabilities\b",),
    "share_capital": (
        r"^\s*(?:\(?[a-z0-9]+\)?\s*)?(?:equity\s+)?share capital\b",
    ),
    "other_equity": (r"^\s*(?:\(?[a-z0-9]+\)?\s*)?other equity\b",),
    "reserves_surplus": (r"^\s*reserves and surplus\b",),
    "finance_cost": (r"^\s*(?:\(?[a-z0-9ivx.]+\)?\s*)?finance costs?\b",),
    "cfo": (
        r"\bnet cash .*operating activities\b",
        r"\bnet cash flow .*operating activities\b",
    ),
    "eps": (
        r"\bbasic earnings per share\b",
        r"^\s*(?:a\)|\(?1\)?|[-–])?\s*basic\b",
        r"\bbasic and diluted\b",
    ),
    "capex": (
        r"\bpurchase of property,? plant and equipment\b",
        r"\bcapital expenditure\b",
        r"\badditions to property,? plant and equipment\b",
    ),
}

XBRL_PATTERNS = {
    "revenue": (
        "revenuefromoperations",
        "revenuefromoperationsgross",
    ),
    "pat": (
        "profitlossforperiod",
        "profitlossforperiodfromcontinuingoperations",
        "profitlossaftertax",
        "profitaftertax",
    ),
    "eps": (
        "basicearningslosspersharefromcontinuinganddiscontinuedoperations",
        "basicearningslosspersharefromcontinuingoperations",
        "basicearningspershare",
    ),
}


def dump(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n")


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def retain(root: Path, raw: bytes, *, url: str, kind: str) -> dict[str, object]:
    digest = sha256(raw)
    target = root / "raw" / digest
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if target.read_bytes() != raw:
            raise ValueError("content-addressed source collision")
    else:
        target.write_bytes(raw)
    return {
        "url": url,
        "kind": kind,
        "sha256": digest,
        "bytes": len(raw),
        "raw_path": str(target.relative_to(root)),
        "captured_at_utc": datetime.now(UTC).isoformat(),
        "status": "OK",
    }


def normalized_local_name(tag: str) -> str:
    local = tag.rsplit("}", 1)[-1].split(":")[-1]
    return re.sub(r"[^a-z0-9]", "", local.casefold())


def numeric_token(token: str) -> float | None:
    text = token.strip()
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").replace(",", "")
    try:
        value = float(text)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return -value if negative else value


def line_tokens(line: str) -> list[dict[str, object]]:
    result = []
    for match in NUMBER_RE.finditer(line):
        token = match.group(0)
        value = numeric_token(token)
        if value is None:
            continue
        result.append({"offset": match.start(), "token": token, "value": value})
    return result


def numeric_pair(line: str) -> tuple[dict[str, object], dict[str, object]] | None:
    tokens = [
        token
        for token in line_tokens(line)
        if not (
            float(token["value"]).is_integer()
            and 1900 <= float(token["value"]) <= 2100
        )
    ]
    if len(tokens) < 2:
        return None
    while len(tokens) >= 3:
        first = tokens[0]
        value = abs(float(first["value"]))
        source = str(first["token"])
        if value <= 100 and float(first["value"]).is_integer() and "," not in source and "." not in source:
            tokens = tokens[1:]
            continue
        break
    if len(tokens) < 2:
        return None
    return tokens[0], tokens[1]


def collapse(text: str) -> str:
    return " ".join(text.casefold().split())


def statement_score(text: str, kind: str, page_number: int) -> tuple[int, int]:
    normalized = collapse(text)
    score = 0
    if kind == "balance":
        score += 3 * int("balance sheet" in normalized or "statement of financial position" in normalized)
        score += 2 * int("total assets" in normalized)
        score += 2 * int("equity" in normalized and "liabilit" in normalized)
    elif kind == "profit_loss":
        score += 3 * int(
            "statement of profit and loss" in normalized
            or "statement of profit & loss" in normalized
            or "profit and loss account" in normalized
        )
        score += 2 * int("revenue" in normalized)
        score += 2 * int("profit" in normalized)
    elif kind == "cash_flow":
        score += 3 * int(
            "cash flow statement" in normalized
            or "statement of cash flows" in normalized
            or "cash flow" in normalized
        )
        score += 3 * int("operating activities" in normalized)
    else:
        raise ValueError(f"unknown statement kind: {kind}")
    if "consolidated" in normalized[:1600]:
        score -= 4
    if "independent auditor" in normalized[:800]:
        score -= 4
    return score, -page_number


def choose_statement_page(pages: list[str], kind: str) -> tuple[int, str] | None:
    candidates = []
    for index, text in enumerate(pages):
        score, tie = statement_score(text, kind, index)
        threshold = 5 if kind != "cash_flow" else 6
        if score >= threshold:
            candidates.append((score, tie, index, text))
    if not candidates:
        return None
    _, _, index, text = max(candidates)
    return index, text


def unit_scale(text: str) -> dict[str, object] | None:
    normalized = collapse(text[:5000])
    if re.search(r"\b(?:in|amounts? in)\s+(?:rs\.?\s*|₹\s*)?lakhs?\b", normalized) or re.search(
        r"\b(?:in|amounts? in)\s+(?:rs\.?\s*|₹\s*)?lacs?\b", normalized
    ):
        return {"label": "LAKH", "scale_to_inr": 100000.0}
    if re.search(r"\b(?:in|amounts? in)\s+(?:rs\.?\s*|₹\s*)?crores?\b", normalized):
        return {"label": "CRORE", "scale_to_inr": 10000000.0}
    if "amount in rupees" in normalized or "amounts in rupees" in normalized:
        return {"label": "INR", "scale_to_inr": 1.0}
    if re.search(r"\b(?:rs\.?|₹)\s*in\s+lakhs?\b", normalized):
        return {"label": "LAKH", "scale_to_inr": 100000.0}
    return None


def extract_line_fact(
    page_text: str,
    patterns: tuple[str, ...],
    *,
    exclusions: tuple[str, ...] = (),
) -> dict[str, object] | None:
    candidates = []
    lines = page_text.splitlines()
    for index, line in enumerate(lines):
        normalized = line.casefold()
        if any(exclusion in normalized for exclusion in exclusions):
            continue
        if not any(re.search(pattern, normalized) for pattern in patterns):
            continue
        pair = numeric_pair(line)
        if pair is None:
            continue
        first, second = pair
        score = 0
        score += 2 if len(line) <= 240 else -1
        score += 1 if index < int(len(lines) * 0.9) else 0
        if any(word in normalized for word in ("calculated", "computed", "policy", "reconciliation")):
            score -= 4
        candidates.append((score, -index, line.rstrip(), first, second))
    if not candidates:
        return None
    _, _, line, current, prior = max(candidates)
    return {
        "source_line": line,
        "current_token": current["token"],
        "prior_token": prior["token"],
        "current": float(current["value"]),
        "prior": float(prior["value"]),
        "derivation": "DIRECT",
    }


def equity_section_has_extra_components(page_text: str) -> bool:
    normalized = collapse(page_text)
    warning_tokens = (
        "share application money",
        "share warrants",
        "money received against share warrants",
        "non-controlling interest",
        "minority interest",
        "hybrid capital",
    )
    return any(token in normalized for token in warning_tokens)


def derive_equity(page_text: str) -> dict[str, object] | None:
    if equity_section_has_extra_components(page_text):
        return None
    share = extract_line_fact(page_text, FACT_PATTERNS["share_capital"])
    other = extract_line_fact(page_text, FACT_PATTERNS["other_equity"])
    mode = "SHARE_CAPITAL_PLUS_OTHER_EQUITY"
    if other is None:
        other = extract_line_fact(page_text, FACT_PATTERNS["reserves_surplus"])
        mode = "SHARE_CAPITAL_PLUS_RESERVES_SURPLUS"
    if share is None or other is None:
        return None
    current = float(share["current"]) + float(other["current"])
    prior = float(share["prior"]) + float(other["prior"])
    return {
        "current": current,
        "prior": prior,
        "derivation": mode,
        "components": {"share_capital": share, "other_component": other},
    }


def extract_borrowings(page_text: str) -> dict[str, object] | None:
    rows = []
    for line in page_text.splitlines():
        normalized = line.casefold()
        if "borrowings" not in normalized or "other" in normalized:
            continue
        if any(token in normalized for token in ("repayment", "proceeds", "risk", "covenant")):
            continue
        pair = numeric_pair(line)
        if pair is None:
            continue
        rows.append(
            {
                "source_line": line.rstrip(),
                "current": float(pair[0]["value"]),
                "prior": float(pair[1]["value"]),
                "current_token": pair[0]["token"],
                "prior_token": pair[1]["token"],
            }
        )
    if len(rows) != 2:
        return None
    return {
        "current": sum(float(row["current"]) for row in rows),
        "prior": sum(float(row["prior"]) for row in rows),
        "derivation": "TWO_EXPLICIT_BORROWING_ROWS",
        "components": rows,
    }


def extract_pdf_from_container(raw: bytes, source_url: str) -> bytes | None:
    suffix = Path(urlparse(source_url).path).suffix.casefold()
    if suffix == ".pdf":
        return raw
    if suffix != ".zip":
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            candidates = [
                name
                for name in archive.namelist()
                if not name.endswith("/") and Path(name).suffix.casefold() == ".pdf"
            ]
            if len(candidates) != 1:
                return None
            return archive.read(candidates[0])
    except (OSError, RuntimeError, zipfile.BadZipFile):
        return None


def extract_pages(pdf_raw: bytes) -> tuple[list[str], str | None]:
    try:
        reader = PdfReader(io.BytesIO(pdf_raw), strict=False)
    except (OSError, PdfReadError, TypeError, ValueError) as exc:
        return [], f"{type(exc).__name__}: {exc}"
    pages = []
    for page in reader.pages[:MAX_PAGES]:
        try:
            pages.append(page.extract_text(extraction_mode="layout") or "")
        except (KeyError, OSError, TypeError, ValueError):
            pages.append("")
    return pages, None


def attach_fact_provenance(
    fact: dict[str, object] | None,
    *,
    statement: str,
    page_number: int,
    unit: dict[str, object] | None,
) -> dict[str, object] | None:
    if fact is None:
        return None
    result = dict(fact)
    result["statement"] = statement
    result["page_number"] = page_number
    result["unit"] = unit
    if unit is not None:
        scale = float(unit["scale_to_inr"])
        result["current_inr"] = float(result["current"]) * scale
        result["prior_inr"] = float(result["prior"]) * scale
    return result


def extract_report(row: dict[str, object], corpus_root: Path) -> dict[str, object]:
    report_path = corpus_root / str(row["raw_path"])
    raw = report_path.read_bytes()
    if sha256(raw) != row.get("sha256"):
        raise ValueError(f"annual-report container hash mismatch for {row['symbol']}")
    pdf_raw = extract_pdf_from_container(raw, str(row["report_url"]))
    result: dict[str, object] = {
        "symbol": row["symbol"],
        "group": row["group"],
        "from_year": row["from_year"],
        "to_year": row["to_year"],
        "report_url": row["report_url"],
        "report_sha256": row["sha256"],
        "status": "PENDING",
    }
    if pdf_raw is None:
        result["status"] = "PDF_CONTAINER_UNUSABLE"
        return result
    if sha256(pdf_raw) != row.get("pdf_sha256"):
        raise ValueError(f"annual-report PDF hash mismatch for {row['symbol']}")
    result["pdf_sha256"] = row["pdf_sha256"]
    pages, error = extract_pages(pdf_raw)
    if error is not None:
        result["status"] = "PDF_PARSE_FAILED"
        result["error"] = error
        return result
    if not any(page.strip() for page in pages):
        result["status"] = "NO_TEXT_NO_OCR"
        return result

    selected = {
        kind: choose_statement_page(pages, kind)
        for kind in ("balance", "profit_loss", "cash_flow")
    }
    result["statement_pages"] = {
        kind: (selection[0] + 1 if selection is not None else None)
        for kind, selection in selected.items()
    }
    facts: dict[str, object] = {}

    balance = selected["balance"]
    if balance is not None:
        page_index, text = balance
        unit = unit_scale(text)
        assets = extract_line_fact(text, FACT_PATTERNS["assets"])
        equity = extract_line_fact(
            text,
            FACT_PATTERNS["equity"],
            exclusions=("equity and liabilities", "equity share capital"),
        )
        if equity is None:
            equity = derive_equity(text)
        total = extract_line_fact(text, FACT_PATTERNS["equity_and_liabilities"])
        borrowings = extract_borrowings(text)
        for name, fact in (
            ("total_assets", assets),
            ("total_equity", equity),
            ("total_equity_and_liabilities", total),
            ("total_borrowings", borrowings),
        ):
            attached = attach_fact_provenance(
                fact,
                statement="BALANCE_SHEET",
                page_number=page_index + 1,
                unit=unit,
            )
            if attached is not None:
                facts[name] = attached

    profit_loss = selected["profit_loss"]
    if profit_loss is not None:
        page_index, text = profit_loss
        unit = unit_scale(text)
        for name, pattern_name in (
            ("revenue", "revenue"),
            ("pat", "pat"),
            ("finance_cost", "finance_cost"),
        ):
            fact = extract_line_fact(text, FACT_PATTERNS[pattern_name])
            attached = attach_fact_provenance(
                fact,
                statement="PROFIT_AND_LOSS",
                page_number=page_index + 1,
                unit=unit,
            )
            if attached is not None:
                facts[name] = attached
        eps = extract_line_fact(text, FACT_PATTERNS["eps"])
        if eps is not None:
            facts["basic_eps"] = attach_fact_provenance(
                eps,
                statement="PROFIT_AND_LOSS",
                page_number=page_index + 1,
                unit={"label": "INR_PER_SHARE", "scale_to_inr": 1.0},
            )

    cash_flow = selected["cash_flow"]
    if cash_flow is not None:
        page_index, text = cash_flow
        unit = unit_scale(text)
        for name, pattern_name in (("operating_cash_flow", "cfo"), ("capex", "capex")):
            fact = extract_line_fact(text, FACT_PATTERNS[pattern_name])
            attached = attach_fact_provenance(
                fact,
                statement="CASH_FLOW",
                page_number=page_index + 1,
                unit=unit,
            )
            if attached is not None:
                facts[name] = attached

    result["facts"] = facts
    assets = facts.get("total_assets")
    total = facts.get("total_equity_and_liabilities")
    identity: dict[str, object] | None = None
    if isinstance(assets, dict) and isinstance(total, dict):
        current_assets = float(assets["current"])
        current_total = float(total["current"])
        prior_assets = float(assets["prior"])
        prior_total = float(total["prior"])
        current_residual = abs(current_assets - current_total) / max(abs(current_assets), 1.0)
        prior_residual = abs(prior_assets - prior_total) / max(abs(prior_assets), 1.0)
        identity = {
            "current_residual": current_residual,
            "prior_residual": prior_residual,
            "current_pass": current_residual <= BALANCE_TOLERANCE,
            "prior_pass": prior_residual <= BALANCE_TOLERANCE,
        }
    result["balance_identity"] = identity
    result["status"] = "EXTRACTED"
    return result


def valid_xbrl_url(value: object) -> str | None:
    url = str(value or "").strip()
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").casefold() not in ARCHIVE_HOSTS:
        return None
    return url if url.casefold().endswith((".xml", ".xhtml", ".html")) else None


def parse_period(value: object) -> date | None:
    text = str(value or "").strip()
    for fmt in ("%d-%b-%Y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            parsed = time.strptime(text, fmt)
            return date(parsed.tm_year, parsed.tm_mon, parsed.tm_mday)
        except ValueError:
            continue
    return None


def fetch_annual_listing(client: NSEClient, root: Path, year: int) -> list[dict[str, object]]:
    params = {
        "index": "equities",
        "period": "Annual",
        "from_date": f"01-01-{year}",
        "to_date": f"31-12-{year}",
    }
    payload, raw = client._json_get_with_raw(LEGACY, params=params)
    url = LEGACY.url + "?" + urlencode(params)
    retain(root, raw, url=url, kind=f"annual-result-listing-{year}")
    if not isinstance(payload, list):
        raise TypeError("annual result listing must be a list")
    return [row for row in payload if isinstance(row, dict)]


def standalone_xbrl_map(rows: list[dict[str, object]]) -> dict[tuple[str, int], str]:
    candidates: dict[tuple[str, int], list[tuple[str, str]]] = {}
    for row in rows:
        symbol = str(row.get("symbol") or "").strip().upper()
        period = parse_period(row.get("toDate") or row.get("qe_Date"))
        url = valid_xbrl_url(row.get("xbrl"))
        if not symbol or period is None or url is None:
            continue
        consolidated = str(row.get("consolidated") or "").strip().casefold()
        if consolidated == "consolidated":
            continue
        published = str(row.get("broadCastDate") or row.get("broadcast_Date") or "")
        candidates.setdefault((symbol, period.year), []).append((published, url))
    return {
        key: max(values, key=lambda item: (item[0], item[1]))[1]
        for key, values in candidates.items()
    }


def fetch_archive(url: str) -> bytes | None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 marketlab-h019-numeric-audit/1"})
    for attempt in range(3):
        try:
            response = session.get(url, timeout=(8, 30), allow_redirects=True)
            host = (urlparse(response.url).hostname or "").casefold()
            if host not in ARCHIVE_HOSTS:
                raise ValueError("structured filing redirected outside NSE archive hosts")
            if response.status_code == 404:
                return None
            if (
                response.status_code in {403, 429} or response.status_code >= 500
            ) and attempt < 2:
                time.sleep(0.5 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.content or None
        except (requests.RequestException, ValueError):
            if attempt < 2:
                time.sleep(0.5 * (attempt + 1))
    return None


def structured_facts(raw: bytes) -> dict[str, list[dict[str, object]]]:
    result = {name: [] for name in XBRL_PATTERNS}
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return result
    for node in root.iter():
        if not isinstance(node.tag, str) or node.text is None:
            continue
        name = normalized_local_name(node.tag)
        text = node.text.strip().replace(",", "")
        try:
            value = float(text)
        except ValueError:
            continue
        if not math.isfinite(value):
            continue
        for fact, patterns in XBRL_PATTERNS.items():
            if name in patterns:
                result[fact].append(
                    {
                        "concept": name,
                        "value": value,
                        "unit_ref": node.attrib.get("unitRef"),
                        "context_ref": node.attrib.get("contextRef"),
                    }
                )
    return result


def compare_fact(
    pdf_fact: dict[str, object] | None,
    candidates: list[dict[str, object]],
    *,
    eps: bool = False,
) -> dict[str, object] | None:
    if pdf_fact is None or not candidates or "current_inr" not in pdf_fact:
        return None
    target = float(pdf_fact["current_inr"])
    scored = []
    for candidate in candidates:
        value = float(candidate["value"])
        absolute = abs(value - target)
        relative = absolute / max(abs(target), 1.0)
        scored.append((relative, absolute, candidate))
    relative, absolute, best = min(scored, key=lambda item: (item[0], item[1]))
    passed = relative <= XBRL_REL_TOLERANCE
    if eps:
        passed = passed or absolute <= EPS_ABS_TOLERANCE
    return {
        "pdf_value": target,
        "structured_value": float(best["value"]),
        "structured_concept": best["concept"],
        "structured_context_ref": best.get("context_ref"),
        "relative_difference": relative,
        "absolute_difference": absolute,
        "pass": passed,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    corpus_root = Path(args.corpus_root)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    source_summary = json.loads((corpus_root / "source-audit-v2-summary.json").read_text())
    if source_summary.get("status") != REPORT_CORPUS_STATUS:
        raise ValueError("unexpected H019 source corpus status")
    if source_summary.get("market_outcomes_opened") is not False:
        raise ValueError("H019 source corpus is not outcome-blind")
    corpus = json.loads((corpus_root / "annual-report-content-sample.json").read_text())
    if not isinstance(corpus, list) or len(corpus) != REPORT_COUNT:
        raise ValueError(f"expected {REPORT_COUNT} frozen reports")

    extracted = []
    for number, row in enumerate(corpus, 1):
        if not isinstance(row, dict):
            raise TypeError("frozen report row is not an object")
        result = extract_report(row, corpus_root)
        extracted.append(result)
        print(
            f"H019 numeric PDF extraction {number}/{len(corpus)} {row['group']} {row['symbol']}: {result['status']}",
            flush=True,
        )
    dump(out / "pdf-numeric-extractions.json", extracted)

    client = NSEClient(timeout=20, attempts=4)
    xbrl_listing = []
    try:
        xbrl_listing = fetch_annual_listing(client, out, 2018)
    except (NSEAcquisitionError, KeyError, TypeError, ValueError) as exc:
        dump(out / "structured-crosscheck-error.json", {"error": f"{type(exc).__name__}: {exc}"})
    xbrl_map = standalone_xbrl_map(xbrl_listing)

    crosschecks = []
    for result in extracted:
        key = (str(result["symbol"]), int(result["to_year"]))
        url = xbrl_map.get(key)
        if url is None:
            continue
        raw = fetch_archive(url)
        if raw is None:
            crosschecks.append(
                {"symbol": result["symbol"], "to_year": result["to_year"], "url": url, "status": "FETCH_FAILED"}
            )
            continue
        retained = retain(out, raw, url=url, kind="standalone-annual-result-xbrl")
        candidates = structured_facts(raw)
        facts = result.get("facts") if isinstance(result.get("facts"), dict) else {}
        comparisons = {
            "revenue": compare_fact(facts.get("revenue"), candidates["revenue"]),
            "pat": compare_fact(facts.get("pat"), candidates["pat"]),
            "eps": compare_fact(facts.get("basic_eps"), candidates["eps"], eps=True),
        }
        crosschecks.append(
            {
                "symbol": result["symbol"],
                "to_year": result["to_year"],
                "status": "EVALUATED",
                "url": url,
                "source_sha256": retained["sha256"],
                "comparisons": comparisons,
            }
        )
    dump(out / "structured-crosschecks.json", crosschecks)

    def has_fact(report: dict[str, object], name: str) -> bool:
        facts = report.get("facts")
        return isinstance(facts, dict) and isinstance(facts.get(name), dict)

    core_names = ("revenue", "pat", "total_assets", "total_equity")
    core_current = sum(all(has_fact(report, name) for name in core_names) for report in extracted)
    core_two_year = sum(
        all(
            has_fact(report, name)
            and "prior" in report["facts"][name]
            for name in core_names
        )
        for report in extracted
    )
    cfo_current = sum(has_fact(report, "operating_cash_flow") for report in extracted)
    balance_pass = sum(
        isinstance(report.get("balance_identity"), dict)
        and bool(report["balance_identity"].get("current_pass"))
        for report in extracted
    )
    exit_core = sum(
        report.get("group") == "EXIT_PROXY" and all(has_fact(report, name) for name in core_names)
        for report in extracted
    )

    pnl_comparisons = []
    eps_comparisons = []
    for row in crosschecks:
        comparisons = row.get("comparisons")
        if not isinstance(comparisons, dict):
            continue
        for name in ("revenue", "pat"):
            comparison = comparisons.get(name)
            if isinstance(comparison, dict):
                pnl_comparisons.append(comparison)
        comparison = comparisons.get("eps")
        if isinstance(comparison, dict):
            eps_comparisons.append(comparison)
    pnl_pass = sum(bool(item["pass"]) for item in pnl_comparisons)
    pnl_rate = pnl_pass / len(pnl_comparisons) if pnl_comparisons else 0.0

    gates = {
        "core_current_ge_8": core_current >= 8,
        "operating_cash_flow_ge_8": cfo_current >= 8,
        "core_two_year_ge_6": core_two_year >= 6,
        "balance_identity_current_ge_6": balance_pass >= 6,
        "exit_proxy_core_current_ge_3": exit_core >= 3,
        "structured_revenue_pat_comparisons_ge_5": len(pnl_comparisons) >= 5,
        "structured_revenue_pat_pass_rate_ge_80pct": len(pnl_comparisons) >= 5 and pnl_rate >= 0.80,
        "market_outcomes_opened_false": True,
    }
    summary = {
        "status": "H019_NUMERIC_EXTRACTION_AUDIT_ONLY",
        "market_outcomes_opened": False,
        "live_capital_allowed": False,
        "frozen_report_count": len(extracted),
        "core_current_reports": core_current,
        "operating_cash_flow_reports": cfo_current,
        "core_two_year_reports": core_two_year,
        "balance_identity_current_pass_reports": balance_pass,
        "exit_proxy_core_current_reports": exit_core,
        "structured_revenue_pat_comparisons": len(pnl_comparisons),
        "structured_revenue_pat_pass_count": pnl_pass,
        "structured_revenue_pat_pass_rate": pnl_rate,
        "structured_eps_comparisons": len(eps_comparisons),
        "structured_eps_pass_count": sum(bool(item["pass"]) for item in eps_comparisons),
        "extraction_status": dict(Counter(str(report.get("status")) for report in extracted)),
        "gates": gates,
        "pass": all(gates.values()),
    }
    dump(out / "numeric-extraction-summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
