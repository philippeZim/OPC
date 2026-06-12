# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

OPC is a transpiler for **SimplC** — a Python-inspired dialect that compiles to standard C. SimplC removes boilerplate (no semicolons, no braces, no `#include`) while staying close to C semantics. The file extension in practice is `.opc` (the reference doc says `.sc`).

The entire transpiler lives in a single file: `transpiler.py`.

## Workflow

```bash
# Transpile a .opc file to C
python3 transpiler.py program.opc          # produces program.c
python3 transpiler.py program.opc out.c   # explicit output path

# Compile the C output
gcc output.c -o program -lm

# With warnings
gcc -Wall -Wextra output.c -o program -lm
```

For programs using `list[T]` or `map[K,V]`, `stb_ds.h` must be in the same directory as the output `.c` file (it is bundled here).

## Transpiler architecture (`transpiler.py`)

The `SimplCTranspiler` class owns all state and logic:

- **`__init__`** — initialises per-file state: `needed_includes`, `struct_names`, `map_decls`, `arr_decls`, `generated_map_structs`.
- **`transpile(source)`** — main entry point. Does a pre-scan for struct names, detects auto-includes, then processes the source line-by-line in a single pass.
- **Transform methods** (`try_*`) — each tries to match one pattern and returns `(output_line, is_block)` or `None`. They are tried in priority order; the first match wins. Order matters: `try_del` and `try_map_put` must fire before `try_variable`.
- **`rewrite_map_gets`** — inline-rewrites `mapvar[key]` → `shget()`/`hmget()` in rvalue positions. Called before other transforms so it works inside expressions.
- **`rewrite_arr_methods`** — inline-rewrites `len(a)`, `a.append(x)`, `a.pop()`, `a.insert(i,x)`, `a.free()` to stb_ds macros.
- **`rewrite_map_methods`** — inline-rewrites `len(m)`, `key in m`, `key not in m`, `m.default(val)`, `m.free()` to stb_ds calls. String-keyed maps use `sh*` functions; any other key type uses `hm*` functions.
- **Block tracking** — a stack (`block_indents`) of `(indent_level, block_type)` pairs drives `{`/`}` emission. Block types are `'code'`, `'else_block'`, or `('struct', name)`.
- **`_semi`** — appends `;` to lines that aren't blank, comments, preprocessor directives, or already terminated.
- **`_build_includes` / `_build_map_structs`** — emit preamble (sorted `#include`s, then stb_ds, then generated map `typedef`s).
- **`resolve_type`** — converts SimplC type notation (`list[T]`, `map[K,V]`, `i32`, `char*`, etc.) to C types.

### Key SimplC → C mappings

| SimplC | C |
|--------|---|
| `fn f(x: int) -> int:` | `int f(int x) {` |
| `x: int = 5` | `int x = 5;` |
| `for i in range(n):` | `for (int i = 0; i < n; i++) {` |
| `elif cond:` | `} else if (cond) {` |
| `struct Foo:` | `typedef struct Foo { ... } Foo;` |
| `a: list[int] = []` | `int *a = NULL;` + stb_ds |
| `a: list[int] = [1, 2, 3]` | `int *a = NULL; arrput(a, 1); ...` + stb_ds |
| `a: list[int](N) = []` | `int *a = NULL; arrsetcap(a, N);` + stb_ds |
| `a.append(x)` / `a.pop()` / `a.insert(i,x)` | `arrput` / `arrpop` / `arrins` |
| `del a[i]` / `a.free()` | `arrdel` / `arrfree` |
| `len(a)` | `arrlen(a)` |
| `m: map[K,V] = {}` / `{k: v, ...}` | typedef'd struct pointer (+ `shput`/`hmput` per pair) + stb_ds |
| `m[key] = val` / `m[key]` / `del m[key]` | `shput/hmput` / `shget/hmget` / `shdel/hmdel` |
| `len(m)` / `key in m` / `key not in m` | `shlen/hmlen` / `shgeti/hmgeti >= 0` / `< 0` |
| `m.default(val)` / `m.free()` | `shdefault/hmdefault` / `shfree/hmfree` |
| `print("hi")` | `printf("hi\n");` |

Auto-includes are emitted based on function names and type keywords — you never write `#include` in SimplC.
