// Tests for the OPC / SimplC autocomplete core in static/opc-hint.js.
//
// Run with:    node --test tests/test_hint_core.js
// or:          npm test  (if a script is added)
//
// The module is consumed through Node's `require`, which triggers the UMD
// branch that exports the pure functions.  We never touch the DOM /
// CodeMirror globals — every test works against the public pure surface.
"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");

const hint = require(path.join(__dirname, "..", "static", "opc-hint.js"));

// A minimal CodeMirror stub.  `suggest()` only needs read access — it doesn't
// actually call back into the editor, the entry.hint callbacks do (and we
// don't exercise those in unit tests).
function stubCm(text, line, ch) {
  return {
    getValue: () => text,
    getCursor: () => ({ line, ch }),
    getLine: (n) => text.split("\n")[n] || "",
    getTokenAt: () => ({}),
  };
}

// Convenience: collect just the `text` of a candidate list.
const texts = (list) => list.map((c) => c.text);

// Convenience: collect `text` and `displayText` so the user-visible label
// is covered (e.g. function signatures get appended parens).
const labels = (list) => list.map((c) => c.displayText || c.text);

// ── parseSymbols ────────────────────────────────────────────────────────────
test("parseSymbols: struct definitions and their fields", () => {
  const src = [
    "struct Point:",
    "    x: float",
    "    y: float",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.deepEqual(Object.keys(syms.structs), ["Point"]);
  assert.deepEqual(syms.structFields.Point, { x: "float", y: "float" });
});

test("parseSymbols: struct field types are kept verbatim (incl. pointers)", () => {
  const src = [
    "struct Player:",
    "    name: char*,",
    "    hp: int,",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.equal(syms.structFields.Player.name, "char*");
  assert.equal(syms.structFields.Player.hp, "int");
});

test("parseSymbols: variable declarations tie a name to a struct type", () => {
  const src = [
    "struct Point:",
    "    x: int",
    "fn main() -> int:",
    "    p: Point",
    "    return 0",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.equal(syms.structVars.p, "Point");
});

test("parseSymbols: list[T] / map[K,V] annotations drive the right bucket", () => {
  const src = [
    "fn main() -> int:",
    "    a: list[int] = []",
    "    m: map[char*, int] = {}",
    "    return 0",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.equal(syms.listVars.a, 1);
  assert.equal(syms.mapVars.m, 1);
  assert.equal(syms.structVars.a, undefined);
  assert.equal(syms.structVars.m, undefined);
});

test("parseSymbols: `file` / `OpcFile` annotations are fileVars", () => {
  const src = [
    "fn main() -> int:",
    "    f: file = read_file(\"x.txt\")",
    "    return 0",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.equal(syms.fileVars.f, 1);
});

test("parseSymbols: function parameters count as declarations", () => {
  const src = [
    "struct Vec:",
    "    x: int",
    "fn dot(a: Vec, b: Vec) -> int:",
    "    return 0",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.equal(syms.structVars.a, "Vec");
  assert.equal(syms.structVars.b, "Vec");
});

test("parseSymbols: for-loop variables are visible as vars", () => {
  const src = [
    "fn main() -> int:",
    "    for i in range(10):",
    "        print(i)",
    "    return 0",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.equal(syms.vars.i, 1);
});

test("parseSymbols: function definitions are tracked separately", () => {
  const src = [
    "fn add(a: int, b: int) -> int:",
    "    return a + b",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.equal(syms.funcs.add, 1);
});

// ── detectContext ───────────────────────────────────────────────────────────
test("detectContext: `recv.` is recognised as a member access on a struct", () => {
  const src = [
    "struct Point:",
    "    x: float",
    "fn main() -> int:",
    "    p: Point",
    "    print(p.)",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  const ctx = hint.detectContext("    print(p.", syms);
  assert.equal(ctx.kind, "member");
  assert.equal(ctx.recv, "p");
  assert.equal(ctx.container, "struct:Point");
});

test("detectContext: `recv.` on a list offers list methods", () => {
  const src = "fn f() -> int:\n    a: list[int] = []\n    a.";
  const syms = hint.parseSymbols(src);
  const ctx = hint.detectContext("    a.", syms);
  assert.equal(ctx.kind, "member");
  assert.equal(ctx.container, "list");
});

test("detectContext: `recv.` on a file offers the OpcFile fields", () => {
  const src = "fn f() -> int:\n    f: file = read_file(\"x\")\n    f.";
  const syms = hint.parseSymbols(src);
  const ctx = hint.detectContext("    f.", syms);
  assert.equal(ctx.kind, "member");
  assert.equal(ctx.container, "file");
});

test("detectContext: after `:` switches to a type context", () => {
  const syms = hint.parseSymbols("");
  assert.equal(hint.detectContext("x: ", syms).kind, "type");
  assert.equal(hint.detectContext("f(p: ", syms).kind, "type");
});

test("detectContext: after `->` switches to a type context", () => {
  const syms = hint.parseSymbols("");
  assert.equal(hint.detectContext("fn f() -> ", syms).kind, "type");
});

test("buildList: type context offers the fn(...) function-pointer snippet", () => {
  const syms = hint.parseSymbols("");
  const ctx = hint.detectContext("op: ", syms);
  const list = hint.buildList(ctx, syms);
  const fn = list.find((c) => c._filter === "fn");
  assert.ok(fn, "fn snippet should be present in type position");
  assert.equal(fn.className, "cm-hint-snippet");
});

test("detectContext: `import` prefix is its own context", () => {
  const syms = hint.parseSymbols("");
  assert.equal(hint.detectContext("import foo", syms).kind, "import");
});

test("detectContext: a bare expression falls through to `expr`", () => {
  const syms = hint.parseSymbols("");
  assert.equal(hint.detectContext("    x", syms).kind, "expr");
});

// ── chained member access ──────────────────────────────────────────────────
test("detectContext: `outer.inner.` resolves through the struct chain", () => {
  const src = [
    "struct Inner:",
    "    x: int",
    "    y: int",
    "struct Outer:",
    "    inner: Inner",
    "fn main() -> int:",
    "    o: Outer",
    "    print(o.inner.)",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  const ctx = hint.detectContext("    print(o.inner.", syms);
  assert.equal(ctx.kind, "member");
  assert.equal(ctx.recv, "inner");
  assert.equal(ctx.container, "struct:Inner");
});

test("detectContext: chained access yields the inner struct's field list", () => {
  const src = [
    "struct Inner:",
    "    x: int",
    "    y: int",
    "struct Outer:",
    "    inner: Inner",
    "fn main() -> int:",
    "    o: Outer",
    "    print(o.inner.)",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  const ctx = hint.detectContext("    print(o.inner.", syms);
  assert.deepEqual(texts(hint.buildList(ctx, syms)), ["x", "y"]);
});

test("detectContext: chained access through a list field offers list methods", () => {
  const src = [
    "struct Bag:",
    "    items: list[int]",
    "fn main() -> int:",
    "    b: Bag",
    "    b.items.",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  const ctx = hint.detectContext("    b.items.", syms);
  assert.equal(ctx.container, "list");
  assert.deepEqual(texts(hint.buildList(ctx, syms)),
                   ["append", "insert", "pop", "free"]);
});

test("resolveChainType: single typed variable → [TypeName]", () => {
  const src = "struct S:\n    x: int\nfn f() -> int:\n    s: S\n    s";
  const syms = hint.parseSymbols(src);
  assert.deepEqual(hint.resolveChainType("s", syms), ["S"]);
});

test("resolveChainType: deep chain → innermost type", () => {
  const src = [
    "struct C:",
    "    v: int",
    "struct B:",
    "    c: C",
    "struct A:",
    "    b: B",
    "fn f() -> int:",
    "    a: A",
    "    a.b.c",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.deepEqual(hint.resolveChainType("a.b.c", syms), ["C"]);
});

test("resolveChainType: dead-end link returns null", () => {
  const src = "struct S:\n    x: int\nfn f() -> int:\n    s: S\n    s.nope";
  const syms = hint.parseSymbols(src);
  assert.equal(hint.resolveChainType("s.nope", syms), null);
});

test("buildList: a fixed-size array var is offered as an iterable in expr position", () => {
  // Powers `for x in <arr>:` completion for fixed arrays (T[N]).
  const src = [
    "fn main() -> int:",
    "    nums: int[3] = {1, 2, 3}",
    "    for x in ",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  assert.equal(syms.vars.nums, 1);
  const ctx = hint.detectContext("    for x in ", syms);
  assert.equal(ctx.kind, "expr");
  assert.ok(texts(hint.buildList(ctx, syms)).includes("nums"));
});

// ── buildList ───────────────────────────────────────────────────────────────
test("buildList: struct field entries carry the field name", () => {
  const src = [
    "struct Vec2:",
    "    x: int",
    "    y: int",
    "fn main() -> int:",
    "    v: Vec2",
    "    v.",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  const ctx = hint.detectContext("    v.", syms);
  const list = hint.buildList(ctx, syms);
  assert.deepEqual(texts(list).sort(), ["x", "y"]);
  for (const c of list) {
    assert.equal(c.className, "cm-hint-prop");
  }
});

test("buildList: typed-file receiver offers data / size / ok", () => {
  const src = "fn f() -> int:\n    f: file = read_file(\"x\")\n    f.";
  const syms = hint.parseSymbols(src);
  const ctx = hint.detectContext("    f.", syms);
  assert.deepEqual(texts(hint.buildList(ctx, syms)),
                   ["data", "size", "ok"]);
});

test("buildList: unknown receiver falls back to list+map methods", () => {
  const syms = hint.parseSymbols("fn f() -> int:\n    x: int\n    x.");
  const ctx = { kind: "member", recv: "x", chain: "x", container: "any" };
  const list = texts(hint.buildList(ctx, syms));
  // Every list method and every map method should be there.
  for (const m of ["append", "insert", "pop", "default", "free"]) {
    assert.ok(list.includes(m), `expected "${m}" in ${list}`);
  }
});

test("buildList: type position suggests list / map / primitives", () => {
  const list = texts(hint.buildList({ kind: "type" }, hint.parseSymbols("")));
  for (const t of ["list", "map", "int", "float", "char", "void"]) {
    assert.ok(list.includes(t), `expected "${t}" in ${list}`);
  }
});

test("buildList: type position also includes user-defined struct names", () => {
  const src = "struct Foo:\n    x: int";
  const syms = hint.parseSymbols(src);
  const list = texts(hint.buildList({ kind: "type" }, syms));
  assert.ok(list.includes("Foo"), `expected "Foo" in ${list}`);
});

test("buildList: expression position includes functions, variables, snippets, keywords", () => {
  const src = [
    "struct S:",
    "    x: int",
    "fn greet(name: char*) -> int:",
    "    return 0",
    "fn main() -> int:",
    "    s: S",
    "    ",
  ].join("\n");
  const syms = hint.parseSymbols(src);
  const list = texts(hint.buildList({ kind: "expr" }, syms));
  for (const expected of ["greet", "s", "S", "fn", "if", "for", "print", "printf"]) {
    assert.ok(list.includes(expected), `expected "${expected}" in ${list}`);
  }
});

test("buildList: import position returns an empty list (free-form module name)", () => {
  const out = hint.buildList({ kind: "import" }, hint.parseSymbols(""));
  assert.deepEqual(out, []);
});

// ── suggest (end-to-end with a stub) ────────────────────────────────────────
test("suggest: typing `p.` on a struct variable returns only its fields", () => {
  const src = [
    "struct Point:",
    "    x: float",
    "    y: float",
    "fn main() -> int:",
    "    p: Point",
    "    print(p.)",
  ].join("\n");
  const cm = stubCm(src, 5, 12);
  const res = hint.suggest(cm);
  assert.ok(res, "expected a hint result");
  assert.deepEqual(texts(res.list).sort(), ["x", "y"]);
});

test("suggest: typing `a.` on a list returns only list methods", () => {
  const src = [
    "fn main() -> int:",
    "    a: list[int] = []",
    "    a.",
  ].join("\n");
  const cm = stubCm(src, 2, 7);
  const res = hint.suggest(cm);
  // Empty prefix → list methods are returned in alphabetical order.
  assert.deepEqual(texts(res.list).sort(),
                   ["append", "free", "insert", "pop"]);
});

test("suggest: typing `f.` on a file returns the OpcFile fields", () => {
  const src = [
    "fn main() -> int:",
    "    f: file = read_file(\"x\")",
    "    f.",
  ].join("\n");
  const cm = stubCm(src, 2, 7);
  const res = hint.suggest(cm);
  // Empty prefix → OpcFile fields are returned in alphabetical order.
  assert.deepEqual(texts(res.list).sort(), ["data", "ok", "size"]);
});

test("suggest: typing `o.inner.` walks the chain and returns Inner's fields", () => {
  const src = [
    "struct Inner:",
    "    x: int",
    "    y: int",
    "struct Outer:",
    "    inner: Inner",
    "fn main() -> int:",
    "    o: Outer",
    "    print(o.inner.)",
  ].join("\n");
  const cm = stubCm(src, 7, 18);
  const res = hint.suggest(cm);
  assert.deepEqual(texts(res.list).sort(), ["x", "y"]);
});

test("suggest: prefix filter narrows the candidate set", () => {
  const src = [
    "struct Point:",
    "    x: float",
    "    y: float",
    "    z: float",
    "fn main() -> int:",
    "    p: Point",
    "    print(p.x)",
  ].join("\n");
  // cursor after `p.x` → prefix is "x" → only `x` matches.
  const cm = stubCm(src, 6, 13);
  const res = hint.suggest(cm);
  assert.deepEqual(texts(res.list), ["x"]);
});

test("suggest: returns null inside a string / comment", () => {
  const src = "fn f() -> int:\n    s: char* = \"hello \"";
  const cm = stubCm(src, 1, 25);
  cm.getTokenAt = () => ({ type: "string" });
  assert.equal(hint.suggest(cm), null);
});

test("suggest: returns null when there are no candidates", () => {
  const src = "import ";
  const cm = stubCm(src, 0, 7);
  // `import` is its own context with an empty candidate list, so `suggest`
  // should bail out cleanly instead of returning a popup.
  assert.equal(hint.suggest(cm), null);
});
