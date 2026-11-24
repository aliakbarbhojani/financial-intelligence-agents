#!/usr/bin/env python3
"""Known-answer and property tests for tools/fincalc.py (standard library unittest).

Reference values are textbook results or closed-form formulas computed independently
inside the tests (not by calling the function under test).
"""
import json
import math
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CALC = ROOT / "tools" / "fincalc.py"
sys.path.insert(0, str(ROOT / "tools"))
import fincalc  # noqa: E402


def run(*args):
    p = subprocess.run([sys.executable, str(CALC), *map(str, args)], capture_output=True, text=True)
    return p.returncode, json.loads(p.stdout)


class TimeValue(unittest.TestCase):
    def test_FC01_compound_annual(self):          # 10,000 @5% annual, 10y -> 16,288.95
        _, o = run("compound", 10000, "5%", 10, "--n", 1)
        self.assertAlmostEqual(o["results"]["future_value"], 16288.95, places=2)

    def test_FC02_compound_monthly(self):         # 10,000 @5% monthly, 10y -> 16,470.09
        _, o = run("compound", 10000, "5%", 10)
        self.assertAlmostEqual(o["results"]["future_value"], 16470.09, places=2)

    def test_FC03_annuity(self):                  # 100/month @6% for 10y -> 16,387.93
        _, o = run("compound", 0, "6%", 10, "--contrib", 100)
        self.assertAlmostEqual(o["results"]["future_value"], 16387.93, places=2)
        self.assertAlmostEqual(o["results"]["total_contributed"], 12000.00, places=2)

    def test_FC04_annuity_due(self):              # annuity due = ordinary * (1+i)
        _, o = run("compound", 0, "6%", 10, "--contrib", 100, "--timing", "begin")
        self.assertAlmostEqual(o["results"]["future_value"], 16387.93 * 1.005, delta=0.02)

    def test_FC05_goal_inverse_of_annuity(self):
        _, o = run("goal", 16387.93, 10, "6%")
        self.assertAlmostEqual(o["results"]["required_contribution_per_period"], 100.00, places=2)

    def test_FC06_effective_rate(self):           # 12% nominal monthly -> 12.6825% EAR
        _, o = run("effective-rate", "12%")
        self.assertAlmostEqual(o["results"]["effective_annual_rate_pct"], 12.6825, places=4)

    def test_FC07_zero_rate(self):
        _, o = run("compound", 1000, "0", 5, "--contrib", 10)
        self.assertAlmostEqual(o["results"]["future_value"], 1600.0, places=2)


class Loans(unittest.TestCase):
    def test_FC10_mortgage_payment(self):         # 200k @6% 30y -> 1,199.10; interest 231,676.38
        _, o = run("loan", 200000, "6%", 30)
        self.assertAlmostEqual(o["results"]["payment"], 1199.10, places=2)
        self.assertAlmostEqual(o["results"]["total_interest"], 231676.38, delta=0.05)

    def test_FC11_amortization_balance_closed_form(self):
        P, i, n, k = 200000, 0.06 / 12, 360, 60
        pmt = P * i / (1 - (1 + i) ** -n)
        expected = P * (1 + i) ** k - pmt * ((1 + i) ** k - 1) / i   # ~186,108.71
        _, o = run("amortize", P, "6%", 30, "--at", k)
        self.assertAlmostEqual(o["results"]["after_payment"]["balance"], expected, delta=0.01)
        self.assertAlmostEqual(expected, 186108.71, delta=0.5)

    def test_FC12_fee_apr_newton_crosscheck(self):
        # 10,000 @12% for 12 months with 200 fee; independent Newton solve for APR
        _, o = run("loan", 10000, "12%", 1, "--fees", 200)
        pmt = 10000 * 0.01 / (1 - 1.01 ** -12)
        r = 0.01
        for _ in range(100):
            f = sum(pmt / (1 + r) ** t for t in range(1, 13)) - 9800
            df = sum(-t * pmt / (1 + r) ** (t + 1) for t in range(1, 13))
            r -= f / df
        self.assertAlmostEqual(o["results"]["apr_incl_fees_nominal_pct"], r * 1200, places=3)
        self.assertGreater(o["results"]["apr_incl_fees_nominal_pct"], 12.0)

    def test_FC13_total_interest_identity(self):
        _, o = run("loan", 25000, "7.5%", 5)
        R = o["results"]
        self.assertAlmostEqual(R["payment"] * R["number_of_payments"] - 25000, R["total_interest"], delta=0.5)

    def test_FC14_payoff_single_debt_matches_loan(self):
        # exact payment 470.7347...; round UP to the cent as lenders do. Rounding down leaves a
        # ~0.17 residual and (correctly) needs a 25th month (issue FC14 in tests/TEST_REPORT.md).
        pmt = 10000 * 0.01 / (1 - 1.01 ** -24)
        pmt_c = math.ceil(pmt * 100) / 100
        data = {"debts": [{"name": "a", "balance": 10000, "rate": "12%", "min_payment": pmt_c}],
                "monthly_budget": pmt_c, "strategy": "avalanche"}
        _, o = run("payoff", json.dumps(data))
        self.assertEqual(o["results"]["avalanche"]["months"], 24)
        self.assertAlmostEqual(o["results"]["avalanche"]["total_interest"], pmt * 24 - 10000, delta=1.0)

    def test_FC15_avalanche_beats_snowball_when_orders_differ(self):
        data = {"debts": [{"name": "big-expensive", "balance": 6000, "rate": "24%", "min_payment": 120},
                          {"name": "small-cheap", "balance": 800, "rate": "4%", "min_payment": 25}],
                "monthly_budget": 500}
        _, o = run("payoff", json.dumps(data))
        R = o["results"]
        self.assertLess(R["avalanche"]["total_interest"], R["snowball"]["total_interest"])
        self.assertEqual(R["snowball"]["payoff_order"][0], "small-cheap")
        self.assertEqual(R["avalanche"]["payoff_order"][0], "big-expensive")

    def test_FC16_payoff_budget_below_minimums_errors(self):
        data = {"debts": [{"name": "a", "balance": 1000, "rate": "20%", "min_payment": 100}], "monthly_budget": 50}
        code, o = run("payoff", json.dumps(data))
        self.assertEqual(code, 1)
        self.assertIn("error", o)


