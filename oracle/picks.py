"""Daily recommendations, WINNER ONLY.

Rules (set by the user): only markets Winner actually sells, only selections priced at MIN_ODDS (1.50) or more.
Winner sells: 1X2, over/under 2.5, total-goals ranges (0-1, 2-3, 4+), both teams to score, and the 3-way handicap
('הימור יתרון'). Everything is priced from the same calibrated score matrix; a selection's probability can never
exceed ~1/odds, so with odds >= 1.50 the achievable ceiling is about 60-65%: a '90% pick' does not exist at these
prices, and the module says so instead of inventing one.
Every day's top picks are logged before kickoff and settled, so the claimed probability is audited."""
import datetime as dt
import numpy as np, pandas as pd
from .config import DATA

PICKS_CSV = DATA / "daily_picks.csv"
MIN_ODDS = 1.50
MKT_LABEL = {"o25": "מעל 2.5 שערים", "u25": "מתחת 2.5 שערים", "tg01": "0 עד 1 שערים", "tg23": "2 עד 3 שערים", "tg4p": "4 שערים ומעלה",
             "btts": "שתיהן מבקיעות", "nobtts": "לפחות אחת לא מבקיעה"}


def _marg(row):
    """P(home goals - away goals = d) for d in -6..6 (ends carry the tails)."""
    mg = (row.get("dist") or {}).get("marg")
    return None if not mg else {int(k): v / 100 for k, v in mg.items()}


def hc_probs(marg, s):
    """Winner's 3-way handicap. s = the margin (home-away) that ties after the handicap. A: d>s, X: d==s, B: d<s."""
    a = sum(p for d, p in marg.items() if d > s)
    x = marg.get(s, 0.0)
    b = sum(p for d, p in marg.items() if d < s)
    return a, x, b


def hc_eval(d, s):
    return "A" if d > s else ("X" if d == s else "B")


def _hc_labels(h, a, s):
    """Plain-Hebrew meaning of Winner's 3-way handicap outcomes (A: d>s, X: d==s, B: d<s; d = home - away goals)."""
    def not_lose(team, n):
        return f"{team} לא מפסידה" if n == 1 else f"{team} לא מפסידה בהפרש {n} או יותר"
    if s > 0:
        return (f"{h} מנצחת בהפרש {s + 1} או יותר", f"{h} מנצחת בדיוק בהפרש {s}", not_lose(a, s))
    L = -s
    return (not_lose(h, L), f"{a} מנצחת בדיוק בהפרש {L}", f"{a} מנצחת בהפרש {L + 1} או יותר")


def menu(row):
    """All Winner-sold selections of one match with model probability, price, EV and eligibility (price >= MIN_ODDS)."""
    o, dist = row.get("odds"), row.get("dist")
    if not o or not dist:
        return []
    h, a = row["home"], row["away"]
    out = []

    def add(key, label, p, price, group):
        if price:
            out.append(dict(key=key, label=label, p=round(100 * p, 1), price=float(price), ev=round(p * float(price) - 1, 3),
                            eligible=float(price) >= MIN_ODDS, group=group))

    add("1", f"{h} מנצחת", row["pH"] / 100, o.get("h"), "תוצאה")
    add("x", "תיקו", row["pD"] / 100, o.get("d"), "תוצאה")
    add("2", f"{a} מנצחת", row["pA"] / 100, o.get("a"), "תוצאה")
    mk = dist.get("mk") or {}
    for k, price in (("o25", o.get("over25")), ("u25", o.get("under25")), ("btts", o.get("btts_yes")), ("nobtts", o.get("btts_no"))):
        if price and k in mk:
            add(k, MKT_LABEL[k], mk[k] / 100, price, "שערים")
    for k, price in (o.get("tg") or {}).items():
        if k in mk:
            add(k, MKT_LABEL[k], mk[k] / 100, price, "שערים")
    hc, marg = o.get("hc"), _marg(row)
    if hc and marg:
        pa, px, pb = hc_probs(marg, hc["s"])
        labs = _hc_labels(h, a, hc["s"])
        for k, p, lab, pr in (("A", pa, labs[0], hc["prices"][0]), ("X", px, labs[1], hc["prices"][1]), ("B", pb, labs[2], hc["prices"][2])):
            add(f"hc:{hc['s']}:{k}", lab + " (יתרון)", p, pr, "יתרון")
    return sorted(out, key=lambda x: -x["p"])


