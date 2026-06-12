"""§15 Complete example — word frequency counter from reference.md."""
from tests.conftest import assert_runs, assert_transpiles_to


WORD_FREQ_SOURCE = """\
fn main() -> int:
    freq: map[char*, int] = {}
    freq.default(0)

    words: list[char*] = []
    words.append("hello")
    words.append("world")
    words.append("hello")
    words.append("foo")
    words.append("world")
    words.append("hello")

    // Count frequencies
    for i in range(len(words)):
        current: int = freq[words[i]]
        freq[words[i]] = current + 1

    // Print results
    printf("Word frequencies:\\n")
    for i in range(len(freq)):
        printf("  %s: %d\\n", freq[i].key, freq[i].value)

    freq.free()
    words.free()
    return 0
"""


def test_word_freq_transpile(transpile):
    c = transpile(WORD_FREQ_SOURCE)
    assert_transpiles_to(c, [
        'shdefault(freq, 0);',
        'char **words = NULL;',
        'arrput(words, "hello");',
        'arrput(words, "world");',
        'arrput(words, "foo");',
        'for (int i = 0; i < arrlen(words); i++) {',
        'int current = shget(freq, words[i]);',
        'shput(freq, words[i], current + 1);',
        'for (int i = 0; i < shlen(freq); i++) {',
        'freq[i].key',
        'freq[i].value',
        'shfree(freq);',
        'arrfree(words);',
    ])


def test_word_freq_runs(run_simplc):
    result = run_simplc(WORD_FREQ_SOURCE)
    assert result.ok, f"compile stderr:\n{result.compile.stderr}\nrun stderr:\n{result.stderr}"
    # Iteration order is hash-order; check structure and totals.
    lines = result.stdout.splitlines()
    assert lines[0] == "Word frequencies:"
    pairs = {line.strip().rstrip(":").split(": ")[0]: int(line.strip().rstrip(":").split(": ")[1])
             for line in lines[1:]}
    assert pairs == {"hello": 3, "world": 2, "foo": 1}
    assert sum(pairs.values()) == 6