class Investment(unittest.TestCase):
    def test_FC20_npv(self):                       # -21.0368
        _, o = run("npv", "10%", -1000, 300, 400, 500)
        exp = -1000 + 300 / 1.1 + 400 / 1.21 + 500 / 1.331
        self.assertAlmostEqual(o["results"]["npv"], exp, places=3)

    def test_FC21_irr(self):                       # -1000, 400x3 -> 9.70%
        _, o = run("irr", -1000, 400, 400, 400)
        self.assertAlmostEqual(o["results"]["irr_pct"], 9.701, places=2)

    def test_FC22_irr_npv_consistency(self):
        cfs = [-5000, 1200, 1500, 1800, 2100]
        r = fincalc.irr(cfs)
        self.assertAlmostEqual(fincalc.npv(r, cfs), 0.0, places=6)

    def test_FC23_dcf_perpetuity_identity(self):  # flat FCF 100, r=10%, g=0 -> EV 1000 exactly
        _, o = run("dcf", "--fcf", 100, "--growth", 0, "--years", 5, "--discount", "10%", "--terminal-growth", 0)
        self.assertAlmostEqual(o["results"]["enterprise_value"], 1000.0, places=2)

    def test_FC24_dcf_gordon_identity_with_growth(self):
        # constant growth g in explicit and terminal periods equals Gordon: FCF0*(1+g)/(r-g)
        _, o = run("dcf", "--fcf", 100, "--growth", "3%", "--years", 7, "--discount", "9%", "--terminal-growth", "3%")
        self.assertAlmostEqual(o["results"]["enterprise_value"], 100 * 1.03 / 0.06, places=2)

    def test_FC25_dcf_rejects_r_le_g(self):
        code, o = run("dcf", "--fcf", 100, "--discount", "3%", "--terminal-growth", "3%")
        self.assertEqual(code, 1)

    def test_FC26_reverse_dcf_roundtrip(self):
        _, o = run("reverse-dcf", "--price", 1000, "--fcf", 100, "--years", 5, "--discount", "10%", "--terminal-growth", 0)
        self.assertAlmostEqual(o["results"]["implied_annual_fcf_growth_pct"], 0.0, places=3)

    def test_FC27_dcf_sensitivity_grid_monotonic(self):
        _, o = run("dcf", "--fcf", 100, "--growth", "5%", "--discount", "9%", "--terminal-growth", "2%", "--sensitivity")
        g = o["results"]["sensitivity_value_per_share"]
        self.assertGreater(g["r=8.00%"]["tg=2.00%"], g["r=10.00%"]["tg=2.00%"])

    def test_FC28_ratios(self):
        data = {"price": 50, "shares": 100, "net_income": 500, "revenue": 4000, "equity": 2500,
                "total_debt": 1000, "cash": 500, "ebit": 800, "tax_rate": 0.25, "operating_cash_flow": 700,
                "capex": -200, "dividends_per_share": 1, "eps_growth_pct": 10, "revenue_prev": 3200}
        _, o = run("ratios", json.dumps(data))
        R = o["results"]
        self.assertAlmostEqual(R["eps"], 5.0); self.assertAlmostEqual(R["pe"], 10.0)
        self.assertAlmostEqual(R["ps"], 1.25); self.assertAlmostEqual(R["peg"], 1.0)
        self.assertAlmostEqual(R["roe_pct"], 20.0); self.assertAlmostEqual(R["debt_to_equity"], 0.4)
        self.assertAlmostEqual(R["roic_pct"], 800 * 0.75 / 3000 * 100, places=4)
        self.assertAlmostEqual(R["fcf"], 500.0); self.assertAlmostEqual(R["fcf_yield_pct"], 10.0)
        self.assertAlmostEqual(R["dividend_yield_pct"], 2.0); self.assertAlmostEqual(R["payout_ratio_pct"], 20.0)
        self.assertAlmostEqual(R["revenue_growth_pct"], 25.0)

    def test_FC29_pe_negative_earnings_flagged(self):
        _, o = run("ratios", json.dumps({"price": 10, "shares": 10, "net_income": -5}))
        self.assertIsNone(o["results"]["pe"])
        self.assertTrue(any("not meaningful" in n for n in o["notes"]))


