"""One-off: football-data calls the club 'La Coruna', ESPN/Winner 'Deportivo': one canonical name, no duplicate fixture."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent
p = R / "oracle/names.py"; s = p.read_text(encoding="utf-8")
if '"La Coruna": "Deportivo"' not in s:
    s = s.replace('"Ferencvarosi TC": "Ferencvaros",', '"La Coruna": "Deportivo", "Deportivo La Coruna": "Deportivo", "RC Deportivo": "Deportivo", "Ferencvarosi TC": "Ferencvaros",', 1)
    p.write_text(s, encoding="utf-8"); ast.parse(s)
p = R / "oracle/data.py"; s = p.read_text(encoding="utf-8")
if 'rs.register("Deportivo", "LL")' not in s:
    old = "    il = fr[\"tsdb\"]"
    new = "    rs.register(\"Deportivo\", \"LL\")   # canonical spelling of football-data's 'La Coruna' (aliased in names.py)\n    il = fr[\"tsdb\"]"
    assert old in s; s = s.replace(old, new, 1)
    p.write_text(s, encoding="utf-8"); ast.parse(s)
print("deportivo patched")
