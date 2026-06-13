"""§19 Function pointers — the `fn(args) -> ret` type shorthand.

SimplC replaces C's awkward `R (*name)(args)` declarator with a readable
`name: fn(args) -> ret` form that mirrors the `fn` used for definitions.
"""
from tests.conftest import assert_runs, assert_transpiles_to


def test_fn_ptr_variable(transpile):
    c = transpile(
        'fn add(a: int, b: int) -> int:\n'
        '    return a + b\n'
        'fn main() -> int:\n'
        '    op: fn(int, int) -> int = add\n'
        '    return op(2, 3)\n'
    )
    assert_transpiles_to(c, ['int (*op)(int, int) = add;'])


def test_fn_ptr_no_init(transpile):
    c = transpile(
        'fn main() -> int:\n'
        '    op: fn(int) -> int\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, ['int (*op)(int);'])


def test_fn_ptr_void_args(transpile):
    c = transpile(
        'fn main() -> int:\n'
        '    cb: fn() -> void\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, ['void (*cb)(void);'])


def test_fn_ptr_parameter(transpile):
    c = transpile(
        'fn apply(f: fn(int, int) -> int, x: int, y: int) -> int:\n'
        '    return f(x, y)\n'
    )
    assert_transpiles_to(c, ['int apply(int (*f)(int, int), int x, int y) {'])


def test_fn_ptr_struct_field(transpile):
    c = transpile(
        'struct Calc:\n'
        '    op: fn(int, int) -> int\n'
        '    name: char*\n'
    )
    assert_transpiles_to(c, ['int (*op)(int, int);'])


def test_fn_ptr_pointer_arg_type(transpile):
    c = transpile(
        'fn main() -> int:\n'
        '    cmp: fn(char*, char*) -> int\n'
        '    return 0\n'
    )
    assert_transpiles_to(c, ['int (*cmp)(char *, char *);'])


FUNCTION_POINTER_PROGRAM = """\
fn add(a: int, b: int) -> int:
    return a + b

fn sub(a: int, b: int) -> int:
    return a - b

fn apply(f: fn(int, int) -> int, x: int, y: int) -> int:
    return f(x, y)

struct Calc:
    op: fn(int, int) -> int
    name: char*

fn main() -> int:
    op: fn(int, int) -> int = add
    printf("%d\\n", apply(op, 3, 4))
    op = sub
    printf("%d\\n", apply(op, 10, 3))
    c: Calc = {add, "adder"}
    printf("%s=%d\\n", c.name, c.op(5, 6))
    return 0
"""


def test_fn_ptr_program_runs(run_simplc):
    assert_runs(run_simplc(FUNCTION_POINTER_PROGRAM), "7\n7\nadder=11\n")
