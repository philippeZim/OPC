"""§16 Edge cases — tests that probe boundary conditions and known-fragile areas.

Each test group targets a specific potential failure mode. Tests that expose
confirmed bugs are marked with a comment so they double as regression tests
once the bug is fixed.
"""
import pytest

from tests.conftest import assert_runs, assert_transpiles_to


# ── §16.1 return with compound literal (no = sign) ─────────────────
# BUG: _semi checks `'=' in s and s.endswith('}')` to decide whether to
# add a semicolon to a struct-init line. A positional compound literal
# return like `return (Vec2){a, b}` has no `=` sign but still needs `;`.

RETURN_COMPOUND_LITERAL_SOURCE = """\
struct Vec2:
    x: double,
    y: double

fn make_vec(a: double, b: double) -> Vec2:
    return (Vec2){a, b}

fn main() -> int:
    v: Vec2 = make_vec(3.0, 4.0)
    printf("%.1f %.1f\\n", v.x, v.y)
    return 0
"""


def test_return_compound_literal_has_semicolon(transpile):
    """return (T){...} must end with ; even though it has no = sign."""
    c = transpile(RETURN_COMPOUND_LITERAL_SOURCE)
    assert "return (Vec2){a, b};" in c, (
        "Missing semicolon on compound-literal return.\n"
        f"Actual output:\n{c}"
    )


def test_return_compound_literal_compiles(run_simplc):
    result = run_simplc(RETURN_COMPOUND_LITERAL_SOURCE)
    assert result.compile.ok, result.compile.stderr


def test_return_compound_literal_runs(run_simplc):
    assert_runs(run_simplc(RETURN_COMPOUND_LITERAL_SOURCE), "3.0 4.0\n")


# ── §16.2 map read-modify-write: RHS m[key] not rewritten ─────────
# BUG: When a line starts with `m[key] = ...`, skip_map_rewrite is set
# to True to prevent the LHS from being wrongly rewritten. However, this
# flag also prevents rewriting map reads on the RHS, so
#   m["x"] = m["x"] + 5
# becomes
#   shput(m, "x", m["x"] + 5)   ← m["x"] on RHS is NOT rewritten
# instead of the correct:
#   shput(m, "x", shget(m, "x") + 5)

MAP_RHS_REWRITE_SOURCE = """\
fn main() -> int:
    m: map[char*, int] = {}
    m["x"] = 10
    m["x"] = m["x"] + 5
    printf("x=%d\\n", m["x"])
    m.free()
    return 0
"""


def test_map_rhs_rewrite_transpile(transpile):
    """m[k] on the RHS of an assignment must be rewritten to shget/hmget."""
    c = transpile(MAP_RHS_REWRITE_SOURCE)
    assert 'shput(m, "x", shget(m, "x") + 5);' in c, (
        f"RHS not rewritten. Actual output:\n{c}"
    )


def test_map_rhs_rewrite_runs(run_simplc):
    """Read-modify-write via m[k] = m[k] + val must work end-to-end."""
    assert_runs(run_simplc(MAP_RHS_REWRITE_SOURCE), "x=15\n")


# ── §16.3 print() with explicit \\n already in string ─────────────
# BUG: print("hello\n") produces printf("hello\n\n") — double newline.
# The `print` shorthand always appends \n; a user who adds their own
# \n gets two.

def test_print_always_appends_newline(transpile):
    """print() always appends \\n, even if the string already ends with \\n."""
    src = 'fn main() -> int:\n    print("line\\n")\n    return 0\n'
    c = transpile(src)
    assert 'printf("line\\n\\n");' in c


# ── §16.4 for-range with negative start value ─────────────────────

NEGATIVE_RANGE_START_SOURCE = """\
fn main() -> int:
    for i in range(-3, 2):
        printf("%d ", i)
    printf("\\n")
    return 0
"""


def test_negative_range_start_transpile(transpile):
    c = transpile(NEGATIVE_RANGE_START_SOURCE)
    assert "for (int i = -3; i < 2; i++)" in c


