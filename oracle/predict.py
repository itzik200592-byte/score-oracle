"""Live predictions, prediction ledger (honest self-tracking), and the Hebrew HTML report."""
import json, html, datetime as dt
import numpy as np, pandas as pd
from .config import WEIGHTS_JSON, LEDGER_CSV, ADJ_JSON, OUT, LEAGUES
from .models import Suite, COMPONENTS, outcome_probs, over25, btts
from .evaluate import blend, group_of, GROUPS
from .sniper import pick, top_k, tier
from .models import score_matrix, DEFAULT_RHO, BIG4
from .odds import load_live, devig_power, lambdas_from_probs, p_over_from, LIVE_MARKET_WEIGHT
from .names import norm

DEFAULT_CFG = dict(weights={g: {c: 1 / len(cs) for c in cs} for g, cs in GROUPS.items()}, beta=0.0, draw_scale=1.0,
                   cuts=[0.11, 0.14], params={})


def load_cfg():
    if WEIGHTS_JSON.exists():
        return json.loads(WEIGHTS_JSON.read_text(encoding="utf-8"))
    print("note: ensemble.json missing, using equal weights. Run `python -m oracle backtest` to learn them.")
    return DEFAULT_CFG


def load_adj():
    return json.loads(ADJ_JSON.read_text(encoding="utf-8")) if ADJ_JSON.exists() else {}


def predict_fixtures(m, fixtures, cfg=None, adj=None, as_of=None):
    cfg = cfg or load_cfg()
    adj = load_adj() if adj is None else adj
    as_of = as_of or (pd.Timestamp.now().normalize() + pd.Timedelta(days=1))
    suite = Suite(cfg.get("params") or {}).fit(m[m.played], as_of)
    mats = suite.matrices(fixtures, adj)
    live, _ = load_live()
    out = []
    for i, r in enumerate(fixtures.itertuples(index=False)):
        w = dict(cfg["weights"][group_of(r.league)])
        comps = {c: mats[c][i] for c in w}
        base = blend(comps, w)
        if base is None:
            continue
        pH0, pD0, pA0 = outcome_probs(base)
        live_used = False
        key = (r.date.date().isoformat(), norm(r.home), norm(r.away))
        if key in live and r.league not in BIG4:
            # competitions without odds history: fold the live bookmaker price into the blend
            o = live[key]
            T = float((base.sum(1) * np.arange(base.shape[0])).sum() + (base.sum(0) * np.arange(base.shape[1])).sum())
            lh, la = lambdas_from_probs(devig_power([o["h"], o["d"], o["a"]]), T, p_over_from(o))
            comps["mkt"] = score_matrix(lh, la, DEFAULT_RHO)
            w = {c: (1 - LIVE_MARKET_WEIGHT) * v for c, v in w.items()}
            w["mkt"] = LIVE_MARKET_WEIGHT
            live_used = True
        P = blend(comps, w)
        h, a = pick(P, cfg["beta"], cfg.get("draw_scale", 1.0))
        pH, pD, pA = outcome_probs(P)
        tops = top_k(P, 5)
        p_pick = float(P[h, a])
        sscore = p_pick  # tier = the model's own confidence in the picked scoreline
        out.append(dict(date=r.date.date().isoformat(), league=r.league, home=r.home, away=r.away, pick=f"{h}-{a}",
                        p_pick=p_pick, tier=tier(sscore, cfg["cuts"]), pH=pH, pD=pD, pA=pA, pH0=pH0, pD0=pD0, pA0=pA0, live_mkt=live_used, over25=over25(P), btts=btts(P),
                        top5=" | ".join(f"{x}-{y} {100 * p:.1f}%" for (x, y), p in tops),
                        exp_goals_h=float((P.sum(1) * np.arange(P.shape[0])).sum()),
                        exp_goals_a=float((P.sum(0) * np.arange(P.shape[1])).sum()),
                        parts=",".join(c for c in w if not np.isnan(mats[c][i][0, 0]))))
    return pd.DataFrame(out)


def upcoming(m, days=7, leagues=None):
    today = pd.Timestamp.now().normalize()
    f = m[(~m.played) & (m.date >= today) & (m.date <= today + pd.Timedelta(days=days))]
    if leagues:
        f = f[f.league.isin(leagues)]
    return f.sort_values(["date", "league"]).reset_index(drop=True)


# ----------------------------------------------------------------- ledger
def ledger_add(pred):
    if pred.empty:
        return
    pred = pred.assign(made=dt.datetime.now().isoformat(timespec="minutes"))
    if LEDGER_CSV.exists():
        old = pd.read_csv(LEDGER_CSV)
        # keep the earliest prediction per fixture (no hindsight rewrites)
        key = lambda d: d.league + "|" + d.date + "|" + d.home + "|" + d.away
        new = pred[~key(pred).isin(set(key(old)))]
        pred = pd.concat([old, new], ignore_index=True)
    pred.to_csv(LEDGER_CSV, index=False, encoding="utf-8")


