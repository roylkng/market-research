"""L003: prospective-only, source-bounded earnings expectations and guidance changes.

The H021 universe is U001, not HG009. This module never edits H021/H002,
predicts returns, or treats contemporary LLM interpretation as past information.
A receipt and reviewer status are assertions, not cryptographic issuer identity.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256
from math import isfinite
from urllib.parse import urlparse

from marketlab.alpha import digest

H021_PANEL_ID = "AE001-H021-EXPECTATIONS-v1"
GUIDANCE_UNIT = frozenset({"INR_CRORE", "INR_LAKH", "PERCENT", "UNITS", "INR_PER_SHARE"})
GUIDANCE_METRIC = frozenset({
    "REVENUE", "EBITDA", "EPS", "CAPACITY", "ORDER_BACKLOG",
    "CAPEX", "OPERATING_MARGIN", "VOLUME", "PRODUCTION",
})
DOC_TYPES = frozenset({"NSE_ORIGINAL", "ISSUER_IR_ORIGINAL"})


@dataclass(frozen=True)
class QuantifiedGuidance:
    symbol: str
    isin: str
    metric: str
    period_end: str
    accounting_scope: str
    unit: str
    value: float
    value_literal: str
    statement_excerpt: str
    original_document_bytes: bytes
    expected_sha256: str
    source_url: str
    source_type: str
    published_utc: str
    first_seen_utc: str
    reviewer_status: str


def _utc(value: str | None) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value) if isinstance(value, str) else None
    except ValueError:
        return None
    if parsed is None or parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        return None
    return parsed


def _abstain(symbol: str, reasons: list[str]) -> dict:
    return {
        "status": "ABSTAIN", "symbol": symbol, "reasons": sorted(set(reasons)),
        "forecast_return": None, "investment_authorized": False,
    }


def _valid_receipt(doc: QuantifiedGuidance, cutoff: datetime) -> list[str]:
    reasons: list[str] = []
    if not doc.symbol or not doc.isin:
        reasons.append("issuer_identity_missing")
    if doc.metric not in GUIDANCE_METRIC or doc.unit not in GUIDANCE_UNIT:
        reasons.append("metric_or_unit_unsupported")
    if doc.accounting_scope not in {"CONSOLIDATED", "STANDALONE", "PROJECT", "SEGMENT"}:
        reasons.append("accounting_scope_unverified")
    try:
        datetime.fromisoformat(doc.period_end)
    except (ValueError, TypeError):
        reasons.append("period_end_invalid")
    if not isinstance(doc.value, (int, float)) or isinstance(doc.value, bool) or not isfinite(doc.value):
        reasons.append("guidance_value_invalid")
    try:
        displayed = Decimal(doc.value_literal.replace(",", ""))
        if not displayed.is_finite() or displayed != Decimal(str(doc.value)):
            reasons.append("guidance_literal_mismatch")
    except (InvalidOperation, AttributeError, TypeError):
        reasons.append("guidance_literal_invalid")
    if (
        not isinstance(doc.original_document_bytes, bytes)
        or not doc.original_document_bytes
        or sha256(doc.original_document_bytes).hexdigest() != doc.expected_sha256
    ):
        reasons.append("original_bytes_digest_mismatch")
    if (
        not isinstance(doc.statement_excerpt, str)
        or not doc.statement_excerpt.strip()
        or not isinstance(doc.value_literal, str)
        or doc.value_literal not in doc.statement_excerpt
        or not isinstance(doc.original_document_bytes, bytes)
        or doc.statement_excerpt.encode("utf-8") not in doc.original_document_bytes
    ):
        reasons.append("quantified_original_excerpt_not_bound")
    parsed = urlparse(doc.source_url)
    if parsed.scheme != "https" or not parsed.netloc or doc.source_type not in DOC_TYPES:
        reasons.append("original_source_url_or_type_invalid")
    if doc.source_type == "NSE_ORIGINAL" and parsed.hostname not in {
        "nsearchives.nseindia.com", "archives.nseindia.com"
    }:
        reasons.append("nse_source_host_mismatch")
    pub = _utc(doc.published_utc)
    seen = _utc(doc.first_seen_utc)
    if pub is None or seen is None or not pub <= seen <= cutoff:
        reasons.append("source_publication_or_capture_after_cutoff")
    if doc.reviewer_status != "INDEPENDENTLY_REVIEWED":
        reasons.append("financial_semantic_review_missing")
    return reasons


def assess_guidance_revision(
    prior: QuantifiedGuidance | None,
    current: QuantifiedGuidance | None,
    *,
    decision_cutoff_utc: str,
) -> dict:
    """Exact-text-bounded issuer guidance delta. Novelty is not a return signal."""
    cutoff = _utc(decision_cutoff_utc)
    symbol = current.symbol if current is not None else (prior.symbol if prior is not None else "")
    if cutoff is None:
        return _abstain(symbol, ["exact_utc_decision_cutoff_required"])
    if prior is None or current is None:
        return _abstain(symbol, ["prior_and_current_public_guidance_required"])
    reasons = _valid_receipt(prior, cutoff) + _valid_receipt(current, cutoff)
    if (
        (prior.symbol, prior.isin, prior.metric, prior.period_end, prior.accounting_scope, prior.unit)
        != (current.symbol, current.isin, current.metric, current.period_end,
            current.accounting_scope, current.unit)
    ):
        reasons.append("issuer_period_scope_metric_comparability_mismatch")
    if (
        _utc(prior.published_utc) is not None
        and _utc(current.published_utc) is not None
        and _utc(prior.published_utc) >= _utc(current.published_utc)
    ):
        reasons.append("guidance_not_chronologically_revised")
    if reasons:
        return _abstain(symbol, reasons)
    absolute_delta = current.value - prior.value
    pct = None if prior.value == 0 else 100 * absolute_delta / abs(prior.value)
    return {
        "status": "SOURCE_BOUNDED_GUIDANCE_DELTA_ONLY",
        "symbol": symbol, "isin": current.isin, "metric": current.metric,
        "period_end": current.period_end, "accounting_scope": current.accounting_scope,
        "unit": current.unit, "prior_value": prior.value, "current_value": current.value,
        "absolute_delta": round(absolute_delta, 8),
        "percent_delta": None if pct is None else round(pct, 8),
        "quantified_change_observed": absolute_delta != 0,
        "source_information_cutoff_utc": decision_cutoff_utc,
        "prior_original_sha256": prior.expected_sha256,
        "current_original_sha256": current.expected_sha256,
        "provenance_review_asserted_not_independently_authenticated_by_code": True,
        "headline_novelty_or_full_information_set_proved": False,
        "h002_signal_modified": False, "long_term_expected_return": None,
        "forecast_return": None, "investment_authorized": False,
    }


def assess_sealed_h021_feature(
    panel: dict,
    *,
    symbol: str,
    isin: str,
    decision_cutoff_utc: str,
) -> dict:
    """Reuse point-in-time H021 only for exact U001 identity and causal cutoff.

    The sealed panel is an existing derived artifact, not original consensus
    bytes. Current capture manifests still need independent custody audits.
    """
    cutoff = _utc(decision_cutoff_utc)
    if cutoff is None:
        return _abstain(symbol, ["exact_utc_decision_cutoff_required"])
    if panel.get("panel_id") != H021_PANEL_ID or panel.get("source_hypothesis") != "H021":
        return _abstain(symbol, ["wrong_frozen_h021_source"])
    if panel.get("outcomes_attached") is not False or panel.get("live_capital_allowed") is not False:
        return _abstain(symbol, ["future_outcomes_or_live_capital_forbidden"])
    signature = panel.get("panel_sha256")
    unsigned = {k: v for k, v in panel.items() if k != "panel_sha256"}
    if not isinstance(signature, str) or digest(unsigned) != signature:
        return _abstain(symbol, ["h021_panel_hash_mismatch"])
    rows = panel.get("rows")
    if not isinstance(rows, list) or panel.get("row_count") != len(rows):
        return _abstain(symbol, ["h021_panel_rows_invalid"])
    identities = [(r.get("symbol"), r.get("isin")) for r in rows if isinstance(r, dict)]
    if len(identities) != len(rows) or len(set(identities)) != len(rows):
        return _abstain(symbol, ["h021_duplicate_or_invalid_identity"])
    known = _utc(panel.get("feature_known_at_utc"))
    earliest = _utc(panel.get("earliest_execution_open_utc"))
    if known is None or earliest is None or not known < earliest:
        return _abstain(symbol, ["h021_feature_execution_clock_invalid"])
    if any(_utc(r.get("known_at_utc")) != known for r in rows):
        return _abstain(symbol, ["h021_row_known_at_mismatch"])
    if known > cutoff:
        return _abstain(symbol, ["h021_capture_after_decision_cutoff"])
    matches = [r for r in rows if (r.get("symbol"), r.get("isin")) == (symbol, isin)]
    if len(matches) != 1:
        return _abstain(symbol, ["not_in_sealed_h021_u001_universe"])
    row = matches[0]
    vals = row.get("values")
    if not isinstance(vals, dict):
        return _abstain(symbol, ["h021_feature_values_invalid"])
    revision = vals.get("h021_primary_eps_revision_30d_pct")
    eligible = row.get("primary_signal_reason") == "ELIGIBLE"
    if not eligible or revision is None:
        return {
            "status": "NO_SIGNAL", "symbol": symbol, "isin": isin,
            "reason": row.get("primary_signal_reason") or "H021_REVISION_MISSING",
            "h021_universe_only": "U001", "investment_authorized": False,
            "forecast_return": None,
        }
    if isinstance(revision, bool) or not isinstance(revision, (float, int)) or not isfinite(revision):
        return _abstain(symbol, ["h021_revision_invalid"])
    return {
        "status": "PROSPECTIVE_H021_REVISION_SOURCE_ONLY",
        "symbol": symbol, "isin": isin,
        "revision_pct": revision, "known_at_utc": panel["feature_known_at_utc"],
        "earliest_execution_open_utc": panel["earliest_execution_open_utc"],
        "panel_sha256": signature, "source_hypothesis": "H021",
        "h021_universe_only": "U001", "hg009_100_cohort_join_authorized": False,
        "source_original_consensus_bytes_verified_by_this_function": False,
        "prospective_alpha_validated": False, "forecast_return": None,
        "investment_authorized": False,
    }
