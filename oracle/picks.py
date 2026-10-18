"""Daily 'strongest recommendation': the most probable non-trivial market of the day, with an honest price check.

Probabilities come from the same calibrated score matrix as everything else; scripts/market_calibration.py showed that
when the model says 85-95% for a market it happens 89-92% of the time (slightly conservative). A market only qualifies
when it is likely (>= MIN_P) AND clearly above its own base rate (a 'lift'), so near-certain trivia (over 0.5 goals,
under 4.5 goals) does not crowd out real information. Every day's picks are logged and settled to prove the claimed
probability."""
import json, datetime as dt
import numpy as np, pandas as pd
from .config import DATA
from .markets import MARKETS, ON_WINNER, market_probs_fast

PICKS_CSV = DATA / "daily_picks.csv"
CAL_JSON = DATA / "market_calibration.json"
MIN_P = 0.85
MIN_LIFT = 8.0          # percentage points above the market's unconditional base rate
TRIVIAL = {"o05", "u45"}  # near-certain for almost every match: shown in the menu, never the headline


def _base():
    try:
        return {k: v["base_rate"] for k, v in json.loads(CAL_JSON.read_text(encoding="utf-8")).items()}
    except Exception:
        return {}


def winner_prices(o):
    """Map our market keys to Winner decimal prices from the odds block (only markets Winner really sells)."""
    if not o:
        return {}
    pr = {"1": o.get("h"), "x": o.get("d"), "2": o.get("a"), "o25": o.get("over25"), "u25": o.get("under25"),
          "btts": o.get("btts_yes"), "nobtts": o.get("btts_no")}
    pr.update(o.get("tg") or {})
    return {k: v for k, v in pr.items() if v}


def menu(row):
    """All markets of one match, most probable first: key, label, p%, lift, Winner price/EV (if sold), sold flag."""
    mk = (row.get("dist") or {}).get("mk")
    if not mk:
        return []
    base = _base()
    prices = winner_prices(row.get("odds"))
    out = []
    for k, p in mk.items():
        b = base.get(k)
        price = prices.get(k)
        out.append(dict(key=k, label=MARKETS[k][0], p=p, base=b, lift=None if b is None else round(p - b, 1),
                        price=price, ev=None if not price else round(p / 100 * price - 1, 3), on_winner=k in ON_WINNER))
    return sorted(out, key=lambda x: -x["p"])


def day_picks(rows, day, top=8):
    """rows: exported predictions. Returns the day's headline + lists."""
    cand = []
    for r in rows:
        if r["date"] != day:
            continue
        for m in menu(r):
            if m["key"] in TRIVIAL or m["p"] < 100 * MIN_P or (m["lift"] is not None and m["lift"] < MIN_LIFT):
                continue
            cand.append(dict(m, date=r["date"], league=r["league"], home=r["home"], away=r["away"],
                             kickoff=(r.get("odds") or {}).get("kickoff")))
    # one line per match: its most probable qualifying market (a match shouldn't fill the list three times)
    best = {}
    for c in sorted(cand, key=lambda x: -x["p"]):
        best.setdefault((c["home"], c["away"]), c)
    safe = sorted(best.values(), key=lambda x: -x["p"])[:top]
    # what Winner itself sells, even if less probable: highest-probability sold market per match
    sold = []
    for r in rows:
        if r["date"] != day:
            continue
        ms = [m for m in menu(r) if m["on_winner"] and m["price"] and m["key"] in ("1", "2", "o25", "u25", "tg23", "tg4p", "tg01", "btts", "nobtts")]
        if ms:
            m = max(ms, key=lambda x: x["p"])
            sold.append(dict(m, date=r["date"], league=r["league"], home=r["home"], away=r["away"], kickoff=(r.get("odds") or {}).get("kickoff")))
    sold = sorted(sold, key=lambda x: -x["p"])[:top]
    ev = sorted([dict(m, date=r["date"], league=r["league"], home=r["home"], away=r["away"], kickoff=(r.get("odds") or {}).get("kickoff"))
                 for r in rows if r["date"] == day for m in menu(r) if m["price"] and m["key"] in ("1", "x", "2", "o25", "u25", "btts", "nobtts")],
                key=lambda x: -x["ev"])[:5]
    return dict(date=day, headline=safe[0] if safe else None, safe=safe, sold=sold, best_ev=ev)


