"""Hardening tests for H022 document-comparability audit v2."""
from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from marketlab.h022_document_audit import AuditError, canonical_hash, load_json
from marketlab.h022_document_audit_v2 import (
    COHORT_ID,
    COHORT_SHA256,
    E002_RULE_SHA256,
    INPUT_PATHS,
    SOURCE_RULE_SHA256,
    VERSION,
    audit_snapshot,
    validate_frozen_scope,
    verify_git_snapshot,
    read_pinned_inputs,
)

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "tests/fixtures/h022_document_audit"
PIN = "434ce97508de7c1005d1acfef9829cfe90199c22"
AT = "2026-10-15T17:00:00Z"


def raw(doc):
    return (json.dumps(doc, indent=2, sort_keys=True) + "\n").encode()


def seal(doc, key):
    doc.pop(key, None)
    doc[key] = canonical_hash(doc)
    return doc


class V2ScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.signal_raw = (FOLDER / "signal-ledger.json").read_bytes()
        cls.source_raw = (FOLDER / "source-ledger.json").read_bytes()
        cls.e002_raw = (FOLDER / "e002-ledger.json").read_bytes()

    def audit(self, **kwargs):
        return audit_snapshot(
            self.signal_raw,
            self.source_raw,
            self.e002_raw,
            snapshot_commit=PIN,
            reviewed_at_utc=AT,
            **kwargs,
        )

    def test_exact_frozen_scope_and_e002_are_bound(self):
        report = self.audit()
        self.assertEqual(report["audit_version"], VERSION)
        self.assertEqual(report["scope_identity"]["cohort_id"], COHORT_ID)
        self.assertEqual(report["scope_identity"]["cohort_sha256"], COHORT_SHA256)
        self.assertEqual(report["scope_identity"]["source_rule_sha256"], SOURCE_RULE_SHA256)
        self.assertEqual(report["scope_identity"]["e002_rule_sha256"], E002_RULE_SHA256)
        self.assertEqual(report["e002_record_count"], 4)
        self.assertEqual(len(report["input_files"]), 3)
        self.assertFalse(report["git_blob_bindings_checked"])

    def test_every_current_signal_has_bound_extraction(self):
        report = self.audit()
        for row in report["annotations"]:
            self.assertEqual(row["current_extraction"]["status"], "TEXT_READY")
            self.assertEqual(len(row["current_extraction"]["raw_sha256"]), 64)
            self.assertEqual(len(row["current_extraction"]["text_sha256"]), 64)
            self.assertFalse(row["current_extraction"]["text_body_supplied_to_audit"])

    def test_marico_keeps_notice_result_with_bound_e002(self):
        row = next(r for r in self.audit()["annotations"] if r["symbol"] == "MARICO")
        self.assertEqual(row["comparability"], "NOT_COMPARABLE")
        self.assertEqual(row["current"]["document_kind"], "FUTURE_CALL_NOTICE")
        self.assertEqual(row["current_extraction"]["page_count"], 3)
        self.assertEqual(row["current_extraction"]["text_char_count"], 4082)

    def test_coforge_e002_metadata_is_visible_without_promoting_it(self):
        row = next(r for r in self.audit()["annotations"] if r["symbol"] == "COFORGE")
        self.assertEqual(row["current_extraction"]["page_count"], 1)
        self.assertEqual(row["comparability"], "REVIEW_REQUIRED")

    def test_resealed_cohort_drift_is_rejected(self):
        signals = load_json(self.signal_raw)
        sources = load_json(self.source_raw)
        e002 = load_json(self.e002_raw)
        for doc in (signals, sources, e002):
            doc["cohort_id"] = "DIFFERENT"
            seal(doc, "ledger_sha256")
        with self.assertRaises(AuditError):
            validate_frozen_scope(signals, sources, e002)

    def test_resealed_source_rule_drift_is_rejected(self):
        signals = load_json(self.signal_raw)
        sources = load_json(self.source_raw)
        e002 = load_json(self.e002_raw)
        sources["source_rule_sha256"] = "0" * 64
        seal(sources, "ledger_sha256")
        with self.assertRaises(AuditError):
            validate_frozen_scope(signals, sources, e002)

    def test_resealed_feature_version_drift_is_rejected(self):
        signals = load_json(self.signal_raw)
        sources = load_json(self.source_raw)
        e002 = load_json(self.e002_raw)
        signals["records"][0]["feature_version"] = "changed"
        seal(signals["records"][0], "signal_record_sha256")
        seal(signals, "ledger_sha256")
        with self.assertRaises(AuditError):
            validate_frozen_scope(signals, sources, e002)

    def test_e002_rule_drift_is_rejected(self):
        signals = load_json(self.signal_raw)
        sources = load_json(self.source_raw)
        e002 = load_json(self.e002_raw)
        e002["records"][0]["rule_sha256"] = "0" * 64
        seal(e002, "ledger_sha256")
        with self.assertRaises(AuditError):
            validate_frozen_scope(signals, sources, e002)

    def test_signal_to_e002_raw_hash_mismatch_is_rejected(self):
        signals = load_json(self.signal_raw)
        sources = load_json(self.source_raw)
        e002 = load_json(self.e002_raw)
        e002["records"][0]["raw_sha256"] = "0" * 64
        seal(e002, "ledger_sha256")
        with self.assertRaises(AuditError):
            validate_frozen_scope(signals, sources, e002)

    def test_signal_to_e002_text_hash_mismatch_is_rejected(self):
        signals = load_json(self.signal_raw)
        sources = load_json(self.source_raw)
        e002 = load_json(self.e002_raw)
        e002["records"][0]["text_sha256"] = "0" * 64
        seal(e002, "ledger_sha256")
        with self.assertRaises(AuditError):
            validate_frozen_scope(signals, sources, e002)

    def test_extra_e002_record_is_rejected(self):
        signals = load_json(self.signal_raw)
        sources = load_json(self.source_raw)
        e002 = load_json(self.e002_raw)
        extra = copy.deepcopy(e002["records"][0])
        extra["source_id"] = "f" * 64
        e002["records"].append(extra)
        e002["record_count"] += 1
        seal(e002, "ledger_sha256")
        with self.assertRaises(AuditError):
            validate_frozen_scope(signals, sources, e002)

    def test_previous_v1_audit_cannot_be_silently_chained(self):
        v1 = load_json((ROOT / "research/audits/h022/P001/document-comparability-2026-10-15.json").read_bytes())
        with self.assertRaises(AuditError):
            self.audit(previous_audit=v1)

    def test_v2_chain_is_scope_bound(self):
        first = self.audit()
        second = self.audit(previous_audit=first)
        self.assertEqual(second["previous_audit_sha256"], first["audit_sha256"])

    def test_git_blob_map_mismatch_is_rejected(self):
        bogus = {path: "0" * 40 for path in INPUT_PATHS}
        with self.assertRaises(AuditError):
            self.audit(git_blob_shas=bogus)


