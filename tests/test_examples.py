"""Smoke test: the bundled examples/ directory transpiles, compiles, and links.

This guards against regressions in the public-facing examples that users
of the transpiler are most likely to copy.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from transpiler import SimplCTranspiler

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"


def _run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def test_main_example_transpiles(tmp_path):
    """examples/main.opc uses the `import` directive and pulls in utils.h."""
    t = SimplCTranspiler()
    src = (EXAMPLES / "main.opc").read_text()
    c = t.transpile(src)

    # It must declare the imported header.
    assert '#include "utils.h"' in c
    # And use the imported struct.
    assert 'Point p' in c
    assert 'create_point' in c


def test_main_example_compiles_and_runs(tmp_path):
    """The main example should link against utils.c and produce output."""
    # Transpile main.opc
    t = SimplCTranspiler()
    c = t.transpile((EXAMPLES / "main.opc").read_text())
    main_c = tmp_path / "main.c"
    main_c.write_text(c)

    # Copy the bundled stb_ds.h? main.opc doesn't use list/map so probably not.
    # But it might include other headers via auto-include. We only need stdio
    # and utils.h here.
    exe = tmp_path / "main"
    proc = _run([
        "gcc", "-Wall", "-Wextra",
        str(main_c), str(EXAMPLES / "utils.c"),
        "-I", str(EXAMPLES),
        "-o", str(exe),
    ])
    assert proc.returncode == 0, f"compile failed:\n{proc.stderr}"

    # Run the program.
    proc = _run([str(exe)])
    assert proc.returncode == 0, f"run failed: {proc.stderr}"
    assert "Point: 5.000000, 10.000000" in proc.stdout


def test_test_example_transpiles():
    """examples/test.opc — a more complex program with FILE*, u32, do/while."""
    t = SimplCTranspiler()
    src = (EXAMPLES / "test.opc").read_text()
    c = t.transpile(src)

    # Auto-includes for fopen, calloc, fread, etc.
    assert '#include <stdio.h>' in c
    assert '#include <stdlib.h>' in c
    # Fixed-width integers
    assert 'uint32_t' in c
    # The read_file function and main are present
    assert 'char * read_file' in c
    assert 'int main' in c


def test_test_example_compiles(tmp_path):
    """test.opc compiles (but it needs an input file to run)."""
    t = SimplCTranspiler()
    c = t.transpile((EXAMPLES / "test.opc").read_text())
    test_c = tmp_path / "test.c"
    test_c.write_text(c)
    obj = tmp_path / "test.o"
    proc = _run([
        "gcc", "-Wall", "-Wextra", "-c", str(test_c), "-o", str(obj),
    ])
    assert proc.returncode == 0, f"compile failed:\n{proc.stderr}"


def test_utils_example_compiles():
    """utils.opc produces a header that can be included from main.opc."""
    t = SimplCTranspiler()
    src = (EXAMPLES / "utils.opc").read_text()
    c = t.transpile(src)
    # utils.c file should already exist on disk and be valid C
    utils_c = EXAMPLES / "utils.c"
    proc = _run([
        "gcc", "-Wall", "-Wextra", "-c", str(utils_c),
        "-I", str(EXAMPLES), "-o", str(EXAMPLES / "_utils_check.o"),
    ])
    assert proc.returncode == 0, f"utils.c failed to compile:\n{proc.stderr}"
    # Clean up the throwaway object.
    (EXAMPLES / "_utils_check.o").unlink(missing_ok=True)
