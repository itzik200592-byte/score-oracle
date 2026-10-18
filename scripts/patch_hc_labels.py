import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "oracle/picks.py"; s = p.read_text(encoding="utf-8")
a = s.index("def _hc_labels(h, a, s):"); b = s.index("def menu(row):")
new = '''def _hc_labels(h, a, s):
    """Plain-Hebrew meaning of Winner's 3-way handicap outcomes (A: d>s, X: d==s, B: d<s; d = home - away goals)."""
    def not_lose(team, n):
        return f"{team} לא מפסידה" if n == 1 else f"{team} לא מפסידה בהפרש {n} או יותר"
    if s > 0:
        return (f"{h} מנצחת בהפרש {s + 1} או יותר", f"{h} מנצחת בדיוק בהפרש {s}", not_lose(a, s))
    L = -s
    return (not_lose(h, L), f"{a} מנצחת בדיוק בהפרש {L}", f"{a} מנצחת בהפרש {L + 1} או יותר")


'''
s = s[:a] + new + s[b:]
p.write_text(s, encoding="utf-8"); ast.parse(s); print("labels fixed")
