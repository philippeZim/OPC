"""§1 Hello World — the smallest complete SimplC program."""
from tests.conftest import assert_runs, assert_transpiles_to


SOURCE = """\
fn main() -> int:
    print("Hello, World!")
    return 0
"""


def test_transpiles_to_hello_world(transpile):
    c = transpile(SOURCE)
    assert_transpiles_to(c, [
        '#include <stdio.h>',
        'int main() {',
        'printf("Hello, World!\\n");',
        'return 0;',
    ])
    # No semicolons, no braces, no includes in source.
    assert '{' not in SOURCE.split('fn main')[0]


def test_hello_world_runs(run_simplc):
    result = run_simplc(SOURCE)
    assert_runs(result, "Hello, World!\n")
