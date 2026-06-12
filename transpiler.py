#!/usr/bin/env python3
"""
SimplC -> C Transpiler
Converts a simplified, Python-inspired C dialect into compilable C code.
Supports stb_ds dynamic arrays and hash maps via list[T] and map[K,V] syntax.
"""

import os
import re
import sys


class SimplCTranspiler:
    STDINT_TYPES = {
        'i8': 'int8_t', 'i16': 'int16_t', 'i32': 'int32_t', 'i64': 'int64_t',
        'u8': 'uint8_t', 'u16': 'uint16_t', 'u32': 'uint32_t', 'u64': 'uint64_t',
    }

    STDIO_FUNCS = {'printf', 'scanf', 'puts', 'putchar', 'getchar', 'gets',
                   'fopen', 'fclose', 'fread', 'fwrite', 'fprintf', 'fscanf',
                   'fgets', 'fputs', 'fflush', 'fseek', 'ftell', 'rewind',
                   'snprintf', 'sprintf', 'sscanf', 'perror', 'print'}

    STDLIB_FUNCS = {'malloc', 'calloc', 'realloc', 'free', 'exit', 'abort',
                    'atexit', 'atoi', 'atol', 'atof', 'strtol', 'strtod',
                    'rand', 'srand', 'abs', 'labs', 'qsort', 'bsearch',
                    'system', 'getenv'}

    STRING_FUNCS = {'strlen', 'strcpy', 'strncpy', 'strcat', 'strncat',
                    'strcmp', 'strncmp', 'strchr', 'strrchr', 'strstr',
                    'memcpy', 'memmove', 'memset', 'memcmp'}

    MATH_FUNCS = {'sin', 'cos', 'tan', 'asin', 'acos', 'atan', 'atan2',
                  'sqrt', 'pow', 'exp', 'log', 'log10', 'ceil', 'floor',
                  'fabs', 'fmod', 'round', 'trunc'}

    BOOL_KEYWORDS = {'true', 'false', 'bool'}
    ASSERT_FUNCS = {'assert'}
    CTYPE_FUNCS = {'isalpha', 'isdigit', 'isalnum', 'isspace', 'isupper',
                   'islower', 'toupper', 'tolower', 'isprint', 'ispunct'}

    # stb_ds macro names that should NOT get semicolons suppressed or mangled
    STBDS_FUNCS = {
        'arrput', 'arrpush', 'arrpop', 'arrfree', 'arrlen', 'arrlenu',
        'arrins', 'arrinsn', 'arrdel', 'arrdeln', 'arrdelswap',
        'arrsetlen', 'arrsetcap', 'arrcap', 'arraddnptr', 'arraddnindex',
        'hmput', 'hmputs', 'hmget', 'hmgets', 'hmgetp', 'hmgeti',
        'hmdel', 'hmlen', 'hmlenu', 'hmfree', 'hmdefault', 'hmdefaults',
        'hmget_ts', 'hmgeti_ts', 'hmgetp_ts', 'hmgetp_null',
        'shput', 'shputs', 'shget', 'shgets', 'shgetp', 'shgeti',
        'shdel', 'shlen', 'shlenu', 'shfree', 'shdefault', 'shdefaults',
        'shgetp_null', 'sh_new_arena', 'sh_new_strdup',
        'stbds_rand_seed',
    }

    RESERVED = {'case', 'default', 'goto', 'struct', 'enum', 'union',
                'typedef', 'extern', 'static', 'register', 'volatile',
                'const', 'return', 'if', 'else', 'while', 'for',
                'switch', 'do', 'break', 'continue', 'fn', 'del'}

    def __init__(self):
        self.needed_includes = set()
        self.user_imports = set()
        self.struct_names = set()
        self.map_decls = {}        # var_name -> (key_type, val_type, struct_name, is_string_key)
        self.arr_decls = set()     # var names declared as arr[T]
        self.generated_map_structs = {}  # struct_name -> typedef line
        self.prototypes = []
        self.struct_definitions = []
        self.current_struct_lines = []

    # ── type helpers ──────────────────────────────────────────────

    def _sanitize_struct_tag(self, raw: str) -> str:
        """Turn a C type like 'char *' into a safe identifier fragment."""
        return raw.replace(' ', '').replace('*', 'ptr').replace('[', '_').replace(']', '_')

    def resolve_type(self, raw_type: str) -> str:
        # list[T] → T *
        arr_m = re.match(r'^list\[(.+)\]$', raw_type.strip())
        if arr_m:
            inner = self.resolve_type(arr_m.group(1).strip())
            if inner.endswith('*'):
                return inner + '*'
            return inner + ' *'

        # map[K,V] → handled elsewhere (we return the generated struct ptr)
        map_m = re.match(r'^map\[(.+?),\s*(.+)\]$', raw_type.strip())
        if map_m:
            key_t = self.resolve_type(map_m.group(1).strip())
            val_t = self.resolve_type(map_m.group(2).strip())
            sname = self._map_struct_name(key_t, val_t)
            self._ensure_map_struct(key_t, val_t, sname)
            return sname + ' *'

        arr_match = re.match(r'^(.+?)(\[.+\])$', raw_type.strip())
        if arr_match:
            return self.resolve_type(arr_match.group(1)) + arr_match.group(2)
        if raw_type.endswith('*'):
            base = self.resolve_type(raw_type[:-1].strip())
            if base.endswith('*'):
                return base + '*'
            return base + ' *'
        stripped = raw_type.strip()
        if stripped in self.STDINT_TYPES:
            self.needed_includes.add('stdint')
            return self.STDINT_TYPES[stripped]
        if stripped == 'bool':
            self.needed_includes.add('stdbool')
        if stripped in self.struct_names:
            return stripped
        return stripped

    def _map_struct_name(self, key_type: str, val_type: str) -> str:
        return '__map_' + self._sanitize_struct_tag(key_type) + '_' + self._sanitize_struct_tag(val_type)

    def _is_string_key(self, key_type: str) -> bool:
        return key_type.strip() in ('char *', 'char*')

    def _ensure_map_struct(self, key_type: str, val_type: str, struct_name: str):
        if struct_name not in self.generated_map_structs:
            guard = f"OPC_MAP_{struct_name}"
            self.generated_map_structs[struct_name] = (
                f'#ifndef {guard}\n'
                f'#define {guard}\n'
                f'typedef struct {struct_name} {{ {key_type} key; {val_type} value; }} {struct_name};\n'
                f'#endif'
            )
            self.needed_includes.add('stb_ds')

    # ── auto-include detection ────────────────────────────────────

    _STRING_OR_CHAR_LITERAL = re.compile(
        r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\''
    )

    def detect_auto_includes(self, code: str):
        # Replace string and char literals with empty placeholders so that
        # identifiers inside them (e.g. `printf("free")`) are not treated
        # as if they were top-level function calls.
        stripped = self._STRING_OR_CHAR_LITERAL.sub('""', code)
        # Method-call syntax: `var.free(` is the list/map `.free()`, not the
        # stdlib `free` function. Skip identifiers preceded by `.`.
        ids = set(re.findall(r'(?<!\.)\b([a-zA-Z_]\w*)\s*\(', stripped))
        words = set(re.findall(r'(?<![\w.])\b([a-zA-Z_]\w*)\b', stripped))
        if ids & self.STDIO_FUNCS:   self.needed_includes.add('stdio')
        if ids & self.STDLIB_FUNCS:  self.needed_includes.add('stdlib')
        if ids & self.STRING_FUNCS:  self.needed_includes.add('string')
        if ids & self.MATH_FUNCS:    self.needed_includes.add('math')
        if words & self.BOOL_KEYWORDS: self.needed_includes.add('stdbool')
        if ids & self.ASSERT_FUNCS:  self.needed_includes.add('assert')
        if ids & self.CTYPE_FUNCS:   self.needed_includes.add('ctype')
        if ids & self.STBDS_FUNCS:   self.needed_includes.add('stb_ds')
        # list[] / map[] in source also trigger stb_ds
        if re.search(r'\blist\[', code) or re.search(r'\bmap\[', code):
            self.needed_includes.add('stb_ds')

    # ── utility ───────────────────────────────────────────────────

    def _split_args(self, s: str) -> list:
        depth = 0; parts = []; cur = []
        for ch in s:
            if ch in '([': depth += 1; cur.append(ch)
            elif ch in ')]': depth -= 1; cur.append(ch)
            elif ch == ',' and depth == 0: parts.append(''.join(cur)); cur = []
            else: cur.append(ch)
        if cur: parts.append(''.join(cur))
        return parts

    def _find_bracket_expr(self, s: str, start: int) -> str | None:
        """Given s[start] == '[', return contents up to matching ']'."""
        if start >= len(s) or s[start] != '[':
            return None
        depth = 0
        i = start
        while i < len(s):
            if s[i] == '[': depth += 1
            elif s[i] == ']':
                depth -= 1
                if depth == 0:
                    return s[start+1:i]
            i += 1
        return None

    def _find_paren_content(self, s: str, start: int):
        """Given s[start] == '(', return (content, end_pos) or None."""
        if start >= len(s) or s[start] != '(':
            return None
        depth = 0
        i = start
        while i < len(s):
            if s[i] in '([': depth += 1
            elif s[i] in ')]':
                depth -= 1
                if depth == 0:
                    return (s[start+1:i], i+1)
            i += 1
        return None

    # ── transform: map put  (name[key] = val) ────────────────────

    def try_map_put(self, s):
        """Match: mapvar[key_expr] = value_expr"""
        m = re.match(r'^(\s*)(\w+)\[', s)
        if not m:
            return None
        indent, name = m.group(1), m.group(2)
        if name not in self.map_decls:
            return None
        # find the bracket expression
        bracket_start = m.end() - 1  # position of '['
        key_expr = self._find_bracket_expr(s, bracket_start)
        if key_expr is None:
            return None
        rest_start = bracket_start + len(key_expr) + 2  # past the ']'
        rest = s[rest_start:].strip()
        if not rest.startswith('='):
            return None
        val_expr = rest[1:].strip()
        is_str = self.map_decls[name][3]
        func = 'shput' if is_str else 'hmput'
        return (f'{indent}{func}({name}, {key_expr.strip()}, {val_expr})', False)

    # ── transform: del name[key/index] ───────────────────────────

    def try_del(self, s):
        m = re.match(r'^(\s*)del\s+(\w+)\[', s)
        if not m:
            return None
        indent, name = m.group(1), m.group(2)
        bracket_start = s.index('[', m.start(2))
        key_expr = self._find_bracket_expr(s, bracket_start)
        if key_expr is None:
            return None
        if name in self.map_decls:
            is_str = self.map_decls[name][3]
            func = 'shdel' if is_str else 'hmdel'
            return (f'{indent}{func}({name}, {key_expr.strip()})', False)
        if name in self.arr_decls:
            return (f'{indent}arrdel({name}, {key_expr.strip()})', False)
        return None

    # ── inline rewriting: map[key] reads in expressions ──────────

    def rewrite_map_gets(self, line: str) -> str:
        """Replace mapvar[expr] with shget/hmget(mapvar, expr) in rvalue positions."""
        for var, (kt, vt, sn, is_str) in self.map_decls.items():
            func = 'shget' if is_str else 'hmget'
            result = line
            search_start = 0
            replacements = []
            while True:
                idx = result.find(var + '[', search_start)
                if idx == -1:
                    break
                if idx > 0 and (result[idx-1].isalnum() or result[idx-1] == '_'):
                    search_start = idx + len(var)
                    continue
                bracket_pos = idx + len(var)
                key_expr = self._find_bracket_expr(result, bracket_pos)
                if key_expr is None:
                    search_start = bracket_pos + 1
                    continue
                end_pos = bracket_pos + len(key_expr) + 2  # after ']'
                if end_pos < len(result) and result[end_pos] == '.':
                    search_start = end_pos
                    continue
                replacements.append((idx, end_pos, f'{func}({var}, {key_expr.strip()})'))
                search_start = end_pos

            for start, end, repl in reversed(replacements):
                result = result[:start] + repl + result[end:]
            line = result
        return line

    # ── inline rewriting: Pythonic arr methods ────────────────────

    def rewrite_arr_methods(self, line: str) -> str:
        if not self.arr_decls:
            return line

        result = line

        # len(arr_var) → arrlen(arr_var)
        parts = []
        i = 0
        while i < len(result):
            m = re.search(r'\blen\(', result[i:])
            if not m:
                parts.append(result[i:])
                break
            base = i + m.start()
            paren = i + m.end() - 1
            parts.append(result[i:base])
            pc = self._find_paren_content(result, paren)
            if pc and pc[0].strip() in self.arr_decls:
                parts.append(f'arrlen({pc[0]})')
                i = pc[1]
            else:
                parts.append('len(')
                i = paren + 1
        result = ''.join(parts)

        # arr_var.method(args) → stb_ds macro
        METHOD_MAP = {
            'append': ('arrput',  True),
            'insert': ('arrins',  True),
            'pop':    ('arrpop',  False),
            'free':   ('arrfree', False),
        }
        for var in self.arr_decls:
            for method, (macro, pass_args) in METHOD_MAP.items():
                pat = re.compile(rf'\b{re.escape(var)}\.{method}\(')
                parts = []
                i = 0
                while i < len(result):
                    m = pat.search(result, i)
                    if not m:
                        parts.append(result[i:])
                        break
                    parts.append(result[i:m.start()])
                    paren = m.end() - 1
                    pc = self._find_paren_content(result, paren)
                    if pc is None:
                        parts.append(result[m.start():m.end()])
                        i = m.end()
                        continue
                    if pass_args and pc[0].strip():
                        parts.append(f'{macro}({var}, {pc[0]})')
                    else:
                        parts.append(f'{macro}({var})')
                    i = pc[1]
                result = ''.join(parts)

        return result

    # ── inline rewriting: Pythonic map methods ───────────────────

    def rewrite_map_methods(self, line: str) -> str:
        if not self.map_decls:
            return line

        result = line

        # len(map_var) → shlen(map_var) / hmlen(map_var)
        parts = []
        i = 0
        while i < len(result):
            m = re.search(r'\blen\(', result[i:])
            if not m:
                parts.append(result[i:])
                break
            base = i + m.start()
            paren = i + m.end() - 1
            parts.append(result[i:base])
            pc = self._find_paren_content(result, paren)
            if pc and pc[0].strip() in self.map_decls:
                var = pc[0].strip()
                _, _, _, is_str = self.map_decls[var]
                parts.append(f'{"shlen" if is_str else "hmlen"}({pc[0]})')
                i = pc[1]
            else:
                parts.append('len(')
                i = paren + 1
        result = ''.join(parts)

        for var, (kt, vt, sn, is_str) in self.map_decls.items():
            geti     = 'shgeti'   if is_str else 'hmgeti'
            free_f   = 'shfree'   if is_str else 'hmfree'
            default_f = 'shdefault' if is_str else 'hmdefault'
            vp = re.escape(var)

            result = re.sub(
                rf'(\b\w+\b|"[^"]*")\s+not\s+in\s+\b{vp}\b',
                lambda m, v=var, g=geti: f'{g}({v}, {m.group(1)}) < 0',
                result
            )
            result = re.sub(
                rf'(\b\w+\b|"[^"]*")\s+in\s+\b{vp}\b',
                lambda m, v=var, g=geti: f'{g}({v}, {m.group(1)}) >= 0',
                result
            )

            pat = re.compile(rf'\b{vp}\.default\(')
            parts = []
            i = 0
            while i < len(result):
                m = pat.search(result, i)
                if not m:
                    parts.append(result[i:])
                    break
                parts.append(result[i:m.start()])
                paren = m.end() - 1
                pc = self._find_paren_content(result, paren)
                if pc is None:
                    parts.append(result[m.start():m.end()])
                    i = m.end()
                    continue
                parts.append(f'{default_f}({var}, {pc[0]})')
                i = pc[1]
            result = ''.join(parts)

            result = re.sub(rf'\b{vp}\.free\(\)', f'{free_f}({var})', result)

        return result

    # ── transform: imports ────────────────────────────────────────

    def try_import(self, s):
        m = re.match(r'^(\s*)import\s+([a-zA-Z0-9_]+)\s*$', s)
        if not m: return None
        indent, name = m.group(1), m.group(2)
        self.user_imports.add(name)
        return (f'{indent}#include "{name}.h"', False)

    # ── transform: function definition ────────────────────────────

    def try_function(self, s):
        m = re.match(r'^(\s*)fn\s+(\w+)\s*\(([^)]*)\)\s*->\s*(\S+)\s*:\s*$', s)
        if not m: return None
        indent, name, pr, ret = m.group(1), m.group(2), m.group(3).strip(), self.resolve_type(m.group(4))
        cp = []
        if pr:
            for p in self._split_args(pr):
                p = p.strip()
                pm = re.match(r'^(\w+)\s*:\s*(.+)$', p)
                if pm:
                    pn, raw_t = pm.group(1), pm.group(2).strip()
                    pt = self.resolve_type(raw_t)
                    self._register_container_param(pn, raw_t)
                    arr = re.match(r'^(.+?)(\[.+\])$', pt)
                    if arr: cp.append(f'{arr.group(1)} {pn}{arr.group(2)}')
                    else: cp.append(f'{pt} {pn}')
                else: cp.append(p)

        func_sig = f'{ret} {name}({", ".join(cp)})'
        if name != 'main':
            self.prototypes.append(func_sig + ';')

        return (f'{indent}{func_sig}', True)

    def _register_container_param(self, name: str, raw_type: str) -> None:
        """If `raw_type` is a `list[T]` or `map[K, V]`, register `name` in
        `arr_decls` / `map_decls` so the function body can use the usual
        method-call and `name[key]` shorthand. Without this, parameter-typed
        containers are invisible to the rewrite passes.
        """
        list_m = re.match(r'^list\[(.+)\]$', raw_type.strip())
        if list_m:
            self.resolve_type(list_m.group(1).strip())
            self.arr_decls.add(name)
            self.needed_includes.add('stb_ds')
            return
        map_m = re.match(r'^map\[(.+?),\s*(.+)\]$', raw_type.strip())
        if map_m:
            key_t = self.resolve_type(map_m.group(1).strip())
            val_t = self.resolve_type(map_m.group(2).strip())
            sname = self._map_struct_name(key_t, val_t)
            self._ensure_map_struct(key_t, val_t, sname)
            is_str = self._is_string_key(key_t)
            self.map_decls[name] = (key_t, val_t, sname, is_str)

    # ── transform: for-range ──────────────────────────────────────

    def try_for_range(self, s):
        m = re.match(r'^(\s*)for\s+(\w+)\s+in\s+range\((.+)\)\s*:\s*$', s)
        if not m: return None
        indent, var = m.group(1), m.group(2)
        args = self._split_args(m.group(3))
        if len(args) == 1: start, end, step = '0', args[0].strip(), '1'
        elif len(args) == 2: start, end, step = args[0].strip(), args[1].strip(), '1'
        elif len(args) == 3: start, end, step = args[0].strip(), args[1].strip(), args[2].strip()
        else: return None
        neg = step.startswith('-')
        sa = step.lstrip('-')
        if step == '1': inc = f'{var}++'
        elif step == '-1': inc = f'{var}--'
        elif neg: inc = f'{var} -= {sa}'
        else: inc = f'{var} += {step}'
        cmp = '>' if neg else '<'
        return (f'{indent}for (int {var} = {start}; {var} {cmp} {end}; {inc})', True)

    # ── transform: else-if / else ─────────────────────────────────

    def try_else_if(self, s):
        m = re.match(r'^(\s*)elif\s+(.+):\s*$', s)
        if not m: return None
        return (f'{m.group(1)}else if ({m.group(2).strip()})', 'else_block')

    def try_else(self, s):
        m = re.match(r'^(\s*)else\s*:\s*$', s)
        if not m: return None
        return (f'{m.group(1)}else', 'else_block')

    # ── transform: if / while / switch ────────────────────────────

    def try_control(self, s):
        m = re.match(r'^(\s*)(if|while|switch)\s+(.+):\s*$', s)
        if not m: return None
        return (f'{m.group(1)}{m.group(2)} ({m.group(3).strip()})', True)

    def try_for_plain(self, s):
        m = re.match(r'^(\s*)for\s+(.+):\s*$', s)
        if not m: return None
        return (f'{m.group(1)}for ({m.group(2).strip()})', True)

    # ── transform: variable declarations ──────────────────────────

    def try_variable(self, s):
        # name: type = value
        m = re.match(r'^(\s*)(\w+)\s*:\s*(.+?)\s*=\s*(.+)$', s)
        if m:
            indent, name, raw, val = m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip()
            if name in self.RESERVED: return None

            arr_m = re.match(r'^list\[(.+)\]$', raw)
            if arr_m:
                elem_t = self.resolve_type(arr_m.group(1).strip())
                self.arr_decls.add(name)
                self.needed_includes.add('stb_ds')
                star = '*' if elem_t.endswith('*') else ' *'
                cap_m = re.match(r'^\[\s*(\d+)\s*\]$', val)
                empty_m = re.match(r'^\[\s*\]$', val)
                if empty_m:
                    return (f'{indent}{elem_t}{star}{name} = NULL', False)
                elif cap_m:
                    cap = cap_m.group(1)
                    return (f'{indent}{elem_t}{star}{name} = NULL;\n{indent}arrsetcap({name}, {cap})', False)
                else:
                    return (f'{indent}{elem_t}{star}{name} = {val}', False)

            map_m = re.match(r'^map\[(.+?),\s*(.+)\]$', raw)
            if map_m:
                key_t = self.resolve_type(map_m.group(1).strip())
                val_t = self.resolve_type(map_m.group(2).strip())
                sname = self._map_struct_name(key_t, val_t)
                self._ensure_map_struct(key_t, val_t, sname)
                is_str = self._is_string_key(key_t)
                self.map_decls[name] = (key_t, val_t, sname, is_str)
                return (f'{indent}{sname} *{name} = {val}', False)

            ct = self.resolve_type(raw)
            arr = re.match(r'^(.+?)(\[.+\])$', ct)
            if arr: return (f'{indent}{arr.group(1)} {name}{arr.group(2)} = {val}', False)
            return (f'{indent}{ct} {name} = {val}', False)

        # name: type  (no initializer)
        m = re.match(r'^(\s*)(\w+)\s*:\s*(\S+)\s*$', s)
        if m:
            indent, name, raw = m.group(1), m.group(2), m.group(3).strip()
            if name in self.RESERVED: return None

            arr_m = re.match(r'^list\[(.+)\]$', raw)
            if arr_m:
                elem_t = self.resolve_type(arr_m.group(1).strip())
                self.arr_decls.add(name)
                self.needed_includes.add('stb_ds')
                if elem_t.endswith('*'):
                    return (f'{indent}{elem_t}*{name}', False)
                return (f'{indent}{elem_t} *{name}', False)

            map_m = re.match(r'^map\[(.+?),\s*(.+)\]$', raw)
            if map_m:
                key_t = self.resolve_type(map_m.group(1).strip())
                val_t = self.resolve_type(map_m.group(2).strip())
                sname = self._map_struct_name(key_t, val_t)
                self._ensure_map_struct(key_t, val_t, sname)
                is_str = self._is_string_key(key_t)
                self.map_decls[name] = (key_t, val_t, sname, is_str)
                return (f'{indent}{sname} *{name}', False)

            ct = self.resolve_type(raw)
            arr = re.match(r'^(.+?)(\[.+\])$', ct)
            if arr: return (f'{indent}{arr.group(1)} {name}{arr.group(2)}', False)
            return (f'{indent}{ct} {name}', False)

        return None

    # ── transform: print() shorthand ──────────────────────────────

    def try_print(self, s):
        m = re.match(r'^(\s*)print\((.+)\)\s*$', s)
        if not m: return None
        indent, args = m.group(1), m.group(2)
        if re.match(r'^".*"$', args.strip()):
            inner = args.strip()[1:-1]
            return (f'{indent}printf("{inner}\\n")', False)
        return (f'{indent}printf({args})', False)

    # ── transform: struct definition ──────────────────────────────

    def try_struct(self, s):
        m = re.match(r'^(\s*)struct\s+(\w+)\s*:\s*$', s)
        if not m: return None
        indent, name = m.group(1), m.group(2)
        self.struct_names.add(name)
        return (f'{indent}typedef struct {name}', 'struct_block', name)

    def try_struct_field(self, s):
        indent = ' ' * (len(s) - len(s.lstrip()))
        stripped = s.strip().rstrip(',')
        m = re.match(r'^(\w+)\s*:\s*(.+)$', stripped)
        if not m: return None
        name, raw = m.group(1), m.group(2).strip()
        if name in self.RESERVED: return None
        ct = self.resolve_type(raw)
        arr = re.match(r'^(.+?)(\[.+\])$', ct)
        if arr: return f'{indent}{arr.group(1)} {name}{arr.group(2)};'
        return f'{indent}{ct} {name};'

    def _pre_scan_structs(self, source: str):
        for m in re.finditer(r'^[ \t]*struct\s+(\w+)\s*:', source, re.MULTILINE):
            self.struct_names.add(m.group(1))

    # ── main transpile ────────────────────────────────────────────

    def transpile(self, source: str) -> str:
        self.needed_includes = set()
        self.user_imports = set()
        self.struct_names = set()
        self.map_decls = {}
        self.arr_decls = set()
        self.generated_map_structs = {}
        self.prototypes = []
        self.struct_definitions = []
        self.current_struct_lines = []
        self._pre_scan_structs(source)
        self.detect_auto_includes(source)

        transforms = [
            self.try_import,
            self.try_del,
            self.try_map_put,
            self.try_function,
            self.try_for_range,
            self.try_else_if,
            self.try_else,
            self.try_control,
            self.try_for_plain,
            self.try_variable,
            self.try_print,
        ]

        lines = source.splitlines()
        output = []
        block_indents = []

        for line in lines:
            stripped = line.rstrip()
            if not stripped:
                output.append('')
                continue

            indent = len(stripped) - len(stripped.lstrip())

            # Close blocks when we dedent
            while block_indents and indent <= block_indents[-1][0]:
                lvl, btype = block_indents.pop()
                if isinstance(btype, tuple) and btype[0] == 'struct':
                    sname = btype[1]
                    output.append(' ' * lvl + '} ' + sname + ';')
                    output.append(f"#endif // OPC_STRUCT_{sname}")
                    
                    self.current_struct_lines.append('} ' + sname + ';')
                    guard = f"OPC_STRUCT_{sname}"
                    struct_def = "\n".join([f"#ifndef {guard}", f"#define {guard}"] + self.current_struct_lines + [f"#endif"])
                    self.struct_definitions.append(struct_def)
                    self.current_struct_lines = []
                else:
                    output.append(' ' * lvl + '}')

            # Check if we're inside a struct block
            in_struct = block_indents and isinstance(block_indents[-1][1], tuple) and block_indents[-1][1][0] == 'struct'

            if in_struct:
                field = self.try_struct_field(stripped)
                if field:
                    output.append(field)
                    self.current_struct_lines.append("    " + field.lstrip())
                else:
                    semi_field = self._semi(stripped)
                    output.append(semi_field)
                    self.current_struct_lines.append("    " + semi_field.lstrip())
                continue

            # Try struct definition
            sr = self.try_struct(stripped)
            if sr:
                text, _, sname = sr
                guard = f"OPC_STRUCT_{sname}"
                output.append(f"#ifndef {guard}")
                output.append(f"#define {guard}")
                output.append(text + ' {')
                self.current_struct_lines = [text.lstrip() + ' {']
                block_indents.append((indent, ('struct', sname)))
                continue

            skip_map_rewrite = False

            put_m = re.match(r'^\s*(\w+)\[', stripped)
            if put_m and put_m.group(1) in self.map_decls:
                bpos = stripped.index('[', put_m.start(1))
                kexpr = self._find_bracket_expr(stripped, bpos)
                if kexpr is not None:
                    after = stripped[bpos + len(kexpr) + 2:].strip()
                    if after.startswith('='):
                        skip_map_rewrite = True

            del_m = re.match(r'^\s*del\s+(\w+)\[', stripped)
            if del_m and del_m.group(1) in self.map_decls:
                skip_map_rewrite = True

            if not skip_map_rewrite:
                stripped = self.rewrite_map_gets(stripped)
            stripped = self.rewrite_arr_methods(stripped)
            if not skip_map_rewrite:
                stripped = self.rewrite_map_methods(stripped)

            # Try transforms
            result = None
            for t in transforms:
                result = t(stripped)
                if result is not None:
                    break

            if result is not None:
                text, is_block = result
                if not skip_map_rewrite:
                    text = self.rewrite_map_gets(text)
                text = self.rewrite_arr_methods(text)
                if not skip_map_rewrite:
                    text = self.rewrite_map_methods(text)
                
                if is_block == 'else_block':
                    if output and output[-1].strip() == '}':
                        prev = output[-1]
                        output[-1] = f'{prev.rstrip()} {text.strip()}' + ' {'
                    else:
                        output.append(text + ' {')
                    block_indents.append((indent, 'code'))
                elif is_block:
                    output.append(text + ' {')
                    block_indents.append((indent, 'code'))
                else:
                    output.append(self._semi(text))
            else:
                stripped = self.rewrite_map_gets(stripped)
                stripped = self.rewrite_arr_methods(stripped)
                stripped = self.rewrite_map_methods(stripped)
                output.append(self._semi(stripped))

        while block_indents:
            lvl, btype = block_indents.pop()
            if isinstance(btype, tuple) and btype[0] == 'struct':
                sname = btype[1]
                output.append(' ' * lvl + '} ' + sname + ';')
                output.append(f"#endif // OPC_STRUCT_{sname}")
                
                self.current_struct_lines.append('} ' + sname + ';')
                guard = f"OPC_STRUCT_{sname}"
                struct_def = "\n".join([f"#ifndef {guard}", f"#define {guard}"] + self.current_struct_lines + [f"#endif"])
                self.struct_definitions.append(struct_def)
                self.current_struct_lines = []
            else:
                output.append(' ' * lvl + '}')

        has_main = any(re.match(r'^\s*fn\s+main\s*\(', ln) for ln in lines)
        text = '\n'.join(output)
        inc = self._build_includes(has_main)
        structs = self._build_map_structs()
        preamble = '\n'.join(filter(None, [inc, structs]))
        return (preamble + '\n\n' + text) if preamble else text

    # ── semicolon insertion ───────────────────────────────────────

    def _semi(self, line: str) -> str:
        s = line.strip()
        if not s: return line
        if '=' in s and s.endswith('}'):
            return line + ';'
        if (s.startswith('#') or s.startswith('//') or s.startswith('/*') or
            (s.startswith('*') and (len(s) == 1 or not s[1].isalnum())) or
            s.endswith('{') or s.endswith('}') or
            s.startswith('}') or s.endswith(',') or s.endswith('\\') or
            s.endswith(';')):
            return line
        return line + ';'

    # ── include / struct / header emission ────────────────────────

    def _build_includes(self, has_main: bool = True) -> str:
        std_map = {'stdio': 'stdio', 'stdlib': 'stdlib', 'string': 'string',
                   'math': 'math', 'stdint': 'stdint', 'stdbool': 'stdbool',
                   'assert': 'assert', 'ctype': 'ctype'}
        lines = []
        for k in sorted(self.needed_includes):
            if k in std_map:
                lines.append(f'#include <{std_map[k]}.h>')
                
        if 'stb_ds' in self.needed_includes:
            if has_main:
                lines.append('#define STB_DS_IMPLEMENTATION')
            lines.append('#include "stb_ds.h"')
            
        return '\n'.join(lines)

    def _build_map_structs(self) -> str:
        if not self.generated_map_structs:
            return ''
        return '\n'.join(self.generated_map_structs.values())

    def generate_header(self, module_name: str) -> str:
        guard = re.sub(r'[^A-Za-z0-9_]', '_', module_name).upper() + "_H"
        lines = [
            f"#ifndef {guard}",
            f"#define {guard}",
            ""
        ]
        
        inc = self._build_includes(has_main=False)
        if inc:
            inc_lines = []
            for ln in inc.splitlines():
                if ln.strip() != '#define STB_DS_IMPLEMENTATION':
                    inc_lines.append(ln)
            if inc_lines:
                lines.append("\n".join(inc_lines))
                lines.append("")
            
        structs = self._build_map_structs()
        if structs:
            lines.append(structs)
            lines.append("")
            
        if self.struct_definitions:
            lines.append("\n\n".join(self.struct_definitions))
            lines.append("")
            
        if self.prototypes:
            lines.append("\n".join(self.prototypes))
            lines.append("")
            
        lines.append(f"#endif // {guard}")
        return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python transpiler.py <input.sc> [output.c] [--header]")
        sys.exit(1)
        
    args = sys.argv[1:]
    force_header = False
    if '--header' in args:
        force_header = True
        args.remove('--header')
        
    if not args:
        print("Usage: python transpiler.py <input.sc> [output.c] [--header]")
        sys.exit(1)
        
    inf = args[0]
    outf = args[1] if len(args) > 1 else inf.rsplit('.', 1)[0] + '.c'
    
    with open(inf) as f: 
        src = f.read()
        
    t = SimplCTranspiler()
    c_code = t.transpile(src)
    
    with open(outf, 'w') as f: 
        f.write(c_code)
    print(f"Transpiled {inf} -> {outf}")
    
    # Auto-generate header if exported structs/functions exist, or if explicitly requested
    if force_header or t.prototypes or t.struct_definitions or t.generated_map_structs:
        base_name = os.path.splitext(os.path.basename(inf))[0]
        header_code = t.generate_header(base_name)
        header_out = os.path.splitext(outf)[0] + '.h'
        with open(header_out, 'w') as f:
            f.write(header_code)
        print(f"Generated header -> {header_out}")

if __name__ == '__main__':
    main()
