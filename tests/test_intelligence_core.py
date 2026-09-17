import unittest
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from marketlab.intelligence_core import (
    Bar,
    Coverage,
    Evidence,
    EvidenceError,
    Mechanism,
    Requirement,
    Session,
    active_evidence,
    common_window_returns,
    company_packet,
    per_share_scenario,
)

T = datetime(2026, 9, 17, 4, 30, tzinfo=UTC)


def fact(identifier="f1", **overrides):
    values = {'identifier': identifier, 'subject': "DEMO", 'facet': "prospects", 'claim_key': "FY27|capacity|units", 'value': "200", 'role': "REPORTED_FACT", 'publisher': "issuer", 'origin': "issuer-announcement-1", 'source_url': "https://example.org/announcement", 'content_sha256': "a" * 64, 'published_at': T - timedelta(hours=3), 'first_seen_at': T - timedelta(hours=2), 'processed_at': T - timedelta(hours=1), 'expires_at': T + timedelta(days=30), 'quote': "Illustrative installed capacity: 200 units."}
    values.update(overrides)
    return Evidence(**values)


def req(subject="DEMO", facet="prospects", channel="filings", needs_claim=True):
    return Requirement(subject, facet, channel, timedelta(hours=1), timedelta(days=1), needs_claim)


def scan(subject="DEMO", facet="prospects", channel="filings", **overrides):
    values = {'subject': subject, 'facet': facet, 'channel': channel, 'window_start': T - timedelta(days=2), 'through': T - timedelta(minutes=15), 'completed_at': T - timedelta(minutes=10), 'status': "COMPLETE"}
    values.update(overrides)
    return Coverage(**values)


def mechanism(**overrides):
    values = {'subject': "DEMO", 'event': "capacity-commissioned", 'economic_driver': "saleable volume", 'channel': "capacity -> utilisation -> revenue -> cash flow", 'horizon': "60_SESSIONS", 'prior_expectation': "Synthetic prior: 150 capacity units", 'change_from_expectation': "Synthetic +50 units, demand conversion unproven", 'price_response_already_observed': "UNKNOWN, market data not supplied", 'invalidation': "Customer qualification fails", 'supporting_ids': ("f1",)}
    values.update(overrides)
    return Mechanism(**values)


def packet(**overrides):
    values = {'subject': "DEMO", 'horizon': "60_SESSIONS", 'as_of': T, 'evidence': [fact()], 'coverage': [scan()], 'requirements': [req()], 'mechanisms': [mechanism()]}
    values.update(overrides)
    return company_packet(**values)