# ---------------------------------------------------------------- accountability: log every day's picks, settle them
PCOLS = ["made", "date", "league", "home", "away", "key", "label", "p", "price", "rank", "result", "hit", "settled"]


def _load():
    if not PICKS_CSV.exists():
        return pd.DataFrame(columns=PCOLS)
    df = pd.read_csv(PICKS_CSV, dtype={c: object for c in ("made", "date", "league", "home", "away", "key", "label", "result")})
    for c in PCOLS:
        if c not in df:
            df[c] = None
    for c in ("p", "price", "rank"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["settled"] = df["settled"].astype(str).isin(["True", "true", "1"])
    df["hit"] = df["hit"].astype(str).isin(["True", "true", "1"])
    for c in ("result",):
        df[c] = df[c].astype(object).where(df[c].notna(), "")
    return df


def record(rows, days):
    """Log the top qualifying markets (headline + next ones) of each day once, before kickoff."""
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    led = _load()
    have = {(r.date, r.home, r.away, r.key) for r in led.itertuples()}
    new = []
    for d in days:
        dp = day_picks(rows, d, top=5)
        for i, c in enumerate(dp["safe"]):
            if (c["date"], c["home"], c["away"], c["key"]) in have:
                continue
            ko = c.get("kickoff")
            if ko and ":" in str(ko):
                hh, mm = [int(x) for x in str(ko).split(":")]
                if now >= dt.datetime.fromisoformat(c["date"]).replace(hour=hh, minute=mm) - dt.timedelta(hours=3, minutes=15):
                    continue
            new.append(dict(made=now.isoformat(timespec="minutes"), date=c["date"], league=c["league"], home=c["home"], away=c["away"],
                            key=c["key"], label=c["label"], p=c["p"], price=c.get("price"), rank=i + 1, result="", hit=False, settled=False))
    if new:
        led = pd.concat([led, pd.DataFrame(new)], ignore_index=True)
        led.to_csv(PICKS_CSV, index=False, encoding="utf-8")
    return len(new)


def settle(m):
    led = _load()
    if led.empty:
        return None
    res = m[m.played][["league", "date", "home", "away", "hg", "ag"]].copy()
    res["date_r"] = res.date.dt.date.astype(str)
    for i, r in led.iterrows():
        if bool(r.settled):
            continue
        g = res[(res.league == r.league) & (res.home == r.home) & (res.away == r.away)]
        g = g[(pd.to_datetime(g.date_r) - pd.Timestamp(r.date)).abs() <= pd.Timedelta(days=3)]
        if g.empty:
            continue
        hg, ag = int(g.iloc[0].hg), int(g.iloc[0].ag)
        led.at[i, "result"] = f"{hg}-{ag}"
        led.at[i, "hit"] = bool(MARKETS[r.key][1](hg, ag))
        led.at[i, "settled"] = True
    led.to_csv(PICKS_CSV, index=False, encoding="utf-8")
    s = led[led.settled]
    if s.empty:
        return dict(n=0, open=int(len(led)), recent=[])
    return dict(n=int(len(s)), open=int((~led.settled).sum()), hits=int(s.hit.sum()), hit_rate=round(100 * float(s.hit.mean()), 1),
                promised=round(float(s.p.mean()), 1),
                headline=dict(n=int((s["rank"] == 1).sum()), hits=int(s[s["rank"] == 1].hit.sum())),
                recent=[dict(date=r.date, home=r.home, away=r.away, label=r.label, p=r.p, result=r.result, hit=bool(r.hit), price=None if pd.isna(r.price) else r.price)
                        for r in s.sort_values("date", ascending=False).head(30).itertuples()])