def test_negative_range_start_runs(run_simplc):
    assert_runs(run_simplc(NEGATIVE_RANGE_START_SOURCE), "-3 -2 -1 0 1 \n")


# ── §16.5 for-range with negative step other than -1 ──────────────

NEGATIVE_STEP_SOURCE = """\
fn main() -> int:
    for i in range(10, 0, -2):
        printf("%d ", i)
    printf("\\n")
    return 0
"""


def test_negative_step_transpile(transpile):
    c = transpile(NEGATIVE_STEP_SOURCE)
    assert "for (int i = 10; i > 0; i -= 2)" in c


def test_negative_step_runs(run_simplc):
    assert_runs(run_simplc(NEGATIVE_STEP_SOURCE), "10 8 6 4 2 \n")


# ── §16.6 break and continue inside loops ─────────────────────────

BREAK_CONTINUE_SOURCE = """\
fn main() -> int:
    total: int = 0
    for i in range(10):
        if i == 7:
            break
        if i % 2 == 0:
            continue
        total += i
    printf("%d\\n", total)
    return 0
"""


def test_break_continue_transpile(transpile):
    c = transpile(BREAK_CONTINUE_SOURCE)
    assert "break;" in c
    assert "continue;" in c


def test_break_continue_runs(run_simplc):
    # Odd values from 1..6 (skipping even, stopping before 7): 1+3+5 = 9
    assert_runs(run_simplc(BREAK_CONTINUE_SOURCE), "9\n")


# ── §16.7 switch without a default case ───────────────────────────

SWITCH_NO_DEFAULT_SOURCE = """\
fn main() -> int:
    x: int = 3
    switch x:
        case 1: printf("one\\n"); break
        case 2: printf("two\\n"); break
        case 3: printf("three\\n"); break
    return 0
"""


def test_switch_no_default_transpile(transpile):
    c = transpile(SWITCH_NO_DEFAULT_SOURCE)
    assert_transpiles_to(c, [
        "switch (x) {",
        'case 1: printf("one\\n"); break;',
        'case 3: printf("three\\n"); break;',
    ])
    assert "default" not in c


def test_switch_no_default_runs(run_simplc):
    assert_runs(run_simplc(SWITCH_NO_DEFAULT_SOURCE), "three\n")


# ── §16.8 four-level elif chain ────────────────────────────────────

MULTI_ELIF_SOURCE = """\
fn grade(score: int) -> char*:
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    elif score >= 60:
        return "D"
    else:
        return "F"

fn main() -> int:
    printf("%s %s %s %s %s\\n",
           grade(95), grade(85), grade(75), grade(65), grade(50))
    return 0
"""


def test_multi_elif_transpile(transpile):
    c = transpile(MULTI_ELIF_SOURCE)
    assert_transpiles_to(c, [
        "if (score >= 90) {",
        "} else if (score >= 80) {",
        "} else if (score >= 70) {",
        "} else if (score >= 60) {",
        "} else {",
    ])


def test_multi_elif_runs(run_simplc):
    assert_runs(run_simplc(MULTI_ELIF_SOURCE), "A B C D F\n")


# ── §16.9 map with struct value type ──────────────────────────────

MAP_STRUCT_VALUE_SOURCE = """\
struct Point:
    x: int,
    y: int

fn main() -> int:
    cache: map[char*, Point] = {}
    cache["origin"] = ((Point){0, 0})
    cache["corner"] = ((Point){10, 20})
    origin: Point = cache["origin"]
    corner: Point = cache["corner"]
    printf("origin=(%d,%d) corner=(%d,%d)\\n",
           origin.x, origin.y, corner.x, corner.y)
    cache.free()
    return 0
"""


def test_map_struct_value_transpile(transpile):
    c = transpile(MAP_STRUCT_VALUE_SOURCE)
    assert_transpiles_to(c, [
        "typedef struct Point {",
        "typedef struct __map_charptr_Point",
        "__map_charptr_Point *cache = NULL;",
        'shput(cache, "origin"',
        'Point origin = shget(cache, "origin");',
    ])


