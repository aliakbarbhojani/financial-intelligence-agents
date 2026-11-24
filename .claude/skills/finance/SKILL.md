---
name: finance
description: Manual entry point for the Financial Intelligence multi-agent team (budgeting, debt, online income, market research, investment due diligence, forecasting). Runs only when the user types /finance.
argument-hint: "[quick|standard|deep] <request>  |  agent <agent-name> <request>  |  status  |  stop  |  help"
disable-model-invocation: true
allowed-tools: Read, Bash(python3 .claude/hooks/finance_gate.py status), Bash(python3 .claude/hooks/finance_gate.py deactivate), Bash(python .claude/hooks/finance_gate.py status), Bash(python .claude/hooks/finance_gate.py deactivate), Bash(python3 tools/fincalc.py *), Bash(python tools/fincalc.py *)
---

# /finance: Financial Intelligence System

The user explicitly started a finance session. Arguments: `$ARGUMENTS`

The `UserPromptSubmit` hook has already opened a time-limited finance session that lets finance agents be spawned. Without it, the `PreToolUse` gate blocks them.

> **Python command:** examples use `python3`. On Windows (python.org installer) use `python` instead. If `python3` fails once, switch to `python` for the rest of the session.

## Step 1: Parse the arguments

| First word | Action |
|---|---|
| `help` or empty | Print the usage table below and stop. |
| `status` | Run `python3 .claude/hooks/finance_gate.py status` and report the result in one line. Stop. |
| `stop` | Run `python3 .claude/hooks/finance_gate.py deactivate`, confirm the finance session is closed, and stop. |
| `agent` | Single-agent mode, see Step 3. |
| `quick` / `standard` / `deep` | That mode; the rest of the text is the request. |
| anything else | Mode = `standard`; the full text is the request. |

Usage table (for `help`):
```
/finance <request>                     Standard mode (default)
/finance quick <request>               Minimal agents, light verification
/finance deep <request>                Full research + adversarial verification (more usage)
/finance agent <name> <request>        Run one specialist directly (unreviewed)
/finance status | stop | help
Agents: budget-analyst, financing-advisor, income-strategist, market-researcher, market-analyst,
        investment-researcher, market-forecaster, forecast-supervisor, risk-compliance-analyst,
        head-financial-intelligence, chief-financial-authority
```

## Step 2: Full workflow (quick / standard / deep)

1. Read `.claude/agents/financial-orchestrator.md` and **act as the Financial Orchestrator**, following its protocol (§1–§10) exactly, in this main session. Also follow the shared standards in `.claude/skills/finance-standards/SKILL.md` (read it if it isn't already in context).
2. Delegate to specialists with the `Agent` tool, using the compact brief format. Pass only the information they need from this conversation: the request, the constraints the user disclosed, and prior handoffs. Never pass the whole conversation.
3. If the `Agent` tool is unavailable, tell the user in one line that the team can't run here, explain why, and stop. Don't simulate the agents.
4. Deliver the authorised report and the Authorization block.
5. Close the session: run `python3 .claude/hooks/finance_gate.py deactivate`. Then **stop**: no follow-up research, monitoring or unsolicited suggestions beyond one optional next step.

## Step 3: Single-agent mode (`/finance agent <name> <request>`)

1. Check that `<name>` is one of the 11 specialists listed above. If it isn't, show the list and stop.
2. Spawn that agent once, with a brief following orchestrator §4 and mode `standard`, marked `direct invocation`.
3. Present its output with the banner `UNREVIEWED SINGLE-AGENT OUTPUT: not verified by the Head of Financial Intelligence or authorised by the Chief Financial Authority.` Offer to run the full verified workflow instead.
4. Run `python3 .claude/hooks/finance_gate.py deactivate` and stop.

## Memory and privacy

- Save nothing about the user's finances unless they explicitly authorise it. To save a preference, ask first, then append to `memory/private/preferences.md` with the date and the record type `USER_PREFERENCE`.
- `memory/`, `reports/` and `.claude/state/` contents are git-ignored. Never commit, push or upload them.
