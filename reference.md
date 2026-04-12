# SimplC Language Reference

SimplC is a Python-inspired dialect that transpiles to standard C. It removes boilerplate — no semicolons, no braces, no `#include` — while staying close enough to C that you always know what the output will be.

**File extension:** `.sc`
**Transpile:** `python3 transpiler.py program.sc [output.c]`
**Compile:** `gcc output.c -o program -lm`

---

## 1. Hello World

The smallest complete program:

```python
fn main() -> int:
    print("Hello, World!")
    return 0
```

Transpiles to:

```c
#include <stdio.h>

int main() {
    printf("Hello, World!\n");
    return 0;
}
```

`print()` is a convenience wrapper (see §10). `#include <stdio.h>` is detected and inserted automatically (see §11). The semicolons, braces, and include are all generated — you never write them.

---

## 2. Variables & Types

Declare with **`name: type`** or **`name: type = value`**:

```python
fn main() -> int:
    x: int = 42
    pi: double = 3.14159
    ch: char = 'A'
    name: char* = "Alice"

    ptr: int* = &x
    dptr: char** = &name

    nums: int[10]
    matrix: double[3][3]

    count: int

    return 0
```

Transpiles to:

```c
int main() {
    int x = 42;
    double pi = 3.14159;
    char ch = 'A';
    char * name = "Alice";

    int * ptr = &x;
    char ** dptr = &name;

    int nums[10];
    double matrix[3][3];

    int count;

    return 0;
}
```

### 2.1 Fixed-Width Integer Types

SimplC provides short aliases for `<stdint.h>` types. Using any of them auto-includes `<stdint.h>`.

| SimplC | C |
|--------|---|
| `i8`   | `int8_t` |
| `i16`  | `int16_t` |
| `i32`  | `int32_t` |
| `i64`  | `int64_t` |
| `u8`   | `uint8_t` |
| `u16`  | `uint16_t` |
| `u32`  | `uint32_t` |
| `u64`  | `uint64_t` |

```python
small: i8 = -128
byte: u8 = 255
id: i32 = 100000
big: u64 = 18446744073709551615
```

Transpiles to:

```c
#include <stdint.h>

int8_t small = -128;
uint8_t byte = 255;
int32_t id = 100000;
uint64_t big = 18446744073709551615;
```

### 2.2 Booleans

`bool`, `true`, and `false` auto-include `<stdbool.h>`:

```python
flag: bool = true
done: bool = false
```

Transpiles to:

```c
#include <stdbool.h>

bool flag = true;
bool done = false;
```

---

## 3. Functions

Declare with **`fn name(params) -> return_type:`** — parameters use `name: type`:

```python
fn add(a: int, b: int) -> int:
    return a + b

fn greet(name: char*) -> void:
    printf("Hello, %s!\n", name)

fn get_answer() -> int:
    return 42
```

Transpiles to:

```c
int add(int a, int b) {
    return a + b;
}

void greet(char * name) {
    printf("Hello, %s!\n", name);
}

int get_answer() {
    return 42;
}
```

### 3.1 Pointer & Array Parameters

```python
fn swap(a: int*, b: int*) -> void:
    temp: int = *a
    *a = *b
    *b = temp

fn sum_array(data: int[10], len: int) -> int:
    total: int = 0
    for i in range(len):
        total += data[i]
    return total
```

Transpiles to:

```c
void swap(int * a, int * b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

int sum_array(int data[10], int len) {
    int total = 0;
    for (int i = 0; i < len; i++) {
        total += data[i];
    }
    return total;
}
```

### 3.2 Recursion

```python
fn fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)
```

Transpiles to:

```c
int fibonacci(int n) {
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}
```

---

## 4. Control Flow

### 4.1 if / elif / else

Condition followed by colon, body indented:

```python
x: int = 15
if x > 20:
    printf("big\n")
elif x > 10:
    printf("medium\n")
else:
    printf("small\n")
```

Transpiles to:

```c
int x = 15;
if (x > 20) {
    printf("big\n");
} else if (x > 10) {
    printf("medium\n");
} else {
    printf("small\n");
}
```

### 4.2 while

```python
count: int = 0
while count < 5:
    printf("%d ", count)
    count += 1
```