class BudgetAndStats(unittest.TestCase):
    def test_FC30_budget_totals_and_periods(self):
        data = {"income": [{"name": "pay", "amount": 2000, "period": "biweekly"}],
                "expenses": [{"name": "rent", "amount": 1500, "type": "essential"},
                             {"name": "insurance", "amount": 600, "period": "annual", "type": "essential"},
                             {"name": "car loan", "amount": 300, "type": "debt"},
                             {"name": "dining", "amount": 400, "type": "discretionary"},
                             {"name": "retirement", "amount": 500, "type": "savings"}],
                "emergency_fund_balance": 3600}
        _, o = run("budget", json.dumps(data))
        R = o["results"]
        inc = 2000 * 26 / 12
        out = 1500 + 50 + 300 + 400 + 500
        self.assertAlmostEqual(R["monthly_income"], inc, places=2)
        self.assertAlmostEqual(R["monthly_outflows"], out, places=2)
        self.assertAlmostEqual(R["monthly_surplus"], inc - out, places=2)
        self.assertAlmostEqual(R["annual_surplus"], (inc - out) * 12, delta=0.05)
        self.assertAlmostEqual(R["emergency_fund_months_of_needs"], 3600 / 1850, places=1)

    def test_FC31_budget_deficit_flag(self):
        data = {"income": [{"name": "pay", "amount": 1000}], "expenses": [{"name": "rent", "amount": 1200}]}
        _, o = run("budget", json.dumps(data))
        self.assertLess(o["results"]["monthly_surplus"], 0)
        self.assertIn("budget runs a deficit", o["notes"])

    def test_FC32_max_drawdown(self):               # 130 -> 65 = -50%
        _, o = run("stats", "100,120,90,130,65")
        self.assertAlmostEqual(o["results"]["max_drawdown_pct"], -50.0, places=4)

    def test_FC33_rsi_extremes(self):
        self.assertEqual(fincalc.rsi_wilder(list(range(1, 40))), 100.0)
        alt = [100 + (1 if k % 2 else 0) for k in range(60)]
        self.assertAlmostEqual(fincalc.rsi_wilder(alt), 50.0, delta=2.0)

    def test_FC34_volatility_constant_growth_zero(self):
        xs = [100 * 1.01 ** k for k in range(30)]
        _, o = run("stats", ",".join(f"{x:.10f}" for x in xs))
        self.assertAlmostEqual(o["results"]["annualized_volatility_pct"], 0.0, places=4)

    def test_FC35_ema_seed_and_macd_present(self):
        xs = [float(x) for x in range(1, 61)]
        e = fincalc.ema_series(xs, 12)
        self.assertAlmostEqual(e[0], sum(range(1, 13)) / 12)
        _, o = run("stats", ",".join(map(str, xs)))
        self.assertIsNotNone(o["results"]["macd"])

    def test_FC36_vol_band(self):
        _, o = run("vol-band", 100, "20%", 1)
        self.assertAlmostEqual(o["results"]["z=1.0"]["low"], 100 * math.exp(-0.2), places=3)
        self.assertAlmostEqual(o["results"]["z=1.0"]["high"], 100 * math.exp(0.2), places=3)

    def test_FC37_pct(self):
        _, o = run("pct", 80, 100)
        self.assertAlmostEqual(o["results"]["pct_change"], 25.0)


class InputHandling(unittest.TestCase):
    def test_FC40_bare_rate_interpreted_as_percent_and_flagged(self):
        _, o = run("loan", 200000, "6", 30)
        self.assertAlmostEqual(o["results"]["payment"], 1199.10, places=2)
        self.assertTrue(any("interpreted as 6.0%" in n for n in o["notes"]))

    def test_FC41_invalid_json_errors_cleanly(self):
        code, o = run("budget", "{not json")
        self.assertEqual(code, 1)
        self.assertIn("error", o)

    def test_FC42_unknown_period_errors(self):
        code, o = run("budget", json.dumps({"income": [{"name": "x", "amount": 1, "period": "fortnightlyish"}]}))
        self.assertEqual(code, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
