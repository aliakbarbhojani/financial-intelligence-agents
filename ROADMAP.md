# Development Roadmap: Financial Intelligence & Advisory Multi-Agent System

Status values: `NOT STARTED` · `IN PROGRESS` · `COMPLETED` · `BLOCKED` · `FAILED`

| Phase | Status | Updated |
|---|---|---|
| 1. Requirements and environment assessment | COMPLETED | 2026-11-23 |
| 2. Architecture and workflow design | COMPLETED | 2026-11-23 |
| 3. Agent implementation | COMPLETED | 2026-11-23 |
| 4. Shared infrastructure | COMPLETED | 2026-11-23 |
| 5. Testing and validation | IN PROGRESS: automated and loader tests complete; end-to-end runtime tests BLOCKED in build environment | 2026-11-23 |
| 6. Documentation and release preparation | COMPLETED | 2026-11-23 |

**Readiness: PARTIALLY READY.** Critical configuration, guardrail logic, calculations and agent discovery are validated. Live end-to-end workflow tests (R01–R20) must still be run in an authenticated, hook-enabled environment.

---

## Phase 1: Requirements and environment assessment (COMPLETED)

### Environment findings (verified, not assumed)

| Item | Finding | Source |
|---|---|---|
| Claude Code version | 2.1.331 | `claude --version` |
| Subagent format | Markdown + YAML frontmatter in `.claude/agents/`. Only `name` and `description` are required. Unknown fields are silently ignored. | code.claude.com/docs/en/sub-agents |
| Nested delegation | Supported (default up to 3 levels) but configurable via `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH`. Build environment: `1` (off). | docs + env |
| `Agent(type, ...)` allowlist | Enforced only when the agent runs as main thread (`claude --agent`). | docs |
| Skills | `disable-model-invocation: true` = technically enforced manual-only; such skills can't be preloaded into subagents. | code.claude.com/docs/en/skills |
| Hooks | `PreToolUse` input includes `agent_type` inside subagents. Spawn tool `Agent` with `tool_input.subagent_type`. `UserPromptSubmit` receives the typed `/command` line. | code.claude.com/docs/en/hooks |
| Agent `memory:` field | Depends on auto memory. Not used; a controlled `memory/` tree is used instead. | docs |
| Model API in build env | Not available (auth error); end-to-end runtime tests blocked. | runtime probe |
| User hooks in build env | Registered but not executed (organisation managed settings unreadable). | debug log |

### Acceptance criteria and results
| ID | Criterion | Result |
|---|---|---|
| AC1 | 12 valid agents, least privilege, only orchestrator delegates | MET (V01–V09, R-S1, R-S3) |
| AC2 | `/finance` manual-only with modes and subcommands | MET (V20–V21, R-S2) |
| AC3 | Finance agents can't spawn outside a user-opened session | MET at hook-logic level (G01–G13). Live hook execution not verified (R-S4 blocked) |
| AC4 | Agents restricted: calculator-only shell, write paths, no `.claude/` edits, immutable journal | MET at hook-logic level (G20–G35) |
| AC5 | Calculator known-answer tests pass | MET (35/35) |
| AC6 | Verification hierarchy with status vocabularies and ≤ 2 revisions | Implemented (V10, static). Runtime behaviour NOT YET VERIFIED (R04, R06–R17) |
| AC7 | No hardcoded personal data; private data git-ignored | MET (V33, V34) |
| AC8 | Honest test records | MET (tests/TEST_REPORT.md) |

## Phase 2: Architecture and workflow design (COMPLETED)
- Central-executor architecture (main session follows the orchestrator protocol via `/finance`), plus `claude --agent financial-orchestrator` dedicated mode.
- Five workflows (A–E) and an educational path, three operational modes with caps, a verification hierarchy with blocking risk review and a two-stage independent forecast supervision.
- Handoff protocol (Markdown + JSON Schema). Hook-based activation gate and least-privilege enforcement.
- See `docs/ARCHITECTURE.md`, `docs/WORKFLOWS.md`.

## Phase 3: Agent implementation (COMPLETED)
- 12 agents in `.claude/agents/`, shared standards skill, `/finance` entry skill.

## Phase 4: Shared infrastructure (COMPLETED)
- `finance_gate.py` hook, `settings.json` permissions, `fincalc.py` calculator, memory knowledge base with record types, forecast journal and outcomes, error log, research cache, templates, config.

## Phase 5: Testing and validation (IN PROGRESS)
- DONE: 82 automated tests (unit + guardrail + static), all passing; 5 runtime loader/settings checks (4 pass, 1 blocked; 1 defect found and fixed).
- BLOCKED: end-to-end runtime scenarios R01–R20 (no model API credentials; user hooks disabled in build environment).
- NEXT: run `tests/runtime/run_runtime_smoke.sh`, then R06–R20, in an authenticated, trusted workspace. Record results in `tests/TEST_REPORT.md`.

## Phase 6: Documentation and release preparation (COMPLETED)
- README, docs (architecture, workflows, roles, security, usage), CHANGELOG, LICENSE (MIT), `.gitignore`, contribution guide, test report.
- Repository is **not** published. Publishing requires the user's action.

## Future enhancements (proposals, not commitments)
- Optional read-only market-data MCP integration recipes for specific free data sources.
- Automated forecast-outcome evaluation helper (reads journal, compares against fetched data, writes an outcome file).
- A `fincalc` currency-conversion command with explicit FX-rate input and date.
- Plugin packaging for one-command installation (note: plugin subagents ignore `hooks`/`permissionMode`, so project-level hooks would still be needed).
