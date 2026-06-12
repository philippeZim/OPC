"""§6 Dynamic Arrays — list[T] backed by stb_ds."""
from tests.conftest import assert_runs, assert_transpiles_to


# ── §6.1 declaration forms ──────────────────────────────────────────


DECL_SOURCE = """\
fn main() -> int:
    nums: list[int] = []
    words: list[char*] = []
    big: list[double] = [1000]
    nums.free()
    words.free()
    big.free()
    return 0
"""


def test_declaration_transpile(transpile):
    c = transpile(DECL_SOURCE)
    assert_transpiles_to(c, [
        '#define STB_DS_IMPLEMENTATION',
        '#include "stb_ds.h"',
        'int *nums = NULL;',
        'char **words = NULL;',
        'double *big = NULL;',
        'arrsetcap(big, 1000);',
    ])


def test_declaration_runs(run_simplc):
    result = run_simplc(DECL_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"


# ── §6.2 operations ────────────────────────────────────────────────


OPERATIONS_SOURCE = """\
fn main() -> int:
    nums: list[int] = []

    nums.append(10)
    nums.append(20)
    nums.append(30)
    nums.append(40)

    printf("length: %ld\\n", len(nums))

    for i in range(len(nums)):
        printf("nums[%d] = %d\\n", i, nums[i])

    last: int = nums.pop()
    printf("popped: %d\\n", last)
    printf("after pop len: %ld\\n", len(nums))

    nums.insert(1, 99)
    printf("after insert len: %ld\\n", len(nums))

    del nums[0]
    printf("after del len: %ld\\n", len(nums))

    nums.free()
    return 0
"""


def test_operations_transpile(transpile):
    c = transpile(OPERATIONS_SOURCE)
    assert_transpiles_to(c, [
        'int *nums = NULL;',
        'arrput(nums, 10);',
        'arrput(nums, 20);',
        'arrput(nums, 30);',
        'arrput(nums, 40);',
        'arrlen(nums)',
        'int last = arrpop(nums);',
        'arrins(nums, 1, 99);',
        'arrdel(nums, 0);',
        'arrfree(nums);',
    ])


def test_operations_runs(run_simplc):
    result = run_simplc(OPERATIONS_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == (
        "length: 4\n"
        "nums[0] = 10\n"
        "nums[1] = 20\n"
        "nums[2] = 30\n"
        "nums[3] = 40\n"
        "popped: 40\n"
        "after pop len: 3\n"
        "after insert len: 4\n"
        "after del len: 3\n"
    )


# ── §6.3 array of structs ──────────────────────────────────────────


STRUCT_ARRAY_SOURCE = """\
struct Point:
    x: int,
    y: int

fn main() -> int:
    points: list[Point] = []
    points.append(((Point){1, 2}))
    points.append(((Point){3, 4}))

    for i in range(len(points)):
        printf("(%d, %d)\\n", points[i].x, points[i].y)

    points.free()
    return 0
"""


def test_struct_array_transpile(transpile):
    c = transpile(STRUCT_ARRAY_SOURCE)
    assert_transpiles_to(c, [
        'typedef struct Point {',
        'Point *points = NULL;',
        'arrput(points, ((Point){1, 2}));',
        'arrput(points, ((Point){3, 4}));',
        'arrlen(points)',
        'arrfree(points);',
    ])


def test_struct_array_runs(run_simplc):
    result = run_simplc(STRUCT_ARRAY_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "(1, 2)\n(3, 4)\n"


# ── §6.4 stb_ds passthrough functions ──────────────────────────────


PASSTHROUGH_SOURCE = """\
fn main() -> int:
    a: list[int] = []
    a.append(1)
    a.append(2)
    a.append(3)
    printf("lenu: %zu\\n", arrlenu(a))
    printf("cap: %zu\\n", arrcap(a))
    arrsetlen(a, 5)
    a.free()
    return 0
"""


def test_passthrough_transpile(transpile):
    """arrlenu, arrcap, arrsetlen pass through unchanged."""
    c = transpile(PASSTHROUGH_SOURCE)
    assert_transpiles_to(c, [
        'arrlenu(a)',
        'arrcap(a)',
        'arrsetlen(a, 5)',
    ])


def test_passthrough_runs(run_simplc):
    result = run_simplc(PASSTHROUGH_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"


# ── arrdelswap: reference mentions it (works on declared arr) ──────


ARRDELSWAP_SOURCE = """\
fn main() -> int:
    a: list[int] = []
    a.append(1)
    a.append(2)
    a.append(3)
    arrdelswap(a, 0)
    printf("first: %d\\n", a[0])
    a.free()
    return 0
"""


def test_arrdelswap_runs(run_simplc):
    """arrdelswap removes first, swapping in last (3) at index 0."""
    result = run_simplc(ARRDELSWAP_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "first: 3\n"
