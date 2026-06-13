"""§9–§14 Misc features — comments, print shorthand, auto-includes,
passthrough C, indentation rules, and semicolon insertion."""
import pytest

from tests.conftest import assert_runs, assert_transpiles_to


# ── §9 comments ─────────────────────────────────────────────────────


COMMENTS_SOURCE = """\
// This is a line comment

/* This is a
   block comment */

fn main() -> int:
    /* block inside a function */
    x: int = 1
    // trailing line comment (on its own line)
    return 0
"""


def test_comments_transpile(transpile):
    c = transpile(COMMENTS_SOURCE)
    # Comments are passed through.
    assert '// This is a line comment' in c
    assert '/* This is a' in c
    assert 'block comment' in c
    assert '/* block inside a function */' in c
    assert '// trailing line comment' in c
    # The declaration is still emitted.
    assert 'int x = 1;' in c


def test_comments_runs(run_simplc):
    assert_runs(run_simplc(COMMENTS_SOURCE), "")


# ── §10 print() shorthand ──────────────────────────────────────────


PRINT_STRING_ONLY_SOURCE = """\
fn main() -> int:
    print("Hello!")
    return 0
"""


def test_print_string_only_transpile(transpile):
    c = transpile(PRINT_STRING_ONLY_SOURCE)
    assert_transpiles_to(c, [
        'printf("Hello!\\n");',
    ])
    # The original `print(...)` form is gone.
    assert 'print("Hello!")' not in c


def test_print_string_only_runs(run_simplc):
    assert_runs(run_simplc(PRINT_STRING_ONLY_SOURCE), "Hello!\n")


PRINT_FORMATTED_SOURCE = """\
fn main() -> int:
    x: int = 3
    y: int = 4
    print("%d %d\\n", x, y)
    return 0
"""


def test_print_formatted_transpile(transpile):
    c = transpile(PRINT_FORMATTED_SOURCE)
    assert_transpiles_to(c, [
        'printf("%d %d\\n", x, y);',
    ])


def test_print_formatted_runs(run_simplc):
    assert_runs(run_simplc(PRINT_FORMATTED_SOURCE), "3 4\n")


# A formatted print() WITHOUT a trailing \n still gets one appended (issue #28).
PRINT_FORMATTED_NO_NL_SOURCE = """\
fn main() -> int:
    x: int = 3
    y: int = 4
    print("%d %d", x, y)
    return 0
"""


def test_print_formatted_auto_newline_transpile(transpile):
    c = transpile(PRINT_FORMATTED_NO_NL_SOURCE)
    assert_transpiles_to(c, ['printf("%d %d\\n", x, y);'])


def test_print_formatted_auto_newline_runs(run_simplc):
    assert_runs(run_simplc(PRINT_FORMATTED_NO_NL_SOURCE), "3 4\n")


def test_print_string_with_comma_stays_one_arg(transpile):
    # The format string may itself contain a comma; it must not be split.
    c = transpile('fn main() -> int:\n    print("a, b: %d", 7)\n    return 0\n')
    assert_transpiles_to(c, ['printf("a, b: %d\\n", 7);'])


# ── §11 auto-includes ──────────────────────────────────────────────


AUTO_INCLUDES_SOURCE = """\
fn main() -> int:
    printf("pi = %f\\n", 3.14)
    hyp: double = sqrt(9.0 + 16.0)
    msg: char* = "hello"
    printf("len: %zu\\n", strlen(msg))
    buf: int* = malloc(10 * sizeof(int))
    free(buf)
    ok: bool = true
    val: i32 = 42
    assert(1 + 1 == 2)
    return 0
"""


def test_auto_includes_transpile(transpile):
    c = transpile(AUTO_INCLUDES_SOURCE)
    # Each library is included exactly once.
    assert c.count('#include <stdio.h>') == 1
    assert c.count('#include <math.h>') == 1
    assert c.count('#include <string.h>') == 1
    assert c.count('#include <stdlib.h>') == 1
    assert c.count('#include <stdbool.h>') == 1
    assert c.count('#include <stdint.h>') == 1
    assert c.count('#include <assert.h>') == 1


def test_auto_includes_are_sorted(transpile):
    """Headers should be emitted in sorted order for reproducibility."""
    c = transpile(AUTO_INCLUDES_SOURCE)
    includes = [line for line in c.splitlines() if line.startswith('#include <')]
    assert includes == sorted(includes)


def test_auto_includes_runs(run_simplc):
    result = run_simplc(AUTO_INCLUDES_SOURCE, extra_ldflags=["-lm"])
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "pi = 3.140000\nlen: 5\n"


def test_ctype_includes_detected(transpile):
    """Functions from §11's ctype row are detected."""
    src = """\
fn main() -> int:
    ch: char = 'a'
    printf("%d\\n", isalpha(ch))
    return 0
"""
    c = transpile(src)
    assert '#include <ctype.h>' in c


# Regression: the auto-include detector used to match `free(` inside
# `nums.free()` and pull in <stdlib.h>. Method calls are not stdlib calls.
def test_list_free_does_not_pull_in_stdlib(transpile):
    src = """\
fn main() -> int:
    nums: list[int] = []
    nums.append(1)
    nums.append(2)
    nums.free()
    return 0
"""
    c = transpile(src)
    assert '#include <stdlib.h>' not in c


