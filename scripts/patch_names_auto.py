"""One-off: self-consistent canonical names for clubs outside the big-4 namespaces (ESPN writes 'VIKING FK' and
'Viking FK' for the same club) and resolve Winner extra fixtures through the same resolver."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "oracle/names.py"; s = p.read_text(encoding="utf-8")
old = '''        if res is None:
            res = re.sub(r"\\s*\\([A-Z]{3}\\)\\s*$", "", name).strip()
        self.cache[k] = res
        return res'''
new = '''        if res is None:
            # unknown club: the first spelling seen becomes canonical, later spellings (case, accents) map to it
            auto = self.by_league.setdefault("_auto", {})
            if n in auto:
                res = auto[n]
            else:
                res = re.sub(r"\\s*\\([A-Z]{3}\\)\\s*$", "", name).strip()
                if res.isupper() and len(res) > 3:      # 'VIKING FK' -> 'Viking Fk' is worse; keep title case only for all-caps
                    res = res.title().replace(" Fk", " FK").replace(" Fc", " FC").replace(" Sk", " SK")
                auto[n] = res
        self.cache[k] = res
        return res'''
assert old in s, "names fallback block not found"
s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s)

p = R / "oracle/data.py"; s = p.read_text(encoding="utf-8")
old = '''            for x in _json.loads(extra.read_text(encoding="utf-8")):
                dts = pd.Timestamp(x["date"])'''
new = '''            for x in _json.loads(extra.read_text(encoding="utf-8")):
                x = dict(x, home=rs.resolve(x["home"], x["league"]), away=rs.resolve(x["away"], x["league"]))
                dts = pd.Timestamp(x["date"])'''
assert old in s, "extra block not found"
s = s.replace(old, new)
p.write_text(s, encoding="utf-8"); ast.parse(s)
print("names patched")
