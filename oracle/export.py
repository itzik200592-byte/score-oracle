"""Export everything the mobile site needs into docs/data.json."""
import json, datetime as dt, re
import numpy as np, pandas as pd
from .config import ROOT, OUT, LEDGER_CSV, LEAGUES, WEIGHTS_JSON

DOCS = ROOT / "docs"
_TOP = re.compile(r"(\d+)-(\d+) ([\d.]+)%")


def _ledger_stats(m):
    if not LEDGER_CSV.exists():
        return None
    led = pd.read_csv(LEDGER_CSV)
    res = m[m.played][["league", "date", "home", "away", "hg", "ag"]].copy()
    res["date_r"] = res.date.dt.date.astype(str)
    j = led.merge(res.drop(columns="date"), on=["league", "home", "away"])
    j = j[(pd.to_datetime(j.date_r) - pd.to_datetime(j.date)).abs() <= pd.Timedelta(days=3)]
    if j.empty:
        return {"n": 0}
    j["hit"] = j.pick == (j.hg.astype(int).astype(str) + "-" + j.ag.astype(int).astype(str))
    pk = j.pick.str.split("-", expand=True).astype(int)
    j["out_ok"] = np.sign(pk[0] - pk[1]) == np.sign(j.hg - j.ag)

    def block(g):
        return {"n": int(len(g)), "exact": int(g.hit.sum()), "exact_pct": round(100 * g.hit.mean(), 1),
                "result_pct": round(100 * g.out_ok.mean(), 1)}
    out = {"all": block(j), "by_tier": {t: block(g) for t, g in j.groupby("tier")},
           "by_league": {lg: block(g) for lg, g in j.groupby("league")}}
    recent = j.sort_values("date", ascending=False).head(40)
    out["recent"] = [dict(date=r.date, league=r.league, home=r.home, away=r.away, pick=r.pick, tier=r.tier,
                          actual=f"{int(r.hg)}-{int(r.ag)}", hit=bool(r.hit), out_ok=bool(r.out_ok))
                     for r in recent.itertuples()]
    return out


from .odds import load_live as _load_live, ODDS_LIVE, LIVE_MARKET_WEIGHT  # noqa: F401

MIN_STAR_ODDS = 1.5     # user rule: odds of 1.5 or more ...
MIN_STAR_PROB = 50.0    # ... and the prediction rates that outcome at 50% or more ("looks safe")


def _live_odds():
    return _load_live()


def _attach_odds(m, rows):
    """Adds bookmaker odds + model edge + a star flag to each prediction row (in place)."""
    from .names import norm
    live, fetched = _live_odds()
    fd = {}
    for r in m[~m.played].itertuples(index=False):
        if r.o_h == r.o_h and r.o_d == r.o_d and r.o_a == r.o_a:
            fd[(r.date.date().isoformat(), norm(r.home), norm(r.away))] = r
    for row in rows:
        key = (row["date"], norm(row["home"]), norm(row["away"]))
        o = None
        if key in live:
            e = live[key]
            o = dict(h=e["h"], d=e["d"], a=e["a"], src=e.get("source") or "live", at=fetched)
        elif key in fd:
            e = fd[key]
            o = dict(h=round(float(e.o_h), 2), d=round(float(e.o_d), 2), a=round(float(e.o_a), 2),
                     src="football-data (ממוצע שוק)", at=None)
        if not o:
            continue
        p = dict(h=row["pH"], d=row["pD"], a=row["pA"])
        implied = {k: 1 / o[k] for k in "hda"}
        tot = sum(implied.values())
        o["margin"] = round(100 * (tot - 1), 1)
        o["market_p"] = {k: round(100 * implied[k] / tot) for k in "hda"}
        o["ev"] = {k: round(p[k] / 100 * o[k] - 1, 3) for k in "hda"}
        cands = [k for k in "hda" if o[k] >= MIN_STAR_ODDS and p[k] >= MIN_STAR_PROB]
        if cands:
            k = max(cands, key=lambda c: p[c])
            o["star"] = dict(outcome=k, odds=o[k], model_p=p[k], market_p=o["market_p"][k], ev=o["ev"][k], value=o["ev"][k] > 0)
        row["odds"] = o


def export(m, pred):
    DOCS.mkdir(exist_ok=True)
    rows = []
    for r in pred.itertuples(index=False):
        tops = [{"score": f"{a}-{b}", "p": float(p)} for a, b, p in _TOP.findall(r.top5)]
        rows.append(dict(date=r.date, league=r.league, home=r.home, away=r.away, pick=r.pick,
                         p_pick=round(100 * r.p_pick, 1), tier=r.tier, pH=round(100 * r.pH), pD=round(100 * r.pD),
                         pA=round(100 * r.pA), over25=round(100 * r.over25), btts=round(100 * r.btts),
                         xg_h=round(r.exp_goals_h, 2), xg_a=round(r.exp_goals_a, 2), top=tops,
                         live_mkt=bool(getattr(r, "live_mkt", False)), model_only=[round(100 * r.pH0), round(100 * r.pD0), round(100 * r.pA0)]))
    _attach_odds(m, rows)
    bt = None
    f = OUT / "backtest_report.json"
    if f.exists():
        rep = json.loads(f.read_text(encoding="utf-8"))
        e = rep["ensemble"]["all"]
        bt = {"holdout_from": rep["holdout_start"], "n": e["n"], "exact_pct": round(100 * e["exact"], 1),
              "result_pct": round(100 * e["acc_1x2"], 1), "baseline_11": round(100 * rep["baselines"]["always 1-1"], 1),
              "tiers": [{"tier": c["tier"][0], "n": c["n"], "hit_pct": round(100 * c["actual_hit"], 1)} for c in rep["calibration"]]}
    cov = []
    for lg, g in m.groupby("league"):
        p = g[g.played]
        cov.append(dict(league=lg, played=int(len(p)), upcoming=int((~g.played).sum()),
                        last=str(p.date.max().date()) if len(p) else None))
    data = dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                leagues={k: v["he"] for k, v in LEAGUES.items()}, predictions=rows,
                ledger=_ledger_stats(m), backtest=bt, coverage=cov)
    (DOCS / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return DOCS / "data.json"