def test_map_struct_value_runs(run_simplc):
    assert_runs(
        run_simplc(MAP_STRUCT_VALUE_SOURCE),
        "origin=(0,0) corner=(10,20)\n",
    )


# ── §16.10 map typedef deduplication ──────────────────────────────
# Two variables with the same map[K, V] types should emit only ONE typedef.

def test_same_map_type_single_typedef(transpile):
    src = """\
fn main() -> int:
    a: map[char*, int] = {}
    b: map[char*, int] = {}
    a["x"] = 1
    b["y"] = 2
    printf("%d %d\\n", a["x"], b["y"])
    a.free()
    b.free()
    return 0
"""
    c = transpile(src)
    count = c.count("typedef struct __map_charptr_int")
    assert count == 1, (
        f"Expected exactly one typedef for __map_charptr_int, got {count}.\n"
        f"Output:\n{c}"
    )


def test_same_map_type_single_typedef_runs(run_simplc):
    src = """\
fn main() -> int:
    a: map[char*, int] = {}
    b: map[char*, int] = {}
    a["x"] = 1
    b["y"] = 2
    printf("%d %d\\n", a["x"], b["y"])
    a.free()
    b.free()
    return 0
"""
    assert_runs(run_simplc(src), "1 2\n")


# ── §16.11 list as function return type ───────────────────────────

LIST_RETURN_TYPE_SOURCE = """\
fn make_evens(n: int) -> list[int]:
    result: list[int] = []
    for i in range(n):
        if i % 2 == 0:
            result.append(i)
    return result

fn main() -> int:
    evens: list[int] = make_evens(8)
    for i in range(len(evens)):
        printf("%d ", evens[i])
    printf("\\n")
    evens.free()
    return 0
"""


def test_list_return_type_transpile(transpile):
    c = transpile(LIST_RETURN_TYPE_SOURCE)
    assert "int * make_evens(int n) {" in c
    assert "int *result = NULL;" in c
    assert "int *evens = make_evens(8);" in c


def test_list_return_type_runs(run_simplc):
    assert_runs(run_simplc(LIST_RETURN_TYPE_SOURCE), "0 2 4 6 \n")


# ── §16.12 len() in arithmetic expressions ────────────────────────

def test_len_in_arithmetic(transpile):
    src = """\
fn main() -> int:
    nums: list[int] = []
    nums.append(1)
    nums.append(2)
    nums.append(3)
    x: int = len(nums) * 2
    y: int = len(nums) + 1
    printf("%d %d\\n", x, y)
    nums.free()
    return 0
"""
    c = transpile(src)
    assert "arrlen(nums) * 2" in c
    assert "arrlen(nums) + 1" in c


def test_len_in_arithmetic_runs(run_simplc):
    src = """\
fn main() -> int:
    nums: list[int] = []
    nums.append(1)
    nums.append(2)
    nums.append(3)
    x: int = len(nums) * 2
    y: int = len(nums) + 1
    printf("%d %d\\n", x, y)
    nums.free()
    return 0
"""
    assert_runs(run_simplc(src), "6 4\n")


# ── §16.13 import statement ────────────────────────────────────────

def test_import_transpile(transpile):
    src = "import mylib\nfn main() -> int:\n    return 0\n"
    c = transpile(src)
    assert '#include "mylib.h"' in c


# ── §16.14 list parameter in function uses len() and methods ──────

LIST_PARAM_OPS_SOURCE = """\
fn sum_list(nums: list[int], n: int) -> int:
    total: int = 0
    for i in range(n):
        total += nums[i]
    return total

fn main() -> int:
    data: list[int] = []
    data.append(10)
    data.append(20)
    data.append(30)
    printf("%d\\n", sum_list(data, len(data)))
    data.free()
    return 0
"""


