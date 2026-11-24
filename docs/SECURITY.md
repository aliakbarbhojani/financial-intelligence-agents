# Security, privacy and financial safety

## Enforcement matrix: prompted vs technically enforced

"Technical" means Claude Code or the hook blocks the action regardless of what the model decides. "Prompt" means it depends on the model following instructions. Every technical control below has an automated test (`tests/test_finance_gate.py`, `tests/validate_config.py`).

| Requirement | Mechanism | Type | Test |
|---|---|---|---|
| `/finance` never auto-runs | `disable-model-invocation: true` (skill removed from model context; model invocation blocked) | **Technical** (Claude Code) | V20 |
| Finance agents never auto-activate | PreToolUse hook denies `Agent`/`Task` spawns of finance agents unless a finance session was opened by the user | **Technical** (hook) | G01–G13 |
| Session opened only by the user | Opened only by `UserPromptSubmit` (typed `/finance …` or `@agent-<finance-agent>`). The CLI has no `activate` command. `.claude/` edits require approval. | **Technical**, see limitation L2 | G03–G07, G24 |
| Sessions don't linger | 4-hour TTL, closed on `/finance stop`, `/clear`, new session, and at workflow end | **Technical** + prompt (end-of-workflow close) | G05, G09, G10 |
| Only the orchestrator delegates | Specialists: `Agent` in `disallowedTools`. `--agent` mode: `Agent(...)` allowlist | **Technical** (Claude Code) | V06 |
| Least-privilege tools | Explicit `tools:` per agent. No web for budget and chief. Write only for 3 agents | **Technical** (Claude Code) | V05, V07, V08 |
| No arbitrary shell in agents | Hook allows only `python3 tools/fincalc.py …`. Denies `; & \| > < $( )` backticks and newlines | **Technical** (hook) | G20–G23 |
| Agents can't alter their own instructions or guardrails | Hook denies agent writes to `.claude/**`. Main-session edits there require user approval (`ask` rule) | **Technical** | G30 |
| Private memory only with consent | Hook denies agent writes to `memory/private/`. Main-session writes there need approval | **Technical** + prompt (ask before saving) | G31 |
| Forecast journal can't be rewritten | Hook: new files only; Edit and overwrite denied | **Technical** (hook) | G34 |
| Error log append-only | Hook: new files only | **Technical** (hook) | G32 |
| Malicious / local / credentialed URLs | Hook blocks blocklisted domains (+ subdomains), non-HTTP schemes, embedded credentials, and (for agents) loopback and private IPs | **Technical** (hook) | G40–G42 |
| Secrets not readable | `deny` rules for `.env*`, `secrets/`, `~/.ssh`, `~/.aws` | **Technical** (permissions) | V30 |
| No trades, transfers or applications | No agent has transaction-capable tools; the optional MCP example is read-only data. Prompts forbid it | **Technical by absence of tools** + prompt | V05 |
| Prompt-injection resistance | Standards §6: retrieved content is data; injected instructions are quoted and ignored | Prompt | R13 (runtime) |
| No guarantees, no fabrication, no false precision | Standards + agent prompts + supervisor precision audit + Chief checklist | Prompt + review chain | R11, R14, R15 |
| Not a licensed adviser | Standards §6 and Chief checklist | Prompt | R05, R15 |
| Paywalls and logins respected | Standards §6; agents have no browser or credential tools | Prompt + absence of tools | n/a |

## Known limitations
- **L1, hooks must be allowed to run.** Hooks live in `.claude/settings.json` and only run in a *trusted* workspace and where organisation policy permits user hooks. If hooks are disabled, the technical controls marked "hook" fall back to prompt-level behaviour. Check by running `/finance status` (it should respond) and see `docs/USAGE.md#verify-the-guardrails`.
- **L2, the main session is user-supervised, not sandboxed.** In the main session the model could in principle try to create the session state file with a Bash command. That requires a user-approved Bash permission (the file is under `.claude/`, which is protected by an `ask` rule for edits). Don't add broad `Bash(*)` allow rules in this project.
- **L3, `@agent-` mentions.** Mentioning a finance agent opens a session (by design, for manual single-agent use). Natural-language requests such as "use the budget-analyst" do **not**.
- **L4, Python required.** The hook and calculator need Python ≥ 3.9 as `python3` or `python` on PATH. The hook command tries `python3` first and falls back to `python`, which covers the Windows python.org installer. Claude Code on Windows runs hooks through Git Bash.
- **L5, the blocklist ships empty** (except a test domain). Populate `config/blocked-domains.txt` from your regulator's warning lists.
- **L6, WebFetch is pre-approved** for smooth research. Move `WebFetch` from `allow` to `ask` in `.claude/settings.json` if you want to approve every fetch.

## Privacy model
- Nothing personal is stored unless the user explicitly approves, and then only in git-ignored `memory/private/`.
- Agents keep search queries generic and never put personal details into URLs or external services.
- `memory/` journals, logs and caches, `reports/` and `.claude/state/` are git-ignored. Run `git status` before every push.
- Credentials, if any optional integration needs them, go in environment variables, never in files.

## Reporting vulnerabilities
Open a private security advisory on the repository (GitHub → Security → Report a vulnerability). Don't file public issues for security problems.
