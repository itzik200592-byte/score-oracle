"""Reliability of every derived market (all computed from the same score matrix) on the walk-forward backtest.
Answers: when the model says 90% for a market, how often does it happen? (python scripts/market_calibration.py)"""
import sys, json, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
import numpy as np
from oracle.evaluate import load_backtest, blend_all
from oracle.models import G
from oracle.markets import MARKETS, market_probs_fast

if __name__ == "__main__":
    bt = load_backtest()
    rows, mats = bt["rows"], bt["mats"]
    cfg = json.load(open(pathlib.Path(__file__).resolve().parent.parent / "data" / "ensemble.json", encoding="utf-8"))
    P = blend_all(rows, mats, cfg["weights"])
    hg, ag = rows.hg.values.astype(int), rows.ag.values.astype(int)
    n = len(rows)
    probs = {k: np.zeros(n) for k in MARKETS}
    for i, M in enumerate(P):
        mp = market_probs_fast(M)
        for k in MARKETS:
            probs[k][i] = mp[k]
    out = {}
    print(f"{n} matches. For each market: bucket of the model's probability -> actual frequency")
    for k, (label, fn) in MARKETS.items():
        y = np.array([fn(h, a) for h, a in zip(hg, ag)], float)
        p = probs[k]
        bins = [0, .5, .6, .7, .8, .85, .9, .95, 1.01]
        idx = np.digitize(p, bins) - 1
        tab = []
        for b in range(len(bins) - 1):
            s = idx == b
            if s.sum() >= 30:
                tab.append(dict(lo=bins[b], hi=bins[b + 1], n=int(s.sum()), model=round(100 * float(p[s].mean()), 1), actual=round(100 * float(y[s].mean()), 1)))
        hi = p >= 0.85
        out[k] = dict(label=label, base_rate=round(100 * float(y.mean()), 1), buckets=tab,
                      p85=dict(n=int(hi.sum()), model=round(100 * float(p[hi].mean()), 1) if hi.any() else None, actual=round(100 * float(y[hi].mean()), 1) if hi.any() else None))
        h = out[k]["p85"]
        print(f"{k:<14}{label:<28} base {out[k]['base_rate']:5.1f}% | model>=85%: n={h['n']:<5} model {h['model']} actual {h['actual']}")
    (pathlib.Path(__file__).resolve().parent.parent / "data" / "market_calibration.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
