import re, copy

LIBDIR = r"C:\Program Files\KiCad\10.0\share\kicad\symbols"


class Raw(str):
    """Already-escaped string from a library file."""


class Sym(str):
    """Unquoted atom."""


def parse(text):
    tok = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')
    stack, cur = [], []
    for m in tok.finditer(text):
        t = m.group(0)
        if t == "(":
            stack.append(cur)
            cur = []
        elif t == ")":
            done = cur
            cur = stack.pop()
            cur.append(done)
        elif t.startswith('"'):
            cur.append(Raw(t[1:-1]))
        else:
            cur.append(Sym(t))
    return cur[0]


def dump(node, indent=0):
    pad = "\t" * indent
    if isinstance(node, list):
        simple = all(not isinstance(x, list) for x in node)
        if simple:
            return pad + "(" + " ".join(atom(x) for x in node) + ")"
        out = pad + "(" + " ".join(atom(x) for x in node if not isinstance(x, list))
        for x in node:
            if isinstance(x, list):
                out += "\n" + dump(x, indent + 1)
        return out + "\n" + pad + ")"
    return pad + atom(node)


def atom(x):
    if isinstance(x, Sym):
        return str(x)
    if isinstance(x, (int, float)):
        return fmt(x)
    if isinstance(x, Raw):
        return '"' + str(x) + '"'
    return '"' + str(x).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def fmt(v):
    v = round(float(v), 4)
    s = ("%.4f" % v).rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def find(node, key):
    return [x for x in node if isinstance(x, list) and x and x[0] == key]


_libs = {}


def lib_symbol(lib, name):
    if lib not in _libs:
        with open(f"{LIBDIR}\\{lib}.kicad_sym", encoding="utf-8") as f:
            _libs[lib] = {s[1]: s for s in find(parse(f.read()), "symbol")}
    s = copy.deepcopy(_libs[lib][name])
    ext = find(s, "extends")
    if ext:
        parent = lib_symbol(lib, ext[0][1])
        pname = parent[1].split(":")[-1]
        props = {p[1]: p for p in find(s, "property")}
        flat = [Sym("symbol"), name]
        for x in parent[2:]:
            if isinstance(x, list) and x[0] == "property" and x[1] in props:
                flat.append(props.pop(x[1]))
            elif isinstance(x, list) and x[0] == "symbol":
                x[1] = x[1].replace(pname, name, 1)
                flat.append(x)
            else:
                flat.append(x)
        flat[2:2] = list(props.values())
        s = flat
    return s


def pins(symdef, unit=1):
    """Return {number: (x, y, rot, name, etype)} for unit (plus common unit 0)."""
    res = {}
    for sub in find(symdef, "symbol"):
        u = int(sub[1].split("_")[-2])
        if u not in (0, unit):
            continue
        for p in find(sub, "pin"):
            at = find(p, "at")[0]
            num = find(p, "number")[0][1]
            nm = find(p, "name")[0][1]
            res[num] = (float(at[1]), float(at[2]), int(float(at[3])), nm, str(p[1]))
    return res
