"""Walk-forward backtest, ensemble-weight learning, pick-rule selection, calibration. No look-ahead anywhere."""
import json, pickle, os, datetime as dt
from concurrent.futures import ProcessPoolExecutor
import numpy as np, pandas as pd
from scipy.optimize import minimize
from .config import DATA, WEIGHTS_JSON, BIG4
from .models import Suite, COMPONENTS, G, outcome_probs, over25, btts
from .sniper import pick, top_k

BT_PKL = DATA / "backtest.pkl"
GROUPS = {"big4": ["dc", "dcx", "pool", "elo", "mkt"], "IL": ["dc", "pool", "elo"], "CL": ["pool", "elo"]}


def group_of(lg):
    return "big4" if lg in BIG4 else lg


def _bt_block(args):
    """One walk-forward block: fit every component on matches dated strictly before `lo`, predict [lo, hi)."""
    m, lo, hi, suite_params = args
    played = m[m.played]
    rows = played[(played.date >= lo) & (played.date < hi)]
    if rows.empty:
        return None
    suite = Suite(suite_params).fit(m[m.date < lo], lo)
    return rows, suite.matrices(rows)


def run_backtest(m, test_days=540, step_days=14, params=None, verbose=True, workers=None):
    played = m[m.played]
    end = played.date.max() + pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=test_days)
    rows_all, mats_all = [], {c: [] for c in COMPONENTS}
    suite_params = params or {}
    n_blocks = int(np.ceil((end - start).days / step_days))
    jobs = [(m, start + pd.Timedelta(days=b * step_days), start + pd.Timedelta(days=(b + 1) * step_days), suite_params) for b in range(n_blocks)]
    workers = workers or max(1, (os.cpu_count() or 2) - 1)
    if workers > 1:   # blocks are independent (each fits only on its own past), so they run in parallel
        with ProcessPoolExecutor(workers) as ex:
            results = list(ex.map(_bt_block, jobs))
    else:
        results = [_bt_block(j) for j in jobs]
    for b, res in enumerate(results):
        if res is None:
            continue
        rows, mats = res
        rows_all.append(rows)
        for c in COMPONENTS:
            mats_all[c].append(mats[c])
        if verbose:
            print(f"  backtest block {b + 1}/{n_blocks}  {jobs[b][1].date()}  matches={len(rows)}", flush=True)
    rows = pd.concat(rows_all).reset_index(drop=True)
    mats = {c: np.concatenate(v) for c, v in mats_all.items()}
    res = dict(rows=rows, mats=mats, params=suite_params, made=dt.datetime.now().isoformat())
    with open(BT_PKL, "wb") as f:
        pickle.dump(res, f)
    return res


def load_backtest():
    with open(BT_PKL, "rb") as f:
        return pickle.load(f)


def _actual_prob(P, hg, ag):
    hg = np.minimum(hg, G - 1).astype(int)
    ag = np.minimum(ag, G - 1).astype(int)
    return P[np.arange(len(P)), hg, ag]


def fit_weights(rows, mats, group, comps):
    sel = (rows.league.map(group_of) == group).values.copy()
    for c in comps:
        sel &= ~np.isnan(mats[c][:, 0, 0])
    idx = np.where(sel)[0]
    if len(idx) < 40:
        return {c: 1 / len(comps) for c in comps}, len(idx)
    pa = np.stack([_actual_prob(mats[c][idx], rows.hg.values[idx], rows.ag.values[idx]) for c in comps], 1)

    def obj(z):
        w = np.exp(z - z.max()); w /= w.sum()
        return -np.mean(np.log(pa @ w + 1e-9))

    sol = minimize(obj, np.zeros(len(comps)), method="Nelder-Mead", options={"maxiter": 2000, "xatol": 1e-4, "fatol": 1e-7})
    w = np.exp(sol.x - sol.x.max()); w /= w.sum()
    w = 0.85 * w + 0.15 / len(comps)   # floor: every model keeps a voice, so a missing-odds match still has a blend
    return dict(zip(comps, map(float, w))), len(idx)


def blend(mats_row, weights):
    """mats_row: dict comp -> (G,G) or None/NaN. Re-normalises weights over the components that exist."""
    tot, acc = 0.0, np.zeros((G, G))
    for c, w in weights.items():
        M = mats_row.get(c)
        if M is None or np.isnan(M[0, 0]):
            continue
        acc += w * M
        tot += w
    return acc / tot if tot > 0 else None


