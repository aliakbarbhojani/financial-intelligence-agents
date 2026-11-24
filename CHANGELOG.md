# Changelog

All notable changes are documented here. Format: [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning: [SemVer](https://semver.org/).

## [1.0.1] - 2026-11-23

### Fixed
- `fincalc.py` crashed on **Python 3.14** (every command): 3.14's argparse rejects a bare `%` in help text. Escaped it and added regression test FC43; suite verified on Python 3.13 and 3.14.
- If the hook script couldn't be found (e.g. the project was opened one folder too high), Python's exit code 2 made Claude Code block **every** prompt. The hook command now warns without blocking (exit 1) when the script is missing.
- Windows: the hook command falls back from `python3` to `python`; both forms are allowed for the calculator and session commands.

## [1.0.0] - 2026-11-23

### Added
- 12 Claude Code subagents with distinct scopes, least-privilege tools, bounded turns and status vocabularies.
- `/finance` manual entry point (`disable-model-invocation: true`) with `quick | standard | deep`, `agent <name>`, `status`, `stop`, `help`.
- `finance-standards` shared skill preloaded into all agents: evidence labels, source tiers, data integrity, research passes, safety, handoff format.
- `finance_gate.py` hook: manual-activation gate for agent spawns, Bash restricted to the calculator, write-path restrictions, append-only forecast journal and error log, URL blocking.
- `tools/fincalc.py` deterministic calculator: compound interest, goals, loans with fee-inclusive APR, amortisation, effective rates, debt payoff simulation, NPV/IRR, DCF with sensitivity, reverse DCF, ratios, budgets, price statistics (volatility, drawdown, SMA, RSI, MACD), volatility bands.
- Controlled file-based memory with record types, a research cache with revalidation dates, a forecast journal and outcomes, and an error log.
- Templates for final reports, handoffs (Markdown + JSON Schema), journal entries, error-log entries, cache entries and test records.
- Test suites: 35 calculator known-answer/property tests, 29 hook guardrail tests, 18 static configuration checks, and a runtime test plan with a smoke script.
- Documentation: README, architecture, workflows, agent roles, security, usage.

### Fixed during development
- Permission `ask` rules written as `Write(path)` were not matched by Claude Code 2.1.331 (runtime warning). Replaced with `Edit(path)`, which covers all file-editing tools, and added a regression check (V30).
- The payoff test assumed a rounded-down payment would clear the debt in exactly 24 months. Corrected the test to round up to the cent, as lenders do (FC14).