def review(m):
    if not LEDGER_CSV.exists():
        return "Ledger is empty. Run `python -m oracle predict` before matches and `review` after they finish."
    led = pd.read_csv(LEDGER_CSV)
    res = m[m.played][["league", "date", "home", "away", "hg", "ag"]].copy()
    res["date"] = res.date.dt.date.astype(str)
    j = led.merge(res, on=["league", "home", "away"], suffixes=("", "_r"))
    j = j[(pd.to_datetime(j.date_r) - pd.to_datetime(j.date)).abs() <= pd.Timedelta(days=3)]
    if j.empty:
        return "No finished matches in the ledger yet."
    j["hit"] = j.pick == (j.hg.astype(int).astype(str) + "-" + j.ag.astype(int).astype(str))
    pk = j.pick.str.split("-", expand=True).astype(int)
    out_p = np.sign(pk[0] - pk[1]); out_a = np.sign(j.hg - j.ag)
    j["out_ok"] = out_p == out_a
    L = [f"LIVE LEDGER: {len(j)} finished predictions", f"  exact score hits: {int(j.hit.sum())}  ({100 * j.hit.mean():.1f}%)",
         f"  correct result (1X2 from the pick): {100 * j.out_ok.mean():.1f}%"]
    for t, g in j.groupby("tier"):
        L.append(f"  tier {t}: n={len(g)}  exact {100 * g.hit.mean():.1f}%  result {100 * g.out_ok.mean():.1f}%")
    for lg, g in j.groupby("league"):
        L.append(f"  {lg}: n={len(g)}  exact {100 * g.hit.mean():.1f}%  result {100 * g.out_ok.mean():.1f}%")
    return "\n".join(L)


# ----------------------------------------------------------------- HTML (Hebrew, RTL)
def html_report(pred, path=None):
    path = path or OUT / f"predictions_{dt.date.today().isoformat()}.html"
    css = """body{font-family:Segoe UI,Arial,sans-serif;background:#0f1419;color:#e6edf3;margin:0;padding:24px}
h1{margin:0 0 4px}h2{margin:28px 0 8px;color:#f0b429}.sub{color:#8b98a5;margin-bottom:16px}
table{width:100%;border-collapse:collapse;background:#161d26;border-radius:10px;overflow:hidden}
th,td{padding:9px 10px;text-align:right;border-bottom:1px solid #222c38;font-size:14px}th{background:#1c2633;color:#8b98a5;font-weight:600}
.pick{font-size:20px;font-weight:700;direction:ltr;display:inline-block}.A{color:#3fb950}.B{color:#f0b429}.C{color:#8b98a5}
.bar{display:inline-block;height:8px;border-radius:4px}.h{background:#3fb950}.d{background:#8b98a5}.a{background:#58a6ff}
.small{color:#8b98a5;font-size:12px;direction:ltr;text-align:left}.note{margin-top:22px;color:#8b98a5;font-size:13px;line-height:1.7}"""
    parts = [f"<!doctype html><html lang='he' dir='rtl'><meta charset='utf-8'><title>Score Oracle</title><style>{css}</style><body>",
             f"<h1>Score Oracle: חיזוי תוצאות</h1><div class='sub'>נוצר ב-{dt.datetime.now():%d/%m/%Y %H:%M}. מודלים סטטיסטיים בלבד, לא ייעוץ הימורים.</div>"]
    for lg in ["IL", "CL", "EL", "PL", "LL", "SA", "L1"]:
        g = pred[pred.league == lg]
        if g.empty:
            continue
        parts.append(f"<h2>{html.escape(LEAGUES[lg]['he'])}</h2><table><tr><th>תאריך</th><th>משחק</th><th>הניחוש</th><th>דירוג</th><th>הסתברות לתוצאה</th><th>ניצחון / תיקו / הפסד (בית)</th><th>עוד תוצאות סבירות</th><th>מעל 2.5</th></tr>")
        for r in g.itertuples():
            bar = "".join(f"<span class='bar {c}' style='width:{max(2, int(70 * p))}px'></span>" for c, p in (("h", r.pH), ("d", r.pD), ("a", r.pA)))
            parts.append(f"<tr><td>{r.date[5:]}</td><td>{html.escape(r.home)} - {html.escape(r.away)}</td>"
                         f"<td><span class='pick {r.tier}'>{r.pick}</span></td><td class='{r.tier}'>{r.tier}</td>"
                         f"<td>{100 * r.p_pick:.1f}%</td><td>{bar}<div class='small'>{100 * r.pH:.0f}% / {100 * r.pD:.0f}% / {100 * r.pA:.0f}%</div></td>"
                         f"<td class='small'>{html.escape(r.top5)}</td><td>{100 * r.over25:.0f}%</td></tr>")
        parts.append("</table>")
    parts.append("<div class='note'>איך לקרוא: <b>A</b> = משחק שבו למודל יש ודאות גבוהה יחסית בתוצאה המדויקת (הכי שווה להתמקד בו), "
                 "<b>B</b> = ודאות בינונית, <b>C</b> = משחק פתוח שבו כמה תוצאות כמעט שוות. גם ב-A פגיעה מדויקת היא בערך אחת מכל שמונה עד עשרה משחקים. "
                 "אין מודל שפוגע בתוצאה מדויקת ברוב המשחקים, כי כדורגל הוא משחק עם הרבה מקריות.</div></body></html>")
    path.write_text("".join(parts), encoding="utf-8")
    return path