Transpiles to:

```c
int count = 0;
while (count < 5) {
    printf("%d ", count);
    count += 1;
}
```

### 4.3 for-range

Python-style `for var in range(...)` with 1, 2, or 3 arguments:

```python
// range(end) — 0 to end, step 1
for i in range(5):
    printf("%d ", i)

// range(start, end) — start to end, step 1
for i in range(10, 20):
    printf("%d ", i)

// range(start, end, step)
for i in range(0, 100, 10):
    printf("%d ", i)

// Negative step (countdown)
for i in range(10, 0, -1):
    printf("%d ", i)
```

Transpiles to:

```c
for (int i = 0; i < 5; i++) {
    printf("%d ", i);
}

for (int i = 10; i < 20; i++) {
    printf("%d ", i);
}

for (int i = 0; i < 100; i += 10) {
    printf("%d ", i);
}

for (int i = 10; i > 0; i--) {
    printf("%d ", i);
}
```

### 4.4 Plain for (C-style)

If you need a non-range for loop, write the three parts after `for`, separated by semicolons:

```python
for int i = 0; i < 5; i++:
    printf("%d ", i)
```

Transpiles to:

```c
for (int i = 0; i < 5; i++) {
    printf("%d ", i);
}
```

### 4.5 switch

```python
day: int = 3
switch day:
    case 1: printf("Monday\n"); break
    case 2: printf("Tuesday\n"); break
    case 3: printf("Wednesday\n"); break
    default: printf("Other\n"); break
```

Transpiles to:

```c
int day = 3;
switch (day) {
    case 1: printf("Monday\n"); break;
    case 2: printf("Tuesday\n"); break;
    case 3: printf("Wednesday\n"); break;
    default: printf("Other\n"); break;
}
```

### 4.6 Nested Blocks

Indentation nesting works to any depth:

```python
for i in range(3):
    for j in range(3):
        if i == j:
            printf("(%d,%d) ", i, j)
```

Transpiles to:

```c
for (int i = 0; i < 3; i++) {
    for (int j = 0; j < 3; j++) {
        if (i == j) {
            printf("(%d,%d) ", i, j);
        }
    }
}
```

---

## 5. Structs

Define with **`struct Name:`** followed by indented fields using `name: type`:

```python
struct Vec2:
    x: double,
    y: double

struct Player:
    name: char*,
    health: int,
    pos: Vec2
```

Transpiles to:

```c
typedef struct Vec2 {
    double x;
    double y;
} Vec2;

typedef struct Player {
    char * name;
    int health;
    Vec2 pos;
} Player;
```

Structs are emitted as `typedef struct Name { ... } Name;` so you use the name directly — no `struct` keyword needed in declarations:

```python
fn vec2_add(a: Vec2, b: Vec2) -> Vec2:
    result: Vec2
    result.x = a.x + b.x
    result.y = a.y + b.y
    return result

fn main() -> int:
    origin: Vec2 = {0.0, 0.0}
    target: Vec2 = {3.0, 4.0}
    sum: Vec2 = vec2_add(origin, target)
    printf("(%f, %f)\n", sum.x, sum.y)
    return 0
```

Transpiles to:

```c
Vec2 vec2_add(Vec2 a, Vec2 b) {
    Vec2 result;
    result.x = a.x + b.x;
    result.y = a.y + b.y;
    return result;
}

int main() {
    Vec2 origin = {0.0, 0.0};
    Vec2 target = {3.0, 4.0};
    Vec2 sum = vec2_add(origin, target);
    printf("(%f, %f)\n", sum.x, sum.y);
    return 0;
}
```

---

## 6. Dynamic Arrays — `arr[T]`

