"""§7 Hash Maps — map[K, V] backed by stb_ds (sh* for string keys, hm* otherwise)."""
from tests.conftest import assert_runs, assert_transpiles_to


# ── §7.1 + §7.2 declaration, put, get, delete ──────────────────────


STRING_KEY_OPS_SOURCE = """\
fn main() -> int:
    scores: map[char*, int] = {}
    scores["alice"] = 100
    scores["bob"] = 200
    x: int = scores["alice"]
    printf("alice=%d bob=%d\\n", x, scores["bob"])
    del scores["bob"]
    printf("len after del: %ld\\n", len(scores))
    scores.free()
    return 0
"""


def test_string_key_ops_transpile(transpile):
    c = transpile(STRING_KEY_OPS_SOURCE)
    assert_transpiles_to(c, [
        '#define STB_DS_IMPLEMENTATION',
        '#include "stb_ds.h"',
        # The transpiler emits a named struct tag (with an OPC_MAP_ guard);
        # the reference shows an anonymous tag. Both are valid C.
        'typedef struct __map_charptr_int { char * key; int value; } __map_charptr_int;',
        '__map_charptr_int *scores = NULL;',
        'shput(scores, "alice", 100);',
        'shput(scores, "bob", 200);',
        'int x = shget(scores, "alice");',
        'shdel(scores, "bob");',
        'shlen(scores)',
    ])


