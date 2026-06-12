"""Run the JavaScript unit tests for the IDE autocomplete core.

The autocomplete logic lives in ``static/opc-hint.js`` and is exercised by
``tests/test_hint_core.js`` under Node's built-in test runner.  This wrapper
invokes ``node --test`` on that file from within pytest so a single
``pytest`` run covers both the Python and JavaScript sides of the project.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HINT_TEST = PROJECT_ROOT / "tests" / "test_hint_core.js"


pytestmark = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="node is required to run the IDE autocomplete JS tests",
)


def test_node_autocomplete_core():
    """`node --test` exits non-zero on any failing subtest."""
    proc = subprocess.run(
        ["node", "--test", str(HINT_TEST)],
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=60,
    )
    assert proc.returncode == 0, (
        "JS autocomplete tests failed.\n"
        f"--- stdout ---\n{proc.stdout}\n"
        f"--- stderr ---\n{proc.stderr}"
    )
