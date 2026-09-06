from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"expected one patch target in {path}, found {text.count(old)}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


path = "src/marketlab/h003_candidates.py"
replace_once(
    path,
    '''EXTRACTION_RULE_ID = "H003-E001"\nEXTRACTION_RULE_SHA256 = "db954a0737bf9b049130c899104008479e677460a21c98b6a54855188180def8"\n''',
    '''EXTRACTION_RULE_ID = "H003-E002"\nEXTRACTION_RULE_SHA256 = "5aff200d6a2222a7cde972ad341bc43b927d9c5b6d26a58766893980515c24a2"\n''',
)
replace_once(
    path,
    '''CANDIDATE_VERSION = "h003_future_commitment_candidate_v1"\n''',
    '''CANDIDATE_VERSION = "h003_future_commitment_candidate_v2"\n''',
)
replace_once(
    path,
    '''FUTURE_MARKERS = (\n    "we will",\n    "we expect",\n    "we target",\n    "our target",\n    "we aim",\n    "we plan",\n    "we intend",\n    "we anticipate",\n    "we should",\n    "we are targeting",\n    "we are aiming",\n    "we are planning",\n    "guidance",\n    "targeting",\n    "aiming for",\n    "plan to",\n    "expect to",\n    "expected to",\n)\n''',
    '''FUTURE_MARKERS = (\n    "we will",\n    "we expect",\n    "we target",\n    "our target",\n    "we aim",\n    "we plan",\n    "we intend",\n    "we anticipate",\n    "we are targeting",\n    "we are aiming",\n    "we are planning",\n    "our guidance",\n    "our plan",\n    "our expectation",\n)\n''',
)
insert_after = '''DEADLINE_MARKERS = (\n    "by fy",\n    "in fy",\n    "during fy",\n    "this fiscal",\n    "next fiscal",\n    "this year",\n    "next year",\n    "this quarter",\n    "next quarter",\n    "by the end",\n    "by end",\n    "within",\n    "over the next",\n    "in the next",\n    "by march",\n    "by june",\n    "by september",\n    "by december",\n    "q1",\n    "q2",\n    "q3",\n    "q4",\n    "h1",\n    "h2",\n)\n'''
replacement = insert_after + '''COMMITMENT_DOMAIN_MARKERS = (\n    "revenue",\n    "sales",\n    "growth",\n    "margin",\n    "ebitda",\n    "ebit",\n    "profit",\n    "pat",\n    "cash flow",\n    "free cash flow",\n    "capex",\n    "capital expenditure",\n    "debt",\n    "leverage",\n    "roce",\n    "roe",\n    "return on capital",\n    "volume",\n    "production",\n    "capacity",\n    "utilisation",\n    "utilization",\n    "commission",\n    "commissioning",\n    "launch",\n    "order book",\n    "orders",\n    "conversion",\n    "market share",\n    "stores",\n    "outlets",\n    "plants",\n    "customers",\n    "subscribers",\n    "homes",\n    "arpu",\n    "realisation",\n    "realization",\n    "cost",\n    "savings",\n    "exports",\n    "shipments",\n    "deliveries",\n    "network",\n    "mw",\n    "gw",\n    "mt",\n    "tonnes",\n    "tons",\n)\n'''
replace_once(path, insert_after, replacement)
replace_once(
    path,
    '''    if document.get("id") != EXTRACTION_RULE_ID:\n        raise H003CandidateError("unexpected H003 extraction rule id")\n    if document.get("status") != "FROZEN":\n''',
    '''    if document.get("schema_version") != 2:\n        raise H003CandidateError("H003 extraction rule schema changed")\n    if document.get("id") != EXTRACTION_RULE_ID:\n        raise H003CandidateError("unexpected H003 extraction rule id")\n    if document.get("supersedes") != "H003-E001":\n        raise H003CandidateError("H003 E002 must supersede the audited E001 pilot")\n    if document.get("status") != "FROZEN":\n''',
)
replace_once(
    path,
    '''    expected_candidate = {\n        "version": CANDIDATE_VERSION,\n        "context_radius_lines": 1,\n        "min_excerpt_chars": 20,\n        "max_excerpt_chars": 800,\n        "require_future_marker": True,\n        "require_quantitative_or_deadline_marker": True,\n        "future_markers": list(FUTURE_MARKERS),\n        "deadline_markers": list(DEADLINE_MARKERS),\n        "exclude_markers": list(EXCLUDE_MARKERS),\n        "quantitative_regex": QUANTITATIVE_REGEX,\n    }\n''',
    '''    expected_candidate = {\n        "version": CANDIDATE_VERSION,\n        "anchor_future_markers": list(FUTURE_MARKERS),\n        "forward_context_lines": 1,\n        "min_excerpt_chars": 20,\n        "max_excerpt_chars": 600,\n        "require_future_marker_on_anchor_line": True,\n        "require_quantitative_or_deadline_marker": True,\n        "require_commitment_domain_marker": True,\n        "deadline_markers": list(DEADLINE_MARKERS),\n        "commitment_domain_markers": list(COMMITMENT_DOMAIN_MARKERS),\n        "exclude_markers": list(EXCLUDE_MARKERS),\n        "quantitative_regex": QUANTITATIVE_REGEX,\n        "dedupe_key": "source_id,page_number,normalized_excerpt",\n    }\n''',
)
replace_once(
    path,
    '''    quantitative_tokens: tuple[str, ...]\n    disposition: ReviewDisposition\n''',
    '''    quantitative_tokens: tuple[str, ...]\n    domain_markers: tuple[str, ...]\n    disposition: ReviewDisposition\n''',
)
replace_once(
    path,
    '''        payload["quantitative_tokens"] = list(self.quantitative_tokens)\n        return payload\n''',
    '''        payload["quantitative_tokens"] = list(self.quantitative_tokens)\n        payload["domain_markers"] = list(self.domain_markers)\n        return payload\n''',
)
replace_once(
    path,
    '''        raise H003CandidateError("encrypted transcript PDF is not allowed by H003-E001")\n''',
    '''        raise H003CandidateError(\n            f"encrypted transcript PDF is not allowed by {EXTRACTION_RULE_ID}"\n        )\n''',
)
replace_once(
    path,
    '''    results: list[ClaimCandidate] = []\n    seen: set[tuple[int, str]] = set()\n    for page in pages:\n        lines = list(page.lines)\n        for index, _line in enumerate(lines):\n            start = max(0, index - 1)\n            end = min(len(lines), index + 2)\n            excerpt = " ".join(lines[start:end])\n            if len(excerpt) < 20:\n                continue\n            if len(excerpt) > 800:\n                excerpt = excerpt[:800].rstrip()\n            lowered = excerpt.casefold()\n            if any(marker in lowered for marker in EXCLUDE_MARKERS):\n                continue\n            future_hits = tuple(marker for marker in FUTURE_MARKERS if marker in lowered)\n            if not future_hits:\n                continue\n            deadline_hits = tuple(marker for marker in DEADLINE_MARKERS if marker in lowered)\n            quantitative_tokens = tuple(\n                token.strip()\n                for token in QUANTITATIVE_PATTERN.findall(excerpt)\n                if token.strip()\n            )\n            if not deadline_hits and not quantitative_tokens:\n                continue\n            key = (page.page_number, excerpt.casefold())\n            if key in seen:\n                continue\n            seen.add(key)\n            line_start = start + 1\n            line_end = end\n''',
    '''    results: list[ClaimCandidate] = []\n    seen: set[tuple[int, str]] = set()\n    for page in pages:\n        lines = list(page.lines)\n        for index, line in enumerate(lines):\n            anchor = line.casefold()\n            future_hits = tuple(marker for marker in FUTURE_MARKERS if marker in anchor)\n            if not future_hits:\n                continue\n            start = index\n            end = min(len(lines), index + 2)\n            excerpt = " ".join(lines[start:end])\n            if len(excerpt) < 20:\n                continue\n            if len(excerpt) > 600:\n                excerpt = excerpt[:600].rstrip()\n            lowered = excerpt.casefold()\n            if any(marker in lowered for marker in EXCLUDE_MARKERS):\n                continue\n            domain_hits = tuple(\n                marker for marker in COMMITMENT_DOMAIN_MARKERS if marker in lowered\n            )\n            if not domain_hits:\n                continue\n            deadline_hits = tuple(marker for marker in DEADLINE_MARKERS if marker in lowered)\n            quantitative_tokens = tuple(\n                token.strip()\n                for token in QUANTITATIVE_PATTERN.findall(excerpt)\n                if token.strip()\n            )\n            if not deadline_hits and not quantitative_tokens:\n                continue\n            key = (page.page_number, excerpt.casefold())\n            if key in seen:\n                continue\n            seen.add(key)\n            line_start = start + 1\n            line_end = end\n''',
)
replace_once(
    path,
    '''                    schema_version=1,\n                    candidate_id=_canonical_hash(identity),\n''',
    '''                    schema_version=2,\n                    candidate_id=_canonical_hash(identity),\n''',
)
replace_once(
    path,
    '''                    quantitative_tokens=quantitative_tokens,\n                    disposition="UNREVIEWED",\n''',
    '''                    quantitative_tokens=quantitative_tokens,\n                    domain_markers=domain_hits,\n                    disposition="UNREVIEWED",\n''',
)

