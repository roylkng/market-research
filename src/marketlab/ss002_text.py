from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
import zipfile
from collections import Counter, defaultdict
from pathlib import PurePosixPath
from typing import Any
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
from pypdf import PdfReader

from marketlab.alpha import AlphaContractError, digest

CORPUS_ID = "SS002-D003-v1"
EXPECTED_D002_ID = "SS002-D002-v1"
EXPECTED_D002_SHA = "eab922954ef20a12a7635107722b4e800b59cfa56ff0659da42afb3fc22218f9"
EXPECTED_DOCUMENT_COUNT = 1539
MAX_TEXT_CHARS = 8000
MAX_ZIP_MEMBERS = 100
MAX_ZIP_MEMBER_BYTES = 50 * 1024 * 1024
MAX_ZIP_TOTAL_BYTES = 250 * 1024 * 1024


class SS002TextError(ValueError):
    """Raised when deterministic text extraction cannot proceed safely."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def normalize_text(value: str) -> str:
    text = unicodedata.normalize("NFKC", value)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+$", "", line) for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _segment(
    *,
    segment_id: str,
    text: str,
    kind: str,
    locator: dict[str, Any],
) -> dict[str, Any] | None:
    normalized = normalize_text(text)
    if not normalized.strip():
        return None
    raw = normalized.encode("utf-8")
    return {
        "segment_id": segment_id,
        "kind": kind,
        "locator": locator,
        "text": normalized,
        "text_sha256": _sha(raw),
        "utf8_byte_count": len(raw),
        "char_count": len(normalized),
    }


def _text_chunks(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    chunks: list[str] = []
    current: list[str] = []
    current_chars = 0

    for line in normalized.split("\n"):
        pieces = (
            [line[i : i + MAX_TEXT_CHARS] for i in range(0, len(line), MAX_TEXT_CHARS)]
            if len(line) > MAX_TEXT_CHARS
            else [line]
        )
        for piece in pieces:
            extra = len(piece) + (1 if current else 0)
            if current and current_chars + extra > MAX_TEXT_CHARS:
                chunks.append("\n".join(current))
                current = []
                current_chars = 0
            current.append(piece)
            current_chars += len(piece) + (1 if len(current) > 1 else 0)
    if current:
        chunks.append("\n".join(current))
    return chunks


def _pdf_segments(raw: bytes, *, document_id: str, prefix: str) -> tuple[list[dict], dict]:
    try:
        reader = PdfReader(io.BytesIO(raw), strict=False)
    except Exception as exc:  # pypdf exposes multiple parser exception classes
        raise SS002TextError(f"PDF_PARSE_FAILED: {type(exc).__name__}: {exc}") from exc

    segments = []
    empty_pages = 0
    failed_pages = 0
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            failed_pages += 1
            continue
        segment = _segment(
            segment_id=f"{prefix}:pdf:page:{index:04d}",
            text=text,
            kind="PDF_PAGE",
            locator={"page_number": index},
        )
        if segment is None:
            empty_pages += 1
        else:
            segments.append(segment)
    return segments, {
        "page_count": len(reader.pages),
        "text_page_count": len(segments),
        "empty_page_count": empty_pages,
        "failed_page_count": failed_pages,
    }


def _xml_text(raw: bytes) -> str:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        raise SS002TextError(f"XML_PARSE_FAILED: {exc}") from exc
    return "\n".join(
        part.strip()
        for part in root.itertext()
        if isinstance(part, str) and part.strip()
    )


def _html_text(raw: bytes) -> str:
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SS002TextError("HTML_NOT_UTF8") from exc
    soup = BeautifulSoup(text, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text("\n")


def _plain_text(raw: bytes) -> str:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise SS002TextError("TEXT_NOT_UTF8") from exc


def _family(raw: bytes, name: str) -> str:
    if raw.startswith(b"%PDF-"):
        return "PDF"
    lower = name.casefold()
    prefix = raw[:4096]
    try:
        text = prefix.decode("utf-8-sig").lstrip().casefold()
    except UnicodeDecodeError:
        text = ""
    if text.startswith("<?xml") or "<xbrl" in text[:512] or "<xhtml" in text[:512]:
        return "XML"
    if "<html" in text[:1024] or "<!doctype html" in text[:1024]:
        return "HTML"
    if lower.endswith((".txt", ".csv")) and text:
        return "PLAIN_TEXT"
    return "UNSUPPORTED"


def _textual_segments(
    raw: bytes,
    *,
    document_id: str,
    prefix: str,
    family: str,
    locator_base: dict[str, Any],
) -> tuple[list[dict], dict]:
    if family == "XML":
        text = _xml_text(raw)
    elif family == "HTML":
        text = _html_text(raw)
    elif family == "PLAIN_TEXT":
        text = _plain_text(raw)
    else:
        raise SS002TextError(f"unsupported textual family: {family}")
    chunks = _text_chunks(text)
    segments = []
    for index, chunk in enumerate(chunks, start=1):
        segment = _segment(
            segment_id=f"{prefix}:text:chunk:{index:04d}",
            text=chunk,
            kind=f"{family}_CHUNK",
            locator={**locator_base, "chunk_index": index},
        )
        if segment is not None:
            segments.append(segment)
    return segments, {"chunk_count": len(segments)}


def _safe_zip_infos(raw: bytes) -> tuple[zipfile.ZipFile, list[zipfile.ZipInfo]]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile as exc:
        raise SS002TextError("ZIP_PARSE_FAILED") from exc
    infos = [info for info in archive.infolist() if not info.is_dir()]
    if len(infos) > MAX_ZIP_MEMBERS:
        archive.close()
        raise SS002TextError("ZIP_MEMBER_LIMIT_EXCEEDED")
    total = 0
    for info in infos:
        if info.flag_bits & 0x1:
            archive.close()
            raise SS002TextError("ZIP_ENCRYPTED_MEMBER")
        if info.file_size > MAX_ZIP_MEMBER_BYTES:
            archive.close()
            raise SS002TextError("ZIP_MEMBER_SIZE_LIMIT_EXCEEDED")
        total += info.file_size
        path = PurePosixPath(info.filename.replace("\\", "/"))
        if path.is_absolute() or ".." in path.parts:
            archive.close()
            raise SS002TextError("ZIP_UNSAFE_MEMBER_PATH")
    if total > MAX_ZIP_TOTAL_BYTES:
        archive.close()
        raise SS002TextError("ZIP_TOTAL_SIZE_LIMIT_EXCEEDED")
    return archive, infos


def _zip_segments(raw: bytes, *, document_id: str) -> tuple[list[dict], dict]:
    archive, infos = _safe_zip_infos(raw)
    segments: list[dict] = []
    members = []
    try:
        for info in sorted(infos, key=lambda item: item.filename):
            member_raw = archive.read(info)
            member_sha = _sha(member_raw)
            member_family = _family(member_raw, info.filename)
            prefix = f"{document_id}:zip:{member_sha}"
            member_segments: list[dict] = []
            details: dict[str, Any] = {}
            state = "UNSUPPORTED"
            try:
                if member_family == "PDF":
                    member_segments, details = _pdf_segments(
                        member_raw,
                        document_id=document_id,
                        prefix=prefix,
                    )
                    state = "READY" if member_segments else "NO_EXTRACTABLE_TEXT"
                elif member_family in {"XML", "HTML", "PLAIN_TEXT"}:
                    member_segments, details = _textual_segments(
                        member_raw,
                        document_id=document_id,
                        prefix=prefix,
                        family=member_family,
                        locator_base={"zip_member": info.filename},
                    )
                    state = "READY" if member_segments else "NO_EXTRACTABLE_TEXT"
            except SS002TextError as exc:
                state = "PARSE_FAILED"
                details = {"error": str(exc)}
            segments.extend(member_segments)
            members.append(
                {
                    "name": info.filename,
                    "member_sha256": member_sha,
                    "uncompressed_bytes": info.file_size,
                    "family": member_family,
                    "state": state,
                    "segment_count": len(member_segments),
                    "details": details,
                }
            )
    finally:
        archive.close()
    return segments, {
        "member_count": len(members),
        "members": members,
        "supported_member_count": sum(
            member["family"] != "UNSUPPORTED" for member in members
        ),
    }



def _segment_manifest_payload(row: dict[str, Any]) -> dict[str, Any]:
    segments = row.get("segments")
    if not isinstance(segments, list):
        raise AlphaContractError("SS002 D003 extraction row requires segments list")
    return {
        "document_id": row.get("document_id"),
        "source_url": row.get("source_url"),
        "d002_family": row.get("d002_family"),
        "extraction_state": row.get("extraction_state"),
        "details": row.get("details") or {},
        "segments": [
            {
                key: value
                for key, value in segment.items()
                if key != "text"
            }
            for segment in segments
        ],
    }


def seal_extraction_row(row: dict[str, Any]) -> dict[str, Any]:
    sealed = dict(row)
    sealed["segment_manifest_sha256"] = digest(_segment_manifest_payload(sealed))
    return sealed

def extract_document_text(
    *,
    document_id: str,
    raw: bytes,
    d002_family: str,
    source_url: str,
) -> dict[str, Any]:
    if _sha(raw) != document_id:
        raise AlphaContractError("SS002 D003 raw SHA does not match document_id")

    try:
        if d002_family == "PDF":
            segments, details = _pdf_segments(
                raw,
                document_id=document_id,
                prefix=document_id,
            )
        elif d002_family == "ZIP_CONTAINER":
            segments, details = _zip_segments(raw, document_id=document_id)
        elif d002_family == "XML_OR_XHTML":
            segments, details = _textual_segments(
                raw,
                document_id=document_id,
                prefix=document_id,
                family="XML",
                locator_base={},
            )
        elif d002_family == "HTML":
            segments, details = _textual_segments(
                raw,
                document_id=document_id,
                prefix=document_id,
                family="HTML",
                locator_base={},
            )
        elif d002_family == "PLAIN_TEXT":
            segments, details = _textual_segments(
                raw,
                document_id=document_id,
                prefix=document_id,
                family="PLAIN_TEXT",
                locator_base={},
            )
        else:
            return seal_extraction_row(
                {
                    "document_id": document_id,
                    "source_url": source_url,
                    "d002_family": d002_family,
                    "extraction_state": "UNSUPPORTED_FAMILY",
                    "details": {},
                    "segments": [],
                }
            )
    except SS002TextError as exc:
        return seal_extraction_row(
            {
                "document_id": document_id,
                "source_url": source_url,
                "d002_family": d002_family,
                "extraction_state": "PARSE_FAILED",
                "details": {"error": str(exc)},
                "segments": [],
            }
        )

    segment_ids = [segment["segment_id"] for segment in segments]
    if len(segment_ids) != len(set(segment_ids)):
        raise AlphaContractError("SS002 D003 duplicate segment IDs within document")
    state = "READY" if segments else "NO_EXTRACTABLE_TEXT"
    base = {
        "document_id": document_id,
        "source_url": source_url,
        "d002_family": d002_family,
        "extraction_state": state,
        "details": details,
        "segments": segments,
    }
    return seal_extraction_row(base)


def _validate_d002_manifest(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    if corpus.get("corpus_id") != EXPECTED_D002_ID:
        raise AlphaContractError("SS002 D003 requires frozen D002 corpus")
    if corpus.get("corpus_sha256") != EXPECTED_D002_SHA:
        raise AlphaContractError("SS002 D003 D002 corpus SHA mismatch")
    if corpus.get("unique_document_id_count") != EXPECTED_DOCUMENT_COUNT:
        raise AlphaContractError("SS002 D003 document count mismatch")
    for field in (
        "return_outcomes_opened",
        "model_fitted",
        "portfolio_eligibility_allowed",
        "live_capital_allowed",
    ):
        if corpus.get(field) is not False:
            raise AlphaContractError(f"SS002 D003 requires D002 {field}=false")
    rows = corpus.get("documents")
    if not isinstance(rows, list):
        raise AlphaContractError("SS002 D003 D002 document rows unavailable")
    return rows


def document_requests(corpus: dict[str, Any]) -> list[dict[str, Any]]:
    rows = _validate_d002_manifest(corpus)
    grouped: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"urls": set(), "families": set(), "event_ids": set(), "symbols": set(), "categories": set()}
    )
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "READY":
            continue
        doc_id = str(row.get("document_id") or "")
        url = str(row.get("source_url") or "")
        family = str(row.get("document_family") or "")
        if not doc_id or len(doc_id) != 64 or not url or not family:
            raise AlphaContractError("SS002 D003 READY D002 row is incomplete")
        item = grouped[doc_id]
        item["urls"].add(url)
        item["families"].add(family)
        item["event_ids"].update(str(v) for v in row.get("event_ids", []))
        item["symbols"].update(str(v) for v in row.get("symbols", []))
        item["categories"].update(str(v) for v in row.get("categories", []))
    if len(grouped) != EXPECTED_DOCUMENT_COUNT:
        raise AlphaContractError(
            f"SS002 D003 expected {EXPECTED_DOCUMENT_COUNT} unique documents, observed {len(grouped)}"
        )
    result = []
    for doc_id, item in sorted(grouped.items()):
        if len(item["families"]) != 1:
            raise AlphaContractError(f"{doc_id}: conflicting D002 document families")
        result.append(
            {
                "document_id": doc_id,
                "source_urls": sorted(item["urls"]),
                "d002_family": next(iter(item["families"])),
                "event_ids": sorted(item["event_ids"]),
                "symbols": sorted(item["symbols"]),
                "categories": sorted(item["categories"]),
            }
        )
    return result


def build_text_corpus(
    *,
    d002_corpus: dict[str, Any],
    extraction_rows: list[dict[str, Any]],
    captured_at_utc: str,
) -> dict[str, Any]:
    requests = document_requests(d002_corpus)
    expected_ids = {row["document_id"] for row in requests}
    by_id: dict[str, dict[str, Any]] = {}
    for row in extraction_rows:
        if not isinstance(row, dict):
            raise TypeError("SS002 D003 extraction rows must be objects")
        doc_id = str(row.get("document_id") or "")
        if doc_id not in expected_ids or doc_id in by_id:
            raise AlphaContractError("SS002 D003 extraction identity mismatch")
        by_id[doc_id] = row
    if set(by_id) != expected_ids:
        raise AlphaContractError("SS002 D003 extraction rows do not cover all documents")

    states = Counter()
    family_counts = Counter()
    ready_count = 0
    reproduced_count = 0
    pdf_reproduced = 0
    pdf_ready = 0
    segment_count = 0
    total_text_chars = 0
    global_segment_ids: set[str] = set()

    manifest_rows = []
    for request in requests:
        row = by_id[request["document_id"]]
        state = str(row.get("extraction_state") or "UNKNOWN")
        states[state] += 1
        family = request["d002_family"]
        family_counts[family] += 1
        if row.get("hash_reproduced") is True:
            reproduced_count += 1
            if family == "PDF":
                pdf_reproduced += 1
        if state == "READY":
            ready_count += 1
            if family == "PDF":
                pdf_ready += 1
        segments = row.get("segments")
        if not isinstance(segments, list):
            raise AlphaContractError("SS002 D003 segments must be a list")
        expected_manifest_sha = seal_extraction_row(
            {
                key: value
                for key, value in row.items()
                if key != "segment_manifest_sha256"
            }
        )["segment_manifest_sha256"]
        if row.get("segment_manifest_sha256") != expected_manifest_sha:
            raise AlphaContractError("SS002 D003 segment manifest SHA mismatch")
        if state == "READY" and not segments:
            raise AlphaContractError("SS002 D003 READY document requires text segments")
        if state != "READY" and segments:
            raise AlphaContractError("SS002 D003 non-READY document cannot carry text segments")
        for segment in segments:
            seg_id = str(segment.get("segment_id") or "")
            text = segment.get("text")
            text_sha = str(segment.get("text_sha256") or "")
            if not seg_id or not isinstance(text, str):
                raise AlphaContractError("SS002 D003 segment is incomplete")
            if seg_id in global_segment_ids:
                raise AlphaContractError("SS002 D003 segment IDs must be globally unique")
            global_segment_ids.add(seg_id)
            if _sha(text.encode("utf-8")) != text_sha:
                raise AlphaContractError("SS002 D003 text SHA mismatch")
            segment_count += 1
            total_text_chars += len(text)
        manifest_rows.append(
            {
                key: value
                for key, value in row.items()
                if key != "segments"
            }
            | {
                "segment_count": len(segments),
                "segment_ids": [segment["segment_id"] for segment in segments],
                "event_ids": request["event_ids"],
                "symbols": request["symbols"],
                "categories": request["categories"],
            }
        )

    reproduced_ratio = reproduced_count / EXPECTED_DOCUMENT_COUNT
    ready_ratio = ready_count / max(reproduced_count, 1)
    pdf_ready_ratio = pdf_ready / max(pdf_reproduced, 1)
    gates = {
        "complete_document_accounting": len(extraction_rows) == EXPECTED_DOCUMENT_COUNT,
        "minimum_hash_reproduction_95pct": reproduced_ratio >= 0.95,
        "minimum_text_ready_90pct": ready_ratio >= 0.90,
        "minimum_pdf_text_ready_92pct": pdf_ready_ratio >= 0.92,
        "deterministic_segment_identity": segment_count == len(global_segment_ids),
    }

    output = {
        "schema_version": 1,
        "corpus_id": CORPUS_ID,
        "classification": "DETERMINISTIC_SPECIAL_SITUATION_TEXT_CORPUS_NOT_ALPHA",
        "captured_at_utc": captured_at_utc,
        "source_d002_corpus_sha256": EXPECTED_D002_SHA,
        "document_count": EXPECTED_DOCUMENT_COUNT,
        "hash_reproduced_count": reproduced_count,
        "hash_reproduced_ratio": reproduced_ratio,
        "text_ready_document_count": ready_count,
        "text_ready_ratio_of_reproduced": ready_ratio,
        "pdf_reproduced_count": pdf_reproduced,
        "pdf_text_ready_count": pdf_ready,
        "pdf_text_ready_ratio": pdf_ready_ratio,
        "segment_count": segment_count,
        "total_text_char_count": total_text_chars,
        "extraction_state_counts": dict(sorted(states.items())),
        "document_family_counts": dict(sorted(family_counts.items())),
        "threshold_passes": gates,
        "feasibility_pass": all(gates.values()),
        "promotion_allowed_to_l001": all(gates.values()),
        "documents": manifest_rows,
        "return_outcomes_opened": False,
        "model_fitted": False,
        "llm_inference_executed": False,
        "portfolio_eligibility_allowed": False,
        "live_capital_allowed": False,
    }
    output["corpus_sha256"] = digest(output)
    return output