def test_list_param_ops_transpile(transpile):
    c = transpile(LIST_PARAM_OPS_SOURCE)
    assert "int sum_list(int * nums, int n) {" in c


def test_list_param_ops_runs(run_simplc):
    assert_runs(run_simplc(LIST_PARAM_OPS_SOURCE), "60\n")


# ── §16.15 nested blocks close correctly at end of file ───────────

def test_nested_block_close_at_eof(transpile):
    """Blocks opened by the last function must still be closed."""
    src = """\
fn double_if(x: int) -> int:
    if x > 0:
        return x * 2
    return 0
"""
    c = transpile(src)
    assert c.count("{") == c.count("}"), (
        f"Unbalanced braces in:\n{c}"
    )


# ── §16.16 uninitialized list variable ────────────────────────────

def test_list_no_initializer_transpile(transpile):
    """list[T] with no = value should produce an uninitialized pointer declaration."""
    src = "fn main() -> int:\n    nums: list[int]\n    return 0\n"
    c = transpile(src)
    assert "int *nums;" in c


# ── §16.17 map key lookup inside if condition ─────────────────────

MAP_CONDITION_SOURCE = """\
fn main() -> int:
    scores: map[char*, int] = {}
    scores["alice"] = 95
    if scores["alice"] > 90:
        printf("excellent\\n")
    else:
        printf("ok\\n")
    scores.free()
    return 0
"""


def test_map_key_in_condition_transpile(transpile):
    c = transpile(MAP_CONDITION_SOURCE)
    assert 'shget(scores, "alice") > 90' in c


def test_map_key_in_condition_runs(run_simplc):
    assert_runs(run_simplc(MAP_CONDITION_SOURCE), "excellent\n")


# ── §16.18 for-range with variable bounds ─────────────────────────

VARIABLE_BOUNDS_SOURCE = """\
fn main() -> int:
    start: int = 2
    end: int = 6
    step: int = 2
    for i in range(start, end, step):
        printf("%d ", i)
    printf("\\n")
    return 0
"""


def test_variable_range_bounds_transpile(transpile):
    c = transpile(VARIABLE_BOUNDS_SOURCE)
    assert "for (int i = start; i < end; i += step)" in c


def test_variable_range_bounds_runs(run_simplc):
    assert_runs(run_simplc(VARIABLE_BOUNDS_SOURCE), "2 4 \n")


# ── §16.19 struct with fixed-size array field ──────────────────────

STRUCT_ARRAY_FIELD_SOURCE = """\
struct Matrix:
    data: int[4],
    rows: int,
    cols: int

fn main() -> int:
    m: Matrix
    m.data[0] = 1
    m.data[1] = 2
    m.data[2] = 3
    m.data[3] = 4
    m.rows = 2
    m.cols = 2
    printf("%d %d\\n", m.data[0], m.data[3])
    return 0
"""


def test_struct_array_field_transpile(transpile):
    c = transpile(STRUCT_ARRAY_FIELD_SOURCE)
    assert_transpiles_to(c, [
        "typedef struct Matrix {",
        "int data[4];",
        "int rows;",
        "int cols;",
        "} Matrix;",
    ])


def test_struct_array_field_runs(run_simplc):
    assert_runs(run_simplc(STRUCT_ARRAY_FIELD_SOURCE), "1 4\n")


# ── §16.20 integer map key lookup in expressions ──────────────────

INT_MAP_EXPR_SOURCE = """\
fn main() -> int:
    table: map[int, int] = {}
    table[1] = 100
    table[2] = 200
    total: int = table[1] + table[2]
    printf("%d\\n", total)
    table.free()
    return 0
"""


def test_int_map_key_in_expr_transpile(transpile):
    c = transpile(INT_MAP_EXPR_SOURCE)
    assert "hmget(table, 1) + hmget(table, 2)" in c


def test_int_map_key_in_expr_runs(run_simplc):
    assert_runs(run_simplc(INT_MAP_EXPR_SOURCE), "300\n")