def blend_all(rows, mats, W):
    P = np.full((len(rows), G, G), np.nan)
    for i, lg in enumerate(rows.league.values):
        w = W[group_of(lg)]
        P[i] = blend({c: mats[c][i] for c in w}, w)
    return P


def rps(P, hg, ag):
    out = []
    for M, x, y in zip(P, hg, ag):
        p = np.array(outcome_probs(M))
        o = np.array([x > y, x == y, x < y], float)
        out.append(0.5 * np.sum((np.cumsum(p) - np.cumsum(o)) ** 2))
    return float(np.mean(out))


def metrics(rows, P, beta=0.0, draw_scale=1.0):
    hg, ag = rows.hg.values.astype(int), rows.ag.values.astype(int)
    n = len(rows)
    picks = np.array([pick(M, beta, draw_scale) for M in P])
    exact = (picks[:, 0] == hg) & (picks[:, 1] == ag)
    ph = np.array([outcome_probs(M) for M in P])
    out_pred = ph.argmax(1)
    out_act = np.where(hg > ag, 0, np.where(hg == ag, 1, 2))
    pick_out = np.where(picks[:, 0] > picks[:, 1], 0, np.where(picks[:, 0] == picks[:, 1], 1, 2))
    t3 = np.array([any(s == (h, a) for s, _ in top_k(M, 3)) for M, h, a in zip(P, hg, ag)])
    ou = np.array([over25(M) > 0.5 for M in P]) == ((hg + ag) >= 3)
    bt = np.array([btts(M) > 0.5 for M in P]) == ((hg > 0) & (ag > 0))
    return dict(n=n, exact=float(exact.mean()), top3=float(t3.mean()), acc_1x2=float((out_pred == out_act).mean()),
                pick_outcome_acc=float((pick_out == out_act).mean()), rps=rps(P, hg, ag),
                logloss=float(-np.mean(np.log(_actual_prob(P, hg, ag) + 1e-9))), ou25=float(ou.mean()), btts=float(bt.mean()))


def tune_everything(bt, split=0.6):
    rows, mats = bt["rows"], bt["mats"]
    order = np.argsort(rows.date.values)
    cut_date = rows.date.values[order][int(len(rows) * split)]
    train = (rows.date.values < cut_date)
    W, info = {}, {}
    for g, comps in GROUPS.items():
        sub_rows = rows[train].reset_index(drop=True)
        sub_m = {c: mats[c][train] for c in COMPONENTS}
        W[g], n = fit_weights(sub_rows, sub_m, g, comps)
        info[g] = n
    # ---- evaluate on the untouched holdout
    hold = ~train
    hrows = rows[hold].reset_index(drop=True)
    hm = {c: mats[c][hold] for c in COMPONENTS}
    P = blend_all(hrows, hm, W)
    report = {"holdout_start": str(pd.Timestamp(cut_date).date()), "weights_trained_on": info, "weights_first_fit": W,
              "components": {}, "ensemble": {}, "baselines": {}, "by_league": {}}
    for c in COMPONENTS:
        ok = ~np.isnan(hm[c][:, 0, 0])
        if ok.sum() > 30:
            report["components"][c] = metrics(hrows[ok].reset_index(drop=True), hm[c][ok])
    # Pick rule = pure argmax of the blended distribution. A draw penalty was tested and rejected:
    # the model is calibrated (draws 24.3% predicted vs 24.4% actual; 1-1 11.35% vs 11.04%) and the penalty
    # changed 440 of 2382 picks for a net +6 hits, i.e. noise. If 1-1 is the most likely score, we say 1-1.
    best_beta, best_ds = 0.0, 1.0
    report["beta"] = best_beta
    report["draw_scale"] = best_ds
    report["ensemble"]["all"] = metrics(hrows, P, best_beta, best_ds)
    report["ensemble"]["mode_only"] = metrics(hrows, P, 0.0)
    for lg in sorted(set(hrows.league)):
        s = (hrows.league == lg).values
        if s.sum() >= 20:
            report["by_league"][lg] = metrics(hrows[s].reset_index(drop=True), P[s], best_beta, best_ds)
    hg, ag = hrows.hg.values, hrows.ag.values
    for nm, (a, b) in {"always 1-1": (1, 1), "always 1-0": (1, 0), "always 2-1": (2, 1), "always 2-0": (2, 0)}.items():
        report["baselines"][nm] = float(((hg == a) & (ag == b)).mean())
    # ---- calibration of the top-score probability  (when should we shoot?)
    picks = np.array([pick(M, best_beta, best_ds) for M in P])
    hit = (picks[:, 0] == hg) & (picks[:, 1] == ag)
    ptop_pick = np.array([M[p[0], p[1]] for M, p in zip(P, picks)])
    # tiers = the model's own confidence in the picked scoreline (no manipulation of which scores may qualify)
    sscore = ptop_pick
    q = np.quantile(sscore, [0.5, 0.8])
    cuts = [float(q[0]), float(q[1])]
    cal = []
    for lo, hi, name in [(0, cuts[0], "C (low)"), (cuts[0], cuts[1], "B (shot)"), (cuts[1], 9e9, "A (strong shot)")]:
        s = (sscore >= lo) & (sscore < hi)
        if s.sum():
            cal.append(dict(tier=name, n=int(s.sum()), mean_predicted=float(ptop_pick[s].mean()), actual_hit=float(hit[s].mean()),
                            draw_picks=float((picks[s][:, 0] == picks[s][:, 1]).mean())))
    report["calibration"] = cal
    report["cuts"] = cuts
    # ---- final weights: refit on ALL backtest data for live use
    Wf = {}
    for g, comps in GROUPS.items():
        Wf[g], _ = fit_weights(rows, mats, g, comps)
    final = dict(weights=Wf, beta=best_beta, draw_scale=best_ds, cuts=cuts, tier_metric="p_pick",
                 tuned=dt.datetime.now().isoformat(), params=bt.get("params", {}))
    WEIGHTS_JSON.write_text(json.dumps(final, indent=2), encoding="utf-8")
    report["weights_final"] = Wf
    return report


