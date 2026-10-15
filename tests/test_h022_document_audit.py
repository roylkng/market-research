"""Synthetic regression cases plus exact, blob-verified retained P001 ledger checks."""
from __future__ import annotations
import copy
import hashlib
import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch
from marketlab.h022_document_audit import AuditError, VERSION, audit_snapshot, canonical_hash, classify_document, compare_documents, load_json, main, timestamp, write_report
ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / 'tests/fixtures/h022_document_audit'
PIN = '434ce97508de7c1005d1acfef9829cfe90199c22'
AT = '2026-10-15T17:00:00Z'
SID = 'a' * 64
TEXT = 'Earnings Call Transcript\nModerator: Welcome to the call.\nAnalyst: Please discuss operations.\nManagement: We have no new guidance.\nModerator: Thank you. The call is concluded.'

def raw(doc):
    return (json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + '\n').encode()

def seal(doc, key):
    doc.pop(key, None)
    doc[key] = canonical_hash(doc)
    return doc

def source(sid=SID, symbol='SYNTHETIC', when='2026-10-14T10:00:00Z', announcement=''):
    return dict(source_id=sid, symbol=symbol, exchange_published_at_utc=when, attachment_text=announcement, attachment_url='https://example.invalid/document.pdf')

def review(text=TEXT, kind='FULL_TRANSCRIPT'):
    return dict(source_id=SID, text_sha256=hashlib.sha256(text.encode()).hexdigest(), document_kind=kind, reviewed_at_utc=AT, reviewer_ref='synthetic-reviewer', evidence_ref='synthetic-fixture:review-1', call_at_utc='2026-10-13T12:00:00Z')

def classify(s=None, **kwargs):
    arguments = dict(source_id=SID, symbol='SYNTHETIC', published_at_utc='2026-10-14T10:00:00Z', as_of_utc='2026-10-14T11:00:00Z')
    arguments.update(kwargs)
    return classify_document(source() if s is None else s, **arguments)

def classified_text(text=TEXT, **kwargs):
    arguments = dict(text=text, expected_text_sha256=hashlib.sha256(text.encode()).hexdigest(), extraction_status='TEXT_READY', review=review(text))
    arguments.update(kwargs)
    return classify(**arguments)

