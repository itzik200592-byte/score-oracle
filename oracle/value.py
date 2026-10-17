"""Winner value scanner + paper-bet ledger.

Honesty first: on 6,673 historical big-4 matches, flat bets on every selection our model rated as positive EV lost
13.9% against AVERAGE market odds (margin ~5%); long shots (odds 6+) lost 24%. Winner's margin is 11-18%, so a
model alone does not beat Winner. This module therefore (1) prices every Winner market with our calibrated
distribution, (2) flags selections only when the edge is larger than what noise and the margin explain, and
(3) records every flagged selection as a PAPER bet at Winner's price so the real ROI is measured before any money
is risked. The site shows the measured ROI next to the picks."""
import datetime as dt
import numpy as np, pandas as pd
from .config import DATA
from .odds import devig_power

PAPER_CSV = DATA / "paper_bets.csv"
# backtest truth per 1X2 odds bucket (flat stakes, EV>5% selections, average market odds). Negative = lost.
HIST_ROI = [((1.0, 1.5), None), ((1.5, 2.2), -10.9), ((2.2, 3.5), -10.2), ((3.5, 6.0), -14.5), ((6.0, 99), -23.6)]
MIN_EDGE = {"1x2": 0.08, "ou": 0.06, "btts": 0.06, "cs": 0.15}   # EV thresholds after Winner's margin


def hist_roi(odds):
    for (lo, hi), r in HIST_ROI:
        if lo <= odds < hi:
            return r
    return None


def scan(rows):
    """rows: exported prediction dicts (with odds + dist). Returns list of value selections sorted by EV."""
    out = []
    for p in rows:
        o, d = p.get("odds"), p.get("dist")
        if not o or not d:
            continue
        base = dict(date=p["date"], league=p["league"], home=p["home"], away=p["away"], kickoff=o.get("kickoff"))
        fair = devig_power([o["h"], o["d"], o["a"]])
        for k, pp, nm in (("h", p["pH"], p["home"]), ("d", p["pD"], "תיקו"), ("a", p["pA"], p["away"])):
            ev = pp / 100 * o[k] - 1
            out.append(dict(base, market="1x2", sel=k, label=nm, odds=o[k], model_p=pp, market_p=round(100 * fair["hda".index(k)]),
                            ev=round(100 * ev, 1), hist_roi=hist_roi(o[k]), surprise=o[k] >= 3.0 and pp >= 100 / o[k]))
        if o.get("over25") and o.get("under25"):
            po = d["over"]["2.5"] / 100
            fo = devig_power([o["over25"], o["under25"]])
            out.append(dict(base, market="ou", sel="over", label="מעל 2.5", odds=o["over25"], model_p=round(100 * po), market_p=round(100 * fo[0]),
                            ev=round(100 * (po * o["over25"] - 1), 1), hist_roi=-8.0, surprise=False))
            out.append(dict(base, market="ou", sel="under", label="מתחת 2.5", odds=o["under25"], model_p=round(100 * (1 - po)), market_p=round(100 * fo[1]),
                            ev=round(100 * ((1 - po) * o["under25"] - 1), 1), hist_roi=-8.0, surprise=False))
        if o.get("btts_yes") and o.get("btts_no"):
            pb = d["btts"] / 100
            fb = devig_power([o["btts_yes"], o["btts_no"]])
            out.append(dict(base, market="btts", sel="yes", label="שתיהן מבקיעות", odds=o["btts_yes"], model_p=round(100 * pb), market_p=round(100 * fb[0]),
                            ev=round(100 * (pb * o["btts_yes"] - 1), 1), hist_roi=None, surprise=False))
        for t in d["top"]:
            pr = (o.get("cs") or {}).get(t["s"])
            if pr:
                out.append(dict(base, market="cs", sel=t["s"], label=f"תוצאה {t['s']}", odds=pr, model_p=t["p"], market_p=None,
                                ev=round(100 * (t["p"] / 100 * pr - 1), 1), hist_roi=None, surprise=False))
    for s in out:
        s["flag"] = s["ev"] >= 100 * MIN_EDGE[s["market"]]
        s["strategies"] = strategies(s)
        s["loss_per_100"] = round(-s["ev"], 1) if s["ev"] < 0 else 0.0        # expected loss per 100 NIS staked, by the model
        s["stake_pct"] = stake_pct(s)
    return sorted(out, key=lambda s: -s["ev"])


def strategies(s):
    """Tags for the paper ledger: several strategies are tracked side by side so we learn which (if any) survives Winner."""
    t = []
    if s["flag"]:
        t.append("model_ev")                                   # model edge above Winner's margin (historically lost)
    if s["market"] == "1x2" and s["odds"] <= 1.6 and s["model_p"] >= 62:
        t.append("favourite")                                  # strong favourites: least negative bucket in the backtest
    if s.get("sharp_flag"):
        t.append("sharp_vs_winner")                            # Winner pays more than the sharp market (only evidence-backed edge)
    return t


