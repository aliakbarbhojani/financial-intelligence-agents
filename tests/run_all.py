#!/usr/bin/env python3
"""Run every automated (non-runtime) test suite and print a summary.

    python3 tests/run_all.py

Suites: test_fincalc (unit, known answers) · test_finance_gate (hook unit tests)
        · validate_config (static validation).
Runtime tests need an authenticated Claude Code session: see tests/runtime/RUNTIME_TESTS.md.
"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

SUITES = ["test_fincalc", "test_finance_gate", "validate_config"]


def main() -> int:
    total = {"run": 0, "fail": 0, "error": 0, "skip": 0}
    for name in SUITES:
        suite = unittest.defaultTestLoader.loadTestsFromName(name)
        res = unittest.TextTestRunner(verbosity=1, stream=sys.stderr).run(suite)
        total["run"] += res.testsRun
        total["fail"] += len(res.failures)
        total["error"] += len(res.errors)
        total["skip"] += len(res.skipped)
        print(f"{name:20s} run={res.testsRun:3d} failures={len(res.failures)} errors={len(res.errors)} "
              f"skipped={len(res.skipped)}")
    passed = total["run"] - total["fail"] - total["error"] - total["skip"]
    print(f"\nTOTAL run={total['run']} passed={passed} failed={total['fail']} errors={total['error']} "
          f"skipped={total['skip']}")
    return 0 if total["fail"] == total["error"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
