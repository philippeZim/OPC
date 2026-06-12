"""§5 Structs — definition, field syntax, and usage in functions."""
from tests.conftest import assert_runs, assert_transpiles_to


# ── plain struct definition ─────────────────────────────────────────


STRUCT_DEF_SOURCE = """\
struct Vec2:
    x: double,
    y: double

struct Player:
    name: char*,
    health: int,
    pos: Vec2
"""


def test_struct_definition_transpile(transpile):
    c = transpile(STRUCT_DEF_SOURCE)
    assert_transpiles_to(c, [
        'typedef struct Vec2 {',
        'double x;',
        'double y;',
        '} Vec2;',
        'typedef struct Player {',
        'char * name;',
        'int health;',
        'Vec2 pos;',
        '} Player;',
    ])


def test_struct_definition_compile(transpile, compile_c):
    result = compile_c(transpile(STRUCT_DEF_SOURCE), compile_only=True)
    assert result.ok, result.stderr


# ── using structs in functions ─────────────────────────────────────


STRUCT_USAGE_SOURCE = """\
struct Vec2:
    x: double,
    y: double

fn vec2_add(a: Vec2, b: Vec2) -> Vec2:
    result: Vec2
    result.x = a.x + b.x
    result.y = a.y + b.y
    return result

fn main() -> int:
    origin: Vec2 = {0.0, 0.0}
    target: Vec2 = {3.0, 4.0}
    sum: Vec2 = vec2_add(origin, target)
    printf("(%f, %f)\\n", sum.x, sum.y)
    return 0
"""


def test_struct_usage_transpile(transpile):
    c = transpile(STRUCT_USAGE_SOURCE)
    assert_transpiles_to(c, [
        'typedef struct Vec2 {',
        'Vec2 vec2_add(Vec2 a, Vec2 b) {',
        'Vec2 result;',
        'result.x = a.x + b.x;',
        'result.y = a.y + b.y;',
        'return result;',
        'Vec2 origin = {0.0, 0.0};',
        'Vec2 target = {3.0, 4.0};',
        'Vec2 sum = vec2_add(origin, target);',
    ])


def test_struct_usage_runs(run_simplc):
    assert_runs(run_simplc(STRUCT_USAGE_SOURCE), "(3.000000, 4.000000)\n")