# Add precision regressions while keeping the E001 sample artifact immutable.
tests = Path("tests/test_h003_candidates.py")
text = tests.read_text(encoding="utf-8")
text += '''\n\ndef test_future_marker_in_neighbor_line_does_not_promote_current_fact():\n    pages = (\n        ExtractedPage(\n            page_number=1,\n            lines=(\n                "ARPU for the quarter came in at Rs. 195.1.",\n                "We expect this to taper down as well.",\n            ),\n        ),\n    )\n    assert generate_candidates(_source(), raw_sha256="d" * 64, pages=pages) == ()\n\n\ndef test_generic_future_without_commitment_domain_is_not_candidate():\n    pages = (\n        ExtractedPage(\n            page_number=1,\n            lines=("We expect this to improve over the next two quarters.",),\n        ),\n    )\n    assert generate_candidates(_source(), raw_sha256="e" * 64, pages=pages) == ()\n\n\ndef test_one_anchor_line_yields_one_candidate_not_overlapping_duplicates():\n    pages = (\n        ExtractedPage(\n            page_number=1,\n            lines=(\n                "We expect revenue growth of 15% next year.",\n                "Current revenue grew 8% this quarter.",\n                "Historic margin was 12%.",\n            ),\n        ),\n    )\n    candidates = generate_candidates(_source(), raw_sha256="f" * 64, pages=pages)\n    assert len(candidates) == 1\n    assert candidates[0].line_start == 1\n    assert candidates[0].line_end == 2\n    assert "revenue" in candidates[0].domain_markers\n'''
tests.write_text(text, encoding="utf-8")