class EvidenceTests(unittest.TestCase):
    def test_timezones_are_mandatory(self):
        with self.assertRaises(EvidenceError):
            fact(published_at=T.replace(tzinfo=None))

    def test_processing_cannot_precede_observation(self):
        with self.assertRaises(EvidenceError):
            fact(processed_at=T - timedelta(hours=4))

    def test_late_discovery_cannot_backdate_a_claim(self):
        late = fact(first_seen_at=T + timedelta(hours=1), processed_at=T + timedelta(hours=2))
        self.assertEqual(active_evidence([late], T), [])

    def test_old_publication_does_not_avoid_processing_cutoff(self):
        late = fact(processed_at=T + timedelta(seconds=1))
        self.assertEqual(active_evidence([late], T), [])

    def test_bad_hash_is_rejected(self):
        with self.assertRaises(EvidenceError):
            fact(content_sha256="not-a-hash")

    def test_source_credentials_are_rejected(self):
        with self.assertRaises(EvidenceError):
            fact(source_url="https://user:password@example.org/source")

    def test_social_lead_cannot_become_a_forecast(self):
        result = packet(evidence=[fact(role="SOCIAL_LEAD")])
        self.assertEqual(result["state"], "RESEARCH_BLOCKED")
        self.assertIn("NO_SUPPORTED_ECONOMIC_MECHANISM", result["blockers"])
        self.assertIsNone(result["forecast"])

    def test_no_validated_model_means_no_forecast_even_when_input_ready(self):
        result = packet()
        self.assertEqual(result["state"], "RESEARCH_READY")
        self.assertIsNone(result["forecast"])
        self.assertFalse(result["live_capital_allowed"])

    def test_copied_news_is_not_independent_corroboration(self):
        result = packet(evidence=[fact(), fact("f2", publisher="newspaper")],
                        mechanisms=[mechanism(supporting_ids=("f1", "f2"))])
        self.assertEqual(result["mechanisms"][0]["origin_count"], 1)

    def test_unknown_news_is_not_no_news(self):
        result = packet(requirements=[req(), req(facet="news", channel="news", needs_claim=False)])
        self.assertIn("NOT_COLLECTED:DEMO/news/news", result["blockers"])

    def test_explicit_complete_empty_window_is_supported(self):
        result = packet(requirements=[req(), req(facet="news", channel="news", needs_claim=False)],
                        coverage=[scan(), scan(facet="news", channel="news")])
        self.assertEqual(result["state"], "RESEARCH_READY")
        self.assertEqual(result["coverage"][1]["state"], "NO_EVENT_IN_SCANNED_WINDOW")

    def test_future_scan_does_not_fill_past_coverage(self):
        result = packet(coverage=[scan(completed_at=T + timedelta(seconds=1))])
        self.assertTrue(any(x.startswith("NOT_COLLECTED") for x in result["blockers"]))

    def test_stale_coverage_blocks(self):
        result = packet(coverage=[scan(through=T - timedelta(hours=2))])
        self.assertTrue(any(x.startswith("STALE_COVERAGE") for x in result["blockers"]))

    def test_new_failed_scan_is_not_hidden_behind_old_success(self):
        result = packet(coverage=[scan(), scan(completed_at=T, status="FETCH_FAILED")])
        self.assertTrue(any(x.startswith("FETCH_FAILED") for x in result["blockers"]))

    def test_missing_market_dependency_blocks_company_packet(self):
        result = packet(requirements=[req(), req(subject="MARKET:IN", facet="macro", channel="rates")])
        self.assertIn("NOT_COLLECTED:MARKET:IN/macro/rates", result["blockers"])

    def test_conflicting_reported_facts_remain_visible(self):
        result = packet(evidence=[fact(), fact("f2", value="100", origin="independent-source")])
        self.assertEqual(result["state"], "RESEARCH_BLOCKED")
        self.assertEqual(len(result["conflicts"]), 1)

    def test_different_analyst_estimates_are_not_conflicting_facts(self):
        result = packet(evidence=[fact(role="EXTERNAL_ESTIMATE"),
                                  fact("f2", role="EXTERNAL_ESTIMATE", value="100", origin="another-analyst")])
        self.assertEqual(result["conflicts"], [])
        self.assertEqual(result["state"], "RESEARCH_READY")

    def test_future_correction_cannot_rewrite_past(self):
        correction = fact("f2", value="100", supersedes="f1", first_seen_at=T + timedelta(hours=1),
                          processed_at=T + timedelta(hours=2))
        self.assertEqual([x.identifier for x in active_evidence([fact(), correction], T)], ["f1"])
        self.assertEqual([x.identifier for x in active_evidence([fact(), correction], T + timedelta(hours=3))], ["f2"])

    def test_cross_origin_supersession_is_not_silent_resolution(self):
        correction = fact("f2", value="100", supersedes="f1", origin="different-origin", processed_at=T)
        with self.assertRaises(EvidenceError):
            active_evidence([fact(), correction], T)

    def test_future_evidence_in_mechanism_is_blocked(self):
        result = packet(evidence=[fact(), fact("f2", processed_at=T + timedelta(seconds=1))],
                        mechanisms=[mechanism(supporting_ids=("f1", "f2"))])
        self.assertTrue(any(x.startswith("UNAVAILABLE_MECHANISM") for x in result["blockers"]))

    def test_mechanism_requires_prior_expectation(self):
        with self.assertRaises(EvidenceError):
            mechanism(prior_expectation="")

    def test_empty_requirement_set_is_rejected(self):
        with self.assertRaises(EvidenceError):
            packet(requirements=[])


