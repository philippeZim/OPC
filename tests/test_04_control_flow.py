"""§4 Control Flow — if/elif/else, while, for-range, plain for, switch, nested."""
from tests.conftest import assert_runs, assert_transpiles_to


# ── §4.1 if / elif / else ───────────────────────────────────────────


IF_ELIF_ELSE_SOURCE = """\
fn main() -> int:
    x: int = 15
    if x > 20:
        printf("big\\n")
    elif x > 10:
        printf("medium\\n")
    else:
        printf("small\\n")
    return 0
"""


def test_if_elif_else_transpile(transpile):
    c = transpile(IF_ELIF_ELSE_SOURCE)
    assert_transpiles_to(c, [
        'int x = 15;',
        'if (x > 20) {',
        'printf("big\\n");',
        '} else if (x > 10) {',
        'printf("medium\\n");',
        '} else {',
        'printf("small\\n");',
    ])


def test_if_elif_else_runs(run_simplc):
    assert_runs(run_simplc(IF_ELIF_ELSE_SOURCE), "medium\n")


# ── §4.2 while ──────────────────────────────────────────────────────


WHILE_SOURCE = """\
fn main() -> int:
    count: int = 0
    while count < 5:
        printf("%d ", count)
        count += 1
    printf("\\n")
    return 0
"""


def test_while_transpile(transpile):
    c = transpile(WHILE_SOURCE)
    assert_transpiles_to(c, [
        'int count = 0;',
        'while (count < 5) {',
        'printf("%d ", count);',
        'count += 1;',
    ])


def test_while_runs(run_simplc):
    assert_runs(run_simplc(WHILE_SOURCE), "0 1 2 3 4 \n")


# ── §4.3 for-range ──────────────────────────────────────────────────


FOR_RANGE_SOURCE = """\
fn main() -> int:
    // range(end)
    for i in range(5):
        printf("%d ", i)
    printf("| ")
    // range(start, end)
    for i in range(10, 13):
        printf("%d ", i)
    printf("| ")
    // range(start, end, step)
    for i in range(0, 100, 25):
        printf("%d ", i)
    printf("| ")
    // Negative step
    for i in range(5, 0, -1):
        printf("%d ", i)
    printf("\\n")
    return 0
"""


def test_for_range_transpile(transpile):
    c = transpile(FOR_RANGE_SOURCE)
    assert_transpiles_to(c, [
        'for (int i = 0; i < 5; i++) {',
        'for (int i = 10; i < 13; i++) {',
        'for (int i = 0; i < 100; i += 25) {',
        'for (int i = 5; i > 0; i--) {',
    ])


def test_for_range_runs(run_simplc):
    assert_runs(run_simplc(FOR_RANGE_SOURCE), "0 1 2 3 4 | 10 11 12 | 0 25 50 75 | 5 4 3 2 1 \n")


# ── §4.4 plain for (C-style) ────────────────────────────────────────


PLAIN_FOR_SOURCE = """\
fn main() -> int:
    for int i = 0; i < 5; i++:
        printf("%d ", i)
    printf("\\n")
    return 0
"""


def test_plain_for_transpile(transpile):
    c = transpile(PLAIN_FOR_SOURCE)
    assert_transpiles_to(c, [
        'for (int i = 0; i < 5; i++) {',
        'printf("%d ", i);',
    ])


def test_plain_for_runs(run_simplc):
    assert_runs(run_simplc(PLAIN_FOR_SOURCE), "0 1 2 3 4 \n")


# ── §4.5 switch ─────────────────────────────────────────────────────


SWITCH_SOURCE = """\
fn main() -> int:
    day: int = 3
    switch day:
        case 1: printf("Monday\\n"); break
        case 2: printf("Tuesday\\n"); break
        case 3: printf("Wednesday\\n"); break
        default: printf("Other\\n"); break
    return 0
"""


def test_switch_transpile(transpile):
    c = transpile(SWITCH_SOURCE)
    assert_transpiles_to(c, [
        'int day = 3;',
        'switch (day) {',
        'case 1: printf("Monday\\n"); break;',
        'case 2: printf("Tuesday\\n"); break;',
        'case 3: printf("Wednesday\\n"); break;',
        'default: printf("Other\\n"); break;',
    ])


def test_switch_runs(run_simplc):
    assert_runs(run_simplc(SWITCH_SOURCE), "Wednesday\n")


# ── §4.6 nested blocks ─────────────────────────────────────────────


NESTED_BLOCKS_SOURCE = """\
fn main() -> int:
    for i in range(3):
        for j in range(3):
            if i == j:
                printf("(%d,%d) ", i, j)
    printf("\\n")
    return 0
"""


def test_nested_blocks_transpile(transpile):
    c = transpile(NESTED_BLOCKS_SOURCE)
    assert_transpiles_to(c, [
        'for (int i = 0; i < 3; i++) {',
        'for (int j = 0; j < 3; j++) {',
        'if (i == j) {',
        'printf("(%d,%d) ", i, j);',
    ])


def test_nested_blocks_runs(run_simplc):
    assert_runs(run_simplc(NESTED_BLOCKS_SOURCE), "(0,0) (1,1) (2,2) \n")
