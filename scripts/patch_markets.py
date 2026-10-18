"""One-off: wire the market menu into predict (distribution.mk), winner (total-goals ranges), export (prices, picks)."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent

# ---- predict.py: markets in the distribution block
p = R / "oracle/predict.py"; s = p.read_text(encoding="utf-8")
if "market_probs_fast" not in s:
    s = s.replace("from .sniper import pick, top_k, tier", "from .sniper import pick, top_k, tier\nfrom .markets import market_probs_fast", 1)
    old = "        exp_total=round(mean_t, 2), likely_total=int(np.argmax(tp)),"
    new = "        exp_total=round(mean_t, 2), likely_total=int(np.argmax(tp)),\n        mk={k: round(100 * v, 1) for k, v in market_probs_fast(P).items()},"
    assert old in s; s = s.replace(old, new)
    p.write_text(s, encoding="utf-8"); ast.parse(s)

# ---- winner.py: total-goals ranges (Winner prints scores right-to-left: '1 - 0' means 0-1)
p = R / "oracle/winner.py"; s = p.read_text(encoding="utf-8")
if '"tg"' not in s:
    old = '''        elif mp.startswith("האם כל קבוצה תבקיע") and "תוצאת סיום" in mp:'''
    new = '''        elif mp.startswith("סך הכל שערים") and "תוצאת סיום" in mp:
            tg = {}
            for o in outs:
                d_ = team_he.clean(o.get("desc", "")).replace(" ", "")
                if d_ in ("1-0", "0-1"):
                    tg["tg01"] = _price(o)
                elif d_ in ("3-2", "2-3"):
                    tg["tg23"] = _price(o)
                elif d_.startswith("4"):
                    tg["tg4p"] = _price(o)
            if len(tg) == 3:
                e["tg"] = tg
        elif mp.startswith("האם כל קבוצה תבקיע") and "תוצאת סיום" in mp:'''
    assert old in s; s = s.replace(old, new, 1)
    s = s.replace('''"cs": cs, "kickoff": _kick(e["time"]),''', '''"cs": cs, "tg": e.get("tg"), "kickoff": _kick(e["time"]),''')
    p.write_text(s, encoding="utf-8"); ast.parse(s)

# ---- export.py: keep tg prices on the odds block; daily picks + accountability
p = R / "oracle/export.py"; s = p.read_text(encoding="utf-8")
if "day_picks" not in s:
    s = s.replace('''            for k in ("over25", "under25", "btts_yes", "btts_no", "kickoff"):
                if e.get(k):
                    o[k] = e[k]''', '''            for k in ("over25", "under25", "btts_yes", "btts_no", "kickoff", "tg"):
                if e.get(k):
                    o[k] = e[k]''')
    old = "    paper = value.settle(m)"
    new = '''    paper = value.settle(m)
    from . import picks
    days = sorted({r["date"] for r in rows if r["date"] >= str(pd.Timestamp.now().date())})[:3]
    if ledger:
        picks.record(rows, days)
    picks_track = picks.settle(m)
    daily = {d: picks.day_picks(rows, d) for d in days}
    for r in rows:   # per-match market menu (probabilities + Winner prices) for the verdict sheet
        r["menu"] = picks.menu(r)[:40]'''
    assert old in s; s = s.replace(old, new, 1)
    s = s.replace("sharp_available=bool(sharp.key()), sharp_matches=sharp_n,", "sharp_available=bool(sharp.key()), sharp_matches=sharp_n, daily=daily, picks_track=picks_track,")
    p.write_text(s, encoding="utf-8"); ast.parse(s)
print("markets patched")
