"""§8 Combined — structs, dynamic arrays, and hash maps in one program."""
from tests.conftest import assert_runs, assert_transpiles_to


COMBINED_SOURCE = """\
struct Player:
    name: char*,
    health: int,
    x: double,
    y: double

fn main() -> int:
    players: list[Player] = []
    players.append(((Player){"Alice", 100, 0.0, 0.0}))
    players.append(((Player){"Bob", 80, 5.0, 3.0}))

    for i in range(len(players)):
        printf("%s: hp=%d\\n", players[i].name, players[i].health)

    index: map[char*, int] = {}
    for i in range(len(players)):
        index[players[i].name] = i

    idx: int = index["Alice"]
    printf("Alice is at index %d\\n", idx)

    shfree(index)
    players.free()
    return 0
"""


def test_combined_transpile(transpile):
    c = transpile(COMBINED_SOURCE)
    assert_transpiles_to(c, [
        'typedef struct Player {',
        'char * name;',
        'int health;',
        'double x;',
        'double y;',
        '} Player;',
        'Player *players = NULL;',
        'arrput(players, ((Player){"Alice", 100, 0.0, 0.0}));',
        'arrput(players, ((Player){"Bob", 80, 5.0, 3.0}));',
        'typedef struct __map_charptr_int { char * key; int value; } __map_charptr_int;',
        '__map_charptr_int *index = NULL;',
        'shput(index, players[i].name, i);',
        'int idx = shget(index, "Alice");',
        'shfree(index);',
        'arrfree(players);',
    ])


def test_combined_runs(run_simplc):
    result = run_simplc(COMBINED_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    assert result.stdout == "Alice: hp=100\nBob: hp=80\nAlice is at index 0\n"
