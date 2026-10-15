"""Does a team-specific home advantage improve the Dixon-Coles model? (python scripts/exp_hfa.py)"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import numpy as np
from oracle.data import load
from oracle import evaluate as E

VARIANTS = {"no team HFA": {}, "team HFA ridge 40": {"hteam_ridge": 40.0}, "team HFA ridge 15": {"hteam_ridge": 15.0},
            "team HFA ridge 6": {"hteam_ridge": 6.0}}

if __name__ == "__main__":
    m = load()
    for nm, pr in VARIANTS.items():
        bt = E.run_backtest(m, 1700, 14, params=pr, verbose=False)
        rows, mats = bt["rows"], bt["mats"]
        out = []
        for lg in ["PL", "LL", "SA", "L1", "IL"]:
            s = (rows.league == lg).values
            M = mats["dc"][s]; ok = ~np.isnan(M[:, 0, 0]); M = M[ok]
            h = np.minimum(rows.hg.values[s][ok].astype(int), 10); a = np.minimum(rows.ag.values[s][ok].astype(int), 10)
            out.append(f"{lg} {-np.mean(np.log(M[np.arange(len(M)), h, a] + 1e-12)):.4f}")
        allm = np.concatenate([mats['dc'][(rows.league == lg).values] for lg in ["PL", "LL", "SA", "L1", "IL"]])
        print(f"{nm:<20}", " | ".join(out), flush=True)
