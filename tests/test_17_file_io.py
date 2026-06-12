"""§18 File Reading — read_file / read_lines and the strategy hints."""
from tests.conftest import assert_runs, assert_transpiles_to


def test_read_file_default_strategy(transpile):
    c = transpile('fn main() -> int:\n    f: file = read_file("data.bin")\n    return 0\n')
    assert_transpiles_to(c, [
        '#include "opc_io.h"',
        'OpcFile f = opc_read_file("data.bin", "auto");',
    ])


def test_read_file_explicit_strategy(transpile):
    c = transpile('fn main() -> int:\n    f: file = read_file("data.bin", "mmap")\n    return 0\n')
    assert_transpiles_to(c, [
        'opc_read_file("data.bin", "mmap");',
    ])


def test_read_lines_and_files_pull_in_stb_ds(transpile):
    c = transpile(
        'fn main() -> int:\n'
        '    lines: list[char*] = read_lines("notes.txt")\n'
        '    free_lines(lines)\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, [
        '#include "stb_ds.h"',
        '#include "opc_io.h"',
        'char **lines = opc_read_lines("notes.txt");',
        'opc_free_lines(lines);',
    ])


def test_file_close_rewrite(transpile):
    c = transpile('fn main() -> int:\n    f: file = read_file("x")\n    file_close(f)\n    return 0\n')
    assert_transpiles_to(c, ['opc_file_close(f);'])


def test_already_rewritten_is_idempotent(transpile):
    # `opc_read_file` must not be rewritten again into `opc_opc_read_file`.
    c = transpile('fn main() -> int:\n    f: file = read_file("x")\n    return 0\n')
    assert 'opc_opc_read_file' not in c


# ── end-to-end: write a file, then read it back three ways ───────────────

WHOLE_FILE = """\
fn main() -> int:
    fp: FILE* = fopen("opc_io_smoke.txt", "w")
    fprintf(fp, "line one\\nline two\\nline three\\n")
    fclose(fp)

    f: file = read_file("opc_io_smoke.txt")
    printf("ok=%d size=%ld\\n", f.ok, f.size)
    printf("%s", f.data)
    file_close(f)

    m: file = read_file("opc_io_smoke.txt", "mmap")
    printf("mmap_size=%ld\\n", m.size)
    file_close(m)

    remove("opc_io_smoke.txt")
    return 0
"""


def test_read_file_runs(run_simplc):
    result = run_simplc(WHOLE_FILE)
    assert_runs(
        result,
        "ok=1 size=29\n"
        "line one\nline two\nline three\n"
        "mmap_size=29\n",
    )


READ_LINES = """\
fn main() -> int:
    fp: FILE* = fopen("opc_io_lines.txt", "w")
    fprintf(fp, "alpha\\nbeta\\ngamma\\n")
    fclose(fp)

    lines: list[char*] = read_lines("opc_io_lines.txt")
    printf("count=%ld\\n", len(lines))
    for i in range(len(lines)):
        printf("[%s]\\n", lines[i])
    free_lines(lines)

    remove("opc_io_lines.txt")
    return 0
"""


def test_read_lines_runs(run_simplc):
    result = run_simplc(READ_LINES)
    assert_runs(
        result,
        "count=3\n[alpha]\n[beta]\n[gamma]\n",
    )


READ_FILES = """\
fn main() -> int:
    fp: FILE* = fopen("opc_a.txt", "w")
    fprintf(fp, "aaa")
    fclose(fp)
    fp = fopen("opc_b.txt", "w")
    fprintf(fp, "bbbb")
    fclose(fp)

    paths: list[char*] = ["opc_a.txt", "opc_b.txt"]
    files: list[file] = read_files(paths)
    for i in range(len(files)):
        printf("%ld:%s\\n", files[i].size, files[i].data)
        file_close(files[i])
    paths.free()
    files.free()

    remove("opc_a.txt")
    remove("opc_b.txt")
    return 0
"""


def test_read_files_runs(run_simplc):
    result = run_simplc(READ_FILES)
    assert_runs(result, "3:aaa\n4:bbbb\n")
