// Custom CodeMirror mode for the OPC / SimplC language.
// Keyword and type lists mirror transpiler.py so highlighting matches semantics.
(function () {
  if (!window.CodeMirror) return;

  var keywords =
    "fn|del|import|return|if|elif|else|while|for|in|range|break|continue|" +
    "switch|case|default|goto|do|struct|enum|union|typedef|extern|static|" +
    "register|volatile|const|sizeof";

  var types =
    "i8|i16|i32|i64|u8|u16|u32|u64|int|uint|float|double|char|void|bool|" +
    "short|long|signed|unsigned|size_t|ssize_t|int8_t|int16_t|int32_t|int64_t|" +
    "uint8_t|uint16_t|uint32_t|uint64_t|FILE|list|map|file|OpcFile";

  var builtins =
    // stdio / stdlib / string / math / ctype helpers + print + stb_ds
    "print|printf|scanf|puts|putchar|getchar|gets|fopen|fclose|fread|fwrite|" +
    "fprintf|fscanf|fgets|fputs|fflush|fseek|ftell|rewind|snprintf|sprintf|" +
    "sscanf|perror|malloc|calloc|realloc|free|exit|abort|atexit|atoi|atol|" +
    "atof|strtol|strtod|rand|srand|abs|labs|qsort|bsearch|system|getenv|" +
    "strlen|strcpy|strncpy|strcat|strncat|strcmp|strncmp|strchr|strrchr|" +
    "strstr|memcpy|memmove|memset|memcmp|sin|cos|tan|asin|acos|atan|atan2|" +
    "sqrt|pow|exp|log|log10|ceil|floor|fabs|fmod|round|trunc|assert|" +
    "isalpha|isdigit|isalnum|isspace|isupper|islower|toupper|tolower|" +
    "isprint|ispunct|len|append|pop|insert|free|default|" +
    // opc_io.h file-reading helpers
    "read_file|read_lines|read_files|file_close|free_lines";

  var atoms = "true|false|NULL|stdin|stdout|stderr";

  CodeMirror.defineSimpleMode("opc", {
    start: [
      // comments
      { regex: /#.*/, token: "comment" },
      { regex: /\/\/.*/, token: "comment" },
      { regex: /\/\*/, token: "comment", next: "comment" },

      // strings & chars
      { regex: /"(?:[^\\"]|\\.)*"?/, token: "string" },
      { regex: /'(?:[^\\']|\\.)*'?/, token: "string-2" },

      // function definition name:  fn NAME(
      { regex: /(\bfn\b)(\s+)([A-Za-z_]\w*)/,
        token: ["keyword", null, "def"] },

      // type after a colon:   name: TYPE
      { regex: /(:)(\s*)([A-Za-z_]\w*)/,
        token: ["operator", null, "variable-3"], sol: false },

      // numbers (hex, float, int, with suffixes)
      { regex: /0[xX][0-9a-fA-F]+[uUlL]*/, token: "number" },
      { regex: /(?:\d+\.?\d*|\.\d+)(?:[eE][+-]?\d+)?[fFuUlL]*/, token: "number" },

      // keyword groups
      { regex: new RegExp("\\b(?:" + keywords + ")\\b"), token: "keyword" },
      { regex: new RegExp("\\b(?:" + types + ")\\b"), token: "variable-3" },
      { regex: new RegExp("\\b(?:" + atoms + ")\\b"), token: "atom" },
      { regex: new RegExp("\\b(?:" + builtins + ")\\b(?=\\s*\\()"), token: "builtin" },

      // function calls (generic)
      { regex: /[A-Za-z_]\w*(?=\s*\()/, token: "variable-2" },

      // member access .field
      { regex: /\.[A-Za-z_]\w*/, token: "property" },

      // operators
      { regex: /->|\+\+|--|==|!=|<=|>=|&&|\|\||[-+*/%=<>!&|^~?:]/, token: "operator" },

      // identifiers
      { regex: /[A-Za-z_]\w*/, token: "variable" },

      { regex: /[{}()\[\]]/, token: "bracket" },
    ],
    comment: [
      { regex: /.*?\*\//, token: "comment", next: "start" },
      { regex: /.*/, token: "comment" },
    ],
    meta: {
      lineComment: "#",
    },
  });

  CodeMirror.defineMIME("text/x-opc", "opc");
})();