class DocumentCases(unittest.TestCase):

    def test_invitation_is_not_transcript(self):
        announcement = 'The Company will hold an investor/analyst conference call. Audio recording and transcript of the said call will be subsequently published on the website.'
        result = classify(source(announcement=announcement))
        self.assertEqual(result['document_kind'], 'FUTURE_CALL_NOTICE')
        self.assertEqual(result['eligibility'], 'INELIGIBLE')
        self.assertFalse(result['full_document_verified'])

    def test_scheduled_wording_is_detected(self):
        result = classify(source(announcement='Earnings call is scheduled next week. The transcript shall be made available later.'))
        self.assertEqual(result['eligibility'], 'INELIGIBLE')

    def test_whitespace_variation(self):
        s = source(announcement='Will\n host a conference call. TRANSCRIPT will\tbe uploaded later.')
        self.assertEqual(classify(s)['eligibility'], 'INELIGIBLE')

    def test_filename_intimation_never_suffices(self):
        s = source()
        s['attachment_url'] = 'https://example.invalid/TranscriptIntimation.pdf'
        result = classify(s)
        self.assertEqual(result['eligibility'], 'REVIEW_REQUIRED')
        self.assertIn('filename_intimation_is_triage_only', result['reasons'])

    def test_metadata_transcript_mention_not_positive_evidence(self):
        self.assertEqual(classify(source(announcement='Exchange informed about Transcript'))['eligibility'], 'REVIEW_REQUIRED')

    def test_link_only_notice_from_content(self):
        text = 'The transcript is available at https://example.invalid/transcript.pdf'
        self.assertEqual(classified_text(text, review=review(text, 'LINK_ONLY_NOTICE'))['eligibility'], 'INELIGIBLE')

    def test_full_transcript_with_cover_letter(self):
        text = 'Intimation: Please find enclosed the transcript.\n' + TEXT
        self.assertEqual(classified_text(text)['eligibility'], 'ELIGIBLE')

    def test_intimation_filename_does_not_reject_reviewed_transcript(self):
        s = source()
        s['attachment_url'] = 'https://example.invalid/intimation.pdf'
        self.assertEqual(classified_text(s=s)['eligibility'], 'ELIGIBLE')

    def test_no_candidate_count_used_for_classification(self):
        self.assertEqual(classified_text()['eligibility'], 'ELIGIBLE')

    def test_unreviewed_body_cannot_be_promoted(self):
        self.assertEqual(classified_text(review=None)['eligibility'], 'REVIEW_REQUIRED')

    def test_review_requires_nonempty_text(self):
        with self.assertRaises(AuditError):
            classified_text(' ')

    def test_missing_body_requires_review(self):
        self.assertEqual(classify()['eligibility'], 'REVIEW_REQUIRED')

    def test_failed_extraction_unavailable(self):
        self.assertEqual(classify(extraction_status='FAILED')['document_kind'], 'EXTRACTION_FAILED')

    def test_failed_extraction_cannot_have_text(self):
        with self.assertRaises(AuditError):
            classified_text(extraction_status='FAILED')

    def test_unknown_extraction_status_rejected(self):
        with self.assertRaises(AuditError):
            classify(extraction_status='probably_ready')

    def test_wrong_text_hash_rejected(self):
        with self.assertRaises(AuditError):
            classified_text(expected_text_sha256='b' * 64)

    def test_wrong_review_source_rejected(self):
        r = review()
        r['source_id'] = 'b' * 64
        with self.assertRaises(AuditError):
            classified_text(review=r)

    def test_wrong_review_text_rejected(self):
        r = review()
        r['text_sha256'] = 'b' * 64
        with self.assertRaises(AuditError):
            classified_text(review=r)

    def test_missing_reviewer_rejected(self):
        r = review()
        r['reviewer_ref'] = ' '
        with self.assertRaises(AuditError):
            classified_text(review=r)

    def test_review_predating_source_rejected(self):
        r = review()
        r['reviewed_at_utc'] = '2026-10-01T00:00:00Z'
        with self.assertRaises(AuditError):
            classified_text(review=r)

    def test_later_review_does_not_backdate_cutoff(self):
        r = review()
        r['call_at_utc'] = '2026-11-02T12:30:00Z'
        self.assertEqual(classified_text(review=r)['eligibility'], 'INELIGIBLE')

    def test_future_document_rejected(self):
        s = source(when='2026-11-03T10:00:00Z')
        self.assertEqual(classify(s, published_at_utc=s['exchange_published_at_utc'])['eligibility'], 'INELIGIBLE')

    def test_metadata_and_review_conflict_requires_resolution(self):
        s = source(announcement='We will hold a conference call. Transcript will be published later.')
        self.assertEqual(classified_text(s=s)['document_kind'], 'METADATA_CONTENT_CONFLICT')

    def test_incomplete_transcript_not_complete(self):
        self.assertEqual(classified_text(review=review(kind='INCOMPLETE'))['eligibility'], 'REVIEW_REQUIRED')

    def test_other_document_not_eligible(self):
        self.assertEqual(classified_text(review=review(kind='OTHER'))['eligibility'], 'INELIGIBLE')

    def test_unknown_review_kind_rejected(self):
        with self.assertRaises(AuditError):
            classified_text(review=review(kind='probably_transcript'))

    def test_unknown_review_field_rejected(self):
        r = review()
        r['allow_override'] = True
        with self.assertRaises(AuditError):
            classified_text(review=r)

    def test_review_without_text_rejected(self):
        with self.assertRaises(AuditError):
            classify(review=review())

    def test_source_mismatch_rejected(self):
        with self.assertRaises(AuditError):
            classify(source(symbol='WRONG'))

    def test_unknown_source_not_eligible(self):
        r = classify_document(None, source_id=SID, symbol='SYNTHETIC', published_at_utc='2026-10-01T00:00:00Z', as_of_utc=AT)
        self.assertEqual(r['eligibility'], 'REVIEW_REQUIRED')

