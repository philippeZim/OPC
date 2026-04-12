#!/usr/bin/env python3
"""
SimplC -> C Transpiler
Converts a simplified, Python-inspired C dialect into compilable C code.
"""

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

    RESERVED = {'case', 'default', 'goto', 'struct', 'enum', 'union',
                'typedef', 'extern', 'static', 'register', 'volatile',
                'const', 'return', 'if', 'else', 'while', 'for',
                'switch', 'do', 'break', 'continue', 'fn'}

    def __init__(self):
        self.needed_includes = set()
        self.struct_names = set()  # track defined struct names for type resolution

    def resolve_type(self, raw_type: str) -> str:
        arr_match = re.match(r'^(.+?)(\[.+\])$', raw_type.strip())
        if arr_match:
            return self.resolve_type(arr_match.group(1)) + arr_match.group(2)
        if raw_type.endswith('*'):
            return self.resolve_type(raw_type[:-1].strip()) + ' *'
        stripped = raw_type.strip()
        if stripped in self.STDINT_TYPES:
            self.needed_includes.add('stdint')
            return self.STDINT_TYPES[stripped]
        if stripped == 'bool':
            self.needed_includes.add('stdbool')
        # Recognize user-defined struct types
        if stripped in self.struct_names:
            return stripped
        return stripped

    def detect_auto_includes(self, code: str):
        ids = set(re.findall(r'\b([a-zA-Z_]\w*)\s*\(', code))
        words = set(re.findall(r'\b([a-zA-Z_]\w*)\b', code))
        if ids & self.STDIO_FUNCS: self.needed_includes.add('stdio')
        if ids & self.STDLIB_FUNCS: self.needed_includes.add('stdlib')
        if ids & self.STRING_FUNCS: self.needed_includes.add('string')
        if ids & self.MATH_FUNCS: self.needed_includes.add('math')
        if words & self.BOOL_KEYWORDS: self.needed_includes.add('stdbool')
        if ids & self.ASSERT_FUNCS: self.needed_includes.add('assert')
        if ids & self.CTYPE_FUNCS: self.needed_includes.add('ctype')

    def _split_args(self, s: str) -> list:
        depth = 0; parts = []; cur = []
        for ch in s:
            if ch == '(': depth += 1; cur.append(ch)
            elif ch == ')': depth -= 1; cur.append(ch)
            elif ch == ',' and depth == 0: parts.append(''.join(cur)); cur = []
            else: cur.append(ch)
        if cur: parts.append(''.join(cur))
        return parts

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
                    pn, pt = pm.group(1), self.resolve_type(pm.group(2).strip())
                    arr = re.match(r'^(.+?)(\[.+\])$', pt)
                    if arr: cp.append(f'{arr.group(1)} {pn}{arr.group(2)}')
                    else: cp.append(f'{pt} {pn}')
                else: cp.append(p)
        return (f'{indent}{ret} {name}({", ".join(cp)})', True)

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

    def try_else_if(self, s):
        m = re.match(r'^(\s*)else\s+if\s+(.+):\s*$', s)
        if not m: return None
        return (f'{m.group(1)}else if ({m.group(2).strip()})', 'else_block')

    def try_else(self, s):
        m = re.match(r'^(\s*)else\s*:\s*$', s)
        if not m: return None
        return (f'{m.group(1)}else', 'else_block')

    def try_control(self, s):
        m = re.match(r'^(\s*)(if|while|switch)\s+(.+):\s*$', s)
        if not m: return None
        return (f'{m.group(1)}{m.group(2)} ({m.group(3).strip()})', True)

    def try_for_plain(self, s):
        m = re.match(r'^(\s*)for\s+(.+):\s*$', s)
        if not m: return None
        return (f'{m.group(1)}for ({m.group(2).strip()})', True)

    def try_variable(self, s):
        m = re.match(r'^(\s*)(\w+)\s*:\s*(.+?)\s*=\s*(.+)$', s)
        if m:
            indent, name, raw, val = m.group(1), m.group(2), m.group(3).strip(), m.group(4).strip()
            if name in self.RESERVED: return None
            ct = self.resolve_type(raw)
            arr = re.match(r'^(.+?)(\[.+\])$', ct)
            if arr: return (f'{indent}{arr.group(1)} {name}{arr.group(2)} = {val}', False)
            return (f'{indent}{ct} {name} = {val}', False)
        m = re.match(r'^(\s*)(\w+)\s*:\s*(\S+)\s*$', s)
        if m:
            indent, name, raw = m.group(1), m.group(2), m.group(3).strip()
            if name in self.RESERVED: return None
            ct = self.resolve_type(raw)
            arr = re.match(r'^(.+?)(\[.+\])$', ct)
            if arr: return (f'{indent}{arr.group(1)} {name}{arr.group(2)}', False)
            return (f'{indent}{ct} {name}', False)
        return None

    def try_print(self, s):
        m = re.match(r'^(\s*)print\((.+)\)\s*$', s)
        if not m: return None
        indent, args = m.group(1), m.group(2)
        if re.match(r'^".*"$', args.strip()):
            inner = args.strip()[1:-1]
            return (f'{indent}printf("{inner}\\n")', False)
        return (f'{indent}printf({args})', False)

    def try_struct(self, s):
        """Match: struct Ball:"""
        m = re.match(r'^(\s*)struct\s+(\w+)\s*:\s*$', s)
        if not m: return None
        indent, name = m.group(1), m.group(2)
        self.struct_names.add(name)
        return (f'{indent}typedef struct {name}', 'struct_block', name)

    def try_struct_field(self, s):
        """Match struct fields like: x: int,  or  speed: double"""
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
        """Pre-scan to collect struct names so resolve_type can recognize them."""
        for m in re.finditer(r'^[ \t]*struct\s+(\w+)\s*:', source, re.MULTILINE):
            self.struct_names.add(m.group(1))

    def transpile(self, source: str) -> str:
        self.needed_includes = set()
        self.struct_names = set()
        self._pre_scan_structs(source)
        self.detect_auto_includes(source)

        transforms = [self.try_function, self.try_for_range, self.try_else_if,
                       self.try_else, self.try_control, self.try_for_plain,
                       self.try_variable, self.try_print]

        lines = source.splitlines()
        output = []
        block_indents = []  # stack of (indent_level, block_type)
        # block_type: 'code' or ('struct', name)

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
                    output.append(' ' * lvl + '} ' + btype[1] + ';')
                else:
                    output.append(' ' * lvl + '}')

            # Check if we're inside a struct block
            in_struct = block_indents and isinstance(block_indents[-1][1], tuple) and block_indents[-1][1][0] == 'struct'

            if in_struct:
                # Process as struct field
                field = self.try_struct_field(stripped)
                if field:
                    output.append(field)
                else:
                    output.append(self._semi(stripped))
                continue

            # Try struct definition
            sr = self.try_struct(stripped)
            if sr:
                text, _, sname = sr
                output.append(text + ' {')
                block_indents.append((indent, ('struct', sname)))
                continue

            # Try other transforms
            result = None
            for t in transforms:
                result = t(stripped)
                if result is not None:
                    break

            if result is not None:
                text, is_block = result
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
                output.append(self._semi(stripped))

        while block_indents:
            lvl, btype = block_indents.pop()
            if isinstance(btype, tuple) and btype[0] == 'struct':
                output.append(' ' * lvl + '} ' + btype[1] + ';')
            else:
                output.append(' ' * lvl + '}')

        text = '\n'.join(output)
        inc = self._build_includes()
        return (inc + '\n\n' + text) if inc else text

    def _semi(self, line: str) -> str:
        s = line.strip()
        if not s: return line
        if '=' in s and s.endswith('}'):
            return line + ';'
        if (s.startswith('#') or s.startswith('//') or s.startswith('/*') or
            s.startswith('*') or s.endswith('{') or s.endswith('}') or
            s.startswith('}') or s.endswith(',') or s.endswith('\\') or
            s.endswith(';')):
            return line
        return line + ';'

    def _build_includes(self) -> str:
        m = {'stdio': 'stdio', 'stdlib': 'stdlib', 'string': 'string',
             'math': 'math', 'stdint': 'stdint', 'stdbool': 'stdbool',
             'assert': 'assert', 'ctype': 'ctype'}
        return '\n'.join(f'#include <{m[k]}.h>' for k in sorted(self.needed_includes) if k in m)


def main():
    if len(sys.argv) < 2:
        print("Usage: python transpiler.py <input.sc> [output.c]")
        sys.exit(1)
    inf = sys.argv[1]
    outf = sys.argv[2] if len(sys.argv) > 2 else inf.rsplit('.', 1)[0] + '.c'
    with open(inf) as f: src = f.read()
    t = SimplCTranspiler()
    with open(outf, 'w') as f: f.write(t.transpile(src))
    print(f"Transpiled {inf} -> {outf}")

if __name__ == '__main__':
    main()