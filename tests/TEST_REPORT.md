# Test report: v1.0.0 (2026-11-23)

Build environment: Linux, Python 3.13, Claude Code 2.1.331 (CLI present, **no model API credentials**, user hooks disabled by the environment's organisation policy).

Test types: **unit** (real code, synthetic inputs) · **static** (file and config inspection) · **runtime** (real Claude Code process). No results below are simulated or mocked unless marked.

## Summary

| Suite | Type | Run | Pass | Fail | Blocked / not run |
|---|---|---|---|---|---|
| Calculator known-answer and property tests (`test_fincalc.py`) | unit | 35 | 35 | 0 | 0 |
| Hook guardrail tests (`test_finance_gate.py`) | unit (real hook script, synthetic hook payloads) | 29 | 29 | 0 | 0 |
| Static configuration validation (`validate_config.py`) | static | 18 | 18 | 0 | 0 |
| Claude Code loader and settings checks (R-S1…R-S5) | runtime (partial) | 5 | 4 | 0 (1 failed, fixed, passed on retest) | 1 blocked |
| End-to-end agent workflows (R01–R20) | runtime | 0 | n/a | n/a | **20 not run** (no API credentials) |
| **Total** | | **87** | **86** | **0** | **21** |

## Runtime checks performed in the build environment

| ID | Objective | Expected | Actual | Status |
|---|---|---|---|---|
| R-S1 | Claude Code discovers all 12 agents | All 12 identifiers resolvable | `claude --agent no-such-agent` listed all 12 finance agents among the available agents | PASS |
| R-S2 | Both project skills load | `project: 2` skills | Debug log: `Loaded 17 unique skills (… project: 2 …)` | PASS |
| R-S3 | All frontmatter fields recognised | 0 "does not recognize or apply" warnings | 0 warnings | PASS |
| R-S4 | Hooks registered and executing | 3 events registered; state file created by `/finance` | Registered: debug log names `PreToolUse, SessionStart, UserPromptSubmit`. **Execution blocked**: the environment disables user hooks because it can't read the organisation's managed settings | BLOCKED (execution); registration PASS |
| R-S5 | Settings permission rules effective | No warnings | **FAIL:** `Write(./.claude/**)` and `Write(./memory/private/**)` reported as never matched. **Fix:** replaced with `Edit(...)` rules, added regression check V30. **Retest:** no warnings | PASS on retest |

## Issues found and resolved

| ID | Issue | Root cause | Correction | Retest |
|---|---|---|---|---|
| FC14 | Payoff test expected 24 months, got 25 | Test rounded payment *down* (470.73 < 470.7347), leaving a ~0.17 residual; the simulator was correct | Test now rounds up to the cent, as lenders do | PASS |
| R-S5 | Ineffective `Write(path)` ask rules | Claude Code matches file-permission rules via `Edit(path)` only | Rules changed to `Edit(path)`; static check added | PASS |
| D1 | Design: the original plan had the orchestrator as a nested subagent | Build environment has `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=1` (nesting off) | Main session now acts as central executor via `/finance`; nested mode stays supported | V06, static |
| D2 | Design: a CLI `activate` command would let the model open sessions itself | Allow-listed CLI commands are model-runnable | No `activate` command exists; sessions open only from the `UserPromptSubmit` hook | G24 |

## Coverage of the specification's test list

| Spec requirement | Covered by | Status |
|---|---|---|
| Arithmetic, percentages, compound interest, loans, ratios, valuation | FC01–FC42 | PASS (unit) |
| Currency/period consistency (period normalisation) | FC30, FC42 | PASS (unit). Cross-currency handling is prompt-level, R04/R08 |
| Prompt injection | Standards §6; R13 | NOT RUN (runtime) |
| Fabrication / guarantees / suspicious offers | R11, R14, R15, R07 | NOT RUN (runtime) |
| Trade/transfer requests | R05; no transaction tools (V05) | static PASS; runtime NOT RUN |
| Manual-activation bypass | G01–G13, V20; R01–R03 | unit + static PASS; runtime NOT RUN |
| Sensitive data exposure | G31, V30, V33, V34 | PASS (unit + static) |
| Permission modification | G30, V06, V08 | PASS (unit + static) |
| Agent discovery | R-S1 | PASS (runtime) |
| Correct selection, delegation, supervisor intervention, revision bounds, authorisation | R04, R06–R12, R17 | NOT RUN (runtime) |
| Efficiency (simple requests don't activate the full team) | R04/R18 (measures `subagent_stats.spawned`) | NOT RUN (runtime) |

## How to complete validation
1. Clone into a trusted workspace with an authenticated Claude Code.
2. `bash tests/runtime/run_runtime_smoke.sh` runs R01–R05 automatically.
3. Run R06–R20 from `tests/runtime/RUNTIME_TESTS.md` and record each one with `templates/test-record.md`.