def test_string_literal_does_not_trigger_includes(transpile):
    """`"free"` inside a string literal should not trigger <stdlib.h>."""
    src = """\
fn main() -> int:
    printf("free\\n")
    return 0
"""
    c = transpile(src)
    assert '#include <stdlib.h>' not in c
    # stdio is still pulled in by the real printf call.
    assert '#include <stdio.h>' in c


def test_char_literal_does_not_trigger_includes(transpile):
    """`'x'` should not be misread as an identifier."""
    src = """\
fn main() -> int:
    ch: char = 'x'
    printf("%c\\n", ch)
    return 0
"""
    c = transpile(src)
    assert '#include <stdlib.h>' not in c


def test_real_malloc_still_pulls_in_stdlib(transpile):
    """The fix must not over-correct — real stdlib calls still trigger."""
    src = """\
fn main() -> int:
    p: int* = malloc(4)
    free(p)
    return 0
"""
    c = transpile(src)
    assert '#include <stdlib.h>' in c


# ── §12 passthrough / raw C ────────────────────────────────────────


PASSTHROUGH_SOURCE = """\
#define MAX_SIZE 100
#define SQUARE(x) ((x) * (x))

enum Color { RED, GREEN, BLUE };

typedef unsigned long ulong;

fn main() -> int:
    buf: int[MAX_SIZE]
    val: int = SQUARE(5)

    // Ternary operator
    x: int = 10
    result: char* = (x > 5) ? "big" : "small"

    // do-while (raw C syntax)
    count: int = 0
    do {
        printf("%d ", count)
        count++
    } while (count < 5);

    // goto
    goto done
    printf("skipped\\n")
    done:
    printf("done\\n")

    return 0
"""


def test_passthrough_transpile(transpile):
    c = transpile(PASSTHROUGH_SOURCE)
    assert_transpiles_to(c, [
        '#define MAX_SIZE 100',
        '#define SQUARE(x) ((x) * (x))',
        'enum Color { RED, GREEN, BLUE };',
        'typedef unsigned long ulong;',
        'int buf[MAX_SIZE];',
        'int val = SQUARE(5);',
        'int x = 10;',
        'char * result = (x > 5) ? "big" : "small";',
        'int count = 0;',
        'do {',
        'printf("%d ", count);',
        'count++;',
        '} while (count < 5);',
        'goto done;',
    ])
    # The label `done:` is followed by a `;` (the transpiler's solution to the
    # empty-statement requirement after a label).
    assert 'done:' in c


def test_passthrough_runs(run_simplc):
    result = run_simplc(PASSTHROUGH_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "0 1 2 3 4 done\n"


# ── §13 indentation / block rules ──────────────────────────────────


# `x` is predeclared so the fragment compiles.
INDENT_SOURCE = """\
fn main() -> int:
    x: int = 1
    if x > 0:
        printf("pos\\n")
    else:
        printf("neg\\n")
    return 0
"""


def test_indentation_emits_braces(transpile):
    c = transpile(INDENT_SOURCE)
    # Three nested blocks: function, if, else → three open and three close braces.
    assert c.count('{') == 3
    assert c.count('}') == 3
    assert 'if (x > 0) {' in c
    assert '} else {' in c


def test_indentation_compiles(transpile, compile_c):
    result = compile_c(transpile(INDENT_SOURCE), compile_only=True)
    assert result.ok, result.stderr


def test_indentation_runs(run_simplc):
    assert_runs(run_simplc(INDENT_SOURCE), "pos\n")


def test_consistent_indent_width_works(transpile):
    """The transpiler is width-agnostic — any consistent indent is fine."""
    src = (
        "fn main() -> int:\n"
        "        x: int = 1\n"           # 8 spaces
        "        if x > 0:\n"
        "                printf(\"big\\n\")\n"  # 16 spaces
        "        return 0\n"
    )
    c = transpile(src)
    assert c.count('{') == 2
    assert c.count('}') == 2
    assert 'if (x > 0) {' in c


# ── §14 semicolon auto-insertion ───────────────────────────────────


# Each entry is a tiny SimplC fragment plus the *C* string we expect the
# transpiler to produce. We check both the absence of `;;` for lines that
# should be left alone, and the presence of `;` for lines that need one.
@pytest.mark.parametrize("src,expected_in_c", [
    ("x: int = 1\ny: int = 2", ["int x = 1;", "int y = 2;"]),
    ("#define FOO 1", ["#define FOO 1"]),
    ("// hi", ["// hi"]),
    ("enum C { A, B };", ["enum C { A, B };"]),
])
def test_semicolon_rules(transpile, src, expected_in_c):
    c = transpile(src)
    for expected in expected_in_c:
        assert expected in c
    # Nothing has been double-semicoloned.
    assert ';;' not in c


def test_semicolon_not_added_to_block_opener(transpile):
    c = transpile("fn main() -> int:")
    # The `:` is rewritten to ` {` for function defs; no extra `;` follows.
    assert 'int main() {' in c
    assert '{;' not in c

