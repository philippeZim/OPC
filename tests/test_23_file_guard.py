"""§22 Automatic file-read error checking (issue #29).

Reading a file can fail; SimplC now inserts the `if !f.ok` / NULL check into
the generated C automatically, so a failed `read_file` / `read_lines` aborts
loudly instead of being used uninitialised.
"""
from tests.conftest import assert_runs, assert_transpiles_to


def test_read_file_gets_ok_guard(transpile):
    c = transpile('fn main() -> int:\n    f: file = read_file("x")\n    return 0\n')
    assert_transpiles_to(c, [
        'OpcFile f = opc_read_file("x", "auto");',
        'if (!f.ok) exit(',
    ])


def test_read_file_with_strategy_gets_guard(transpile):
    c = transpile('fn main() -> int:\n    f: file = read_file("x", "mmap")\n    return 0\n')
    assert_transpiles_to(c, ['if (!f.ok) exit('])


def test_read_lines_gets_null_guard(transpile):
    c = transpile(
        'fn main() -> int:\n'
        '    lines: list[char*] = read_lines("notes.txt")\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, [
        'char **lines = opc_read_lines("notes.txt");',
        'if (lines == NULL) exit(',
    ])


def test_guard_is_idempotent_on_rewrite(transpile):
    c = transpile('fn main() -> int:\n    f: file = read_file("x")\n    return 0\n')
    assert 'opc_opc_read_file' not in c
    # Exactly one guard for one read.
    assert c.count('if (!f.ok) exit(') == 1


def test_non_io_file_var_has_no_guard(transpile):
    # A bare `file` declaration that isn't a read_file() result must not get a guard.
    c = transpile('fn main() -> int:\n    f: file\n    return 0\n')
    assert 'exit(' not in c


GUARD_SUCCESS_PROGRAM = """\
fn main() -> int:
    fp: FILE* = fopen("opc_guard_ok.txt", "w")
    fprintf(fp, "hello\\n")
    fclose(fp)

    f: file = read_file("opc_guard_ok.txt")
    printf("size=%ld\\n", f.size)
    file_close(f)

    remove("opc_guard_ok.txt")
    return 0
"""


def test_guard_passes_for_existing_file(run_simplc):
    assert_runs(run_simplc(GUARD_SUCCESS_PROGRAM), "size=6\n")


GUARD_FAILURE_PROGRAM = """\
fn main() -> int:
    f: file = read_file("opc_definitely_missing_file.xyz")
    printf("should not reach here\\n")
    return 0
"""


def test_guard_aborts_for_missing_file(run_simplc):
    result = run_simplc(GUARD_FAILURE_PROGRAM)
    assert result.compile.ok, result.compile.stderr
    assert result.returncode != 0
    assert "should not reach here" not in result.stdout
    assert "failed to read file" in result.stderr
