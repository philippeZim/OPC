"""§3 Functions — declarations, parameters, and recursion."""
from transpiler import SimplCTranspiler

from tests.conftest import assert_runs, assert_transpiles_to


# ── §3 basic function forms ─────────────────────────────────────────


BASIC_FUNCTIONS_SOURCE = """\
fn add(a: int, b: int) -> int:
    return a + b

fn greet(name: char*) -> void:
    printf("Hello, %s!\\n", name)

fn get_answer() -> int:
    return 42

fn main() -> int:
    printf("%d\\n", add(2, 3))
    greet("World")
    printf("%d\\n", get_answer())
    return 0
"""


def test_basic_functions_transpile(transpile):
    c = transpile(BASIC_FUNCTIONS_SOURCE)
    assert_transpiles_to(c, [
        'int add(int a, int b) {',
        'return a + b;',
        'void greet(char * name) {',
        'printf("Hello, %s!\\n", name);',
        'int get_answer() {',
        'return 42;',
    ])


def test_basic_functions_run(run_simplc):
    assert_runs(run_simplc(BASIC_FUNCTIONS_SOURCE), "5\nHello, World!\n42\n")


def test_basic_functions_generate_prototypes():
    """The transpiler collects function prototypes for the header file."""
    t = SimplCTranspiler()
    t.transpile(BASIC_FUNCTIONS_SOURCE)
    assert t.prototypes == [
        'int add(int a, int b);',
        'void greet(char * name);',
        'int get_answer();',
    ]


# ── §3.1 pointer and array parameters ──────────────────────────────


PTR_AND_ARR_PARAMS_SOURCE = """\
fn swap(a: int*, b: int*) -> void:
    temp: int = *a
    *a = *b
    *b = temp

fn sum_array(data: int[10], len: int) -> int:
    total: int = 0
    for i in range(len):
        total += data[i]
    return total
"""


def test_pointer_and_array_params_transpile(transpile):
    c = transpile(PTR_AND_ARR_PARAMS_SOURCE)
    assert_transpiles_to(c, [
        'void swap(int * a, int * b) {',
        'int temp = *a;',
        '*a = *b;',
        '*b = temp;',
        'int sum_array(int data[10], int len) {',
        'int total = 0;',
        'for (int i = 0; i < len; i++) {',
        'total += data[i];',
        'return total;',
    ])


def test_pointer_and_array_params_compile(transpile, compile_c):
    # The fragment defines no `main`, so use compile-only.
    c = transpile(PTR_AND_ARR_PARAMS_SOURCE)
    result = compile_c(c, compile_only=True)
    assert result.ok, result.stderr


# ── §3.2 recursion ─────────────────────────────────────────────────


RECURSION_SOURCE = """\
fn fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)

fn main() -> int:
    printf("%d\\n", fibonacci(10))
    return 0
"""


def test_recursion_transpile(transpile):
    c = transpile(RECURSION_SOURCE)
    assert_transpiles_to(c, [
        'int fibonacci(int n) {',
        'if (n <= 1) {',
        'return n;',
        'return fibonacci(n - 1) + fibonacci(n - 2);',
    ])


def test_recursion_runs(run_simplc):
    # fibonacci(10) = 55
    assert_runs(run_simplc(RECURSION_SOURCE), "55\n")