class GitBindingTests(unittest.TestCase):
    def test_unresolvable_named_snapshot_is_rejected(self):
        raws = (b"a", b"b", b"c")
        completed = type("R", (), {"stdout": "f" * 40 + "\n"})()
        with tempfile.TemporaryDirectory() as tmp, patch(
            "subprocess.run", return_value=completed
        ), self.assertRaises(AuditError):
            verify_git_snapshot(Path(tmp), PIN, raws)

    def test_historical_commit_does_not_require_checkout_head(self):
        import hashlib

        def blob(data):
            return hashlib.sha1(
                b"blob " + str(len(data)).encode() + b"\\0" + data
            ).hexdigest()

        raws = (b"a", b"b", b"c")
        responses = [PIN, *(blob(item) for item in raws)]
        calls = iter(type("R", (), {"stdout": value + "\\n"})() for value in responses)
        with tempfile.TemporaryDirectory() as tmp, patch(
            "subprocess.run", side_effect=lambda *a, **k: next(calls)
        ):
            observed = verify_git_snapshot(Path(tmp), PIN, raws)
        self.assertEqual(len(observed), 3)

    def test_reads_historical_inputs_not_working_directory(self):
        returned = iter((b"a", b"b", b"c"))
        with tempfile.TemporaryDirectory() as tmp, patch(
            "subprocess.run",
            side_effect=lambda *a, **k: type("R", (), {"stdout": next(returned)})(),
        ) as mocked:
            self.assertEqual(read_pinned_inputs(Path(tmp), PIN), (b"a", b"b", b"c"))
            self.assertEqual(mocked.call_count, 3)
            self.assertTrue(all("show" in call.args[0] for call in mocked.call_args_list))

    def test_changed_working_file_is_rejected(self):
        calls = iter([
            type("R", (), {"stdout": PIN + "\n"})(),
            type("R", (), {"stdout": "0" * 40 + "\n"})(),
        ])
        with tempfile.TemporaryDirectory() as tmp, patch(
            "subprocess.run", side_effect=lambda *a, **k: next(calls)
        ), self.assertRaises(AuditError):
            verify_git_snapshot(Path(tmp), PIN, (b"a", b"b", b"c"))


if __name__ == "__main__":
    unittest.main()
