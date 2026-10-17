"""One-off: sanity guard in sharp.compare: a huge disagreement between Winner and the sharp market means a
data mismatch (wrong fixture, swapped teams), not an edge. Flag only consistent, moderate edges."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "oracle/sharp.py"; s = p.read_text(encoding="utf-8")
old = '''        edge = {k: round(100 * (s[k] * o[k] - 1), 1) for k in "hda"}
        best = max(edge, key=edge.get)
        r["sharp"] = dict(p={k: round(100 * s[k]) for k in "hda"}, edge=edge, books=s["books"], is_sharp=s["sharp"],
                          flag=(best if edge[best] >= 100 * min_edge else None))
        n += 1'''
new = '''        edge = {k: round(100 * (s[k] * o[k] - 1), 1) for k in "hda"}
        best = max(edge, key=edge.get)
        # consistency: Winner's and the sharp market's favourite must agree and no edge may exceed +25%
        # (that size only happens when the fixture or the home/away sides are mismatched)
        w_imp = {k: 1 / o[k] for k in "hda"}
        consistent = max(w_imp, key=w_imp.get) == max("hda", key=lambda k: s[k]) and edge[best] <= 25
        r["sharp"] = dict(p={k: round(100 * s[k]) for k in "hda"}, edge=edge, books=s["books"], is_sharp=s["sharp"],
                          consistent=consistent, flag=(best if consistent and edge[best] >= 100 * min_edge else None))
        n += 1'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s); print("guard patched")
