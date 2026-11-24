# Usage guide

## Install

**Requirements:** Claude Code (built and validated against 2.1.331; requires subagents, skills and hooks support) · Python ≥ 3.9 on PATH as `python3` · optional: git.

### Option 1: Use the repository as your finance workspace (recommended)
```bash
git clone https://github.com/aliakbarbhojani/financial-intelligence-agents.git
cd financial-intelligence-agents
python3 tests/run_all.py        # all automated tests should pass
claude                          # accept the workspace trust dialog once (hooks need it)
```

### Option 2: Add the team to an existing project
Copy `.claude/agents/`, `.claude/skills/finance/`, `.claude/skills/finance-standards/`, `.claude/hooks/finance_gate.py`, `tools/fincalc.py`, `config/`, `templates/` and `memory/` into your project, then **merge** (don't overwrite) the `permissions` and `hooks` blocks from `.claude/settings.json` into your project's settings. Add the `.gitignore` entries.

> User-level install (`~/.claude/agents`) isn't recommended: the hook, calculator and memory paths are project-relative.

## Verify the guardrails
1. In Claude Code, type: `Use the budget-analyst subagent to make me a budget`. Expected result: the spawn is **denied** by finance-gate and you're pointed to `/finance`.
2. Type `/finance status`. Expected: `finance session: INACTIVE`.
3. Type `/finance quick What is an emergency fund?`. Expected: a short, authorised answer, after which the session closes.

If step 1 isn't denied, hooks aren't running. Check that the workspace is trusted, that your organisation allows user hooks, and that `python3` works (see SECURITY.md, L1).

## Commands

| Command | What it does |
|---|---|
| `/finance <request>` | Standard mode (default) |
| `/finance quick <request>` | Minimal agents, light verification, few or no searches |
| `/finance deep <request>` | Full research and adversarial verification (more usage; also proposed by the orchestrator when needed) |
| `/finance agent <name> <request>` | One specialist, unreviewed |
| `@agent-<name> <request>` | Same as above, via Claude Code mentions |
| `/finance status` · `/finance stop` · `/finance help` | Session control |
| `claude --agent financial-orchestrator` | Dedicated finance session; orchestrator allowlist enforced |

## Example requests
```text
/finance quick Net income 3,800/month. Rent 1,450, groceries 420, transit 130, phone 55,
               dining 280, subscriptions 75. How much can I save, and how long to a 3-month emergency fund?

/finance Compare: Loan A 20,000 at 8.4% over 4 years with a 250 fee, vs Loan B 20,000 at 7.6% over 6 years, no fee.
         I'm in <jurisdiction>. Which costs less overall and what are the risks?

/finance I have 5 hours a week and strong writing skills. What legitimate online income options fit, and
         what would the first 90 days look like?

/finance Research current inflation, policy-rate and labour-market conditions in <country>.

/finance deep Full due diligence on <TICKER> (<exchange>): valuation, moat, risks, bull/base/bear.

/finance deep Build 6-month scenarios for <index>, with the forecast independently reviewed.

/finance 70% of my portfolio is one tech stock. Assess the risk.

/finance agent risk-compliance-analyst Is this offer legitimate? "Guaranteed 4% weekly returns, invite friends for bonuses."
```

Tip: state your **jurisdiction, currency, time horizon and risk tolerance** for personalised analysis. Otherwise you'll get conditional analysis with stated assumptions.

## What you get back
A report scaled to the request, using labels such as [FACT], [CALC], [ANALYSIS], [ASSUMPTION] and [FORECAST], data timestamps and exchanges for market data, a sources table, and a closing **Authorization** block naming the agents involved, the verification outcome and any material limitations. Ask for a saved copy and it's written to `reports/` (git-ignored).

## Memory
- The team reads `memory/knowledge/` (methodologies, source preferences, lessons) automatically.
- It logs analytical errors to `memory/error-log/` and every forecast to `memory/forecast-journal/` (immutable).
- To evaluate an old forecast: `/finance agent head-financial-intelligence Evaluate forecast FJ-… against what actually happened`. The outcome is written as a new file in `memory/forecast-journal/outcomes/`.
- Preferences ("always report in EUR") are saved to `memory/private/` only after you say yes.
- Delete any memory by deleting the file.

## Optional integrations
- **Market-data MCP server:** see `config/mcp.example.json`. Use read-only servers only, keep keys in environment variables, and grant the server only to research agents via `mcpServers:` in their frontmatter. Review cost, permissions and code first.
- **Model tiers:** edit each agent's `model:` line (`opus`, `sonnet`, `haiku`, `fable`, `inherit`).

## Troubleshooting
| Symptom | Fix |
|---|---|
| `/finance` not in the menu | Make sure you started `claude` in the repo root, and that `.claude/skills/finance/SKILL.md` exists |
| Agents not found | Run `claude --agent nope -p x`; the error lists the available agents |
| Spawn denied during a `/finance` run | The session expired (4h) or was stopped. Re-run `/finance …`. Adjust the TTL with `FIN_AGENTS_SESSION_TTL_MIN` |
| Agent says it can't run a command | Expected: agents may only run `tools/fincalc.py` |
| "Team can't run here" | The `Agent` tool is unavailable in this environment |
