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

## 6. Dynamic Arrays — `list[T]`

Dynamic arrays use [stb_ds.h](https://github.com/nothings/stb). Place `stb_ds.h` in the same directory as your output `.c` file.

### 6.1 Declaration

**`name: list[T] = []`** declares an empty dynamic array of element type `T`. You can initialize it with values using a list literal, and/or pre-allocate capacity by writing `(N)` after the type:

```python
nums: list[int] = []
words: list[char*] = []
points: list[Point] = []
vals: list[int] = [1, 2, 3]
big: list[double](1000) = []
both: list[int](10) = [1, 2, 3]
```

Transpiles to:

```c
int *nums = NULL;
char **words = NULL;
Point *points = NULL;
int *vals = NULL;
arrput(vals, 1);
arrput(vals, 2);
arrput(vals, 3);
double *big = NULL;
arrsetcap(big, 1000);
int *both = NULL;
arrsetcap(both, 10);
arrput(both, 1);
arrput(both, 2);
arrput(both, 3);
```

The transpiler auto-emits `#define STB_DS_IMPLEMENTATION` and `#include "stb_ds.h"`.

### 6.2 Operations

```python
fn main() -> int:
    nums: list[int] = []

    // Append
    nums.append(10)
    nums.append(20)
    nums.append(30)
    nums.append(40)

    // Length
    printf("length: %ld\n", len(nums))

    // Iterate (normal array indexing)
    for i in range(len(nums)):
        printf("nums[%d] = %d\n", i, nums[i])

    // Pop last element
    last: int = nums.pop()

    // Insert at index
    nums.insert(1, 99)

    // Delete at index
    del nums[0]

    // Pre-allocate capacity at declaration
    big: list[double](1000) = []

    // Free
    nums.free()
    big.free()
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

`len()` works anywhere in an expression — inside `range()`, conditions, assignments.

### 6.3 Array of Structs

```python
struct Point:
    x: int,
    y: int

fn main() -> int:
    points: list[Point] = []
    points.append(((Point){1, 2}))
    points.append(((Point){3, 4}))

    for i in range(len(points)):
        printf("(%d, %d)\n", points[i].x, points[i].y)

    points.free()
    return 0
```

### 6.4 Quick Reference

| SimplC | C | Description |
|--------|---|-------------|
| `a: list[T] = []` | `T *a = NULL;` | Declare empty dynamic array |
| `a: list[T] = [v1, v2, ...]` | `T *a = NULL; arrput(a, v1); ...` | Declare and initialize with values |
| `a: list[T](N) = []` | `T *a = NULL; arrsetcap(a, N);` | Declare with initial capacity |
| `a.append(val)` | `arrput(a, val)` | Append value |
| `a.pop()` | `arrpop(a)` | Remove & return last element |
| `a.insert(i, val)` | `arrins(a, i, val)` | Insert at index `i` |
| `del a[i]` | `arrdel(a, i)` | Delete at index `i` (shift) |
| `arrdelswap(a, i)` | `arrdelswap(a, i)` | Delete at index `i` (swap with last, O(1)) |
| `len(a)` | `arrlen(a)` | Length (`ptrdiff_t`) |
| `arrlenu(a)` | `arrlenu(a)` | Length (`size_t`) |
| `arrcap(a)` | `arrcap(a)` | Current capacity |
| `arrsetlen(a, n)` | `arrsetlen(a, n)` | Set length (allocate if needed) |
| `a.free()` | `arrfree(a)` | Free and set to NULL |

---

## 7. Hash Maps — `map[K, V]`

Hash maps use stb_ds.h under the hood — all stb_ds details are hidden.

### 7.1 Declaration

**`name: map[K, V] = {}`** declares a hash map with key type `K` and value type `V`. It can also be initialized with key/value pairs using a map literal:

```python
scores: map[char*, int] = {}
ages: map[int, double] = {}
prices: map[char*, int] = {"apple": 1, "pear": 2}
```

The literal form transpiles to a `NULL` declaration followed by one `shput`/`hmput` per pair:

```c
__map_charptr_int *prices = NULL;
shput(prices, "apple", 1);
shput(prices, "pear", 2);
```

### 7.2 Put, Get, Delete

```python
scores["alice"] = 100          // put
scores["bob"] = 200
x: int = scores["alice"]       // get
del scores["bob"]              // delete
```

### 7.3 Length, Existence

```python
printf("count: %d\n", len(scores))

if "alice" in scores:
    printf("found\n")

if "dave" not in scores:
    printf("missing\n")
```

Transpiles to:

```c
printf("count: %d\n", shlen(scores));

if (shgeti(scores, "alice") >= 0) {
    printf("found\n");
}

if (shgeti(scores, "dave") < 0) {
    printf("missing\n");
}
```

### 7.4 Default Values

A map can return a fixed value for any key that's missing — useful for
counters, sparse arrays, and "have we seen this?" flags. There are two
ways to set the default.

**At declaration time** — pass the default inside `()` right after the
type:

```python
config: map[char*, int](-1) = {}
config["width"] = 1920

missing: int = config["nonexistent"]   // returns -1
```

This is shorthand for declaring the map and then immediately calling
`m.default(...)`. The same form works without an initializer
(`config: map[char*, int](-1)`) and with a literal of pairs
(`prices: map[char*, int](-1) = {"apple": 1, "pear": 2}`).

**After declaration** — call `m.default(val)` at any point:

```python
config: map[char*, int] = {}
config.default(0)
config["width"] = 1920

missing: int = config["nonexistent"]   // returns 0
```

Works the same for integer-keyed maps:

```python
ages: map[int, double](-1.0) = {}
printf("missing: %f\n", ages[9999])   // prints -1.0
```

### 7.5 Iteration

Iterate by index; access entries with `.key` and `.value`:

```python
for i in range(len(scores)):
    printf("%s -> %d\n", scores[i].key, scores[i].value)
```

Transpiles to:

```c
for (int i = 0; i < shlen(scores); i++) {
    printf("%s -> %d\n", scores[i].key, scores[i].value);
}
```

### 7.6 Free

```python
scores.free()
ages.free()
```

### 7.7 Maps as Function Parameters

`map[K,V]` works in function signatures:

```python
fn lookup(db: map[char*, int], key: char*) -> int:
    return db[key]
```

### 7.8 Quick Reference

| SimplC | Description |
|--------|-------------|
| `m: map[K, V] = {}` | Declare a map |
| `m: map[K, V] = {k1: v1, ...}` | Declare and initialize with pairs |
| `m: map[K, V](default) = {}` | Declare a map with a default for missing keys |
| `m[key] = val` | Insert / update |
| `m[key]` | Get value |
| `del m[key]` | Delete entry |
| `len(m)` | Number of entries |
| `key in m` | True if key exists |
| `key not in m` | True if key absent |
| `m.default(val)` | Value for missing keys |
| `m.free()` | Free the map |
| `m[i].key` / `m[i].value` | Access entry during iteration |

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
    players: list[Player] = []
    players.append(((Player){"Alice", 100, 0.0, 0.0}))
    players.append(((Player){"Bob", 80, 5.0, 3.0}))

    for i in range(len(players)):
        printf("%s: hp=%d\n", players[i].name, players[i].health)

    // Map for quick lookup by name
    index: map[char*, int] = {}
    for i in range(len(players)):
        index[players[i].name] = i

    idx: int = index["Alice"]
    printf("Alice is at index %d\n", idx)

    shfree(index)
    players.free()
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

`print(...)` maps to `printf` and appends `\n` to the format string for you —
both for a bare string and for the formatted form:

```python
print("Hello!")
print("%d %d", x, y)
```

Transpiles to:

```c
printf("Hello!\n");
printf("%d %d\n", x, y);
```

If the format string already ends with `\n`, none is added — so you never get a
double newline:

```python
print("%d\n", x)        // → printf("%d\n", x);  (unchanged)
```

The newline is only appended when the first argument is a string literal. If you
pass a runtime string (`print(msg)`), it is forwarded unchanged — add your own
`\n`, or use `printf` directly. Standard `printf` always works too — `print` is
just shorthand.

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
| `list[T]`, `map[K,V]`, `arrput`, `hmput`, etc. | `#define STB_DS_IMPLEMENTATION` + `#include "stb_ds.h"` |
| `read_file`, `read_lines`, `read_files`, etc. | `#include "opc_io.h"` (see §12) |

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

## 12. Reading Files

SimplC ships a small, portable file-reading runtime (`opc_io.h`, auto-included and copied next to your output just like `stb_ds.h`). One verb covers the common cases, and a **strategy hint** lets you pick the fastest mechanism for your access pattern — without writing any platform code. Each strategy maps to the matching OS primitive (and an OS-specific fast path where one is faster), falling back gracefully everywhere else.

### 12.1 Choosing a strategy

Use this decision tree to pick the read that fits your use case:

```
Reading many files at once, want to saturate an NVMe / keep the queue full?
├─ yes → read_files(paths)              // io_uring batch on Linux (opt-in), else sequential
└─ no  → Random access (jumping around the file), not pure front-to-back?
         ├─ yes → Does the file comfortably fit in RAM?
         │        ├─ yes → read_file(path, "mmap")    // zero-copy memory map
         │        └─ no  → read_file(path, "pread")   // positioned reads, large blocks
         └─ no  → Line-oriented text you want split into lines?
                  ├─ yes → read_lines(path)           // buffered getline → list[char*]
                  └─ no  → read_file(path)            // whole file, large sequential blocks
```

| SimplC | Use case | Mechanism |
|--------|----------|-----------|
| `read_file(path)` | Slurp a whole file, scan it front-to-back | `read()` in large blocks (POSIX) / `ReadFile` (Windows) |
| `read_file(path, "mmap")` | Random access over a file that fits in RAM | `mmap` (POSIX) / file mapping (Windows) — zero-copy |
| `read_file(path, "pread")` | Random access over a large file | positioned `pread` |
| `read_file(path, "stream")` | Buffered standard I/O | `fread` |
| `read_file(path, "uring")` | Single file, Linux NVMe fast path | io_uring (opt-in, falls back to `pread`) |
| `read_lines(path)` | Line-oriented text | `getline` → `list[char*]` |
| `read_files(paths)` | Many files concurrently | io_uring batch (Linux, opt-in) / sequential |

Unknown strategy strings fall back to the default — a typo changes performance, never correctness.

### 12.2 Whole-file reads — `read_file`

`read_file` returns an **`OpcFile`** with three fields: `data` (the bytes, NUL-terminated for convenience except under `"mmap"`), `size` (byte count), and `ok` (`1` on success). Release it with `file_close`.

```python
fn main() -> int:
    f: OpcFile = read_file("data.txt")
    if !f.ok:
        printf("could not read file\n")
        return 1

    printf("read %ld bytes\n", f.size)
    printf("%s", f.data)

    file_close(f)
    return 0
```

Transpiles to:

```c
#include <stdio.h>
#include "opc_io.h"

int main() {
    OpcFile f = opc_read_file("data.txt", "auto");
    if (!f.ok) {
        printf("could not read file\n");
        return 1;
    }
    printf("read %ld bytes\n", f.size);
    printf("%s", f.data);
    opc_file_close(f);
    return 0;
}
```

Pass a strategy as the second argument for a different access pattern — the return type and `file_close` are identical:

```python
big: OpcFile = read_file("huge.bin", "mmap")   // zero-copy, random access
process(big.data, big.size)
file_close(big)
```

### 12.3 Line-oriented text — `read_lines`

`read_lines` returns a `list[char*]` of lines (the trailing newline is stripped), so all the usual `list` operations — `len()`, indexing, iteration — work directly. Release it with `free_lines` (which frees the strings **and** the list).

```python
fn main() -> int:
    lines: list[char*] = read_lines("notes.txt")
    printf("%ld lines\n", len(lines))
    for i in range(len(lines)):
        printf("%d: %s\n", i, lines[i])
    free_lines(lines)
    return 0
```

### 12.4 Many files at once — `read_files`

`read_files` takes a `list[char*]` of paths and returns a `list[OpcFile]` in the same order. On Linux built with io_uring (see §12.5) the reads are issued concurrently to keep the device queue full; everywhere else they run sequentially. Close each `OpcFile` and free the list.

```python
fn main() -> int:
    paths: list[char*] = ["a.txt", "b.txt", "c.txt"]
    files: list[OpcFile] = read_files(paths)

    for i in range(len(files)):
        printf("%s: %ld bytes\n", paths[i], files[i].size)
        file_close(files[i])

    paths.free()
    files.free()
    return 0
```

### 12.5 Enabling the Linux io_uring fast path

io_uring is **opt-in** so the default build stays dependency-free. Enable it by compiling with the flag and linking `liburing`:

```bash
gcc output.c -o program -DOPC_USE_URING -luring
```

With `OPC_USE_URING` defined, `read_files` submits all reads through io_uring; without it (or on non-Linux hosts), the exact same SimplC source reads the files sequentially. You don't change a line of code to move between the two.

### 12.6 Quick Reference

| SimplC | C | Description |
|--------|---|-------------|
| `f: OpcFile = read_file(path)` | `opc_read_file(path, "auto")` | Whole file, sequential |
| `read_file(path, "mmap")` | `opc_read_file(path, "mmap")` | Zero-copy memory map |
| `read_file(path, "pread")` | `opc_read_file(path, "pread")` | Positioned reads |
| `read_file(path, "stream")` | `opc_read_file(path, "stream")` | Buffered `fread` |
| `f.data` / `f.size` / `f.ok` | struct fields | Bytes / length / success flag |
| `file_close(f)` | `opc_file_close(f)` | Free or unmap an `OpcFile` |
| `read_lines(path)` | `opc_read_lines(path)` | Text → `list[char*]` |
| `free_lines(lines)` | `opc_free_lines(lines)` | Free a `read_lines` result |
| `read_files(paths)` | `opc_read_files(paths)` | Many files → `list[OpcFile]` |

> A user-defined `fn read_file(...)` (or any name above) shadows the builtin — your own function wins, and no `opc_io.h` is pulled in.

---

## 13. Passthrough / Raw C

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

## 14. Indentation & Block Rules

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

## 15. Semicolons

Semicolons are **auto-inserted**. You never write them. The transpiler appends `;` to any line that:

- Is not blank
- Is not a comment (`//`, `/*`, `*`)
- Is not a preprocessor directive (`#`)
- Does not end with `{`, `}`, `,`, `\`, or already end with `;`

---

## 16. Complete Example

A word frequency counter combining structs, dynamic arrays, and hash maps:

```python
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
    printf("Word frequencies:\n")
    for i in range(len(freq)):
        printf("  %s: %d\n", freq[i].key, freq[i].value)

    freq.free()
    words.free()
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

## 17. Building & Toolchain

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

# Enable the Linux io_uring fast path for read_files (see §12.5)
gcc output.c -o program -DOPC_USE_URING -luring
```

For programs using `list[T]` or `map[K,V]`, place `stb_ds.h` in the same directory as the output `.c` file. The transpiler emits `#define STB_DS_IMPLEMENTATION` automatically, so you only need the single header — no separate compilation step. Programs that read files (§12) also use the bundled `opc_io.h`. Both headers are copied next to your output `.c` automatically on transpile, so you never copy them by hand.

---

## 18. Syntax Summary

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
| dyn array | `a: list[int] = []` | `int *a = NULL;` |
| arr append | `a.append(x)` | `arrput(a, x);` |
| arr pop | `a.pop()` | `arrpop(a)` |
| arr insert | `a.insert(i, x)` | `arrins(a, i, x);` |
| arr delete | `del a[i]` | `arrdel(a, i);` |
| arr length | `len(a)` | `arrlen(a)` |
| arr free | `a.free()` | `arrfree(a);` |
| map decl | `m: map[K, V] = {}` | typedef + pointer |
| map decl + default | `m: map[K, V](val) = {}` | typedef + pointer + `shdefault/hmdefault` |
| map put | `m[key] = val` | `shput/hmput` |
| map get | `m[key]` | `shget/hmget` |
| map del | `del m[key]` | `shdel/hmdel` |
| map length | `len(m)` | `shlen/hmlen` |
| map exists | `key in m` | `shgeti/hmgeti >= 0` |
| map absent | `key not in m` | `shgeti/hmgeti < 0` |
| map default | `m.default(val)` | `shdefault/hmdefault` |
| map free | `m.free()` | `shfree/hmfree` |
| map iterate | `m[i].key` / `m[i].value` | direct array access |
| read file | `f: OpcFile = read_file(path)` | `opc_read_file(path, "auto")` |
| read (strategy) | `read_file(path, "mmap")` | `opc_read_file(path, "mmap")` |
| close file | `file_close(f)` | `opc_file_close(f)` |
| read lines | `read_lines(path)` | `opc_read_lines(path)` → `list[char*]` |
| free lines | `free_lines(lines)` | `opc_free_lines(lines)` |
| read many | `read_files(paths)` | `opc_read_files(paths)` → `list[OpcFile]` |