class PairCases(unittest.TestCase):

    def test_real_zero_is_preserved(self):
        d = classified_text()
        out = compare_documents(d, d, frozen_primary_signal=0.0)
        self.assertEqual(out['advisory_primary_signal'], 0.0)
        self.assertEqual(out['comparability'], 'COMPARABLE_DOCUMENTS_ONLY')

    def test_invalid_current_is_not_neutral_zero(self):
        a = dict(eligibility='INELIGIBLE')
        b = classified_text()
        out = compare_documents(a, b, frozen_primary_signal=-0.936)
        self.assertIsNone(out['advisory_primary_signal'])
        self.assertFalse(out['canonical_signal_replacement'])
        self.assertFalse(out['canonical_outcome_scoring_changed'])

    def test_invalid_prior_cannot_make_false_rebound(self):
        out = compare_documents(classified_text(), dict(eligibility='INELIGIBLE'), frozen_primary_signal=1.2)
        self.assertEqual(out['comparability'], 'NOT_COMPARABLE')
        self.assertIsNone(out['advisory_primary_signal'])

    def test_unverified_prior_blocks_interpretation(self):
        out = compare_documents(classified_text(), classify(), frozen_primary_signal=0.1)
        self.assertEqual(out['comparability'], 'REVIEW_REQUIRED')

    def test_two_notices_with_zero_difference_still_invalid(self):
        a = dict(eligibility='INELIGIBLE')
        self.assertIsNone(compare_documents(a, a, frozen_primary_signal=0.0)['advisory_primary_signal'])

    def test_null_frozen_signal_stays_null(self):
        d = classified_text()
        self.assertEqual(compare_documents(d, d, frozen_primary_signal=None)['comparability'], 'NO_FROZEN_NUMERIC_SIGNAL')

    def test_nonfinite_signal_rejected(self):
        for value in (float('inf'), float('nan'), True, '0'):
            with self.subTest(value=value), self.assertRaises(AuditError):
                compare_documents(classified_text(), classified_text(), frozen_primary_signal=value)

