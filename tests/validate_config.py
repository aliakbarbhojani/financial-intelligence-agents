#!/usr/bin/env python3
"""Static validation of agent, skill, settings, template and repository configuration.

Type: static checks (no Claude Code runtime). Uses PyYAML if installed, otherwise a minimal
frontmatter parser sufficient for this repository's files.
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENTS = ROOT / ".claude" / "agents"
EXPECTED = ["financial-orchestrator", "budget-analyst", "financing-advisor", "income-strategist",
            "market-researcher", "market-analyst", "investment-researcher", "market-forecaster",
            "forecast-supervisor", "risk-compliance-analyst", "head-financial-intelligence",
            "chief-financial-authority"]
KNOWN_TOOLS = {"Agent", "Read", "Write", "Edit", "MultiEdit", "Glob", "Grep", "Bash", "WebSearch",
               "WebFetch", "NotebookEdit", "AskUserQuestion", "Skill", "TodoWrite"}
MODELS = {"sonnet", "opus", "haiku", "fable", "inherit"}
KNOWN_AGENT_FIELDS = {"name", "description", "tools", "disallowedTools", "model", "permissionMode",
                      "maxTurns", "autoCompactWindow", "skills", "mcpServers", "hooks", "memory",
                      "background", "omitClaudeMd", "effort", "isolation", "color", "initialPrompt",
                      "experimental"}
KNOWN_SKILL_FIELDS = {"name", "description", "when_to_use", "argument-hint", "arguments",
                      "disable-model-invocation", "user-invocable", "allowed-tools", "disallowed-tools",
                      "model", "effort", "context", "agent", "background", "hooks", "paths", "shell",
                      "metadata", "license", "compatibility"}


def split_frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        raise ValueError("missing YAML frontmatter")
    return m.group(1), m.group(2)


def parse_yaml(src):
    try:
        import yaml  # type: ignore
        return yaml.safe_load(src)
    except ImportError:
        out, key = {}, None
        for line in src.splitlines():
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            if line.startswith("  - ") and key:
                out.setdefault(key, []).append(line[4:].strip())
                continue
            k, _, v = line.partition(":")
            key, v = k.strip(), v.strip()
            out[key] = (True if v == "true" else False if v == "false" else
                        int(v) if v.isdigit() else v.strip('"') if v else [])
        return out


def tool_names(spec):
    if not spec:
        return []
    if isinstance(spec, list):
        items = spec
    else:  # comma-separated, respecting parentheses
        items, depth, cur = [], 0, ""
        for ch in str(spec):
            depth += ch == "("
            depth -= ch == ")"
            if ch == "," and depth == 0:
                items.append(cur)
                cur = ""
            else:
                cur += ch
        items.append(cur)
    return [re.sub(r"\(.*\)$", "", i.strip()) for i in items if i.strip()]


def load_agent(name):
    fm, body = split_frontmatter((AGENTS / f"{name}.md").read_text(encoding="utf-8"))
    return parse_yaml(fm), body


class Agents(unittest.TestCase):
    def test_V01_exactly_twelve_expected_agents(self):
        found = sorted(p.stem for p in AGENTS.glob("*.md"))
        self.assertEqual(found, sorted(EXPECTED))

    def test_V02_frontmatter_valid_and_names_match(self):
        for n in EXPECTED:
            fm, body = load_agent(n)
            self.assertEqual(fm.get("name"), n)
            self.assertRegex(n, r"^[a-z][a-z0-9-]*$")
            self.assertTrue(fm.get("description"), n)
            self.assertGreater(len(body.strip()), 800, f"{n}: system prompt too thin")
            unknown = set(fm) - KNOWN_AGENT_FIELDS
            self.assertFalse(unknown, f"{n}: unrecognised fields (silently ignored by Claude Code): {unknown}")

    def test_V03_descriptions_declare_manual_use(self):
        for n in EXPECTED:
            self.assertIn("Manual use only", load_agent(n)[0]["description"], n)

    def test_V04_models_valid(self):
        for n in EXPECTED:
            m = load_agent(n)[0].get("model", "inherit")
            self.assertTrue(m in MODELS or str(m).startswith("claude-"), f"{n}: {m}")

    def test_V05_tools_known_and_least_privilege(self):
        for n in EXPECTED:
            fm, _ = load_agent(n)
            tools = tool_names(fm.get("tools"))
            self.assertTrue(tools, f"{n}: tools must be explicit (least privilege)")
            for t in tools + tool_names(fm.get("disallowedTools")):
                self.assertIn(t, KNOWN_TOOLS, f"{n}: unknown tool {t}")

    def test_V06_only_orchestrator_can_delegate(self):
        for n in EXPECTED:
            fm, _ = load_agent(n)
            tools = tool_names(fm.get("tools"))
            if n == "financial-orchestrator":
                self.assertIn("Agent", tools)
                allow = re.search(r"Agent\((.*?)\)", str(fm["tools"])).group(1)
                self.assertEqual(sorted(a.strip() for a in allow.split(",")), sorted(EXPECTED[1:]))
            else:
                self.assertNotIn("Agent", tools, n)
                self.assertIn("Agent", tool_names(fm.get("disallowedTools")), n)

    def test_V07_no_web_for_offline_roles(self):
        for n in ("budget-analyst", "chief-financial-authority"):
            tools = tool_names(load_agent(n)[0]["tools"])
            self.assertNotIn("WebSearch", tools); self.assertNotIn("WebFetch", tools)

    def test_V08_write_only_where_needed(self):
        writers = {n for n in EXPECTED if "Write" in tool_names(load_agent(n)[0]["tools"])}
        self.assertEqual(writers, {"financial-orchestrator", "market-forecaster", "head-financial-intelligence"})

    def test_V09_shared_standards_preloaded_and_turns_bounded(self):
        for n in EXPECTED:
            fm, _ = load_agent(n)
            self.assertIn("finance-standards", fm.get("skills") or [], n)
            if n != "financial-orchestrator":
                self.assertTrue(1 <= int(fm.get("maxTurns", 0)) <= 50, n)

    def test_V10_required_sections_present(self):
        checks = {
            "investment-researcher": ["Investment thesis", "Counterarguments", "Bull / base / bear",
                                      "invalidation", "time horizon", "Risk-adjusted"],
            "market-forecaster": ["Forecast creation date", "Forecast time horizon", "Key assumptions",
                                  "Bullish scenario", "Base-case scenario", "Bearish scenario",
                                  "Confidence assessment", "invalidate the forecast", "scheduled"],
            "forecast-supervisor": ["APPROVED WITH CONDITIONS", "REVISION REQUIRED", "INSUFFICIENT EVIDENCE",
                                    "REJECTED", "look-ahead", "survivorship", "overfitting", "leakage"],
            "chief-financial-authority": ["AUTHORIZED WITH LIMITATIONS", "never authorise"],
            "head-financial-intelligence": ["majority vote", "error-log", "ADDITIONAL RESEARCH REQUIRED"],
            "risk-compliance-analyst": ["BLOCK", "Stress test", "Suitability", "never** claim"],
            "market-researcher": ["Pass 1", "Pass 2", "Pass 3"],
            "income-strategist": ["Initial investment", "Time to first revenue", "Legal & geographic"],
        }
        for n, needles in checks.items():
            body = load_agent(n)[1]
            for s in needles:
                self.assertIn(s.lower(), body.lower(), f"{n}: missing '{s}'")


class Skills(unittest.TestCase):
    def skill(self, name):
        fm, body = split_frontmatter((ROOT / ".claude/skills" / name / "SKILL.md").read_text(encoding="utf-8"))
        return parse_yaml(fm), body

    def test_V20_finance_entry_is_manual_only(self):
        fm, body = self.skill("finance")
        self.assertIs(fm.get("disable-model-invocation"), True)
        self.assertIn("$ARGUMENTS", body)
        self.assertFalse(set(fm) - KNOWN_SKILL_FIELDS)

    def test_V21_entry_skill_cannot_activate_gate(self):
        fm, _ = self.skill("finance")
        allowed = str(fm.get("allowed-tools"))
        self.assertNotIn("finance_gate.py *", allowed)
        self.assertNotIn("activate)", allowed.replace("deactivate)", ""))

    def test_V22_standards_preloadable(self):
        fm, body = self.skill("finance-standards")
        self.assertNotEqual(fm.get("disable-model-invocation"), True,
                            "skills with disable-model-invocation cannot be preloaded into subagents")
        self.assertIs(fm.get("user-invocable"), False)
        for s in ("[FACT]", "Tier 1", "untrusted data", "### HANDOFF", "fincalc"):
            self.assertIn(s, body)


class SettingsAndFiles(unittest.TestCase):
    def test_V30_settings_json_valid_and_hooks_wired(self):
        s = json.loads((ROOT / ".claude/settings.json").read_text())
        for ev in ("UserPromptSubmit", "SessionStart", "PreToolUse"):
            self.assertIn(ev, s["hooks"])
            cmd = s["hooks"][ev][0]["hooks"][0]["command"]
            self.assertIn(".claude/hooks/finance_gate.py", cmd)
        m = s["hooks"]["PreToolUse"][0]["matcher"].split("|")
        for t in ("Agent", "Bash", "Write", "Edit", "WebFetch"):
            self.assertIn(t, m)
        self.assertTrue((ROOT / ".claude/hooks/finance_gate.py").exists())
        allow = " ".join(s["permissions"]["allow"])
        self.assertNotIn("finance_gate.py *", allow)
        # Claude Code 2.1.331 warns that Write(path) rules are never matched; Edit(path) covers all
        # file-editing tools (found in runtime test R-S1).
        self.assertIn("Edit(./.claude/**)", s["permissions"]["ask"])
        for rule in s["permissions"]["ask"] + s["permissions"]["deny"]:
            self.assertFalse(rule.startswith("Write("), f"ineffective rule: {rule}")

    def test_V31_json_files_parse(self):
        for p in ("config/modes.json", "config/mcp.example.json", "templates/handoff.schema.json"):
            json.loads((ROOT / p).read_text())
        modes = json.loads((ROOT / "config/modes.json").read_text())["modes"]
        self.assertEqual(set(modes), {"quick", "standard", "deep"})
        self.assertTrue(modes["deep"]["requires_explicit_user_opt_in"])

    def test_V32_required_repository_files(self):
        for p in ("README.md", "ROADMAP.md", "CHANGELOG.md", "LICENSE", "CLAUDE.md", ".gitignore",
                  "docs/ARCHITECTURE.md", "docs/WORKFLOWS.md", "docs/AGENT_ROLES.md", "docs/SECURITY.md",
                  "docs/USAGE.md", "memory/README.md", "templates/final-report.md", "templates/handoff.md",
                  "templates/forecast-journal-entry.md", "templates/error-log-entry.md", "tools/fincalc.py"):
            self.assertTrue((ROOT / p).exists(), p)

    def test_V33_no_hardcoded_personal_data(self):
        email = re.compile(r"[A-Za-z0-9._%+-]+@(?!example\.|anthropic\.com)[A-Za-z0-9.-]+\.[a-z]{2,}")
        phone = re.compile(r"\+?\d{1,2}[\s.-]?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}")
        homedir = re.compile(r"(/home/(?!claude/|user/)[a-z]+|/Users/[A-Za-z]+|C:\\\\Users\\\\)")
        for p in ROOT.rglob("*"):
            if p.is_file() and p.suffix in {".md", ".json", ".py", ".txt"} and ".git" not in p.parts \
                    and "results" not in p.parts:
                t = p.read_text(encoding="utf-8", errors="ignore")
                for rx in (email, phone, homedir):
                    self.assertIsNone(rx.search(t), f"{p.relative_to(ROOT)}: {rx.pattern}")

    @unittest.skipUnless(shutil.which("git"), "git not installed")
    def test_V34_gitignore_protects_private_data(self):
        import tempfile
        tmp = tempfile.mkdtemp(prefix="fin-gi-")       # throwaway repo: no side effects on ROOT
        shutil.copy(ROOT / ".gitignore", Path(tmp) / ".gitignore")
        subprocess.run(["git", "-C", tmp, "init", "-q"], check=True)

        def ignored(path):
            r = subprocess.run(["git", "-C", tmp, "check-ignore", "--no-index", "-q", path])
            return r.returncode == 0
        for p in ("memory/private/preferences.md", "memory/error-log/EL-1.md", "memory/forecast-journal/FJ-1.md",
                  "memory/forecast-journal/outcomes/OUT-1.md", "memory/research-cache/x.md",
                  "reports/r.md", ".claude/state/finance-session.json", ".env", ".mcp.json",
                  ".claude/settings.local.json"):
            self.assertTrue(ignored(p), f"should be ignored: {p}")
        for p in ("memory/knowledge/lessons.md", "memory/README.md", "memory/private/.gitkeep",
                  ".claude/agents/budget-analyst.md", ".claude/settings.json", "config/mcp.example.json"):
            self.assertFalse(ignored(p), f"should be tracked: {p}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
