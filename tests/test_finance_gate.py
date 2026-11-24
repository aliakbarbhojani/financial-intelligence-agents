#!/usr/bin/env python3
"""Guardrail tests for .claude/hooks/finance_gate.py.

Type: unit tests driving the real hook script through subprocess with JSON payloads shaped
like Claude Code hook input (event names and fields per code.claude.com/docs/en/hooks).
This verifies the hook's decisions. It does NOT prove Claude Code invokes the hook; see the
runtime tests (tests/runtime/) for that.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK_SRC = ROOT / ".claude" / "hooks" / "finance_gate.py"


class GateTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fin-gate-"))
        (self.tmp / ".claude" / "hooks").mkdir(parents=True)
        (self.tmp / ".claude" / "agents").mkdir()
        (self.tmp / "config").mkdir()
        (self.tmp / "memory" / "forecast-journal").mkdir(parents=True)
        shutil.copy(HOOK_SRC, self.tmp / ".claude" / "hooks" / "finance_gate.py")
        shutil.copy(ROOT / "config" / "blocked-domains.txt", self.tmp / "config" / "blocked-domains.txt")
        self.env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.tmp)}
        self.state = self.tmp / ".claude" / "state" / "finance-session.json"

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers
    def hook(self, payload, raw=None):
        p = subprocess.run([sys.executable, str(self.tmp / ".claude/hooks/finance_gate.py")],
                           input=raw if raw is not None else json.dumps(payload),
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip()

    def decision(self, payload):
        out = self.hook(payload)
        if not out:
            return "none"
        try:
            return json.loads(out)["hookSpecificOutput"]["permissionDecision"]
        except (ValueError, KeyError):
            return "context"

    def prompt(self, text, sid="S1"):
        return self.hook({"hook_event_name": "UserPromptSubmit", "session_id": sid, "prompt": text})

    def tool(self, name, tool_input, agent_type=None, sid="S1"):
        d = {"hook_event_name": "PreToolUse", "session_id": sid, "cwd": str(self.tmp),
             "tool_name": name, "tool_input": tool_input}
        if agent_type:
            d["agent_type"] = agent_type
            d["agent_id"] = "a1"
        return self.decision(d)

    def spawn(self, target, **kw):
        return self.tool("Agent", {"subagent_type": target, "prompt": "x", "description": "x"}, **kw)

    # -- manual activation
    def test_G01_spawn_blocked_without_session(self):
        self.assertEqual(self.spawn("budget-analyst"), "deny")

    def test_G02_non_finance_agents_unaffected(self):
        self.assertEqual(self.spawn("Explore"), "none")
        self.assertEqual(self.spawn("general-purpose"), "none")

    def test_G03_finance_command_opens_session(self):
        self.prompt("/finance quick build me a budget")
        self.assertTrue(self.state.exists())
        self.assertEqual(json.loads(self.state.read_text())["mode"], "quick")
        self.assertEqual(self.spawn("budget-analyst"), "none")

    def test_G04_help_and_status_do_not_open(self):
        for t in ("/finance", "/finance help", "/finance status"):
            self.prompt(t)
            self.assertFalse(self.state.exists(), t)

    def test_G05_stop_closes_session(self):
        self.prompt("/finance compare two loans")
        self.prompt("/finance stop")
        self.assertFalse(self.state.exists())
        self.assertEqual(self.spawn("financing-advisor"), "deny")

    def test_G06_agent_mention_opens_session_only_for_finance_agents(self):
        self.prompt("hey @agent-code-reviewer look at this")
        self.assertFalse(self.state.exists())
        self.prompt('@"market-analyst (agent)" analyse this ticker')
        self.assertTrue(self.state.exists())

    def test_G07_unrelated_prompt_mentioning_finance_does_not_open(self):
        self.prompt("what's a good budget for a birthday party? also finance stuff")
        self.prompt("please use the budget-analyst subagent")   # natural language is NOT activation
        self.assertFalse(self.state.exists())
        self.assertEqual(self.spawn("budget-analyst"), "deny")

    def test_G08_session_id_mismatch_denied(self):
        self.prompt("/finance research inflation", sid="S1")
        self.assertEqual(self.spawn("market-researcher", sid="S2"), "deny")

    def test_G09_expired_session_denied(self):
        self.prompt("/finance research inflation")
        st = json.loads(self.state.read_text())
        st["activated_at"] -= st["ttl_seconds"] + 5
        self.state.write_text(json.dumps(st))
        self.assertEqual(self.spawn("market-researcher"), "deny")

    def test_G10_session_start_clears_on_startup_and_clear_only(self):
        self.prompt("/finance x")
        self.hook({"hook_event_name": "SessionStart", "source": "resume", "session_id": "S1"})
        self.assertTrue(self.state.exists())
        self.hook({"hook_event_name": "SessionStart", "source": "clear", "session_id": "S1"})
        self.assertFalse(self.state.exists())

    def test_G11_nested_delegation_inside_finance_agent_allowed(self):
        self.assertEqual(self.spawn("budget-analyst", agent_type="financial-orchestrator"), "none")

    def test_G12_task_tool_name_also_gated(self):
        self.assertEqual(self.tool("Task", {"subagent_type": "head-financial-intelligence"}), "deny")

    def test_G13_corrupt_state_fails_closed(self):
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text("{corrupt")
        self.assertEqual(self.spawn("budget-analyst"), "deny")

    # -- Bash least privilege
    def test_G20_fincalc_allowed_in_finance_agent(self):
        for cmd in ("python3 tools/fincalc.py loan 200000 6% 30",
                    "python tools/fincalc.py pct 1 2",
                    'python3 "$CLAUDE_PROJECT_DIR"/tools/fincalc.py budget \'{"income":[]}\''):
            self.assertEqual(self.tool("Bash", {"command": cmd}, agent_type="budget-analyst"), "none", cmd)

    def test_G21_other_commands_denied_in_finance_agent(self):
        for cmd in ("curl https://example.com", "rm -rf memory", "python3 -c 'print(1)'",
                    "python3 tools/fincalc.py pct 1 2; rm -rf /",
                    "python3 tools/fincalc.py pct 1 2 | sh",
                    "python3 tools/fincalc.py pct $(cat ~/.ssh/id_rsa) 2",
                    "python3 tools/fincalc.py pct 1 2 > .claude/settings.json",
                    "python3 tools/fincalc.py pct 1 2\nrm x",
                    "python3 .claude/hooks/finance_gate.py deactivate"):
            self.assertEqual(self.tool("Bash", {"command": cmd}, agent_type="market-analyst"), "deny", cmd)

    def test_G22_main_thread_bash_untouched(self):
        self.assertEqual(self.tool("Bash", {"command": "ls -la"}), "none")

    def test_G23_orchestrator_may_close_session(self):
        self.assertEqual(self.tool("Bash", {"command": "python3 .claude/hooks/finance_gate.py deactivate"},
                                   agent_type="financial-orchestrator"), "none")

    def test_G24_no_activate_cli(self):
        p = subprocess.run([sys.executable, str(self.tmp / ".claude/hooks/finance_gate.py"), "activate"],
                           capture_output=True, text=True, env=self.env)
        self.assertEqual(p.returncode, 2)
        self.assertFalse(self.state.exists())

    # -- write restrictions
    def w(self, path, agent="head-financial-intelligence", tool="Write"):
        return self.tool(tool, {"file_path": path, "content": "x"}, agent_type=agent)

    def test_G30_cannot_modify_own_instructions_or_settings(self):
        for p in (".claude/agents/budget-analyst.md", ".claude/settings.json",
                  str(self.tmp / ".claude/hooks/finance_gate.py"), "reports/../.claude/skills/finance/SKILL.md"):
            self.assertEqual(self.w(p), "deny", p)

    def test_G31_private_memory_denied_to_agents(self):
        self.assertEqual(self.w("memory/private/preferences.md", agent="financial-orchestrator"), "deny")

    def test_G32_allowed_locations(self):
        self.assertEqual(self.w("reports/2026-01-01-test.md"), "none")
        self.assertEqual(self.w("memory/research-cache/inflation.md", agent="financial-orchestrator"), "none")
        self.assertEqual(self.w("memory/error-log/EL-20260101-x.md"), "none")

    def test_G33_other_locations_denied(self):
        for p in ("README.md", "tools/fincalc.py", "memory/knowledge/lessons.md", "/tmp/elsewhere.md"):
            self.assertEqual(self.w(p), "deny", p)

    def test_G34_forecast_journal_append_only(self):
        f = "memory/forecast-journal/FJ-20260101-0900-spx.md"
        self.assertEqual(self.w(f, agent="market-forecaster"), "none")
        (self.tmp / f).write_text("original")
        self.assertEqual(self.w(f, agent="market-forecaster"), "deny")                 # overwrite
        self.assertEqual(self.w(f, agent="market-forecaster", tool="Edit"), "deny")    # edit

    def test_G35_main_thread_writes_left_to_permissions(self):
        self.assertEqual(self.tool("Write", {"file_path": "README.md", "content": "x"}), "none")

    # -- web fetch
    def fetch(self, url, agent="market-researcher"):
        return self.tool("WebFetch", {"url": url, "prompt": "x"}, agent_type=agent)

    def test_G40_blocklisted_domains_and_subdomains(self):
        self.assertEqual(self.fetch("https://blocked-example.invalid/offer"), "deny")
        self.assertEqual(self.fetch("https://www.blocked-example.invalid/"), "deny")
        self.assertEqual(self.fetch("https://notblocked-example.invalid/"), "none")

    def test_G41_reputable_source_allowed(self):
        self.assertEqual(self.fetch("https://www.sec.gov/cgi-bin/browse-edgar"), "none")

    def test_G42_dangerous_urls_denied(self):
        for u in ("file:///etc/passwd", "http://127.0.0.1:8080/", "http://localhost/admin",
                  "http://192.168.1.1/", "https://user:pass@example.com/", "ftp://example.com/x"):
            self.assertEqual(self.fetch(u), "deny", u)

    # -- robustness
    def test_G50_malformed_input_defers(self):
        self.assertEqual(self.hook(None, raw="this is not json"), "")

    def test_G51_status_cli(self):
        p = subprocess.run([sys.executable, str(self.tmp / ".claude/hooks/finance_gate.py"), "status"],
                           capture_output=True, text=True, env=self.env)
        self.assertIn("INACTIVE", p.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
