"""One-off: Winner-only picks. margin pmf in the distribution, handicap parsing, odds block, strategy min odds."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent

# ---- predict.py: margin distribution (home - away) for the handicap market
p = R / "oracle/predict.py"; s = p.read_text(encoding="utf-8")
if '"marg"' not in s and "marg=" not in s:
    old = "        mk={k: round(100 * v, 1) for k, v in market_probs_fast(P).items()},"
    new = old + '''
        marg={str(d): round(100 * float(P[(_II - _JJ) == d].sum() if -6 < d < 6 else (P[(_II - _JJ) <= d].sum() if d <= -6 else P[(_II - _JJ) >= d].sum())), 2) for d in range(-6, 7)},'''
    assert old in s; s = s.replace(old, new); p.write_text(s, encoding="utf-8"); ast.parse(s)

# ---- winner.py: parse the 3-way handicap
p = R / "oracle/winner.py"; s = p.read_text(encoding="utf-8")
if '"hc"' not in s:
    old = '''        elif mp.startswith("סך הכל שערים") and "תוצאת סיום" in mp:'''
    new = '''        elif mp.startswith("הימור יתרון") and "תוצאת סיום" in mp and len(outs) == 3:
            import re as _re
            d0 = team_he.clean(outs[0].get("desc", ""))
            mm = _re.search(r"\\(([+-])\\s*(\\d+)\\)", d0)
            if mm:
                sign, line = (1 if mm.group(1) == "+" else -1), int(mm.group(2))
                e["hc"] = dict(s=-sign * line, labels=[team_he.clean(o.get("desc", "")) for o in outs], prices=[_price(o) for o in outs])
        elif mp.startswith("סך הכל שערים") and "תוצאת סיום" in mp:'''
    assert old in s; s = s.replace(old, new, 1)
    s = s.replace('''"cs": cs, "tg": e.get("tg"),''', '''"cs": cs, "tg": e.get("tg"), "hc": e.get("hc"),''')
    p.write_text(s, encoding="utf-8"); ast.parse(s)

# ---- export.py: carry hc into the odds block; picks go through the new module (already wired)
p = R / "oracle/export.py"; s = p.read_text(encoding="utf-8")
s = s.replace('("over25", "under25", "btts_yes", "btts_no", "kickoff", "tg")', '("over25", "under25", "btts_yes", "btts_no", "kickoff", "tg", "hc")')
p.write_text(s, encoding="utf-8"); ast.parse(s)

# ---- value.py: favourite strategy must respect the 1.50 minimum
p = R / "oracle/value.py"; s = p.read_text(encoding="utf-8")
s = s.replace('if s["market"] == "1x2" and s["odds"] <= 1.6 and s["model_p"] >= 62:', 'if s["market"] == "1x2" and 1.5 <= s["odds"] <= 1.9 and s["model_p"] >= 52:')
p.write_text(s, encoding="utf-8"); ast.parse(s)
print("winner-only patched")