class MarketClockTests(unittest.TestCase):
    def setUp(self):
        self.calendar = [Session(date(2026, 9, day), datetime(2026, 9, day, 10, tzinfo=UTC))
                         for day in (10, 11, 15, 16)]
        self.bench = {s.day: Bar(100 + i, s.closes_at + timedelta(hours=1), "price_return_v1")
                      for i, s in enumerate(self.calendar)}
        self.stock = {s.day: Bar(100 + 2 * i, s.closes_at + timedelta(hours=1), "price_return_v1")
                      for i, s in enumerate(self.calendar)}

    def run_window(self, **overrides):
        values = {'calendar': self.calendar, 'cutoff': date(2026, 9, 16), 'horizon': 3, 'as_of': T, 'benchmark': self.bench, 'stocks': {"A": self.stock}}
        values.update(overrides)
        return common_window_returns(**values)

    def test_exact_same_calendar_for_every_stock(self):
        result = self.run_window(stocks={"A": self.stock, "B": self.stock})
        self.assertAlmostEqual(result["benchmark_return_pct"], 3)
        self.assertAlmostEqual(result["stocks"]["A"]["excess_pp"], 3)
        self.assertEqual(result["stocks"]["A"], result["stocks"]["B"])

    def test_missing_stock_session_blocks_not_reindexes_market(self):
        missing = dict(self.stock)
        del missing[date(2026, 9, 11)]
        result = self.run_window(stocks={"A": self.stock, "B": missing})
        self.assertAlmostEqual(result["benchmark_return_pct"], 3)
        self.assertEqual(result["stocks"]["B"]["status"], "MISSING_CALENDAR_BAR")
        self.assertIsNone(result["stocks"]["B"]["return_pct"])

    def test_intraday_session_cannot_be_a_completed_close(self):
        with self.assertRaises(EvidenceError):
            self.run_window(as_of=datetime(2026, 9, 16, 9, tzinfo=UTC))

    def test_bar_must_have_been_available_at_decision(self):
        bars = dict(self.stock)
        bars[date(2026, 9, 16)] = replace(bars[date(2026, 9, 16)], available_at=T + timedelta(hours=1))
        self.assertEqual(self.run_window(stocks={"A": bars})["stocks"]["A"]["status"], "BAR_NOT_YET_AVAILABLE")

    def test_partial_bar_capture_cannot_become_final_by_waiting(self):
        bars = dict(self.stock)
        bars[date(2026, 9, 16)] = replace(bars[date(2026, 9, 16)], available_at=datetime(2026, 9, 16, 8, tzinfo=UTC))
        self.assertEqual(self.run_window(stocks={"A": bars})["stocks"]["A"]["status"], "BAR_CAPTURED_BEFORE_SESSION_CLOSE")

    def test_mixed_adjustments_are_blocked(self):
        bars = dict(self.stock)
        bars[date(2026, 9, 16)] = replace(bars[date(2026, 9, 16)], basis="total_return_v1")
        self.assertEqual(self.run_window(stocks={"A": bars})["stocks"]["A"]["status"], "MIXED_ADJUSTMENT_BASIS")

    def test_same_basis_required_for_stock_and_benchmark(self):
        bars = {day: replace(bar, basis="total_return_v1") for day, bar in self.stock.items()}
        self.assertEqual(self.run_window(stocks={"A": bars})["stocks"]["A"]["status"], "BENCHMARK_BASIS_MISMATCH")


class EconomicsTests(unittest.TestCase):
    def test_growth_and_dilution_can_still_lose_money(self):
        result = per_share_scenario(current_price=100, current_profit=100, future_profit=140,
                                    current_shares=10, future_shares=11, future_pe=7)
        self.assertAlmostEqual(result["profit_growth_pct"], 40)
        self.assertAlmostEqual(result["diluted_eps_growth_pct"], 27.2727272727)
        self.assertAlmostEqual(result["price_return_pct"], -10.9090909091)
        self.assertIsNone(result["probability"])

    def test_dividends_and_costs_are_explicit(self):
        result = per_share_scenario(current_price=100, current_profit=100, future_profit=100,
                                    current_shares=10, future_shares=10, future_pe=10,
                                    dividends_per_share=2, cost_pp=0.5)
        self.assertAlmostEqual(result["cost_adjusted_total_return_pct"], 1.5)

    def test_nonfinite_and_loss_making_pe_inputs_rejected(self):
        for profit in (float("nan"), float("inf"), -1, 0, True):
            with self.subTest(profit=profit), self.assertRaises(EvidenceError):
                per_share_scenario(current_price=100, current_profit=100, future_profit=profit,
                                   current_shares=10, future_shares=10, future_pe=10)


if __name__ == "__main__":
    unittest.main()
