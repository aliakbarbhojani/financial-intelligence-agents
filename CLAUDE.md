# Financial Intelligence Agents: project instructions

This repository defines an **on-demand** 12-agent financial research team for Claude Code.

## Activation rules (important)
- The finance team runs **only** when the user types `/finance ...`, @-mentions a finance agent (`@agent-budget-analyst`), or starts `claude --agent financial-orchestrator`.
- In any other conversation, **don't** delegate to finance agents, start financial workflows, or volunteer financial recommendations. A hook (`.claude/hooks/finance_gate.py`) technically blocks finance-agent spawns outside an open finance session. Don't try to work around it.
- Never write to `.claude/state/` or try to open a finance session yourself.

## Working on this repository (development tasks)
- Run all tests: `python3 tests/run_all.py`
- Calculator: `python3 tools/fincalc.py --help`
- Agent prompts live in `.claude/agents/`, shared rules in `.claude/skills/finance-standards/SKILL.md`, the entry point in `.claude/skills/finance/SKILL.md`.
- After changing agents, skills, settings or hooks, run `python3 tests/validate_config.py` and `python3 tests/test_finance_gate.py`.
- Never commit anything in `memory/private/`, `memory/error-log/`, `memory/forecast-journal/`, `memory/research-cache/`, `reports/` or `.claude/state/`.
