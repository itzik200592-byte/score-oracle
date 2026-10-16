"""One-off: rebuild data/ledger.csv in the v2 schema using the last PRE-KICKOFF published version of each finished day."""
import sys, json, subprocess, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import pandas as pd
from oracle import track
from oracle.config import LEDGER_CSV

SNAP = {"2026-10-14": "2731f01", "2026-10-15": "23c2ca8"}   # git commits of docs/data.json published before those kickoffs
rows = []
for day, commit in SNAP.items():
    d = json.loads(subprocess.run(["git", "show", f"{commit}:docs/data.json"], capture_output=True, text=True, encoding="utf-8").stdout)
    import datetime as dt
    made = d["generated_at"]
    for p in d["predictions"]:
        if p["date"] != day:
            continue
        r = track._row(p, dt.datetime.fromisoformat(made.replace("+00:00", "")))
        r["src"] = "backfill"
        rows.append(r)
LEDGER_CSV.rename(LEDGER_CSV.with_suffix(".v1.csv")) if LEDGER_CSV.exists() and not LEDGER_CSV.with_suffix(".v1.csv").exists() else None
pd.DataFrame(rows, columns=track.COLS).to_csv(LEDGER_CSV, index=False, encoding="utf-8")
print("backfilled", len(rows), "rows")
