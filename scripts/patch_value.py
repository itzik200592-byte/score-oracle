"""One-off patch: multi-strategy paper ledger, expected loss, stake rule, sharp comparison hook."""
import ast, pathlib
R = pathlib.Path(__file__).resolve().parent.parent

p = R / "oracle/value.py"; s = p.read_text(encoding="utf-8")
s = s.replace('''    for s in out:
        s["flag"] = s["ev"] >= 100 * MIN_EDGE[s["market"]]
    return sorted(out, key=lambda s: -s["ev"])''', '''    for s in out:
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
    return round(max(0.0, 0.25 * k) * 100, 2)''')
s = s.replace('PCOLS = ["made", "date", "league", "home", "away", "market", "sel", "label", "odds", "model_p", "ev", "kickoff", "stake", "result", "pnl", "settled"]',
              'PCOLS = ["made", "date", "league", "home", "away", "market", "sel", "label", "odds", "model_p", "ev", "kickoff", "stake", "result", "pnl", "settled", "strategy"]')
old = '''    have = {(r.date, r.home, r.away, r.market, r.sel) for r in led.itertuples()}
    new = []
    for s in selections:
        if not s["flag"]:
            continue
        key = (s["date"], s["home"], s["away"], s["market"], s["sel"])
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
                        kickoff=ko, stake=1.0, result="", pnl=np.nan, settled=False))'''
new = '''    if "strategy" not in led:
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
                            kickoff=ko, stake=1.0, result="", pnl=np.nan, settled=False, strategy=strat))'''
assert old in s; s = s.replace(old, new)
old3 = '''    s = led[led.settled.astype(str) == "True"]
    by = {}
    for mk, g in s.groupby("market"):
        by[mk] = dict(n=int(len(g)), won=int((g.pnl > 0).sum()), pnl=round(float(g.pnl.sum()), 2), roi=round(100 * float(g.pnl.sum()) / max(len(g), 1), 1))'''
new3 = '''    if "strategy" not in led:
        led["strategy"] = "model_ev"
    s = led[led.settled.astype(str) == "True"]
    by = {}
    for mk, g in s.groupby("market"):
        by[mk] = dict(n=int(len(g)), won=int((g.pnl > 0).sum()), pnl=round(float(g.pnl.sum()), 2), roi=round(100 * float(g.pnl.sum()) / max(len(g), 1), 1))
    by_strat = {}
    for st, g in s.groupby("strategy"):
        by_strat[st] = dict(n=int(len(g)), won=int((g.pnl > 0).sum()), pnl=round(float(g.pnl.sum()), 2), roi=round(100 * float(g.pnl.sum()) / max(len(g), 1), 1),
                            open=int(((led.strategy == st) & (led.settled.astype(str) != "True")).sum()))'''
assert old3 in s; s = s.replace(old3, new3)
s = s.replace('roi=round(100 * float(s.pnl.sum()) / max(len(s), 1), 1), by_market=by,', 'roi=round(100 * float(s.pnl.sum()) / max(len(s), 1), 1), by_market=by, by_strategy=by_strat,')
s = s.replace('recent=[dict(date=r.date, home=r.home, away=r.away, label=r.label, odds=r.odds, model_p=r.model_p, result=r.result, pnl=r.pnl)',
              'recent=[dict(date=r.date, home=r.home, away=r.away, label=r.label, odds=r.odds, model_p=r.model_p, result=r.result, pnl=r.pnl, strategy=r.strategy)')
p.write_text(s, encoding="utf-8")

p = R / "oracle/export.py"; s = p.read_text(encoding="utf-8")
old = '''    vsel = value.scan(rows)'''
new = '''    from . import sharp
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
            v["strategies"] = value.strategies(v)'''
assert old in s; s = s.replace(old, new)
s = s.replace('''                value=[v for v in vsel if v["flag"] or v["surprise"]][:80], paper=paper,''',
              '''                value=[v for v in vsel if v["flag"] or v["surprise"] or v.get("sharp_flag") or "favourite" in v["strategies"]][:120], paper=paper,
                sharp_available=bool(sharp.key()), sharp_matches=sharp_n,''')
p.write_text(s, encoding="utf-8")
for f in ("oracle/value.py", "oracle/export.py", "oracle/sharp.py"):
    ast.parse((R / f).read_text(encoding="utf-8"))
print("patched ok")