def format_report(rep):
    L = []
    pc = lambda x: f"{100 * x:5.1f}%"
    L.append(f"BACKTEST (holdout from {rep['holdout_start']}, never seen during tuning)")
    L.append("-" * 78)
    L.append(f"{'model':<16}{'n':>6}{'exact':>8}{'top3':>8}{'1X2':>8}{'RPS':>8}{'logloss':>9}{'O/U2.5':>8}{'BTTS':>8}")
    for name, r in {**{f'component:{k}': v for k, v in rep['components'].items()}, "ENSEMBLE+sniper": rep["ensemble"]["all"],
                    "ENSEMBLE mode": rep["ensemble"]["mode_only"]}.items():
        L.append(f"{name:<16}{r['n']:>6}{pc(r['exact']):>8}{pc(r['top3']):>8}{pc(r['acc_1x2']):>8}{r['rps']:>8.4f}{r['logloss']:>9.4f}{pc(r['ou25']):>8}{pc(r['btts']):>8}")
    L.append("")
    L.append("Dumb baselines (exact score): " + ", ".join(f"{k}: {pc(v)}" for k, v in rep["baselines"].items()))
    L.append(f"Pick rule: draw_scale={rep.get('draw_scale', 1.0)}  (1.0 = pure most-likely scoreline; <1 penalises draw picks)")
    L.append("")
    L.append("By competition (ensemble, holdout):")
    for lg, r in rep["by_league"].items():
        L.append(f"  {lg:<3} n={r['n']:<4} exact {pc(r['exact'])}  1X2 {pc(r['acc_1x2'])}  RPS {r['rps']:.4f}")
    L.append("")
    L.append("When to shoot - exact-hit rate by confidence tier (holdout; confidence = model probability of the picked score):")
    for c in rep["calibration"]:
        L.append(f"  tier {c['tier']:<16} n={c['n']:<4} model said {pc(c['mean_predicted'])}  actually hit {pc(c['actual_hit'])}  draw picks {pc(c.get('draw_picks', 0))}")
    L.append("")
    L.append("Final ensemble weights:")
    for g, w in rep["weights_final"].items():
        L.append(f"  {g:<5} " + "  ".join(f"{k}={v:.2f}" for k, v in w.items()))
    return "\n".join(L)