def day_picks(rows, day, top=10):
    elig_all = []
    for r in rows:
        if r["date"] != day:
            continue
        ko = (r.get("odds") or {}).get("kickoff")
        for m in menu(r):
            if m["eligible"]:
                elig_all.append(dict(m, date=r["date"], league=r["league"], home=r["home"], away=r["away"], kickoff=ko))
    best = {}
    for c in sorted(elig_all, key=lambda x: (-x["p"], -x["ev"])):
        best.setdefault((c["home"], c["away"]), c)
    top_list = sorted(best.values(), key=lambda x: (-x["p"], -x["ev"]))[:top]
    # underdogs: price >= 3, the selection whose model probability most exceeds what the price implies
    dogs = sorted([c for c in elig_all if c["price"] >= 3.0], key=lambda x: -x["ev"])[:4]
    return dict(date=day, headline=top_list[0] if top_list else None, top=top_list, underdogs=dogs, min_odds=MIN_ODDS,
                ceiling=round(100 * max((c["p"] / 100 for c in elig_all), default=0), 1))


# ---------------------------------------------------------------- accountability
PCOLS = ["made", "date", "league", "home", "away", "key", "label", "p", "price", "rank", "result", "hit", "settled", "pnl"]


def _load():
    if not PICKS_CSV.exists():
        return pd.DataFrame(columns=PCOLS)
    df = pd.read_csv(PICKS_CSV, dtype={c: object for c in ("made", "date", "league", "home", "away", "key", "label", "result")})
    for c in PCOLS:
        if c not in df:
            df[c] = None
    for c in ("p", "price", "rank", "pnl"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["settled"] = df["settled"].astype(str).isin(["True", "true", "1"])
    df["hit"] = df["hit"].astype(str).isin(["True", "true", "1"])
    df["result"] = df["result"].astype(object).where(df["result"].notna(), "")
    return df


def record(rows, days):
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    led = _load()
    have = {(r.date, r.home, r.away, r.key) for r in led.itertuples()}
    new = []
    for d in days:
        for i, c in enumerate(day_picks(rows, d, top=3)["top"]):
            if (c["date"], c["home"], c["away"], c["key"]) in have:
                continue
            ko = c.get("kickoff")
            if ko and ":" in str(ko):
                hh, mm = [int(x) for x in str(ko).split(":")]
                if now >= dt.datetime.fromisoformat(c["date"]).replace(hour=hh, minute=mm) - dt.timedelta(hours=3, minutes=15):
                    continue
            new.append(dict(made=now.isoformat(timespec="minutes"), date=c["date"], league=c["league"], home=c["home"], away=c["away"],
                            key=c["key"], label=c["label"], p=c["p"], price=c["price"], rank=i + 1, result="", hit=False, settled=False, pnl=np.nan))
    if new:
        led = pd.concat([led, pd.DataFrame(new)], ignore_index=True)
        led.to_csv(PICKS_CSV, index=False, encoding="utf-8")
    return len(new)


def _won(key, hg, ag):
    d = hg - ag
    if key == "1":
        return hg > ag
    if key == "x":
        return hg == ag
    if key == "2":
        return ag > hg
    if key == "o25":
        return hg + ag >= 3
    if key == "u25":
        return hg + ag <= 2
    if key == "tg01":
        return hg + ag <= 1
    if key == "tg23":
        return 2 <= hg + ag <= 3
    if key == "tg4p":
        return hg + ag >= 4
    if key == "btts":
        return hg > 0 and ag > 0
    if key == "nobtts":
        return hg == 0 or ag == 0
    if key.startswith("hc:"):
        _, s, side = key.split(":")
        return hc_eval(d, int(s)) == side
    return False


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
        hit = _won(r.key, hg, ag)
        led.at[i, "result"] = f"{hg}-{ag}"
        led.at[i, "hit"] = bool(hit)
        led.at[i, "pnl"] = round(float(r.price) - 1, 2) if hit else -1.0
        led.at[i, "settled"] = True
    led.to_csv(PICKS_CSV, index=False, encoding="utf-8")
    s = led[led.settled]
    if s.empty:
        return dict(n=0, open=int(len(led)), recent=[])
    head = s[s["rank"] == 1]
    return dict(n=int(len(s)), open=int((~led.settled).sum()), hits=int(s.hit.sum()), hit_rate=round(100 * float(s.hit.mean()), 1),
                promised=round(float(s.p.mean()), 1), pnl=round(float(s.pnl.sum()), 2), roi=round(100 * float(s.pnl.sum()) / len(s), 1),
                headline=dict(n=int(len(head)), hits=int(head.hit.sum()), pnl=round(float(head.pnl.sum()), 2)),
                recent=[dict(date=r.date, home=r.home, away=r.away, label=r.label, p=r.p, price=r.price, result=r.result, hit=bool(r.hit), pnl=r.pnl)
                        for r in s.sort_values("date", ascending=False).head(30).itertuples()])