def stake_pct(s):
    """Fractional Kelly (1/4) of bankroll. Negative edge -> 0: the honest answer is not to bet."""
    p = s["model_p"] / 100
    b = s["odds"] - 1
    k = (p * b - (1 - p)) / b if b > 0 else 0
    return round(max(0.0, 0.25 * k) * 100, 2)


# ------------------------------------------------------------ paper bets
PCOLS = ["made", "date", "league", "home", "away", "market", "sel", "label", "odds", "model_p", "ev", "kickoff", "stake", "result", "pnl", "settled", "strategy"]


def record(selections):
    """Log every flagged selection once (first time seen, before kickoff) as a 1-unit paper bet."""
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    led = pd.read_csv(PAPER_CSV) if PAPER_CSV.exists() else pd.DataFrame(columns=PCOLS)
    if "strategy" not in led:
        led["strategy"] = "model_ev"
    have = {(r.date, r.home, r.away, r.market, r.sel, r.strategy) for r in led.itertuples()}
    new = []
    for s in selections:
        for strat in s.get("strategies") or []:
            key = (s["date"], s["home"], s["away"], s["market"], s["sel"], strat)
            if key in have:
                continue
            ko = s.get("kickoff")
            if ko and ":" in str(ko):
                hh, mm = [int(x) for x in str(ko).split(":")]
                cutoff = dt.datetime.fromisoformat(s["date"]).replace(hour=hh, minute=mm) - dt.timedelta(hours=3, minutes=15)
                if now >= cutoff:
                    continue
            new.append(dict(made=now.isoformat(timespec="minutes"), date=s["date"], league=s["league"], home=s["home"], away=s["away"],
                            market=s["market"], sel=s["sel"], label=s["label"], odds=s["odds"], model_p=s["model_p"], ev=s["ev"],
                            kickoff=ko, stake=1.0, result="", pnl=np.nan, settled=False, strategy=strat))
    if new:
        led = pd.concat([led, pd.DataFrame(new)], ignore_index=True)
        led.to_csv(PAPER_CSV, index=False, encoding="utf-8")
    return len(new)


def settle(m):
    if not PAPER_CSV.exists():
        return None
    led = pd.read_csv(PAPER_CSV)
    if led.empty:
        return None
    res = m[m.played][["league", "date", "home", "away", "hg", "ag"]].copy()
    res["date_r"] = res.date.dt.date.astype(str)
    for i, r in led.iterrows():
        if r.settled is True or str(r.settled) == "True":
            continue
        g = res[(res.league == r.league) & (res.home == r.home) & (res.away == r.away)]
        g = g[(pd.to_datetime(g.date_r) - pd.Timestamp(r.date)).abs() <= pd.Timedelta(days=3)]
        if g.empty:
            continue
        hg, ag = int(g.iloc[0].hg), int(g.iloc[0].ag)
        won = {"1x2": lambda: {"h": hg > ag, "d": hg == ag, "a": ag > hg}[r.sel],
               "ou": lambda: (hg + ag >= 3) if r.sel == "over" else (hg + ag <= 2),
               "btts": lambda: (hg > 0 and ag > 0) if r.sel == "yes" else not (hg > 0 and ag > 0),
               "cs": lambda: f"{hg}-{ag}" == r.sel}[r.market]()
        led.at[i, "result"] = f"{hg}-{ag}"
        led.at[i, "pnl"] = round(float(r.stake) * (float(r.odds) - 1), 2) if won else -float(r.stake)
        led.at[i, "settled"] = True
    led.to_csv(PAPER_CSV, index=False, encoding="utf-8")
    if "strategy" not in led:
        led["strategy"] = "model_ev"
    s = led[led.settled.astype(str) == "True"]
    by = {}
    for mk, g in s.groupby("market"):
        by[mk] = dict(n=int(len(g)), won=int((g.pnl > 0).sum()), pnl=round(float(g.pnl.sum()), 2), roi=round(100 * float(g.pnl.sum()) / max(len(g), 1), 1))
    by_strat = {}
    for st, g in s.groupby("strategy"):
        by_strat[st] = dict(n=int(len(g)), won=int((g.pnl > 0).sum()), pnl=round(float(g.pnl.sum()), 2), roi=round(100 * float(g.pnl.sum()) / max(len(g), 1), 1),
                            open=int(((led.strategy == st) & (led.settled.astype(str) != "True")).sum()))
    return dict(n=int(len(s)), open=int(len(led) - len(s)), won=int((s.pnl > 0).sum()), pnl=round(float(s.pnl.sum()), 2),
                roi=round(100 * float(s.pnl.sum()) / max(len(s), 1), 1), by_market=by, by_strategy=by_strat,
                recent=[dict(date=r.date, home=r.home, away=r.away, label=r.label, odds=r.odds, model_p=r.model_p, result=r.result, pnl=r.pnl, strategy=r.strategy)
                        for r in s.sort_values("date", ascending=False).head(30).itertuples()])
