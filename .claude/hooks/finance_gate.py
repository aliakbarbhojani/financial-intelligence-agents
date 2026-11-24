#!/usr/bin/env python3
"""
finance_gate.py: technical guardrails for the Financial Intelligence agent team.

Registered in .claude/settings.json for these hook events:
  * UserPromptSubmit : opens a time-limited "finance session" when the user types
                       `/finance ...` or @-mentions a finance agent; `/finance stop` closes it.
  * SessionStart     : closes any finance session on startup or /clear.
  * PreToolUse       : (1) denies spawning finance agents outside an open finance session;
                       (2) inside finance agents, restricts Bash to tools/fincalc.py, restricts
                           writes to reports/ + selected memory/ folders, keeps the forecast journal
                           and error log append-only, and blocks writes to .claude/ and memory/private/;
                       (3) blocks WebFetch to blocklisted / local / credential-bearing URLs.

CLI (safe for the model to run; there is deliberately NO `activate` command):
  python3 .claude/hooks/finance_gate.py status
  python3 .claude/hooks/finance_gate.py deactivate

Standard library only. Python >= 3.9.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

FINANCE_AGENTS = frozenset({
    "financial-orchestrator", "budget-analyst", "financing-advisor", "income-strategist",
    "market-researcher", "market-analyst", "investment-researcher", "market-forecaster",
    "forecast-supervisor", "risk-compliance-analyst", "head-financial-intelligence",
    "chief-financial-authority",
})
DEFAULT_TTL_MIN = 240

# ---------------------------------------------------------------- paths / state

def project_dir(data: dict | None = None) -> Path:
    env = os.environ.get("CLAUDE_PROJECT_DIR")
    if env:
        return Path(env).resolve()
    if data and data.get("cwd"):
        return Path(data["cwd"]).resolve()
    # fall back to repo root relative to this file: <root>/.claude/hooks/finance_gate.py
    return Path(__file__).resolve().parents[2]


def state_file(root: Path) -> Path:
    return root / ".claude" / "state" / "finance-session.json"


def ttl_seconds() -> int:
    try:
        return max(1, int(os.environ.get("FIN_AGENTS_SESSION_TTL_MIN", DEFAULT_TTL_MIN))) * 60
    except ValueError:
        return DEFAULT_TTL_MIN * 60


def read_state(root: Path) -> dict | None:
    f = state_file(root)
    if not f.exists():
        return None
    return json.loads(f.read_text(encoding="utf-8"))  # errors propagate -> caller fails closed


def activate(root: Path, session_id: str, mode: str, via: str) -> dict:
    f = state_file(root)
    f.parent.mkdir(parents=True, exist_ok=True)
    st = {"session_id": session_id or "*", "activated_at": int(time.time()),
          "ttl_seconds": ttl_seconds(), "mode": mode, "via": via}
    f.write_text(json.dumps(st), encoding="utf-8")
    return st


def deactivate(root: Path) -> bool:
    f = state_file(root)
    if f.exists():
        f.unlink()
        return True
    return False


def session_active(root: Path, session_id: str | None) -> bool:
    st = read_state(root)
    if not st:
        return False
    if time.time() - st.get("activated_at", 0) > st.get("ttl_seconds", ttl_seconds()):
        return False
    sid = st.get("session_id", "*")
    return sid == "*" or not session_id or sid == session_id

# ---------------------------------------------------------------- decisions

def deny(reason: str) -> None:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": f"[finance-gate] {reason}",
    }}))
    sys.exit(0)


def no_decision() -> None:
    sys.exit(0)

# ---------------------------------------------------------------- UserPromptSubmit

MENTION_RE = re.compile(
    r"@agent-(?P<a>[a-z0-9-]+)|@\"(?P<b>[a-z0-9-]+) \(agent\)\"", re.IGNORECASE)
FINANCE_CMD_RE = re.compile(r"^\s*/finance(?:\s+(?P<args>.*))?$", re.IGNORECASE | re.DOTALL)


def on_user_prompt(data: dict, root: Path) -> None:
    prompt = data.get("prompt") or ""
    sid = data.get("session_id") or "*"
    m = FINANCE_CMD_RE.match(prompt)
    if m:
        args = (m.group("args") or "").strip()
        first = args.split(maxsplit=1)[0].lower() if args else ""
        if first == "stop":
            deactivate(root)
            return
        if first in ("", "help", "status"):
            return  # informational subcommands never open a session
        mode = first if first in ("quick", "standard", "deep") else ("direct" if first == "agent" else "standard")
        activate(root, sid, mode, "/finance")
        print(f"[finance-gate] Finance session opened (mode={mode}, expires in {ttl_seconds() // 60} min).")
        return
    for mm in MENTION_RE.finditer(prompt):
        name = (mm.group("a") or mm.group("b") or "").lower()
        if name in FINANCE_AGENTS:
            activate(root, sid, "direct", f"@{name}")
            print(f"[finance-gate] Finance session opened for direct invocation of {name}.")
            return

# ---------------------------------------------------------------- PreToolUse helpers

BASH_ALLOWED_RE = re.compile(
    r"""^\s*python3?\s+(?:"?\$\{?CLAUDE_PROJECT_DIR\}?"?/)?tools/fincalc\.py(?:\s|$)""")
GATE_CLI_RE = re.compile(
    r"""^\s*python3?\s+(?:"?\$\{?CLAUDE_PROJECT_DIR\}?"?/)?\.claude/hooks/finance_gate\.py\s+(status|deactivate)\s*$""")
SHELL_META_RE = re.compile(r"[;&|`<>\n\r]|\$\(")


def check_bash(cmd: str, agent_type: str) -> None:
    stripped = re.sub(r'"?\$\{?CLAUDE_PROJECT_DIR\}?"?', "", cmd)
    if SHELL_META_RE.search(stripped):
        deny(f"{agent_type} may not chain, pipe, redirect or substitute shell commands.")
    if BASH_ALLOWED_RE.match(cmd):
        no_decision()
    if agent_type == "financial-orchestrator" and GATE_CLI_RE.match(cmd):
        no_decision()
    deny(f"{agent_type} may only run `python3 tools/fincalc.py ...` (deterministic calculator).")


def rel_to_root(path_str: str, root: Path) -> str | None:
    p = Path(path_str)
    if not p.is_absolute():
        p = root / p
    try:
        return p.resolve().relative_to(root).as_posix()
    except ValueError:
        return None  # outside project


APPEND_ONLY = ("memory/forecast-journal/", "memory/error-log/")
WRITABLE = ("reports/", "memory/research-cache/")


def check_write(tool: str, tool_input: dict, agent_type: str, root: Path) -> None:
    path_str = tool_input.get("file_path") or tool_input.get("notebook_path") or tool_input.get("path") or ""
    rel = rel_to_root(path_str, root)
    if rel is None:
        deny(f"{agent_type} may not write outside the project.")
    if rel.startswith(".claude/") or rel == ".claude":
        deny("Agents may not modify agent definitions, skills, hooks or settings. Propose changes to the user instead.")
    if rel.startswith("memory/private/"):
        deny("Only the main session may save user preferences, and only after explicit user approval.")
    if rel.startswith(APPEND_ONLY):
        if tool != "Write":
            deny(f"{rel} is append-only: create a new entry file instead of editing.")
        if (root / rel).exists():
            deny(f"{rel} already exists; historical journal/log entries are immutable.")
        no_decision()
    if rel.startswith(WRITABLE):
        no_decision()
    deny(f"{agent_type} may only write to reports/, memory/research-cache/, or new entries in "
         f"memory/forecast-journal/ and memory/error-log/.")


def load_blocklist(root: Path) -> set[str]:
    f = root / "config" / "blocked-domains.txt"
    if not f.exists():
        return set()
    out = set()
    for line in f.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip().lower()
        if line:
            out.add(line.lstrip("."))
    return out


def check_url(url: str, root: Path, strict_local: bool) -> None:
    try:
        parts = urlsplit(url)
    except ValueError:
        deny("Malformed URL.")
    if parts.scheme not in ("http", "https"):
        deny(f"Blocked URL scheme '{parts.scheme}'.")
    if parts.username or parts.password:
        deny("URLs containing credentials are blocked.")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        deny("URL has no host.")
    for d in load_blocklist(root):
        if host == d or host.endswith("." + d):
            deny(f"Domain '{host}' is on the project blocklist (config/blocked-domains.txt).")
    if strict_local:
        if host == "localhost" or host.endswith(".localhost") or host.endswith(".local"):
            deny("Finance agents may not fetch local-network addresses.")
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                deny("Finance agents may not fetch private/loopback IP addresses.")
        except ValueError:
            pass

# ---------------------------------------------------------------- PreToolUse

def on_pre_tool_use(data: dict, root: Path) -> None:
    tool = data.get("tool_name") or ""
    ti = data.get("tool_input") or {}
    agent_type = (data.get("agent_type") or "").strip()
    in_finance = agent_type in FINANCE_AGENTS

    if tool in ("Agent", "Task"):
        target = (ti.get("subagent_type") or "").strip()
        if target not in FINANCE_AGENTS:
            no_decision()
        if in_finance:
            no_decision()  # delegation inside an already-running finance workflow
        try:
            if session_active(root, data.get("session_id")):
                no_decision()
        except Exception as exc:  # fail closed for finance agents
            deny(f"Could not read finance session state ({exc}); refusing to spawn {target}.")
        deny(f"'{target}' is a manual-only finance agent. Start a session with `/finance <request>` "
             f"(or mention @agent-{target}). Financial agents never activate automatically.")

    if tool == "WebFetch":
        check_url(str(ti.get("url") or ""), root, strict_local=in_finance)
        no_decision()

    if not in_finance:
        no_decision()

    if tool == "Bash":
        check_bash(str(ti.get("command") or ""), agent_type)
    if tool in ("Write", "Edit", "MultiEdit", "NotebookEdit"):
        check_write(tool, ti, agent_type, root)
    no_decision()

# ---------------------------------------------------------------- main

def main(argv: list[str]) -> int:
    if len(argv) > 1:
        root = project_dir()
        cmd = argv[1]
        if cmd == "status":
            try:
                st = read_state(root)
            except Exception as exc:
                print(f"finance session: UNKNOWN (state unreadable: {exc})")
                return 1
            if st and session_active(root, None):
                left = st["activated_at"] + st.get("ttl_seconds", ttl_seconds()) - int(time.time())
                print(f"finance session: ACTIVE (mode={st.get('mode')}, via={st.get('via')}, "
                      f"expires in {max(0, left) // 60} min)")
            else:
                print("finance session: INACTIVE")
            return 0
        if cmd == "deactivate":
            print("finance session: CLOSED" if deactivate(root) else "finance session: already inactive")
            return 0
        print(__doc__)
        return 2

    raw = sys.stdin.read()
    try:
        data = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        print("[finance-gate] warning: could not parse hook input; deferring to permissions.", file=sys.stderr)
        return 0
    root = project_dir(data)
    event = data.get("hook_event_name")
    if event == "UserPromptSubmit":
        on_user_prompt(data, root)
    elif event == "SessionStart":
        if data.get("source") in ("startup", "clear"):
            deactivate(root)
    elif event == "PreToolUse":
        on_pre_tool_use(data, root)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
