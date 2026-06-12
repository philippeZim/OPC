"""§2 Variables & Types — basic types, fixed-width integers, and booleans."""
from tests.conftest import assert_runs, assert_transpiles_to


# ── §2 basic types ──────────────────────────────────────────────────


BASIC_TYPES_SOURCE = """\
fn main() -> int:
    x: int = 42
    pi: double = 3.14159
    ch: char = 'A'
    name: char* = "Alice"

    ptr: int* = &x
    dptr: char** = &name

    nums: int[10]
    matrix: double[3][3]

    count: int

    return 0
"""


def test_basic_types_transpile(transpile):
    c = transpile(BASIC_TYPES_SOURCE)
    assert_transpiles_to(c, [
        'int x = 42;',
        'double pi = 3.14159;',
        "char ch = 'A';",
        'char * name = "Alice";',
        'int * ptr = &x;',
        'char ** dptr = &name;',
        'int nums[10];',
        'double matrix[3][3];',
        'int count;',
    ])


def test_basic_types_compile(run_simplc):
    # Just compile-check; no output.
    result = run_simplc(BASIC_TYPES_SOURCE)
    assert result.compile.ok, result.compile.stderr


# ── §2.1 fixed-width integer types ──────────────────────────────────


FIXED_WIDTH_SOURCE = """\
fn main() -> int:
    small: i8 = -128
    byte: u8 = 255
    id: i32 = 100000
    big: u64 = 18446744073709551615
    return 0
"""


def test_fixed_width_types_transpile(transpile):
    c = transpile(FIXED_WIDTH_SOURCE)
    assert_transpiles_to(c, [
        '#include <stdint.h>',
        'int8_t small = -128;',
        'uint8_t byte = 255;',
        'int32_t id = 100000;',
        'uint64_t big = 18446744073709551615;',
    ])


def test_fixed_width_aliases(transpiler):
    """All aliases from the table in reference.md map correctly."""
    for src, expected in [
        ("a: i8 = 0", "int8_t a = 0"),
        ("a: i16 = 0", "int16_t a = 0"),
        ("a: i32 = 0", "int32_t a = 0"),
        ("a: i64 = 0", "int64_t a = 0"),
        ("a: u8 = 0", "uint8_t a = 0"),
        ("a: u16 = 0", "uint16_t a = 0"),
        ("a: u32 = 0", "uint32_t a = 0"),
        ("a: u64 = 0", "uint64_t a = 0"),
    ]:
        c = transpiler.transpile(f"fn main() -> int:\n    {src}\n    return 0\n")
        assert expected in c, f"Expected {expected!r} in output for source {src!r}, got:\n{c}"


def test_fixed_width_types_compile(run_simplc):
    result = run_simplc(FIXED_WIDTH_SOURCE)
    assert result.compile.ok, result.compile.stderr


# ── §2.2 booleans ───────────────────────────────────────────────────


BOOLEAN_SOURCE = """\
fn main() -> int:
    flag: bool = true
    done: bool = false
    return 0
"""


def test_booleans_transpile(transpile):
    c = transpile(BOOLEAN_SOURCE)
    assert_transpiles_to(c, [
        '#include <stdbool.h>',
        'bool flag = true;',
        'bool done = false;',
    ])


def test_booleans_compile(run_simplc):
    result = run_simplc(BOOLEAN_SOURCE)
    assert result.compile.ok, result.compile.stderr
