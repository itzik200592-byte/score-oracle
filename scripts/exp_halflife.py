"""Experiment: does a faster goal-level memory fix the CL/IL goal-rate lag? (run: python scripts/exp_halflife.py)"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import numpy as np
from oracle.data import load
from oracle import evaluate as E
from oracle.models import G

VARIANTS = {f"disp CL/IL={d}": {"disp": {"CL": d, "IL": d, "EL": d}} for d in (0.0, 0.15, 0.25, 0.35, 0.5)}

if __name__ == "__main__":
    m = load()
    I, J = np.meshgrid(np.arange(G), np.arange(G), indexing="ij")
    T = I + J
    for nm, pr in VARIANTS.items():
        bt = E.run_backtest(m, 1700, 14, params=pr, verbose=False)
        rows, mats = bt["rows"], bt["mats"]
        last = (rows.date >= rows.date.max() - np.timedelta64(730, "D")).values
        out = []
        for lg in ["CL", "IL", "big4"]:
            s = last & ((rows.league == lg).values if lg != "big4" else rows.league.isin(["PL", "LL", "SA", "L1"]).values)
            for c in (["elo", "pool"] if lg != "big4" else ["dc", "pool"]):
                M = mats[c][s]
                ok = ~np.isnan(M[:, 0, 0])
                M = M[ok]
                h = np.minimum(rows.hg.values[s][ok].astype(int), 10)
                a = np.minimum(rows.ag.values[s][ok].astype(int), 10)
                ll = -np.mean(np.log(M[np.arange(len(M)), h, a] + 1e-12))
                bias = (h + a).mean() - np.mean([(x * T).sum() for x in M])
                t5 = np.mean([(x[T >= 5]).sum() for x in M]); a5 = np.mean((h + a) >= 5)
                out.append(f"{lg}-{c}: ll {ll:.4f} g>=5 {100*t5:.1f}/{100*a5:.1f}")
        print(f"{nm:<22}", " | ".join(out), flush=True)