class SnapshotCases(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.signal_raw = (FOLDER / 'signal-ledger.json').read_bytes()
        cls.source_raw = (FOLDER / 'source-ledger.json').read_bytes()

    def audit(self, a=None, b=None, **kwargs):
        return audit_snapshot(a or self.signal_raw, b or self.source_raw, snapshot_commit=PIN, reviewed_at_utc=AT, **kwargs)

    def test_exact_upstream_blob_identities(self):
        report = self.audit()
        self.assertEqual([i['git_blob_sha'] for i in report['input_files']], ['898e4fadc226cd078a38760b949fe051d3334786', '6c225a5169a925805f51eb8e5ce6d59460186081'])

    def test_all_four_current_and_prior_links_accounted_for(self):
        report = self.audit()
        self.assertEqual(report['signal_count'], 4)
        self.assertEqual(report['prior_source_count'], 4)
        self.assertEqual(report['prior_source_metadata_missing_count'], 4)
        self.assertEqual(report['full_document_review_count'], 0)
        self.assertEqual(report['classification_counts'], {'NOT_COMPARABLE': 1, 'REVIEW_REQUIRED': 3})

    def test_marico_attached_to_original_frozen_hash(self):
        record = next((a for a in self.audit()['annotations'] if a['symbol'] == 'MARICO'))
        self.assertEqual(record['original_signal_record_sha256'], 'bf5fa646682f45594d9c11f981408539fd4ae2fdf8779dab3b9ee939144ec2f9')
        self.assertEqual(record['original_primary_signal'], -0.9360140776517278)
        self.assertIsNone(record['advisory_primary_signal'])

    def test_coforge_filename_is_only_a_warning(self):
        record = next((a for a in self.audit()['annotations'] if a['symbol'] == 'COFORGE'))
        self.assertEqual(record['comparability'], 'REVIEW_REQUIRED')
        self.assertIn('filename_intimation_is_triage_only', record['current']['reasons'])

    def test_current_zero_does_not_get_a_free_pass(self):
        for row in self.audit()['annotations']:
            self.assertIsNone(row['advisory_primary_signal'])

    def test_audit_is_deterministic_and_does_not_mutate_inputs(self):
        before = (self.signal_raw, self.source_raw)
        self.assertEqual(self.audit(), self.audit())
        self.assertEqual(before, (self.signal_raw, self.source_raw))

    def test_tampered_ledger_refused(self):
        doc = load_json(self.signal_raw)
        doc['records'][-1]['primary_signal'] = 0
        with self.assertRaises(AuditError):
            self.audit(a=raw(doc))

    def test_resealed_ledger_with_tampered_record_refused(self):
        doc = load_json(self.signal_raw)
        doc['records'][-1]['primary_signal'] = 0
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(a=raw(doc))

    def test_wrong_source_symbol_refused_after_resealing(self):
        doc = load_json(self.source_raw)
        doc['records'][-1]['source']['symbol'] = 'TCS'
        seal(doc['records'][-1], 'source_record_sha256')
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(b=raw(doc))

    def test_source_first_seen_after_freeze_refused(self):
        doc = load_json(self.source_raw)
        doc['records'][-1]['first_seen_at_utc'] = AT
        seal(doc['records'][-1], 'source_record_sha256')
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(b=raw(doc))

    def test_duplicate_source_refused(self):
        doc = load_json(self.source_raw)
        doc['records'].append(copy.deepcopy(doc['records'][0]))
        doc['record_count'] += 1
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(b=raw(doc))

    def test_missing_current_source_refused(self):
        doc = load_json(self.source_raw)
        doc['records'].pop()
        doc['record_count'] -= 1
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(b=raw(doc))

    def test_outcome_data_refused(self):
        doc = load_json(self.signal_raw)
        doc['stock_return'] = 0.2
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(a=raw(doc))

    def test_scope_mismatch_refused(self):
        doc = load_json(self.source_raw)
        doc['cohort_id'] = 'changed'
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(b=raw(doc))

    def test_no_backdated_audit(self):
        with self.assertRaises(AuditError):
            audit_snapshot(self.signal_raw, self.source_raw, snapshot_commit=PIN, reviewed_at_utc='2026-10-14T12:00:00Z')

    def test_prior_source_must_be_strictly_earlier(self):
        doc = load_json(self.signal_raw)
        doc['records'][-1]['prior_exchange_published_at_utc'] = '2026-11-02T12:00:00Z'
        seal(doc['records'][-1], 'signal_record_sha256')
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(a=raw(doc))

    def test_nonunique_prior_cannot_be_promoted(self):
        doc = load_json(self.signal_raw)
        doc['records'][-1]['prior_group_source_ids'].append(SID)
        seal(doc['records'][-1], 'signal_record_sha256')
        seal(doc, 'ledger_sha256')
        with self.assertRaises(AuditError):
            self.audit(a=raw(doc))

    def test_missing_unique_prior_is_preserved(self):
        doc = load_json(self.signal_raw)
        doc['records'][-1]['prior_source_id'] = None
        doc['records'][-1]['primary_signal'] = None
        seal(doc['records'][-1], 'signal_record_sha256')
        seal(doc, 'ledger_sha256')
        row = self.audit(a=raw(doc))['annotations'][-1]
        self.assertIsNone(row['advisory_primary_signal'])
        self.assertEqual(row['prior']['document_kind'], 'NO_UNIQUE_FROZEN_PRIOR')

    def test_later_signal_inherits_notice_baseline_warning(self):
        signals, sources = (load_json(self.signal_raw), load_json(self.source_raw))
        prior = signals['records'][-1]
        later = copy.deepcopy(prior)
        later.update(source_id=SID, prior_source_id=prior['source_id'], prior_group_source_ids=[prior['source_id']], prior_exchange_published_at_utc=prior['exchange_published_at_utc'], exchange_published_at_utc='2026-10-15T15:00:00Z', signal_frozen_at_utc='2026-10-15T15:05:00Z', primary_signal=1.2)
        seal(later, 'signal_record_sha256')
        signals['records'].append(later)
        signals['record_count'] += 1
        seal(signals, 'ledger_sha256')
        s = source(SID, 'MARICO', later['exchange_published_at_utc'], 'Transcript enclosed')
        r = dict(source=s, first_seen_at_utc='2026-10-15T15:01:00Z')
        seal(r, 'source_record_sha256')
        sources['records'].append(r)
        sources['record_count'] += 1
        seal(sources, 'ledger_sha256')
        out = self.audit(a=raw(signals), b=raw(sources))['annotations'][-1]
        self.assertEqual(out['prior']['document_kind'], 'FUTURE_CALL_NOTICE')
        self.assertEqual(out['comparability'], 'NOT_COMPARABLE')
        self.assertIsNone(out['advisory_primary_signal'])

    def test_previous_audit_hash_chain(self):
        prev = self.audit()
        self.assertEqual(self.audit(previous_audit=prev)['previous_audit_sha256'], prev['audit_sha256'])

    def test_tampered_previous_audit_rejected(self):
        prev = self.audit()
        prev['signal_count'] = 20
        with self.assertRaises(AuditError):
            self.audit(previous_audit=prev)

    def test_immutable_output_and_protected_paths(self):
        report = self.audit()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / 'research/audits/h022/P001/audit.json'
            write_report(report, out, root)
            before = out.read_bytes()
            write_report(report, out, root)
            changed = self.audit(previous_audit=report)
            with self.assertRaises(AuditError):
                write_report(changed, out, root)
            self.assertEqual(out.read_bytes(), before)
            for path in ('registry/p001.json', 'research/prospective/h022/P001/signal-ledger.json', 'research/audits/h022/P001/audit.py'):
                with self.subTest(path=path), self.assertRaises(AuditError):
                    write_report(report, root / path, root)

    def test_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as other:
            root = Path(tmp)
            (root / 'research/audits/h022').mkdir(parents=True)
            (root / 'research/audits/h022/P001').symlink_to(other, target_is_directory=True)
            with self.assertRaises(AuditError):
                write_report(self.audit(), root / 'research/audits/h022/P001/out.json', root)

    def test_cli_local_no_network_and_check_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'research/prospective/h022/P001'
            folder.mkdir(parents=True)
            for name, contents in (('signal-ledger.json', self.signal_raw), ('source-ledger.json', self.source_raw)):
                (folder / name).write_bytes(contents)
            with patch('socket.socket', side_effect=AssertionError('network not allowed')), redirect_stdout(io.StringIO()):
                rc = main(['--repo-root', str(root), '--snapshot-commit', PIN, '--reviewed-at-utc', AT, '--output', 'research/audits/h022/P001/audit.json', '--check'])
            self.assertEqual(rc, 2)
            self.assertEqual((folder / 'signal-ledger.json').read_bytes(), self.signal_raw)
            self.assertEqual((folder / 'source-ledger.json').read_bytes(), self.source_raw)

class JsonCases(unittest.TestCase):

    def test_duplicate_keys_rejected(self):
        with self.assertRaises(AuditError):
            load_json(b'{"x":1,"x":2}')

    def test_nonfinite_or_nonobject_rejected(self):
        for data in (b'{"x":NaN}', b'{"x":Infinity}', b'{"x":1e999}', b'[]', b'null', b'\xff'):
            with self.subTest(data=data), self.assertRaises(AuditError):
                load_json(data)

    def test_timezone_required(self):
        with self.assertRaises(AuditError):
            timestamp('2026-10-15')

    def test_offset_normalized(self):
        self.assertEqual(timestamp('2026-10-15T17:30:00+05:30'), timestamp('2026-10-15T12:00:00Z'))

    def test_version_identifies_shadow_not_frozen_rule(self):
        self.assertEqual(VERSION, 'h022-document-comparability/1')
if __name__ == '__main__':
    unittest.main()
