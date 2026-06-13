// ── OPC / SimplC autocomplete ────────────────────────────────────────────────
// Context-aware completion for the custom "opc" CodeMirror mode, in the spirit
// of PyCharm's editor: keywords, types, builtins and block snippets, plus
// symbols (functions, structs, variables) parsed live from the open buffer.
//
//   * after `:`  / `->`        → types  (incl. list[…] / map[…, …]) + structs
//   * after `recv.`            → list / map methods (or struct fields)
//   * else                      → keywords, atoms, builtins, snippets, symbols
//
// Registered as CodeMirror.hint.opc so `cm.showHint({hint: CodeMirror.hint.opc})`
// works.  app.js wires up the automatic popup and Ctrl-Space.
//
// The file is written as a UMD module: in the browser it self-registers with
// CodeMirror, in Node.js (tests) it exports the pure core so it can be unit
// tested without a DOM.
(function (root, factory) {
  "use strict";
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    var core = factory();
    root.OpcHint = core;
    if (root.CodeMirror) {
      root.CodeMirror.registerHelper("hint", "opc", function (cm) {
        return core.suggest(cm);
      });
    }
  }
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";
  var Pos = (typeof CodeMirror !== "undefined" && CodeMirror.Pos) ||
            function (line, ch) { return { line: line, ch: ch }; };

  // ── vocabulary (mirrors transpiler.py / opc-mode.js) ───────────────────────
  var KEYWORDS = ("fn del import return if elif else while for in range break " +
    "continue switch case default goto do struct enum union typedef extern " +
    "static register volatile const sizeof").split(" ");

  var TYPES = ("i8 i16 i32 i64 u8 u16 u32 u64 int uint float double char void " +
    "bool short long signed unsigned size_t ssize_t int8_t int16_t int32_t " +
    "int64_t uint8_t uint16_t uint32_t uint64_t FILE file OpcFile").split(" ");

  var ATOMS = "true false NULL stdin stdout stderr".split(" ");

  // builtin call signatures — used for the display label and a hint of intent.
  var SIGS = {
    print: "(fmt, …)", printf: "(fmt, …)", scanf: "(fmt, …)", puts: "(s)",
    putchar: "(c)", getchar: "()", gets: "(s)", fopen: "(path, mode)",
    fclose: "(fp)", fread: "(ptr, sz, n, fp)", fwrite: "(ptr, sz, n, fp)",
    fprintf: "(fp, fmt, …)", fscanf: "(fp, fmt, …)", fgets: "(s, n, fp)",
    fputs: "(s, fp)", fflush: "(fp)", fseek: "(fp, off, whence)", ftell: "(fp)",
    rewind: "(fp)", snprintf: "(s, n, fmt, …)", sprintf: "(s, fmt, …)",
    sscanf: "(s, fmt, …)", perror: "(s)",
    malloc: "(count)", calloc: "(count)", realloc: "(ptr, size)", free: "(ptr)",
    exit: "(code)", abort: "()", atexit: "(fn)", atoi: "(s)", atol: "(s)",
    atof: "(s)", strtol: "(s, end, base)", strtod: "(s, end)", rand: "()",
    srand: "(seed)", abs: "(x)", labs: "(x)", qsort: "(base, n, sz, cmp)",
    bsearch: "(key, base, n, sz, cmp)", system: "(cmd)", getenv: "(name)",
    strlen: "(s)", strcpy: "(dst, src)", strncpy: "(dst, src, n)",
    strcat: "(dst, src)", strncat: "(dst, src, n)", strcmp: "(a, b)",
    strncmp: "(a, b, n)", strchr: "(s, c)", strrchr: "(s, c)", strstr: "(s, sub)",
    memcpy: "(dst, src, n)", memmove: "(dst, src, n)", memset: "(s, c, n)",
    memcmp: "(a, b, n)",
    sin: "(x)", cos: "(x)", tan: "(x)", asin: "(x)", acos: "(x)", atan: "(x)",
    atan2: "(y, x)", sqrt: "(x)", pow: "(b, e)", exp: "(x)", log: "(x)",
    log10: "(x)", ceil: "(x)", floor: "(x)", fabs: "(x)", fmod: "(a, b)",
    round: "(x)", trunc: "(x)",
    assert: "(cond)",
    isalpha: "(c)", isdigit: "(c)", isalnum: "(c)", isspace: "(c)",
    isupper: "(c)", islower: "(c)", toupper: "(c)", tolower: "(c)",
    isprint: "(c)", ispunct: "(c)",
    len: "(container)", range: "(stop)", sizeof: "(type)",
    read_file: '(path[, "mmap"|"pread"|"stream"|"uring"])', read_lines: "(path)",
    read_files: "(paths)", file_close: "(file)", free_lines: "(lines)",
  };

  var BUILTINS = Object.keys(SIGS).filter(function (n) {
    return n !== "range" && n !== "sizeof"; // those read better as keywords
  });

  // ── snippets (block constructs) ────────────────────────────────────────────
  // `$|` marks where the caret lands after insertion.
  var SNIPPETS = [
    ["fn", "fn $|() -> i32:", "function definition"],
    ["main", "fn main() -> i32:\n    $|", "program entry point"],
    ["for", "for $| in range():", "range loop"],
    ["fore", "for $| in range(0, , 1):", "range loop (start, stop, step)"],
    ["forl", "for $| in :", "iterate over a list (for elem in list:)"],
    ["if", "if $|:", "if statement"],
    ["elif", "elif $|:", "else-if branch"],
    ["else", "else:\n    $|", "else branch"],
    ["while", "while $|:", "while loop"],
    ["switch", "switch $|:", "switch statement"],
    ["struct", "struct $|:", "struct definition"],
    ["import", "import $|", "include a module"],
    ["print", "print($|)", "print with newline"],
  ];

  // type-position snippets for the container generics.
  var TYPE_SNIPPETS = [
    ["list", "list[$|]", "dynamic array"],
    ["map", "map[$|, ]", "hash map"],
    ["fn", "fn($|) -> ", "function pointer type"],
  ];

  // ── completion helpers ─────────────────────────────────────────────────────
  function renderer(meta) {
    return function (el, data, comp) {
      var label = document.createElement("span");
      label.className = "cm-hint-label";
      label.textContent = comp.displayText || comp.text;
      var tag = document.createElement("span");
      tag.className = "cm-hint-meta";
      tag.textContent = meta || "";
      el.appendChild(label);
      el.appendChild(tag);
    };
  }

  // plain word: keyword / type / atom / symbol
  function word(text, meta, cls) {
    return {
      text: text, displayText: text, _filter: text,
      className: cls, render: renderer(meta),
    };
  }

  // function-like entry: inserts `name()` and drops the caret between the parens
  function call(name, meta, cls) {
    var sig = SIGS[name] || "()";
    return {
      text: name, displayText: name + sig, _filter: name,
      className: cls || "cm-hint-fn", render: renderer(meta),
      hint: function (cm, data, comp) {
        var from = data.from, to = data.to;
        var lineRest = cm.getLine(to.line).slice(to.ch);
        var addParens = lineRest.charAt(0) !== "(";
        cm.replaceRange(comp.text + (addParens ? "()" : ""), from, to, "complete");
        var caret = from.ch + comp.text.length + (addParens ? 1 : 0);
        cm.setCursor(Pos(from.line, caret));
      },
    };
  }

  // snippet entry: expands a template, re-indenting and positioning the caret
  function snippet(trigger, template, meta) {
    return {
      text: trigger, displayText: trigger, _filter: trigger,
      className: "cm-hint-snippet", render: renderer(meta + " ▸"),
      hint: function (cm, data, comp) {
        var from = data.from, to = data.to;
        var indent = (/^\s*/.exec(cm.getLine(from.line)) || [""])[0];
        var tpl = template.replace(/\n/g, "\n" + indent);
        var caret = tpl.indexOf("$|");
        tpl = tpl.replace("$|", "");
        cm.replaceRange(tpl, from, to, "complete");
        if (caret >= 0) {
          var before = tpl.slice(0, caret).split("\n");
          var line = from.line + before.length - 1;
          var ch = before.length === 1
            ? from.ch + before[0].length
            : before[before.length - 1].length;
          cm.setCursor(Pos(line, ch));
        }
      },
    };
  }

  // Strip trailing whitespace and a stray trailing comma from the type
  // capture (struct field lines often end with a comma, e.g. `x: int,`).
  // We intentionally keep a trailing `*` so `char*` stays `char*` — the `*`
  // is a real part of the type expression, not punctuation.
  function normalizeType(ty) {
    return String(ty || "").replace(/[\s,]+$/, "");
  }

  // ── parse symbols from the buffer ──────────────────────────────────────────
  //
  // `structFields[sname]` is a map of `fieldName -> fieldType`, where
  // `fieldType` is the *type expression* as written (e.g. "Inner", "list[int]",
  // "char*").  The detection logic uses that to offer chained field access
  // — typing `outer.inner.` knows to look up `inner`'s declared type and
  // surface the fields of *that* struct, not the outer one.
  function parseSymbols(code) {
    var funcs = {}, structs = {}, vars = {}, listVars = {}, mapVars = {};
    var fileVars = {}, structVars = {}, structFields = {};
    var m, i, line, lineIndent, structIndent, fm, sname;

    // struct definitions + their indented field bodies
    var lines = code.split("\n");
    for (i = 0; i < lines.length; i++) {
      var sm = /^\s*struct\s+([A-Za-z_]\w*)\s*:\s*$/.exec(lines[i]);
      if (!sm) continue;
      sname = sm[1];
      structs[sname] = 1;
      structFields[sname] = {};
      structIndent = (/^[ \t]*/.exec(lines[i]) || [""])[0].length;
      for (var j = i + 1; j < lines.length; j++) {
        line = lines[j];
        if (line.trim() === "") continue;
        lineIndent = (/^[ \t]*/.exec(line) || [""])[0].length;
        if (lineIndent <= structIndent) break;
        fm = /^\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*(?:\s*\*)?(?:\s*\[[^\]]*\])?)/.exec(line);
        if (fm) structFields[sname][fm[1]] = normalizeType(fm[2]);
      }
    }

    var reFn = /\bfn\s+([A-Za-z_]\w*)/g;
    while ((m = reFn.exec(code))) funcs[m[1]] = 1;

    // declarations / params / struct fields:  name : type
    //
    // The type capture is intentionally tight — `name : T` not
    // `name : T, something_else`.  The old greedy `[\w\[\], *]*` happily
    // swallowed the next parameter (e.g. `(a: Vec, b: Vec)` matched `a`
    // with type `Vec, b`), which broke structVar tracking for any param
    // past the first.  The new pattern: name, optional pointer, optional
    // `[K, V, …]` generic — stops at the first character that can't be in
    // a type expression.
    var reDecl = /(?:^|[\n;(,])\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_]\w*(?:\s*\*)?(?:\s*\[[^\]]*\])?)/g;
    while ((m = reDecl.exec(code))) {
      var nm = m[1], ty = normalizeType(m[2]);
      vars[nm] = 1;
      if (/^list\s*\[/.test(ty)) listVars[nm] = 1;
      else if (/^map\s*\[/.test(ty)) mapVars[nm] = 1;
      else if (ty === "file" || ty === "OpcFile") fileVars[nm] = 1;
      else if (structs[ty]) structVars[nm] = ty;
    }

    // loop variables:  for i in …
    var reFor = /\bfor\s+([A-Za-z_]\w*)\s+in\b/g;
    while ((m = reFor.exec(code))) vars[m[1]] = 1;

    return { funcs: funcs, structs: structs, vars: vars,
             listVars: listVars, mapVars: mapVars,
             fileVars: fileVars, structVars: structVars,
             structFields: structFields };
  }

  // Walk a `a.b.c` chain and return the type of the last segment, or null
  // when any link is unknown.  `structFields` is the per-struct map of
  // field-name -> field-type produced by `parseSymbols`.  When more than one
  // struct defines a field with the same name the result is the union
  // (de-duplicated) of those field types so the caller can still offer hints.
  function resolveChainType(chain, syms) {
    if (!chain) return null;
    var segs = chain.split(".").filter(function (s) { return s.length > 0; });
    if (!segs.length) return null;

    // First segment may be a typed variable; everything after must come from
    // struct field types we already parsed.
    var candidates = [];
    var headTy = syms.structVars[segs[0]];
    if (headTy) candidates.push(headTy);
    // If the head isn't a typed variable, fall through to "any field of any
    // struct" by seeding candidates with every struct name.
    if (!candidates.length) {
      for (var s in syms.structs) candidates.push(s);
    }
    if (!candidates.length) return null;

    for (var k = 1; k < segs.length; k++) {
      var field = segs[k];
      var next = {};
      for (var i = 0; i < candidates.length; i++) {
        var cname = candidates[i];
        var fmap = syms.structFields[cname];
        if (!fmap) continue;
        var fty = fmap[field];
        if (fty && !next[fty]) next[fty] = 1;
      }
      candidates = Object.keys(next);
      if (!candidates.length) return null;
    }
    return candidates;
  }

  // ── context detection ──────────────────────────────────────────────────────
  //
  // We distinguish three shapes of the "recv." pattern so chained access
  // (`outer.inner.`) gets field suggestions for `inner`'s struct, not the
  // outer one:
  //   * `recv.`             → single segment: type comes from structVars
  //   * `a.b.c.`            → multi segment: walk the chain
  //   * `recv.` (unknown)   → fall through to "any"
  function detectContext(pre, syms) {
    var mem = /([A-Za-z_]\w*(?:\s*\.\s*[A-Za-z_]\w*)*)\s*\.\s*\w*$/.exec(pre);
    if (mem && /\.\s*\w*$/.test(pre)) {
      var chain = mem[1].replace(/\s+/g, "");
      var segs = chain.split(".");
      var recv = segs[segs.length - 1];

      if (segs.length === 1) {
        // Single receiver — the easy case.
        var kind = syms.listVars[recv] ? "list"
                 : syms.mapVars[recv] ? "map"
                 : syms.fileVars[recv] ? "file"
                 : syms.structVars[recv] ? "struct:" + syms.structVars[recv]
                 : "any";
        return { kind: "member", recv: recv, chain: chain, container: kind };
      }

      // Multi-segment chain — walk it and figure out what the last segment
      // resolves to.  `resolveChainType` returns an array of candidate types
      // (because two different structs may have a field with the same name);
      // we collapse the list into the kinds the builder understands.
      var types = resolveChainType(chain, syms) || [];
      if (types.length === 1) {
        var t = types[0];
        if (/^list\s*\[/.test(t)) {
          return { kind: "member", recv: recv, chain: chain, container: "list" };
        }
        if (/^map\s*\[/.test(t)) {
          return { kind: "member", recv: recv, chain: chain, container: "map" };
        }
        if (t === "file" || t === "OpcFile") {
          return { kind: "member", recv: recv, chain: chain, container: "file" };
        }
        if (syms.structs[t]) {
          return { kind: "member", recv: recv, chain: chain,
                   container: "struct:" + t };
        }
      }
      if (types.length > 1) {
        // Multiple possible struct types — surface the union of fields.
        return { kind: "member", recv: recv, chain: chain,
                 container: "structs:" + types.join("|") };
      }
      return { kind: "member", recv: recv, chain: chain, container: "any" };
    }
    if (/^\s*import\s+\w*$/.test(pre)) return { kind: "import" };
    if (/->\s*[\w *]*$/.test(pre) ||
        /(?:^|[(,])\s*[A-Za-z_]\w*\s*:\s*[\w\[\], *]*$/.test(pre)) {
      return { kind: "type" };
    }
    return { kind: "expr" };
  }

  // ── build candidate list for a context ─────────────────────────────────────
  var LIST_METHODS = [
    ["append", "(value)", "list — push to end"],
    ["insert", "(index, value)", "list — insert at index"],
    ["pop", "()", "list — remove & return last"],
    ["free", "()", "list — release storage"],
  ];
  var MAP_METHODS = [
    ["default", "(value)", "map — default for missing keys"],
    ["free", "()", "map — release storage"],
  ];
  // OpcFile's user-facing fields (mirrors opc_io.h). The internal _opc_*
  // bookkeeping is omitted on purpose.
  var FILE_FIELDS = [
    ["data", "char* — file bytes (NUL-terminated except mmap)"],
    ["size", "long — number of bytes in `data`"],
    ["ok",   "int — 1 on success, 0 on failure"],
  ];

  function methodEntry(name, sig, meta) {
    return {
      text: name, displayText: name + sig, _filter: name,
      className: "cm-hint-method", render: renderer(meta),
      hint: function (cm, data, comp) {
        var from = data.from, to = data.to;
        var addParens = cm.getLine(to.line).slice(to.ch).charAt(0) !== "(";
        cm.replaceRange(comp.text + (addParens ? "()" : ""), from, to, "complete");
        cm.setCursor(Pos(from.line, from.ch + comp.text.length + (addParens ? 1 : 0)));
      },
    };
  }

  function fieldEntry(name, meta, cls) {
    return {
      text: name, displayText: name, _filter: name,
      className: cls || "cm-hint-field", render: renderer(meta),
      hint: function (cm, data, comp) {
        var from = data.from, to = data.to;
        cm.replaceRange(comp.text, from, to, "complete");
        cm.setCursor(Pos(from.line, from.ch + comp.text.length));
      },
    };
  }

  // For "structs:A|B" contexts we offer the *union* of the named structs'
  // fields, with the source struct name as the metadata.  This is what makes
  // `outer.inner.` still useful when `inner` exists on more than one struct.
  function buildStructUnion(types, syms) {
    var out = [];
    var seen = {};
    types.forEach(function (t) {
      var fmap = syms.structFields[t] || {};
      for (var f in fmap) {
        if (seen[f]) continue;
        seen[f] = 1;
        out.push(fieldEntry(f, "field of " + t, "cm-hint-prop"));
      }
    });
    return out;
  }

  function buildList(ctx, syms) {
    var out = [];
    var k;

    if (ctx.kind === "member") {
      // Typed file: offer the OpcFile fields, not list/map methods.
      if (ctx.container === "file") {
        FILE_FIELDS.forEach(function (ff) { out.push(fieldEntry(ff[0], ff[1])); });
        return out;
      }
      // Typed struct: offer that struct's fields.
      if (typeof ctx.container === "string" &&
          ctx.container.indexOf("struct:") === 0) {
        var sname = ctx.container.slice("struct:".length);
        var fields = syms.structFields[sname] || {};
        for (k in fields) out.push(fieldEntry(k, "field of " + sname, "cm-hint-prop"));
        return out;
      }
      // Union of typed structs (chained access whose target could be one
      // of several structs): merge their fields.
      if (typeof ctx.container === "string" &&
          ctx.container.indexOf("structs:") === 0) {
        var types = ctx.container.slice("structs:".length).split("|");
        return buildStructUnion(types, syms);
      }
      // list / map / unknown: container methods, plus (for unknown) the names
      // of vars seen elsewhere so a typed-but-unrecognized receiver still gets
      // some hints.
      var methods = ctx.container === "list" ? LIST_METHODS
                  : ctx.container === "map" ? MAP_METHODS
                  : LIST_METHODS.concat(MAP_METHODS);
      methods.forEach(function (mm) { out.push(methodEntry(mm[0], mm[1], mm[2])); });
      if (ctx.container === "any") {
        for (k in syms.vars) out.push(word(k, "field", "cm-hint-prop"));
      }
      return out;
    }

    if (ctx.kind === "type") {
      TYPE_SNIPPETS.forEach(function (s) { out.push(snippet(s[0], s[1], s[2])); });
      TYPES.forEach(function (t) { out.push(word(t, "type", "cm-hint-type")); });
      for (k in syms.structs) out.push(word(k, "struct", "cm-hint-type"));
      return out;
    }

    if (ctx.kind === "import") return out; // free-form module name

    // expression / statement position
    for (k in syms.vars) {
      if (!syms.funcs[k] && !syms.structs[k]) out.push(word(k, "var", "cm-hint-var"));
    }
    for (k in syms.funcs) out.push(call(k, "fn", "cm-hint-fn"));
    for (k in syms.structs) out.push(word(k, "struct", "cm-hint-type"));
    SNIPPETS.forEach(function (s) { out.push(snippet(s[0], s[1], s[2])); });
    KEYWORDS.forEach(function (w) { out.push(word(w, "keyword", "cm-hint-kw")); });
    TYPES.forEach(function (t) { out.push(word(t, "type", "cm-hint-type")); });
    ATOMS.forEach(function (a) { out.push(word(a, "const", "cm-hint-atom")); });
    BUILTINS.forEach(function (b) { out.push(call(b, "builtin", "cm-hint-builtin")); });
    return out;
  }

  // ── main hint function ─────────────────────────────────────────────────────
  //
  // Designed to work both with a real CodeMirror instance (browser) and a
  // minimal stub (Node.js tests).  The stub only needs:
  //   - getCursor()        → { line, ch }
  //   - getLine(n)         → string
  //   - getTokenAt(pos)    → { type } | {}
  //   - getValue()         → full source
  //   - replaceRange, setCursor (used by entry.hint, not by suggest itself)
  function suggest(cm) {
    var cur = cm.getCursor();
    var token = cm.getTokenAt(cur) || {};
    if (token.type === "string" || token.type === "string-2" ||
        token.type === "comment") return null;

    var line = cm.getLine(cur.line);
    var pre = line.slice(0, cur.ch);
    var wm = /[A-Za-z_]\w*$/.exec(pre);
    var prefix = wm ? wm[0] : "";
    var from = Pos(cur.line, cur.ch - prefix.length);

    var syms = parseSymbols(cm.getValue());
    var ctx = detectContext(pre, syms);
    var candidates = buildList(ctx, syms);

    var lc = prefix.toLowerCase();
    var seen = {};
    var list = [];
    candidates.forEach(function (c) {
      var key = (c._filter || c.text);
      if (seen[key]) return;
      var f = key.toLowerCase();
      // prefix match ranks first; substring match still surfaces (PyCharm-like)
      var rank = f.indexOf(lc) === 0 ? 0 : (lc && f.indexOf(lc) > 0 ? 1 : (lc ? 2 : 0));
      if (lc && rank === 2) return;
      seen[key] = 1;
      c._rank = rank;
      list.push(c);
    });

    list.sort(function (a, b) {
      if (a._rank !== b._rank) return a._rank - b._rank;
      return (a._filter || a.text).localeCompare(b._filter || b.text);
    });

    if (!list.length) return null;
    return { list: list, from: from, to: cur };
  }

  return {
    // core (pure, testable)
    parseSymbols: parseSymbols,
    detectContext: detectContext,
    buildList: buildList,
    resolveChainType: resolveChainType,
    suggest: suggest,
    // entry builders (also useful from tests)
    word: word,
    call: call,
    snippet: snippet,
    methodEntry: methodEntry,
    fieldEntry: fieldEntry,
    // vocabulary (handy for tests and other IDE tooling)
    KEYWORDS: KEYWORDS,
    TYPES: TYPES,
    ATOMS: ATOMS,
    BUILTINS: BUILTINS,
    SNIPPETS: SNIPPETS,
    TYPE_SNIPPETS: TYPE_SNIPPETS,
    LIST_METHODS: LIST_METHODS,
    MAP_METHODS: MAP_METHODS,
    FILE_FIELDS: FILE_FIELDS,
  };
});
