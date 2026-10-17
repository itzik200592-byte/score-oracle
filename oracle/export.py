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
            for k in ("over25", "under25", "btts_yes", "btts_no", "kickoff"):
                if e.get(k):
                    o[k] = e[k]
            cs = (e.get("cs") or {}).get(row["pick"].replace("-", "-"))
            if cs:
                o["pick_price"] = cs
            if row.get("dist"):
                o["cs"] = {t["s"]: e["cs"][t["s"]] for t in row["dist"]["top"] if t["s"] in (e.get("cs") or {})}
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


def _compact(c):
    if not c or "note" in c:
        return None
    def rec(r):
        return None if not r else f"{r['W']}-{r['D']}-{r['L']} (ש {r['gf']}:{r['ga']})"
    out = dict(form=c.get("form_last6"), last10=rec(c.get("last10")), home10=rec(c.get("home_record_last10")),
               away10=rec(c.get("away_record_last10")), table=c.get("table"), rest=c.get("days_since_last_match"),
               m14=c.get("matches_last14d"), partial=bool((c.get("data_coverage") or {}).get("warning")))
    return out


def _attach_context(m, rows):
    from . import context as CX
    for row in rows:
        try:
            dos = CX.dossier(m, row["home"], row["away"], row["league"])
        except Exception:
            continue
        row["ctx"] = dict(home=_compact(dos["home_team"]), away=_compact(dos["away_team"]), h2h=dos["head_to_head_recent"][-3:])


def _opinions():
    """Situation-analyst opinions saved by the agent in data/opinions/*.json -> {(date, norm_home, norm_away): entry}"""
    from .names import norm
    out = {}
    d = ROOT / "data" / "opinions"
    if not d.exists():
        return out
    for f in sorted(d.glob("*.json")):
        try:
            j = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        for e in j.get("matches", []):
            if e.get("date") and e.get("home") and e.get("away"):
                out[(e["date"], norm(e["home"]), norm(e["away"]))] = dict(e, made_at=j.get("made_at"))
    return out


def export(m, pred, ledger=True):
    DOCS.mkdir(exist_ok=True)
    rows = []
    for r in pred.itertuples(index=False):
        tops = [{"score": f"{a}-{b}", "p": float(p)} for a, b, p in _TOP.findall(r.top5)]
        rows.append(dict(date=r.date, league=r.league, home=r.home, away=r.away, pick=r.pick,
                         p_pick=round(100 * r.p_pick, 1), tier=r.tier, pH=round(100 * r.pH), pD=round(100 * r.pD),
                         pA=round(100 * r.pA), over25=round(100 * r.over25), btts=round(100 * r.btts),
                         xg_h=round(r.exp_goals_h, 2), xg_a=round(r.exp_goals_a, 2), top=tops,
                         dist=getattr(r, "dist", None), live_mkt=bool(getattr(r, "live_mkt", False)), model_only=[round(100 * r.pH0), round(100 * r.pD0), round(100 * r.pA0)]))
    _attach_odds(m, rows)
    _attach_context(m, rows)
    from .names import norm as _norm
    ops = _opinions()
    for row in rows:
        e = ops.get((row["date"], _norm(row["home"]), _norm(row["away"])))
        if e:
            v = e.get("verification") or {}
            row["opinion"] = dict(e, verified=v.get("status", "unverified"), unknown_players=v.get("unknown", []))
    from . import track, value
    if ledger:
        track.upsert(rows, m)
    from . import sharp
    sharp_n = 0
    try:
        sharp_n = sharp.compare(rows, sharp.fetch())
    except Exception as ex:
        print("sharp comparison skipped:", ex)
    vsel = value.scan(rows)
    for v in vsel:   # Winner pays more than the sharp market? (only with an Odds API key)
        r = next((x for x in rows if x["date"] == v["date"] and x["home"] == v["home"] and x["away"] == v["away"]), None)
        sh = (r or {}).get("sharp")
        if sh and v["market"] == "1x2":
            v["sharp_p"] = sh["p"][v["sel"]]; v["sharp_edge"] = sh["edge"][v["sel"]]
            v["sharp_flag"] = sh["flag"] == v["sel"]
            v["strategies"] = value.strategies(v)
    if ledger:
        value.record(vsel)
    paper = value.settle(m)
    bt = None
    f = OUT / "backtest_report.json"
    if f.exists():
        rep = json.loads(f.read_text(encoding="utf-8"))
        e = rep["ensemble"]["all"]
        bt = {"holdout_from": rep["holdout_start"], "n": e["n"], "exact_pct": round(100 * e["exact"], 1),
              "result_pct": round(100 * e["acc_1x2"], 1), "baseline_11": round(100 * rep["baselines"]["always 1-1"], 1),
              "tiers": [{"tier": c["tier"][0], "n": c["n"], "hit_pct": round(100 * c["actual_hit"], 1)} for c in rep["calibration"]]}
    fresh, stale = {}, []
    today = pd.Timestamp.now().normalize()
    for lg, g in m.groupby("league"):
        p = g[g.played]
        fresh[lg] = str(p.date.max().date()) if len(p) else None
        # fixtures that should have finished (2+ days ago) but have no result = a results source is broken
        missing = g[(~g.played) & (g.date <= today - pd.Timedelta(days=2)) & (g.date >= today - pd.Timedelta(days=21))]
        if len(missing):
            stale.append(dict(league=lg, missing=int(len(missing)), oldest=str(missing.date.min().date())))
    cov = []
    for lg, g in m.groupby("league"):
        p = g[g.played]
        cov.append(dict(league=lg, played=int(len(p)), upcoming=int((~g.played).sum()),
                        last=str(p.date.max().date()) if len(p) else None))
    calib = {}
    if bt is not None and f.exists():
        calib = {lg: dict(n=v["n"], direction=round(100 * v["acc_1x2"], 1), exact=round(100 * v["exact"], 1))
                 for lg, v in rep.get("by_league", {}).items()}
    data = dict(generated_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
                leagues={k: v["he"] for k, v in LEAGUES.items()}, predictions=rows,
                ledger=_ledger_stats(m), track=track.export_block(m), backtest=bt, coverage=cov, calib=calib, last_result=fresh, stale=stale,
                value=[v for v in vsel if v["flag"] or v["surprise"] or v.get("sharp_flag") or "favourite" in v["strategies"]][:120], paper=paper,
                sharp_available=bool(sharp.key()), sharp_matches=sharp_n,
                value_truth=dict(note="backtest 2022-2026, 6,673 matches, average market odds (Winner margin is higher)", all_ev=-13.9, longshots=-23.6, favourites=-1.4, ou=-7.9))
    (DOCS / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return DOCS / "data.json"