Dynamic arrays use [stb_ds.h](https://github.com/nothings/stb). Place `stb_ds.h` in the same directory as your output `.c` file.

### 6.1 Declaration

**`name: arr[T] = NULL`** declares a dynamic array of element type `T`:

```python
nums: arr[int] = NULL
words: arr[char*] = NULL
points: arr[Point] = NULL
```

Transpiles to:

```c
int *nums = NULL;
char **words = NULL;
Point *points = NULL;
```

The transpiler auto-emits `#define STB_DS_IMPLEMENTATION` and `#include "stb_ds.h"`.

### 6.2 Operations

All stb_ds array macros work directly — they pass through as-is:

```python
fn main() -> int:
    nums: arr[int] = NULL

    // Append
    arrput(nums, 10)
    arrput(nums, 20)
    arrput(nums, 30)
    arrput(nums, 40)

    // Length
    printf("length: %ld\n", arrlen(nums))

    // Iterate (normal array indexing)
    for i in range(arrlen(nums)):
        printf("nums[%d] = %d\n", i, nums[i])

    // Pop last element
    last: int = arrpop(nums)

    // Insert at index
    arrins(nums, 1, 99)

    // Delete at index
    arrdel(nums, 0)

    // Pre-allocate capacity
    big: arr[double] = NULL
    arrsetcap(big, 1000)

    // Free
    arrfree(nums)
    arrfree(big)
    return 0
```

Transpiles to:

```c
#include <stdio.h>
#define STB_DS_IMPLEMENTATION
#include "stb_ds.h"

int main() {
    int *nums = NULL;

    arrput(nums, 10);
    arrput(nums, 20);
    arrput(nums, 30);
    arrput(nums, 40);

    printf("length: %ld\n", arrlen(nums));

    for (int i = 0; i < arrlen(nums); i++) {
        printf("nums[%d] = %d\n", i, nums[i]);
    }

    int last = arrpop(nums);
    arrins(nums, 1, 99);
    arrdel(nums, 0);

    double *big = NULL;
    arrsetcap(big, 1000);

    arrfree(nums);
    arrfree(big);
    return 0;
}
```

### 6.3 Array of Structs

```python
struct Point:
    x: int,
    y: int

fn main() -> int:
    points: arr[Point] = NULL
    arrput(points, ((Point){1, 2}))
    arrput(points, ((Point){3, 4}))

    for i in range(arrlen(points)):
        printf("(%d, %d)\n", points[i].x, points[i].y)

    arrfree(points)
    return 0
```

### 6.4 Quick Reference

| Operation | Description |
|-----------|-------------|
| `arrput(a, val)` | Append value |
| `arrpop(a)` | Remove & return last element |
| `arrins(a, i, val)` | Insert at index `i` |
| `arrdel(a, i)` | Delete at index `i` (shift) |
| `arrdelswap(a, i)` | Delete at index `i` (swap with last, O(1)) |
| `arrlen(a)` | Length (`ptrdiff_t`) |
| `arrlenu(a)` | Length (`size_t`) |
| `arrsetcap(a, n)` | Pre-allocate capacity |
| `arrcap(a)` | Current capacity |
| `arrsetlen(a, n)` | Set length (allocate if needed) |
| `arrfree(a)` | Free and set to NULL |

---

## 7. Hash Maps — `map[K, V]`

Hash maps also use stb_ds.h. The transpiler auto-generates the backing struct that stb_ds requires.

### 7.1 Declaration

**`name: map[K, V] = NULL`** declares a hash map with key type `K` and value type `V`:

```python
scores: map[char*, int] = NULL
ages: map[int, double] = NULL
```

Transpiles to:

```c
#define STB_DS_IMPLEMENTATION
#include "stb_ds.h"
typedef struct { char * key; int value; } __map_charptr_int;
typedef struct { int key; double value; } __map_int_double;

__map_charptr_int *scores = NULL;
__map_int_double *ages = NULL;
```

The transpiler automatically detects whether the key is `char*` (string hashmap → `sh*` functions) or any other type (binary hashmap → `hm*` functions).

### 7.2 Put — Bracket Assignment

Assign with `map[key] = value`:

```python
scores["alice"] = 100
scores["bob"] = 200
ages[42] = 3.14
```

Transpiles to:

```c
shput(scores, "alice", 100);
shput(scores, "bob", 200);
hmput(ages, 42, 3.14);
```

### 7.3 Get — Bracket Access in Expressions

Read with `map[key]` anywhere in an expression:

```python
printf("alice: %d\n", scores["alice"])

total: int = scores["alice"] + scores["bob"]

if scores["alice"] > 90:
    printf("high score\n")
```

Transpiles to:

```c
printf("alice: %d\n", shget(scores, "alice"));

int total = shget(scores, "alice") + shget(scores, "bob");

if (shget(scores, "alice") > 90) {
    printf("high score\n");
}
```

### 7.4 Delete

**`del map[key]`** removes an entry:

```python
del scores["bob"]
del ages[42]
```

Transpiles to:

```c
shdel(scores, "bob");
hmdel(ages, 42);
```

### 7.5 Default Values

Set what missing keys return:

```python
config: map[char*, int] = NULL
shdefault(config, 0)
config["width"] = 1920

w: int = config["width"]
missing: int = config["nonexistent"]   // returns 0
```

Transpiles to:

```c
__map_charptr_int *config = NULL;
shdefault(config, 0);
shput(config, "width", 1920);

int w = shget(config, "width");
int missing = shget(config, "nonexistent");
```

For integer-keyed maps, use `hmdefault`:

```python
ages: map[int, double] = NULL
hmdefault(ages, -1.0)
printf("missing: %f\n", ages[9999])   // prints -1.0
```

### 7.6 Check Key Existence

Use `shgeti` / `hmgeti` — returns the index or `-1`:

```python
if shgeti(scores, "alice") >= 0:
    printf("found\n")
```

Transpiles to:

```c
if (shgeti(scores, "alice") >= 0) {
    printf("found\n");
}
```

### 7.7 Iteration

Iterate by index using `shlen` / `hmlen`. Access the underlying array directly with `.key` and `.value` — the transpiler recognizes `map[i].field` as array access and leaves it alone:

```python
for i in range(shlen(scores)):
    printf("%s -> %d\n", scores[i].key, scores[i].value)
```

Transpiles to:

```c
for (int i = 0; i < shlen(scores); i++) {
    printf("%s -> %d\n", scores[i].key, scores[i].value);
}
```

### 7.8 String Map Modes

stb_ds string maps have different memory management modes. These macros pass through directly:

```python
// Duplicate keys (safe if source strings are freed later)
names: map[char*, int] = NULL
sh_new_strdup(names)

// Arena allocation (efficient for insert-only maps)
tags: map[char*, int] = NULL
sh_new_arena(tags)
```

### 7.9 Maps as Function Parameters

Maps work in function signatures — the transpiler resolves `map[K,V]` to the generated struct pointer:

```python
fn lookup(db: map[char*, int], key: char*) -> int:
    return db[key]
```

Transpiles to:

```c
int lookup(__map_charptr_int * db, char * key) {
    return shget(db, key);
}
```

### 7.10 Free

```python
shfree(scores)      // string-keyed maps
hmfree(ages)         // any-keyed maps
```

### 7.11 Quick Reference

**String-keyed maps (`char*` key):**

| SimplC | C |
|--------|---|
| `m: map[char*, int] = NULL` | `__map_charptr_int *m = NULL;` |
| `m["key"] = val` | `shput(m, "key", val);` |
| `m["key"]` | `shget(m, "key")` |
| `del m["key"]` | `shdel(m, "key");` |
| `shlen(m)` | `shlen(m)` |
| `shgeti(m, "key")` | `shgeti(m, "key")` |
| `shdefault(m, v)` | `shdefault(m, v);` |
| `shfree(m)` | `shfree(m);` |
| `m[i].key` / `m[i].value` | `m[i].key` / `m[i].value` |

**Integer/struct-keyed maps (any non-`char*` key):**

| SimplC | C |
|--------|---|
| `m: map[int, double] = NULL` | `__map_int_double *m = NULL;` |
| `m[42] = val` | `hmput(m, 42, val);` |
| `m[42]` | `hmget(m, 42)` |
| `del m[42]` | `hmdel(m, 42);` |
| `hmlen(m)` | `hmlen(m)` |
| `hmgeti(m, 42)` | `hmgeti(m, 42)` |
| `hmdefault(m, v)` | `hmdefault(m, v);` |
| `hmfree(m)` | `hmfree(m);` |

---

## 8. Structs + Data Structures Combined

Structs, dynamic arrays, and hash maps compose naturally:

```python
struct Player:
    name: char*,
    health: int,
    x: double,
    y: double

fn main() -> int:
    // Array of structs
    players: arr[Player] = NULL
    arrput(players, ((Player){"Alice", 100, 0.0, 0.0}))
    arrput(players, ((Player){"Bob", 80, 5.0, 3.0}))

    for i in range(arrlen(players)):
        printf("%s: hp=%d\n", players[i].name, players[i].health)

    // Map for quick lookup by name
    index: map[char*, int] = NULL
    for i in range(arrlen(players)):
        index[players[i].name] = i

    idx: int = index["Alice"]
    printf("Alice is at index %d\n", idx)

    shfree(index)
    arrfree(players)
    return 0
```

---

## 9. Comments

Both C comment styles pass through unchanged:

```python
// This is a line comment

/* This is a
   block comment */
```

---

## 10. `print()` Shorthand

`print("string")` with a single string literal appends `\n` automatically:

```python
print("Hello!")
```

Transpiles to:

```c
printf("Hello!\n");
```

With format arguments, it passes through to `printf` without adding `\n`:

```python
print("%d %d\n", x, y)
```

Transpiles to:

```c
printf("%d %d\n", x, y);
```

Standard `printf` always works too — `print` is just shorthand.

---

## 11. Auto-Includes

You never write `#include`. The transpiler scans your code for function calls, type names, and keywords, then emits the correct headers:

| You write... | Transpiler adds |
|---|---|
| `printf`, `scanf`, `fopen`, `puts`, etc. | `#include <stdio.h>` |
| `malloc`, `free`, `rand`, `exit`, `atoi`, etc. | `#include <stdlib.h>` |
| `strlen`, `strcmp`, `memcpy`, `strcat`, etc. | `#include <string.h>` |
| `sin`, `cos`, `sqrt`, `pow`, `floor`, etc. | `#include <math.h>` |
| `bool`, `true`, `false` | `#include <stdbool.h>` |
| `i8`, `i32`, `u64`, etc. | `#include <stdint.h>` |
| `assert` | `#include <assert.h>` |
| `isalpha`, `toupper`, `isdigit`, etc. | `#include <ctype.h>` |
| `arr[T]`, `map[K,V]`, `arrput`, `hmput`, etc. | `#define STB_DS_IMPLEMENTATION` + `#include "stb_ds.h"` |

Example — all includes detected automatically:

```python
fn main() -> int:
    printf("pi = %f\n", 3.14)
    hyp: double = sqrt(9.0 + 16.0)
    msg: char* = "hello"
    printf("len: %zu\n", strlen(msg))
    buf: int* = malloc(10 * sizeof(int))
    free(buf)
    ok: bool = true
    val: i32 = 42
    assert(1 + 1 == 2)
    return 0
```

Transpiles to:

```c
#include <assert.h>
#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int main() {
    printf("pi = %f\n", 3.14);
    double hyp = sqrt(9.0 + 16.0);
    char * msg = "hello";
    printf("len: %zu\n", strlen(msg));
    int * buf = malloc(10 * sizeof(int));
    free(buf);
    bool ok = true;
    int32_t val = 42;
    assert(1 + 1 == 2);
    return 0;
}
```

---

## 12. Passthrough / Raw C

Any line that doesn't match a SimplC pattern passes through with auto-semicolons. This means you can freely mix raw C constructs:

```python
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
    printf("skipped\n")
    done:
    printf("done\n")

    return 0
```

Transpiles to:

```c
#include <stdio.h>

#define MAX_SIZE 100
#define SQUARE(x) ((x) * (x))

enum Color { RED, GREEN, BLUE };

typedef unsigned long ulong;

int main() {
    int buf[MAX_SIZE];
    int val = SQUARE(5);

    int x = 10;
    char * result = (x > 5) ? "big" : "small";

    int count = 0;
    do {
        printf("%d ", count);
        count++;
    } while (count < 5);

    goto done;
    printf("skipped\n");
    done:;
    printf("done\n");

    return 0;
}
```

---

## 13. Indentation & Block Rules

SimplC uses **indentation** (like Python) to define blocks. The transpiler converts indentation to `{` / `}`.

**Rules:**

- Any block-opening line ends with `:` — functions, if, else, for, while, switch, struct.
- The body must be indented more than the opening line.
- When indentation returns to the level of the opener, `}` is emitted.
- Any consistent indentation works (spaces or tabs, any width).

```python
fn foo() -> void:           // opens block
    if x > 0:               //   opens nested block
        printf("pos\n")     //     body
    else:                    //   closes if, opens else
        printf("neg\n")     //     body
                             //   closes else
                             // closes function
```

---

## 14. Semicolons

Semicolons are **auto-inserted**. You never write them. The transpiler appends `;` to any line that:

- Is not blank
- Is not a comment (`//`, `/*`, `*`)
- Is not a preprocessor directive (`#`)
- Does not end with `{`, `}`, `,`, `\`, or already end with `;`

---

## 15. Complete Example

A word frequency counter combining structs, dynamic arrays, and hash maps:

```python
fn main() -> int:
    freq: map[char*, int] = NULL
    sh_new_strdup(freq)
    shdefault(freq, 0)

    words: arr[char*] = NULL
    arrput(words, "hello")
    arrput(words, "world")
    arrput(words, "hello")
    arrput(words, "foo")
    arrput(words, "world")
    arrput(words, "hello")

    // Count frequencies
    for i in range(arrlen(words)):
        current: int = freq[words[i]]
        freq[words[i]] = current + 1

    // Print results
    printf("Word frequencies:\n")
    for i in range(shlen(freq)):
        printf("  %s: %d\n", freq[i].key, freq[i].value)

    shfree(freq)
    arrfree(words)
    return 0
```

Transpiles to:

```c
#include <stdio.h>
#define STB_DS_IMPLEMENTATION
#include "stb_ds.h"
typedef struct { char * key; int value; } __map_charptr_int;

int main() {
    __map_charptr_int *freq = NULL;
    sh_new_strdup(freq);
    shdefault(freq, 0);

    char **words = NULL;
    arrput(words, "hello");
    arrput(words, "world");
    arrput(words, "hello");
    arrput(words, "foo");
    arrput(words, "world");
    arrput(words, "hello");

    // Count frequencies
    for (int i = 0; i < arrlen(words); i++) {
        int current = shget(freq, words[i]);
        shput(freq, words[i], current + 1);
    }

    // Print results
    printf("Word frequencies:\n");
    for (int i = 0; i < shlen(freq); i++) {
        printf("  %s: %d\n", freq[i].key, freq[i].value);
    }

    shfree(freq);
    arrfree(words);
    return 0;
}
```

---

## 16. Building & Toolchain

```bash
# Transpile
python3 transpiler.py program.sc

# Transpile to specific output
python3 transpiler.py program.sc output.c

# Compile (basic)
gcc output.c -o program

# Compile with math library
gcc output.c -o program -lm

# Compile with warnings
gcc -Wall -Wextra output.c -o program -lm
```

For programs using `arr[T]` or `map[K,V]`, place `stb_ds.h` in the same directory as the output `.c` file. The transpiler emits `#define STB_DS_IMPLEMENTATION` automatically, so you only need the single header — no separate compilation step.

---

## 17. Syntax Summary

| Feature | SimplC | C |
|---------|--------|---|
| Variable | `x: int = 5` | `int x = 5;` |
| Pointer | `p: int* = &x` | `int * p = &x;` |
| Fixed array | `a: int[10]` | `int a[10];` |
| Function | `fn f(x: int) -> int:` | `int f(int x) {` |
| if | `if cond:` | `if (cond) {` |
| else if | `else if cond:` | `} else if (cond) {` |
| else | `else:` | `} else {` |
| while | `while cond:` | `while (cond) {` |
| for-range | `for i in range(n):` | `for (int i = 0; i < n; i++) {` |
| switch | `switch expr:` | `switch (expr) {` |
| struct | `struct Name:` | `typedef struct Name {` |
| print | `print("hi")` | `printf("hi\n");` |
| dyn array | `a: arr[int] = NULL` | `int *a = NULL;` |
| map decl | `m: map[char*, int] = NULL` | `__map_charptr_int *m = NULL;` |
| map put | `m["k"] = v` | `shput(m, "k", v);` |
| map get | `m["k"]` | `shget(m, "k")` |
| map del | `del m["k"]` | `shdel(m, "k");` |
| map iterate | `m[i].key` | `m[i].key` |
