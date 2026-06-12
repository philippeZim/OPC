"""§6 Dynamic Arrays — list[T] backed by stb_ds."""
from tests.conftest import assert_runs, assert_transpiles_to


# ── §6.1 declaration forms ──────────────────────────────────────────


DECL_SOURCE = """\
fn main() -> int:
    nums: list[int] = []
    words: list[char*] = []
    big: list[double](1000) = []
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


# ── §6.1 literal initialization and capacity (new syntax) ──────────


LITERAL_INIT_SOURCE = """\
fn main() -> int:
    vals: list[int] = [1, 2, 3]
    capped: list[int](10) = []
    both: list[int](10) = [4, 5, 6]
    total: int = 0
    for i in range(len(vals)):
        total += vals[i]
    for i in range(len(both)):
        total += both[i]
    printf("total=%d caplen=%ld\\n", total, len(capped))
    vals.free()
    capped.free()
    both.free()
    return 0
"""


def test_literal_init_transpile(transpile):
    c = transpile(LITERAL_INIT_SOURCE)
    assert_transpiles_to(c, [
        'int *vals = NULL;',
        'arrput(vals, 1);',
        'arrput(vals, 2);',
        'arrput(vals, 3);',
        'int *capped = NULL;',
        'arrsetcap(capped, 10);',
        'int *both = NULL;',
        'arrsetcap(both, 10);',
        'arrput(both, 4);',
        'arrput(both, 5);',
        'arrput(both, 6);',
    ])


def test_literal_init_runs(run_simplc):
    result = run_simplc(LITERAL_INIT_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "total=21 caplen=0\n"


# ── §6.5 iterator for loop (for elem in list:) ────────────────────


FOR_LIST_SOURCE = """\
fn main() -> int:
    nums: list[int] = [10, 20, 30]
    total: int = 0
    for n in nums:
        total += n
    printf("%d\\n", total)
    nums.free()
    return 0
"""


def test_for_list_transpile(transpile):
    c = transpile(FOR_LIST_SOURCE)
    assert_transpiles_to(c, [
        'for (int _opc_i_ = 0; _opc_i_ < arrlen(nums); _opc_i_++)',
        'int n = nums[_opc_i_];',
    ])


def test_for_list_runs(run_simplc):
    result = run_simplc(FOR_LIST_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "60\n"


FOR_LIST_STRINGS_SOURCE = """\
fn main() -> int:
    words: list[char*] = []
    words.append("hello")
    words.append("world")
    for w in words:
        printf("%s\\n", w)
    words.free()
    return 0
"""


def test_for_list_strings_runs(run_simplc):
    result = run_simplc(FOR_LIST_STRINGS_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "hello\nworld\n"


FOR_LIST_NESTED_SOURCE = """\
fn main() -> int:
    outer: list[int] = [1, 2]
    inner: list[int] = [3, 4]
    for a in outer:
        for b in inner:
            printf("%d\\n", a + b)
    outer.free()
    inner.free()
    return 0
"""


def test_for_list_nested_runs(run_simplc):
    result = run_simplc(FOR_LIST_NESTED_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "4\n5\n5\n6\n"
