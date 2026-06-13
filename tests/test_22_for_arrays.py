"""§21 `for x in arr:` over fixed-size arrays and pointers that alias them.

The existing `for elem in list:` shorthand worked only for dynamic `list[T]`
(it used `arrlen`). This extends it to fixed-size arrays `T[N]` — whose length
is known at compile time — and to plain pointers that are assigned a known
fixed array.
"""
from tests.conftest import assert_runs, assert_transpiles_to


def test_for_fixed_array(transpile):
    c = transpile(
        'fn main() -> int:\n'
        '    a: int[3] = {1, 2, 3}\n'
        '    for x in a:\n'
        '        printf("%d\\n", x)\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, [
        'for (int _opc_i_ = 0; _opc_i_ < 3; _opc_i_++) {',
        'int x = a[_opc_i_];',
    ])


def test_for_pointer_alias_of_fixed_array(transpile):
    c = transpile(
        'fn main() -> int:\n'
        '    a: int[3] = {1, 2, 3}\n'
        '    p: int* = a\n'
        '    for x in p:\n'
        '        printf("%d\\n", x)\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, [
        'for (int _opc_i_ = 0; _opc_i_ < 3; _opc_i_++) {',
        'int x = p[_opc_i_];',
    ])


def test_for_fixed_string_array(transpile):
    c = transpile(
        'fn main() -> int:\n'
        '    w: char*[2] = {"a", "b"}\n'
        '    for s in w:\n'
        '        printf("%s\\n", s)\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, [
        'for (int _opc_i_ = 0; _opc_i_ < 2; _opc_i_++) {',
        'char *s = w[_opc_i_];',
    ])


def test_for_dynamic_list_still_uses_arrlen(transpile):
    # Regression: the dynamic list[T] path must keep using arrlen().
    c = transpile(
        'fn main() -> int:\n'
        '    a: list[int] = [1, 2, 3]\n'
        '    for x in a:\n'
        '        printf("%d\\n", x)\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, ['_opc_i_ < arrlen(a)'])


FOR_ARRAYS_PROGRAM = """\
fn main() -> int:
    nums: int[3] = {1, 2, 3}
    for x in nums:
        printf("%d\\n", x)
    p: int* = nums
    for y in p:
        printf("%d\\n", y * 10)
    return 0
"""


def test_for_arrays_program_runs(run_simplc):
    assert_runs(run_simplc(FOR_ARRAYS_PROGRAM), "1\n2\n3\n10\n20\n30\n")
