---
record_type: PERSISTENT_FACT
updated: 2026-11-23
maintainer: user
---

# Verified calculation methodologies

All implemented in `tools/fincalc.py` and covered by known-answer tests in `tests/test_fincalc.py`.

| Topic | Method | fincalc command |
|---|---|---|
| Compound growth | FV = PV·(1 + r/n)^(n·t) | `compound` |
| Regular contributions | FV annuity = PMT·((1+i)^N − 1)/i (×(1+i) if paid at period start) | `compound --contrib` |
| Savings goal | PMT = (Target − FV(current))·i / ((1+i)^N − 1) | `goal` |
| Loan payment | PMT = P·i / (1 − (1+i)^−N) | `loan` |
| Fee-inclusive APR | Periodic rate solving PV(PMT, i, N) = P − fees; nominal APR = i·freq | `loan --fees` |
| Effective annual rate | EAR = (1 + r/n)^n − 1 | `effective-rate` |
| Debt payoff | Monthly simulation; avalanche = highest rate first, snowball = smallest balance first | `payoff` |
| NPV / IRR | NPV = Σ CF_t/(1+r)^t; IRR by bisection on NPV = 0 | `npv`, `irr` |
| DCF | PV of explicit FCF + Gordon terminal value FCF_N·(1+g)/(r−g) | `dcf` |
| Reverse DCF | Bisection on constant growth so value/share = price | `reverse-dcf` |
| Volatility | Sample stdev of simple returns × √(periods per year) | `stats` |
| Max drawdown | min over t of (P_t / running peak − 1) | `stats` |
| RSI | Wilder smoothing, 14 periods | `stats` |
| MACD | EMA12 − EMA26 (SMA-seeded), signal EMA9 | `stats` |
| Volatility band | P·exp(±z·σ·√t), zero drift | `vol-band` |
