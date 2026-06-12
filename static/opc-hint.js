// ── OPC / SimplC autocomplete ────────────────────────────────────────────────
// Context-aware completion for the custom "opc" CodeMirror mode, in the spirit
// of PyCharm's editor: keywords, types, builtins and block snippets, plus
// symbols (functions, structs, variables) parsed live from the open buffer.
//
//   * after `:`  / `->`        → types  (incl. list[…] / map[…, …]) + structs
//   * after `recv.`            → list / map methods (or struct fields)
//   * elsewhere                → keywords, atoms, builtins, snippets, symbols
//
// Registered as CodeMirror.hint.opc so `cm.showHint({hint: CodeMirror.hint.opc})`
// works.  app.js wires up the automatic popup and Ctrl-Space.
(function () {
  if (!window.CodeMirror) return;
  var Pos = CodeMirror.Pos;

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
    print: "(value)", printf: "(fmt, …)", scanf: "(fmt, …)", puts: "(s)",
    putchar: "(c)", getchar: "()", gets: "(s)", fopen: "(path, mode)",
    fclose: "(fp)", fread: "(ptr, sz, n, fp)", fwrite: "(ptr, sz, n, fp)",
    fprintf: "(fp, fmt, …)", fscanf: "(fp, fmt, …)", fgets: "(s, n, fp)",
    fputs: "(s, fp)", fflush: "(fp)", fseek: "(fp, off, whence)", ftell: "(fp)",
    rewind: "(fp)", snprintf: "(s, n, fmt, …)", sprintf: "(s, fmt, …)",
    sscanf: "(s, fmt, …)", perror: "(s)",
    malloc: "(size)", calloc: "(n, size)", realloc: "(ptr, size)", free: "(ptr)",
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
    read_file: '(path[, "mmap"|"pread"|"stream"])', read_lines: "(path)",
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

  // ── parse symbols from the buffer ──────────────────────────────────────────
  function parseSymbols(code) {
    var funcs = {}, structs = {}, vars = {}, listVars = {}, mapVars = {}, m;

    var reFn = /\bfn\s+([A-Za-z_]\w*)/g;
    while ((m = reFn.exec(code))) funcs[m[1]] = 1;

    var reStruct = /\bstruct\s+([A-Za-z_]\w*)/g;
    while ((m = reStruct.exec(code))) structs[m[1]] = 1;

    // declarations / params / struct fields:  name : type
    var reDecl = /(?:^|[\n;(,])\s*([A-Za-z_]\w*)\s*:\s*([A-Za-z_][\w\[\], *]*)/g;
    while ((m = reDecl.exec(code))) {
      var nm = m[1], ty = m[2];
      vars[nm] = 1;
      if (/^list\s*\[/.test(ty)) listVars[nm] = 1;
      else if (/^map\s*\[/.test(ty)) mapVars[nm] = 1;
    }

    // loop variables:  for i in …
    var reFor = /\bfor\s+([A-Za-z_]\w*)\s+in\b/g;
    while ((m = reFor.exec(code))) vars[m[1]] = 1;

    return { funcs: funcs, structs: structs, vars: vars,
             listVars: listVars, mapVars: mapVars };
  }

  // ── context detection ──────────────────────────────────────────────────────
  function detectContext(pre, syms) {
    var mem = /([A-Za-z_]\w*)\s*\.\s*\w*$/.exec(pre);
    if (mem && /\.\s*\w*$/.test(pre)) {
      var recv = mem[1];
      var kind = syms.listVars[recv] ? "list"
               : syms.mapVars[recv] ? "map" : "any";
      return { kind: "member", recv: recv, container: kind };
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

  function buildList(ctx, syms) {
    var out = [];
    var k;

    if (ctx.kind === "member") {
      var methods = ctx.container === "list" ? LIST_METHODS
                  : ctx.container === "map" ? MAP_METHODS
                  : LIST_METHODS.concat(MAP_METHODS);
      methods.forEach(function (mm) { out.push(methodEntry(mm[0], mm[1], mm[2])); });
      // unknown receiver: also offer struct field names seen elsewhere
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
  function opcHint(cm) {
    var cur = cm.getCursor();
    var token = cm.getTokenAt(cur);
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

  CodeMirror.registerHelper("hint", "opc", opcHint);
})();
