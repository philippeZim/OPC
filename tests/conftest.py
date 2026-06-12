"""Shared pytest fixtures for the SimplC transpiler test suite.

Each test gets:
  * a fresh `SimplCTranspiler` instance,
  * a `transpile` helper that returns the generated C source,
  * a `compile_c` helper that invokes gcc and returns a result object,
  * a `run_simplc` helper that transpiles + compiles + executes and
    returns the captured stdout/stderr.

Test isolation is handled by pytest's built-in `tmp_path` fixture; every
test that needs a working directory receives its own scratch directory.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from transpiler import SimplCTranspiler  # noqa: E402

STB_DS_HEADER = PROJECT_ROOT / "stb_ds.h"


@dataclass
class CompileResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    exe_path: Path | None


@dataclass
class RunResult:
    ok: bool
    returncode: int
    stdout: str
    stderr: str
    compile: CompileResult


# ── transpilation helpers ────────────────────────────────────────────


@pytest.fixture
def transpiler() -> SimplCTranspiler:
    """A fresh transpiler instance for each test."""
    return SimplCTranspiler()


@pytest.fixture
def transpile(transpiler):
    """Return a callable that runs the SimplC source through the transpiler."""

    def _transpile(source: str) -> str:
        return transpiler.transpile(source)

    return _transpile


# ── compilation & execution helpers ──────────────────────────────────


def _copy_stb_ds(workdir: Path) -> None:
    """Place stb_ds.h next to the .c file so the `#include "stb_ds.h"` resolves."""
    if STB_DS_HEADER.exists():
        shutil.copy(STB_DS_HEADER, workdir / "stb_ds.h")


def _detect_stb_ds(c_source: str) -> bool:
    return "stb_ds.h" in c_source


@pytest.fixture
def compile_c(tmp_path):
    """Compile a C source string with gcc and return a CompileResult.

    `compile_only=True` adds `-c` to skip linking; this is useful for testing
    pure C syntax/semantics of fragments that don't define a `main`.
    """

    def _compile(
        c_source: str,
        *,
        name: str = "test",
        extra_cflags: list[str] | None = None,
        extra_ldflags: list[str] | None = None,
        compile_only: bool = False,
    ) -> CompileResult:
        src_path = tmp_path / f"{name}.c"
        src_path.write_text(c_source)
        obj_path = tmp_path / f"{name}.o"
        exe_path = tmp_path / name
        cmd = ["gcc", "-Wall", "-Wextra", str(src_path)]
        if compile_only:
            cmd.extend(["-c", "-o", str(obj_path)])
        else:
            cmd.extend(["-o", str(exe_path)])
        if extra_cflags:
            cmd[2:2] = extra_cflags
        if extra_ldflags:
            cmd.extend(extra_ldflags)
        if _detect_stb_ds(c_source):
            _copy_stb_ds(tmp_path)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        return CompileResult(
            ok=(proc.returncode == 0),
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            exe_path=exe_path if (proc.returncode == 0 and not compile_only) else None,
        )

    return _compile


@pytest.fixture
def run_simplc(transpile, compile_c, tmp_path):
    """Transpile, compile, and run a SimplC program. Returns a RunResult."""

    def _run(
        source: str,
        *,
        stdin_input: str | None = None,
        extra_cflags: list[str] | None = None,
        extra_ldflags: list[str] | None = None,
    ) -> RunResult:
        c_source = transpile(source)
        # Write the C to disk for easier debugging on failure.
        (tmp_path / "program.c").write_text(c_source)
        compile_result = compile_c(
            c_source,
            name="program",
            extra_cflags=extra_cflags,
            extra_ldflags=extra_ldflags,
        )
        if not compile_result.ok or compile_result.exe_path is None:
            return RunResult(
                ok=False,
                returncode=-1,
                stdout="",
                stderr="",
                compile=compile_result,
            )
        proc = subprocess.run(
            [str(compile_result.exe_path)],
            capture_output=True,
            text=True,
            input=stdin_input,
        )
        return RunResult(
            ok=(proc.returncode == 0),
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
            compile=compile_result,
        )

    return _run


# ── assertion helpers ────────────────────────────────────────────────


def assert_transpiles_to(
    c_source: str,
    expected_substrings: list[str],
) -> None:
    """Assert that every fragment in `expected_substrings` appears in `c_source`.

    Each entry may be either a plain string (tested with `in`) or a tuple
    `(substring, description)` for clearer error messages.
    """
    missing: list[str] = []
    for entry in expected_substrings:
        if isinstance(entry, tuple):
            frag, desc = entry
        else:
            frag, desc = entry, entry
        if frag not in c_source:
            missing.append(desc)
    if missing:
        snippet = "\n".join(missing)
        raise AssertionError(
            f"Transpiler output missing expected fragment(s):\n{snippet}\n\n"
            f"--- actual C source ---\n{c_source}"
        )


def assert_runs(run_result: RunResult, expected_stdout: str) -> None:
    """Assert that the program compiled, ran successfully, and produced `expected_stdout`."""
    if not run_result.compile.ok:
        raise AssertionError(
            "gcc failed to compile transpiled output:\n"
            f"stdout:\n{run_result.compile.stdout}\n"
            f"stderr:\n{run_result.compile.stderr}\n"
        )
    if not run_result.ok:
        raise AssertionError(
            f"Program exited with code {run_result.returncode}\n"
            f"stdout:\n{run_result.stdout}\n"
            f"stderr:\n{run_result.stderr}\n"
        )
    if run_result.stdout != expected_stdout:
        raise AssertionError(
            f"stdout mismatch.\n"
            f"--- expected ---\n{expected_stdout!r}\n"
            f"--- actual ---\n{run_result.stdout!r}\n"
        )