def test_string_key_ops_runs(run_simplc):
    result = run_simplc(STRING_KEY_OPS_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "alice=100 bob=200\nlen after del: 1\n"


# ── integer key: same code path uses hm* ──────────────────────────


INT_KEY_OPS_SOURCE = """\
fn main() -> int:
    ages: map[int, double] = {}
    ages[1] = 30.5
    ages[2] = 25.0
    printf("age1=%f age2=%f\\n", ages[1], ages[2])
    del ages[2]
    printf("len after del: %ld\\n", len(ages))
    ages.free()
    return 0
"""


def test_int_key_ops_transpile(transpile):
    c = transpile(INT_KEY_OPS_SOURCE)
    assert_transpiles_to(c, [
        'typedef struct __map_int_double { int key; double value; } __map_int_double;',
        '__map_int_double *ages = NULL;',
        'hmput(ages, 1, 30.5);',
        'hmput(ages, 2, 25.0);',
        'hmget(ages, 1)',
        'hmdel(ages, 2);',
        'hmlen(ages)',
    ])


def test_int_key_ops_runs(run_simplc):
    result = run_simplc(INT_KEY_OPS_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "age1=30.500000 age2=25.000000\nlen after del: 1\n"


# ── §7.3 in / not in ──────────────────────────────────────────────


EXISTS_SOURCE = """\
fn main() -> int:
    scores: map[char*, int] = {}
    scores["alice"] = 100
    if "alice" in scores:
        printf("found\\n")
    if "dave" not in scores:
        printf("missing\\n")
    scores.free()
    return 0
"""


def test_in_not_in_transpile(transpile):
    c = transpile(EXISTS_SOURCE)
    assert_transpiles_to(c, [
        'if (shgeti(scores, "alice") >= 0) {',
        'printf("found\\n");',
        'if (shgeti(scores, "dave") < 0) {',
        'printf("missing\\n");',
    ])


def test_in_not_in_runs(run_simplc):
    assert_runs(run_simplc(EXISTS_SOURCE), "found\nmissing\n")


# ── §7.4 default values ────────────────────────────────────────────


DEFAULT_STR_SOURCE = """\
fn main() -> int:
    config: map[char*, int] = {}
    config.default(0)
    config["width"] = 1920
    missing: int = config["nonexistent"]
    printf("missing=%d width=%d\\n", missing, config["width"])
    config.free()
    return 0
"""


def test_default_string_key_transpile(transpile):
    c = transpile(DEFAULT_STR_SOURCE)
    assert_transpiles_to(c, [
        'shdefault(config, 0);',
        'int missing = shget(config, "nonexistent");',
    ])


def test_default_string_key_runs(run_simplc):
    assert_runs(run_simplc(DEFAULT_STR_SOURCE), "missing=0 width=1920\n")


DEFAULT_INT_SOURCE = """\
fn main() -> int:
    ages: map[int, double] = {}
    ages.default(-1.0)
    printf("missing: %f\\n", ages[9999])
    ages.free()
    return 0
"""


def test_default_int_key_transpile(transpile):
    c = transpile(DEFAULT_INT_SOURCE)
    assert_transpiles_to(c, [
        'hmdefault(ages, -1.0);',
        'hmget(ages, 9999)',
    ])


def test_default_int_key_runs(run_simplc):
    assert_runs(run_simplc(DEFAULT_INT_SOURCE), "missing: -1.000000\n")


# ── §7.5 iteration ─────────────────────────────────────────────────


ITERATE_SOURCE = """\
fn main() -> int:
    scores: map[char*, int] = {}
    scores["alice"] = 100
    scores["bob"] = 200
    for i in range(len(scores)):
        printf("%s -> %d\\n", scores[i].key, scores[i].value)
    scores.free()
    return 0
"""


def test_iteration_transpile(transpile):
    c = transpile(ITERATE_SOURCE)
    assert_transpiles_to(c, [
        'for (int i = 0; i < shlen(scores); i++) {',
        'scores[i].key',
        'scores[i].value',
    ])


def test_iteration_runs(run_simplc):
    result = run_simplc(ITERATE_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    # Iteration order is hash-order; just check both pairs are present.
    lines = set(result.stdout.splitlines())
    assert lines == {'alice -> 100', 'bob -> 200'}


# ── §7.6 free ─────────────────────────────────────────────────────


FREE_SOURCE = """\
fn main() -> int:
    a: map[char*, int] = {}
    b: map[int, double] = {}
    a.free()
    b.free()
    return 0
"""


def test_free_transpile(transpile):
    c = transpile(FREE_SOURCE)
    assert_transpiles_to(c, [
        'shfree(a);',
        'hmfree(b);',
    ])


# ── §7.7 maps as function parameters ──────────────────────────────


PARAMS_SOURCE = """\
fn lookup(db: map[char*, int], key: char*) -> int:
    return db[key]

fn main() -> int:
    db: map[char*, int] = {}
    db["x"] = 42
    printf("x=%d\\n", lookup(db, "x"))
    db.free()
    return 0
"""


# §7.7: maps as function parameters. The transpiler registers `map[...]`
# and `list[...]` parameter types in `map_decls` / `arr_decls` so the
# function body can use the same shorthand as a local declaration.
def test_map_params_transpile(transpile):
    c = transpile(PARAMS_SOURCE)
    assert_transpiles_to(c, [
        'int lookup(__map_charptr_int * db, char * key) {',
        'return shget(db, key);',
    ])


def test_map_params_runs(run_simplc):
    assert_runs(run_simplc(PARAMS_SOURCE), "x=42\n")


# ── §7.1 map literal initialization (new syntax) ──────────────────


MAP_LITERAL_SOURCE = """\
fn main() -> int:
    prices: map[char*, int] = {"apple": 1, "pear": 2, "plum": 3}
    squares: map[int, int] = {1: 1, 2: 4, 3: 9}
    printf("apple=%d plum=%d len=%ld\\n", prices["apple"], prices["plum"], len(prices))
    printf("sq2=%d sq3=%d\\n", squares[2], squares[3])
    prices.free()
    squares.free()
    return 0
"""


def test_map_literal_transpile(transpile):
    c = transpile(MAP_LITERAL_SOURCE)
    assert_transpiles_to(c, [
        '__map_charptr_int *prices = NULL;',
        'shput(prices, "apple", 1);',
        'shput(prices, "pear", 2);',
        'shput(prices, "plum", 3);',
        '__map_int_int *squares = NULL;',
        'hmput(squares, 1, 1);',
        'hmput(squares, 2, 4);',
        'hmput(squares, 3, 9);',
    ])


def test_map_literal_runs(run_simplc):
    result = run_simplc(MAP_LITERAL_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "apple=1 plum=3 len=3\nsq2=4 sq3=9\n"
