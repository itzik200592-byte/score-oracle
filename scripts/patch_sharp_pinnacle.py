"""One-off: trust Pinnacle alone when present (some soft books in the feed carry swapped labels); else the median."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "oracle/sharp.py"; s = p.read_text(encoding="utf-8")
old = '''            probs, sharp = [], []
            for b in g.get("bookmakers", []):
                mk = next((m for m in b.get("markets", []) if m["key"] == "h2h"), None)
                if not mk:
                    continue
                o = {x["name"]: x["price"] for x in mk["outcomes"]}
                if h in o and a in o and "Draw" in o:
                    p = devig_power([o[h], o["Draw"], o[a]])
                    (sharp if b["key"] in SHARP_BOOKS else probs).append(p)
                    if b["key"] in SHARP_BOOKS:
                        pass
            use = sharp if sharp else probs
            if not use:
                continue
            p = np.mean(use, axis=0)
            out[(date, _n(h), _n(a))] = dict(h=float(p[0]), d=float(p[1]), a=float(p[2]), books=len(probs) + len(sharp),
                                           sharp=bool(sharp), league=lg)'''
new = '''            probs, pinn = [], None
            for b in g.get("bookmakers", []):
                mk = next((m for m in b.get("markets", []) if m["key"] == "h2h"), None)
                if not mk:
                    continue
                o = {x["name"]: x["price"] for x in mk["outcomes"]}
                if h in o and a in o and "Draw" in o:
                    p = devig_power([o[h], o["Draw"], o[a]])
                    probs.append(p)
                    if b["key"] == "pinnacle":
                        pinn = p
            if not probs:
                continue
            # Pinnacle is the reference price; without it, the median across books resists mislabeled outliers
            p = pinn if pinn is not None else np.median(np.array(probs), axis=0)
            out[(date, _n(h), _n(a))] = dict(h=float(p[0]), d=float(p[1]), a=float(p[2]), books=len(probs),
                                           sharp=pinn is not None, league=lg)'''
assert old in s; s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s); print("pinnacle patched")
