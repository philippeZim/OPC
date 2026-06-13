"""§20 Simplified malloc — element-size inference, NULL guards, leak lint.

`arr: int* = malloc(10)` allocates room for 10 *ints* (not 10 bytes); the
transpiler multiplies by `sizeof(elem)`, inserts an out-of-memory guard, and
keeps a best-effort tally of resources that are never freed.
"""
from transpiler import SimplCTranspiler
from tests.conftest import assert_runs, assert_transpiles_to


def test_malloc_infers_element_size(transpile):
    c = transpile('fn main() -> int:\n    a: int* = malloc(10)\n    free(a)\n    return 0\n')
    assert_transpiles_to(c, ['int * a = malloc((10) * sizeof(int));'])


def test_malloc_adds_null_guard(transpile):
    c = transpile('fn main() -> int:\n    a: int* = malloc(10)\n    free(a)\n    return 0\n')
    assert_transpiles_to(c, ['if (a == NULL) exit('])


def test_calloc_infers_element_size(transpile):
    c = transpile('fn main() -> int:\n    a: double* = calloc(5)\n    free(a)\n    return 0\n')
    assert_transpiles_to(c, ['double * a = calloc(5, sizeof(double));'])


def test_explicit_sizeof_is_left_untouched(transpile):
    # Already-explicit allocations keep their original form (no double sizeof).
    c = transpile('fn main() -> int:\n    a: int* = malloc(10 * sizeof(int))\n    free(a)\n    return 0\n')
    assert 'malloc(10 * sizeof(int))' in c
    assert 'sizeof(int)) * sizeof' not in c


def test_two_arg_malloc_form_untouched(transpile):
    # A (count, size)-style calloc the user wrote by hand is preserved.
    c = transpile('fn main() -> int:\n    a: int* = calloc(4, 8)\n    free(a)\n    return 0\n')
    assert 'calloc(4, 8)' in c


def test_pointer_element_size(transpile):
    c = transpile('fn main() -> int:\n    a: char** = malloc(3)\n    free(a)\n    return 0\n')
    assert_transpiles_to(c, ['malloc((3) * sizeof(char *));'])


# ── leak tracker ─────────────────────────────────────────────────────


def test_leak_tracker_flags_unfreed_malloc():
    t = SimplCTranspiler()
    t.transpile('fn main() -> int:\n    a: int* = malloc(10)\n    return 0\n')
    assert any("'a'" in w and 'malloc' in w for w in t.leak_warnings)


def test_leak_tracker_silent_when_freed():
    t = SimplCTranspiler()
    t.transpile('fn main() -> int:\n    a: int* = malloc(10)\n    free(a)\n    return 0\n')
    assert t.leak_warnings == []


def test_leak_tracker_flags_unfreed_list():
    t = SimplCTranspiler()
    t.transpile('fn main() -> int:\n    a: list[int] = []\n    return 0\n')
    assert any("'a'" in w and 'list' in w for w in t.leak_warnings)


def test_leak_tracker_ignores_returned_resource():
    # Returning a resource transfers ownership — not a leak.
    t = SimplCTranspiler()
    t.transpile('fn make() -> int*:\n    a: int* = malloc(10)\n    return a\n')
    assert t.leak_warnings == []


def test_leak_tracker_flags_unclosed_file():
    t = SimplCTranspiler()
    t.transpile('fn main() -> int:\n    f: file = read_file("x")\n    return 0\n')
    assert any("'f'" in w and 'file' in w for w in t.leak_warnings)


MALLOC_PROGRAM = """\
fn main() -> int:
    arr: int* = malloc(10)
    for i in range(10):
        arr[i] = i * i
    printf("%d %d\\n", arr[3], arr[9])
    free(arr)
    return 0
"""


def test_malloc_program_runs(run_simplc):
    assert_runs(run_simplc(MALLOC_PROGRAM), "9 81\n")
