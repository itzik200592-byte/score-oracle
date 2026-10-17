"""One-off: fuzzy team matching between The Odds API names and our canonical names."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "oracle/sharp.py"; s = p.read_text(encoding="utf-8")
old = '''def compare(rows, sharp_map, min_edge=0.03):
    """Annotate exported prediction rows with sharp fair probs and Winner-vs-sharp edge."""
    if not sharp_map:
        return 0
    n = 0
    for r in rows:
        o = r.get("odds")
        if not o:
            continue
        key_ = (r["date"], _n(r["home"]), _n(r["away"]))
        s = sharp_map.get(key_)
        if not s:
            for dd in (-1, 1):
                d2 = (dt.date.fromisoformat(r["date"]) + dt.timedelta(days=dd)).isoformat()
                s = sharp_map.get((d2, key_[1], key_[2]))
                if s:
                    break
        if not s:
            continue'''
new = '''STOP = {"fc", "cf", "afc", "club", "united", "city", "town", "de", "sc", "ac", "as", "ssc", "us", "sk", "fk", "nk", "tsg", "rb", "vfb", "sl"}


def _toks(s):
    return {t for t in _n(s).replace("-", " ").replace("'", "").split() if t not in STOP and len(t) > 1}


def _same(a, b):
    """our canonical name vs API name: exact after aliases, token containment, or close match."""
    import difflib
    na, nb = _n(a), _n(b)
    if na == nb:
        return True
    ta, tb = _toks(a), _toks(b)
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.84


def compare(rows, sharp_map, min_edge=0.03):
    """Annotate exported prediction rows with sharp fair probs and Winner-vs-sharp edge."""
    if not sharp_map:
        return 0
    by_date = {}
    for (d, h, a), v in sharp_map.items():
        by_date.setdefault(d, []).append((h, a, v))
    n = 0
    for r in rows:
        o = r.get("odds")
        if not o:
            continue
        s = None
        for dd in (0, -1, 1):
            d2 = (dt.date.fromisoformat(r["date"]) + dt.timedelta(days=dd)).isoformat()
            for h, a, v in by_date.get(d2, []):
                if _same(r["home"], h) and _same(r["away"], a):
                    s = v
                    break
            if s:
                break
        if not s:
            continue'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s); print("sharp matching patched")
