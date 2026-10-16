"""Adversarial tests for P019: arithmetic is not permission to invest."""
import unittest

from marketlab.hg009_p019_expectations import (
    Case, EvidenceError, Scenario, evaluate, reverse_hurdles,
)


class ExpectationsTests(unittest.TestCase):
    def base(self, **changes):
        data = dict(symbol="ACE", price_inr=100.0, fully_diluted_shares_cr=10.0,
                    shares_source="original fully diluted cap table", price_source="official dated close",
                    owner_cash_source="audited parent cash bridge",
                    scenarios=(Scenario("bear", 0.5, 40, 10), Scenario("bull", 0.5, 80, 10)),
                    as_of="2026-10-16", terminal_years=3, execution_cost_fraction=0.01,
                    annual_discount_rate=0.10,
                    independent_probability_basis="frozen prospective calibration")
        data.update(changes)
        return Case(**data)

    def test_hurdles(self):
        self.assertAlmostEqual(reverse_hurdles(13764.39)["16"], 1290.4115625)
        self.assertAlmostEqual(reverse_hurdles(25646.15)["16"], 2404.3265625)

    def test_missing_dilution_abstains(self):
        result = evaluate(self.base(fully_diluted_shares_cr=None))
        self.assertEqual(result["status"], "ABSTAIN")
        self.assertFalse(result["investment_authorized"])

    def test_missing_probability_basis_abstains(self):
        self.assertEqual(evaluate(self.base(independent_probability_basis=None))["status"], "ABSTAIN")

    def test_missing_owner_cash_abstains(self):
        self.assertEqual(evaluate(self.base(owner_cash_source=None))["status"], "ABSTAIN")

    def test_synthetic_scenario_value(self):
        result = evaluate(self.base())
        self.assertEqual(result["status"], "SCENARIO_MATH_ONLY")
        self.assertAlmostEqual(result["expected_pv_equity_cr"], 600 / 1.1**3, places=5)
        self.assertFalse(result["investment_authorized"])

    def test_probabilities_rejected(self):
        with self.assertRaises(EvidenceError):
            evaluate(self.base(scenarios=(Scenario("x", 0.7, 10, 10),)))

    def test_negative_cash_no_negative_equity(self):
        result = evaluate(self.base(scenarios=(Scenario("loss", 1.0, -100, 10),)))
        self.assertEqual(result["expected_pv_equity_cr"], 0)

    def test_nan_rejected(self):
        with self.assertRaises(EvidenceError):
            evaluate(self.base(price_inr=float("nan")))

    def test_claims_reduce_terminal_value(self):
        without = evaluate(self.base())
        with_claims = evaluate(self.base(scenarios=(
            Scenario("bear", 0.5, 40, 10, 200),
            Scenario("bull", 0.5, 80, 10, 200),
        )))
        self.assertLess(with_claims["expected_pv_equity_cr"], without["expected_pv_equity_cr"])


if __name__ == "__main__":
    unittest.main()
