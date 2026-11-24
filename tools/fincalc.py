#!/usr/bin/env python3
"""
fincalc.py: deterministic financial calculator for the Financial Intelligence agent team.

Every command prints JSON: {"command", "inputs", "results", "notes"}.
Rates may be given as decimals (0.06) or percentages ("6%"). Bare numbers >= 1 are
interpreted as percentages and flagged in "notes".

Commands (run `fincalc.py <command> -h` for details):
  compound        Future value of a lump sum plus optional regular contributions
  goal            Regular contribution required to reach a target
  loan            Payment, total interest, total cost, fee-inclusive APR
  amortize        Amortisation summary / balance after N payments / schedule rows
  effective-rate  Nominal -> effective annual rate
  payoff          Debt payoff simulation: avalanche vs snowball
  npv             Net present value (first cash flow at t=0)
  irr             Internal rate of return
  dcf             Discounted cash flow valuation (+ sensitivity grid)
  reverse-dcf     Growth rate implied by a current share price
  ratios          Financial ratios from statement inputs (JSON)
  budget          Budget analysis from income/expense JSON
  stats           Returns, volatility, drawdown, SMA, RSI(14), MACD from a price series
  vol-band        Zero-drift lognormal price range from volatility (forecasting baseline)
  pct             Percentage change between two values

Standard library only. Python >= 3.9. No network access.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys

NOTES: list[str] = []
PERIODS = {"weekly": 52, "biweekly": 26, "semimonthly": 24, "monthly": 12,
           "quarterly": 4, "annual": 1, "annually": 1, "yearly": 1}


class CalcError(Exception):
    pass


# ------------------------------------------------------------------ parsing helpers

def rate(v) -> float:
    s = str(v).strip()
    if s.endswith("%"):
        return float(s[:-1]) / 100.0
    x = float(s)
    if abs(x) >= 1:
        NOTES.append(f"rate {s} interpreted as {x}% (pass decimals like 0.06 or '6%' to be explicit)")
        return x / 100.0
    return x


def jarg(s: str):
    try:
        return json.loads(s)
    except json.JSONDecodeError as e:
        raise CalcError(f"invalid JSON argument: {e}")


def r2(x: float, nd: int = 2) -> float:
    return round(x + 0.0, nd)


def out(command: str, inputs: dict, results: dict) -> None:
    print(json.dumps({"command": command, "inputs": inputs, "results": results,
                      "notes": NOTES}, indent=2))


# ------------------------------------------------------------------ core math (importable)

def fv_lump(pv: float, r: float, n_per_year: int, years: float) -> float:
    return pv * (1 + r / n_per_year) ** (n_per_year * years)


def fv_annuity(pmt: float, r: float, n_per_year: int, years: float, begin: bool = False) -> float:
    n = round(n_per_year * years)
    i = r / n_per_year
    fv = pmt * n if i == 0 else pmt * ((1 + i) ** n - 1) / i
    return fv * (1 + i) if begin else fv


def payment(principal: float, r: float, years: float, freq: int = 12) -> float:
    n = round(years * freq)
    i = r / freq
    if n <= 0:
        raise CalcError("term must be positive")
    return principal / n if i == 0 else principal * i / (1 - (1 + i) ** -n)


def pv_annuity(pmt: float, i: float, n: int) -> float:
    return pmt * n if i == 0 else pmt * (1 - (1 + i) ** -n) / i


def solve_bisect(f, lo: float, hi: float, tol: float = 1e-12, max_iter: int = 500) -> float:
    flo, fhi = f(lo), f(hi)
    if flo == 0:
        return lo
    if fhi == 0:
        return hi
    if flo * fhi > 0:
        raise CalcError("no sign change in search interval; solution not bracketed")
    for _ in range(max_iter):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < tol or (hi - lo) / 2 < tol:
            return mid
        if flo * fm < 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def npv(r: float, cfs: list[float]) -> float:
    return sum(cf / (1 + r) ** t for t, cf in enumerate(cfs))


def irr(cfs: list[float]) -> float:
    if not (any(c < 0 for c in cfs) and any(c > 0 for c in cfs)):
        raise CalcError("IRR requires at least one negative and one positive cash flow")
    return solve_bisect(lambda r: npv(r, cfs), -0.9999, 10.0)


def amortization(principal: float, r: float, years: float, freq: int = 12):
    pmt = payment(principal, r, years, freq)
    i = r / freq
    bal = principal
    rows = []
    for k in range(1, round(years * freq) + 1):
        interest = bal * i
        princ = pmt - interest
        bal -= princ
        rows.append({"period": k, "payment": pmt, "interest": interest,
                     "principal": princ, "balance": max(bal, 0.0)})
    return pmt, rows


def dcf_value(fcf0: float, growth: list[float], discount: float, tg: float,
              net_debt: float = 0.0, shares: float = 1.0) -> dict:
    if discount <= tg:
        raise CalcError("discount rate must exceed terminal growth")
    fcf, pv_sum, flows = fcf0, 0.0, []
    for t, g in enumerate(growth, start=1):
        fcf *= (1 + g)
        pv = fcf / (1 + discount) ** t
        pv_sum += pv
        flows.append({"year": t, "fcf": r2(fcf), "pv": r2(pv)})
    n = len(growth)
    tv = fcf * (1 + tg) / (discount - tg)
    pv_tv = tv / (1 + discount) ** n
    ev = pv_sum + pv_tv
    equity = ev - net_debt
    return {"flows": flows, "pv_explicit": pv_sum, "terminal_value": tv, "pv_terminal": pv_tv,
            "enterprise_value": ev, "equity_value": equity,
            "value_per_share": equity / shares if shares else None,
            "terminal_share_of_ev": pv_tv / ev if ev else None}


def sma(xs: list[float], n: int):
    return sum(xs[-n:]) / n if len(xs) >= n else None


def ema_series(xs: list[float], n: int) -> list[float]:
    """EMA seeded with the simple average of the first n values."""
    if len(xs) < n:
        return []
    k = 2 / (n + 1)
    e = [sum(xs[:n]) / n]
    for x in xs[n:]:
        e.append(x * k + e[-1] * (1 - k))
    return e


def rsi_wilder(xs: list[float], n: int = 14):
    if len(xs) < n + 1:
        return None
    ch = [b - a for a, b in zip(xs, xs[1:])]
    gains = [max(c, 0.0) for c in ch]
    losses = [max(-c, 0.0) for c in ch]
    ag, al = sum(gains[:n]) / n, sum(losses[:n]) / n
    for g, l in zip(gains[n:], losses[n:]):
        ag = (ag * (n - 1) + g) / n
        al = (al * (n - 1) + l) / n
    if al == 0:
        return 100.0 if ag > 0 else 50.0
    return 100 - 100 / (1 + ag / al)


def max_drawdown(xs: list[float]) -> dict:
    peak, peak_i, mdd, rng = xs[0], 0, 0.0, (0, 0)
    for i, x in enumerate(xs):
        if x > peak:
            peak, peak_i = x, i
        dd = (x - peak) / peak
        if dd < mdd:
            mdd, rng = dd, (peak_i, i)
    return {"max_drawdown": mdd, "peak_index": rng[0], "trough_index": rng[1]}


def simulate_payoff(debts: list[dict], budget: float, strategy: str, max_months: int = 1200) -> dict:
    ds = [dict(name=d["name"], bal=float(d["balance"]), r=rate(d["rate"]),
               minp=float(d["min_payment"])) for d in debts]
    if budget < sum(d["minp"] for d in ds) - 1e-9:
        raise CalcError("monthly budget is below the sum of minimum payments")
    total_interest, month, order_paid = 0.0, 0, []
    while any(d["bal"] > 0.005 for d in ds):
        month += 1
        if month > max_months:
            return {"strategy": strategy, "paid_off": False,
                    "note": "debts do not amortise within 100 years at this budget"}
        for d in ds:
            if d["bal"] > 0:
                it = d["bal"] * d["r"] / 12
                d["bal"] += it
                total_interest += it
        avail = budget
        for d in ds:
            if d["bal"] > 0:
                p = min(d["minp"], d["bal"])
                d["bal"] -= p
                avail -= p
        active = [d for d in ds if d["bal"] > 0.005]
        key = (lambda d: (-d["r"], d["bal"])) if strategy == "avalanche" else (lambda d: (d["bal"], -d["r"]))
        for d in sorted(active, key=key):
            if avail <= 0:
                break
            p = min(avail, d["bal"])
            d["bal"] -= p
            avail -= p
        for d in ds:
            if d["bal"] <= 0.005 and d["name"] not in order_paid:
                d["bal"] = 0.0
                order_paid.append(d["name"])
    return {"strategy": strategy, "paid_off": True, "months": month,
            "years": r2(month / 12, 2), "total_interest": r2(total_interest), "payoff_order": order_paid}


# ------------------------------------------------------------------ command handlers

def c_compound(a):
    r, n = rate(a.rate), a.n
    fv1 = fv_lump(a.principal, r, n, a.years)
    fv2 = fv_annuity(a.contrib, r, a.contrib_freq, a.years, a.timing == "begin") if a.contrib else 0.0
    if a.contrib and a.contrib_freq != n:
        NOTES.append("contribution frequency differs from compounding; annuity uses rate/contrib_freq per period")
    contributed = a.principal + a.contrib * round(a.contrib_freq * a.years)
    total = fv1 + fv2
    out("compound", vars_clean(a), {"future_value": r2(total), "fv_principal": r2(fv1),
        "fv_contributions": r2(fv2), "total_contributed": r2(contributed),
        "growth": r2(total - contributed)})


def c_goal(a):
    r, n = rate(a.rate), a.n
    remaining = a.target - fv_lump(a.current, r, n, a.years)
    periods = round(n * a.years)
    i = r / n
    if remaining <= 0:
        pmt = 0.0
        NOTES.append("current savings already reach the target at this rate")
    else:
        pmt = remaining / periods if i == 0 else remaining * i / ((1 + i) ** periods - 1)
    out("goal", vars_clean(a), {"required_contribution_per_period": r2(pmt), "periods": periods,
        "total_contributed": r2(pmt * periods + a.current)})


def c_loan(a):
    r = rate(a.rate)
    n = round(a.years * a.freq)
    pmt = payment(a.principal, r, a.years, a.freq)
    total_paid = pmt * n + a.fees
    res = {"payment": r2(pmt), "number_of_payments": n, "total_interest": r2(pmt * n - a.principal),
           "fees": r2(a.fees), "total_cost_of_borrowing": r2(pmt * n - a.principal + a.fees),
           "total_paid": r2(total_paid),
           "effective_annual_rate_excl_fees": r2(((1 + r / a.freq) ** a.freq - 1) * 100, 4)}
    if a.fees > 0:
        net = a.principal - a.fees
        if net <= 0:
            raise CalcError("fees exceed principal")
        i = solve_bisect(lambda x: pv_annuity(pmt, x, n) - net, 1e-12, 5.0)
        res["apr_incl_fees_nominal_pct"] = r2(i * a.freq * 100, 4)
        res["effective_annual_rate_incl_fees_pct"] = r2(((1 + i) ** a.freq - 1) * 100, 4)
    out("loan", vars_clean(a), res)


def c_amortize(a):
    r = rate(a.rate)
    pmt, rows = amortization(a.principal, r, a.years, a.freq)
    res = {"payment": r2(pmt), "number_of_payments": len(rows),
           "total_interest": r2(sum(x["interest"] for x in rows))}
    if a.at:
        if not 1 <= a.at <= len(rows):
            raise CalcError(f"--at must be between 1 and {len(rows)}")
        k = rows[a.at - 1]
        res["after_payment"] = {"period": a.at, "balance": r2(k["balance"]),
                                "interest_paid_to_date": r2(sum(x["interest"] for x in rows[:a.at])),
                                "principal_paid_to_date": r2(sum(x["principal"] for x in rows[:a.at]))}
    if a.rows:
        res["schedule_head"] = [{k: (r2(v) if isinstance(v, float) else v) for k, v in x.items()}
                                for x in rows[:a.rows]]
    out("amortize", vars_clean(a), res)


def c_effective(a):
    r = rate(a.nominal)
    out("effective-rate", vars_clean(a), {"effective_annual_rate_pct": r2(((1 + r / a.n) ** a.n - 1) * 100, 4)})


def c_payoff(a):
    d = jarg(a.data)
    strat = d.get("strategy", "both")
    strategies = ["avalanche", "snowball"] if strat == "both" else [strat]
    res = {s: simulate_payoff(d["debts"], float(d["monthly_budget"]), s) for s in strategies}
    if len(res) == 2 and all(v.get("paid_off") for v in res.values()):
        res["interest_saved_by_avalanche"] = r2(res["snowball"]["total_interest"] - res["avalanche"]["total_interest"])
    out("payoff", d, res)


def c_npv(a):
    r = rate(a.rate)
    out("npv", vars_clean(a), {"npv": r2(npv(r, a.cashflows), 4)})


def c_irr(a):
    out("irr", vars_clean(a), {"irr_pct": r2(irr(a.cashflows) * 100, 4)})


def growth_path(a) -> list[float]:
    if a.growth_path:
        return [rate(x) for x in a.growth_path.split(",")]
    return [rate(a.growth)] * a.years


def c_dcf(a):
    g = growth_path(a)
    d, tg = rate(a.discount), rate(a.terminal_growth)
    res = dcf_value(a.fcf, g, d, tg, a.net_debt, a.shares)
    res = {k: (r2(v, 4) if isinstance(v, float) else v) for k, v in res.items()}
    if (res.get("terminal_share_of_ev") or 0) > 0.75:
        NOTES.append("terminal value exceeds 75% of EV: valuation highly sensitive to long-run assumptions")
    if a.sensitivity:
        grid = {}
        for dd in (-0.01, -0.005, 0, 0.005, 0.01):
            row = {}
            for tt in (-0.005, 0, 0.005):
                try:
                    v = dcf_value(a.fcf, g, d + dd, tg + tt, a.net_debt, a.shares)["value_per_share"]
                    row[f"tg={(tg + tt) * 100:.2f}%"] = r2(v, 2)
                except CalcError:
                    row[f"tg={(tg + tt) * 100:.2f}%"] = None
            grid[f"r={(d + dd) * 100:.2f}%"] = row
        res["sensitivity_value_per_share"] = grid
    out("dcf", vars_clean(a), res)


def c_reverse_dcf(a):
    d, tg = rate(a.discount), rate(a.terminal_growth)
    target = a.price

    def f(g):
        return dcf_value(a.fcf, [g] * a.years, d, tg, a.net_debt, a.shares)["value_per_share"] - target
    g = solve_bisect(f, -0.5, 1.5, tol=1e-10)
    out("reverse-dcf", vars_clean(a), {"implied_annual_fcf_growth_pct": r2(g * 100, 4),
        "years_of_explicit_growth": a.years,
        "interpretation": "constant FCF growth over the explicit period that the price implies, given the discount rate and terminal growth"})


def c_ratios(a):
    x = {k: float(v) for k, v in jarg(a.data).items() if v is not None}
    R = {}

    def has(*ks):
        return all(k in x for k in ks)

    if has("price", "shares"):
        R["market_cap"] = x["price"] * x["shares"]
    if has("net_income", "shares"):
        R["eps"] = x["net_income"] / x["shares"]
    eps = x.get("eps", R.get("eps"))
    if "price" in x and eps:
        R["pe"] = x["price"] / eps if eps > 0 else None
        if eps <= 0:
            NOTES.append("P/E not meaningful: earnings are zero or negative")
    if "market_cap" in R and x.get("revenue"):
        R["ps"] = R["market_cap"] / x["revenue"]
    if R.get("pe") and x.get("eps_growth_pct"):
        R["peg"] = R["pe"] / x["eps_growth_pct"]
        NOTES.append("PEG depends on the growth estimate supplied (eps_growth_pct, in percent)")
    if has("net_income", "equity") and x["equity"] > 0:
        R["roe_pct"] = x["net_income"] / x["equity"] * 100
    if has("ebit", "equity", "total_debt"):
        tax = x.get("tax_rate", 0.0)
        tax = tax / 100 if tax >= 1 else tax
        invested = x["equity"] + x["total_debt"] - x.get("cash", 0.0)
        if invested > 0:
            R["roic_pct"] = x["ebit"] * (1 - tax) / invested * 100
    if has("total_debt", "equity") and x["equity"] > 0:
        R["debt_to_equity"] = x["total_debt"] / x["equity"]
    if "fcf" not in x and has("operating_cash_flow", "capex"):
        x["fcf"] = x["operating_cash_flow"] - abs(x["capex"])
    if "fcf" in x:
        R["fcf"] = x["fcf"]
        if x.get("revenue"):
            R["fcf_margin_pct"] = x["fcf"] / x["revenue"] * 100
        if "market_cap" in R and R["market_cap"]:
            R["fcf_yield_pct"] = x["fcf"] / R["market_cap"] * 100
    for num, key in (("gross_profit", "gross_margin_pct"), ("operating_income", "operating_margin_pct"),
                     ("net_income", "net_margin_pct")):
        if num in x and x.get("revenue"):
            R[key] = x[num] / x["revenue"] * 100
    if has("dividends_per_share", "price") and x["price"]:
        R["dividend_yield_pct"] = x["dividends_per_share"] / x["price"] * 100
        if eps and eps > 0:
            R["payout_ratio_pct"] = x["dividends_per_share"] / eps * 100
    if has("current_assets", "current_liabilities") and x["current_liabilities"]:
        R["current_ratio"] = x["current_assets"] / x["current_liabilities"]
    if has("ebit", "interest_expense") and x["interest_expense"]:
        R["interest_coverage"] = x["ebit"] / abs(x["interest_expense"])
    if "market_cap" in R and "total_debt" in x:
        R["enterprise_value"] = R["market_cap"] + x["total_debt"] - x.get("cash", 0.0)
        if x.get("ebitda"):
            R["ev_to_ebitda"] = R["enterprise_value"] / x["ebitda"]
    for k in ("revenue", "net_income"):
        prev = f"{k}_prev"
        if k in x and x.get(prev):
            R[f"{k}_growth_pct"] = (x[k] / x[prev] - 1) * 100
    out("ratios", x, {k: (r2(v, 4) if isinstance(v, float) else v) for k, v in R.items()})


def to_monthly(amount: float, period: str) -> float:
    p = PERIODS.get(str(period or "monthly").lower())
    if p is None:
        raise CalcError(f"unknown period '{period}'; use one of {sorted(PERIODS)}")
    return float(amount) * p / 12


def c_budget(a):
    d = jarg(a.data)
    inc = sum(to_monthly(i["amount"], i.get("period")) for i in d.get("income", []))
    cats = {"essential": 0.0, "debt": 0.0, "discretionary": 0.0, "savings": 0.0}
    lines = []
    for e in d.get("expenses", []):
        t = e.get("type", "essential").lower()
        if t not in cats:
            raise CalcError(f"expense type '{t}' must be one of {list(cats)}")
        m = to_monthly(e["amount"], e.get("period"))
        cats[t] += m
        lines.append({"name": e["name"], "monthly": r2(m), "type": t,
                      "pct_of_income": r2(m / inc * 100, 1) if inc else None})
    spend = sum(cats.values())
    surplus = inc - spend
    needs = cats["essential"] + cats["debt"]
    res = {"monthly_income": r2(inc), "monthly_outflows": r2(spend), "monthly_surplus": r2(surplus),
           "annual_surplus": r2(surplus * 12), "weekly_surplus": r2(surplus * 12 / 52),
           "category_totals": {k: r2(v) for k, v in cats.items()},
           "savings_rate_pct": r2((cats["savings"] + max(surplus, 0)) / inc * 100, 1) if inc else None,
           "debt_to_income_pct": r2(cats["debt"] / inc * 100, 1) if inc else None,
           "rule_50_30_20_actual_pct": {
               "needs": r2(needs / inc * 100, 1) if inc else None,
               "wants": r2(cats["discretionary"] / inc * 100, 1) if inc else None,
               "savings_and_surplus": r2((cats["savings"] + surplus) / inc * 100, 1) if inc else None},
           "lines": sorted(lines, key=lambda l: -l["monthly"])}
    if "emergency_fund_balance" in d and needs > 0:
        res["emergency_fund_months_of_needs"] = r2(float(d["emergency_fund_balance"]) / needs, 1)
    if surplus < 0:
        NOTES.append("budget runs a deficit")
    out("budget", d, res)


def c_stats(a):
    s = a.prices.strip()
    xs = [float(v) for v in (jarg(s) if s.startswith("[") else s.split(","))]
    if len(xs) < 2:
        raise CalcError("need at least two prices")
    rets = [b / a_ - 1 for a_, b in zip(xs, xs[1:])]
    ppy = a.periods_per_year
    res = {"observations": len(xs), "total_return_pct": r2((xs[-1] / xs[0] - 1) * 100, 4),
           "cagr_pct": r2(((xs[-1] / xs[0]) ** (ppy / (len(xs) - 1)) - 1) * 100, 4),
           "annualized_volatility_pct": r2(statistics.stdev(rets) * math.sqrt(ppy) * 100, 4) if len(rets) > 1 else None,
           **{k: (r2(v * 100, 4) if k == "max_drawdown" else v) for k, v in max_drawdown(xs).items()}}
    res["max_drawdown_pct"] = res.pop("max_drawdown")
    for n in (20, 50, 200):
        v = sma(xs, n)
        res[f"sma_{n}"] = r2(v, 4) if v is not None else None
    rsi = rsi_wilder(xs, 14)
    res["rsi_14"] = r2(rsi, 2) if rsi is not None else None
    e12, e26 = ema_series(xs, 12), ema_series(xs, 26)
    if e26:
        macd = [a_ - b for a_, b in zip(e12[len(e12) - len(e26):], e26)]
        sig = ema_series(macd, 9)
        res["macd"] = r2(macd[-1], 4)
        res["macd_signal"] = r2(sig[-1], 4) if sig else None
        res["macd_histogram"] = r2(macd[-1] - sig[-1], 4) if sig else None
    NOTES.append("indicators describe past prices only; they are not predictive signals")
    out("stats", {"observations": len(xs), "periods_per_year": ppy}, res)


def c_vol_band(a):
    sigma = rate(a.vol)
    s = sigma * math.sqrt(a.years)
    res = {}
    for z in (1.0, 1.645, 1.96):
        res[f"z={z}"] = {"low": r2(a.price * math.exp(-z * s), 4), "high": r2(a.price * math.exp(z * s), 4)}
    NOTES.append("zero-drift lognormal band from historical volatility; assumes constant volatility and "
                 "normal log-returns (fat tails make extreme moves more likely than shown)")
    out("vol-band", vars_clean(a), res)


def c_pct(a):
    if a.old == 0:
        raise CalcError("old value is zero; percentage change undefined")
    out("pct", vars_clean(a), {"change": r2(a.new - a.old, 6), "pct_change": r2((a.new / a.old - 1) * 100, 4)})


def vars_clean(a) -> dict:
    return {k: v for k, v in vars(a).items() if k not in ("func",)}


# ------------------------------------------------------------------ CLI

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="fincalc.py", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("compound", help="FV of lump sum + contributions")
    s.add_argument("principal", type=float); s.add_argument("rate"); s.add_argument("years", type=float)
    s.add_argument("--n", type=int, default=12, help="compounding periods/year (default 12)")
    s.add_argument("--contrib", type=float, default=0.0, help="regular contribution amount")
    s.add_argument("--contrib-freq", type=int, default=12)
    s.add_argument("--timing", choices=["end", "begin"], default="end")
    s.set_defaults(func=c_compound)

    s = sp.add_parser("goal", help="required regular saving to reach a target")
    s.add_argument("target", type=float); s.add_argument("years", type=float); s.add_argument("rate")
    s.add_argument("--current", type=float, default=0.0); s.add_argument("--n", type=int, default=12)
    s.set_defaults(func=c_goal)

    s = sp.add_parser("loan", help="loan payment and total cost")
    s.add_argument("principal", type=float); s.add_argument("rate"); s.add_argument("years", type=float)
    s.add_argument("--freq", type=int, default=12); s.add_argument("--fees", type=float, default=0.0)
    s.set_defaults(func=c_loan)

    s = sp.add_parser("amortize", help="amortisation summary")
    s.add_argument("principal", type=float); s.add_argument("rate"); s.add_argument("years", type=float)
    s.add_argument("--freq", type=int, default=12); s.add_argument("--at", type=int)
    s.add_argument("--rows", type=int, default=0)
    s.set_defaults(func=c_amortize)

    s = sp.add_parser("effective-rate", help="nominal -> effective annual rate")
    s.add_argument("nominal"); s.add_argument("--n", type=int, default=12)
    s.set_defaults(func=c_effective)

    s = sp.add_parser("payoff", help='debt payoff: \'{"debts":[{"name":"card","balance":5000,"rate":"22%","min_payment":150}],"monthly_budget":600,"strategy":"both"}\'')
    s.add_argument("data"); s.set_defaults(func=c_payoff)

    s = sp.add_parser("npv", help="NPV; first cash flow is t=0")
    s.add_argument("rate"); s.add_argument("cashflows", type=float, nargs="+")
    s.set_defaults(func=c_npv)

    s = sp.add_parser("irr", help="IRR of cash flows (t=0 first)")
    s.add_argument("cashflows", type=float, nargs="+"); s.set_defaults(func=c_irr)

    s = sp.add_parser("dcf", help="DCF valuation")
    s.add_argument("--fcf", type=float, required=True, help="base-year free cash flow")
    s.add_argument("--growth", default="0"); s.add_argument("--growth-path", help="comma list per year, overrides --growth/--years")
    s.add_argument("--years", type=int, default=5); s.add_argument("--discount", required=True)
    s.add_argument("--terminal-growth", default="0.02"); s.add_argument("--net-debt", type=float, default=0.0)
    s.add_argument("--shares", type=float, default=1.0); s.add_argument("--sensitivity", action="store_true")
    s.set_defaults(func=c_dcf)

    s = sp.add_parser("reverse-dcf", help="growth implied by price")
    s.add_argument("--price", type=float, required=True); s.add_argument("--fcf", type=float, required=True)
    s.add_argument("--years", type=int, default=10); s.add_argument("--discount", required=True)
    s.add_argument("--terminal-growth", default="0.02"); s.add_argument("--net-debt", type=float, default=0.0)
    s.add_argument("--shares", type=float, default=1.0)
    s.set_defaults(func=c_reverse_dcf)

    s = sp.add_parser("ratios", help='ratios from JSON: price, shares, net_income, revenue, equity, total_debt, cash, ebit, tax_rate, fcf|operating_cash_flow+capex, gross_profit, operating_income, dividends_per_share, current_assets, current_liabilities, interest_expense, ebitda, eps_growth_pct, revenue_prev, net_income_prev')
    s.add_argument("data"); s.set_defaults(func=c_ratios)

    s = sp.add_parser("budget", help='budget JSON: {"income":[{"name","amount","period"}],"expenses":[{"name","amount","period","type":"essential|debt|discretionary|savings"}],"emergency_fund_balance":0}')
    s.add_argument("data"); s.set_defaults(func=c_budget)

    s = sp.add_parser("stats", help="price-series statistics (comma list or JSON array, oldest first)")
    s.add_argument("prices"); s.add_argument("--periods-per-year", type=int, default=252)
    s.set_defaults(func=c_stats)

    s = sp.add_parser("vol-band", help="price range from volatility")
    s.add_argument("price", type=float); s.add_argument("vol", help="annualised volatility"); s.add_argument("years", type=float)
    s.set_defaults(func=c_vol_band)

    s = sp.add_parser("pct", help="percentage change")
    s.add_argument("old", type=float); s.add_argument("new", type=float); s.set_defaults(func=c_pct)
    return p


def main(argv=None) -> int:
    NOTES.clear()
    args = build_parser().parse_args(argv)
    try:
        args.func(args)
    except (CalcError, KeyError, ValueError, ZeroDivisionError, OverflowError) as e:
        print(json.dumps({"command": args.cmd, "error": f"{type(e).__name__}: {e}"}), file=sys.stdout)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
