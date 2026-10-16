"""Track record: every prediction as it was published BEFORE kickoff, settled against the real result.
The ledger keeps the latest version published before the match starts (news, odds and adjustments included),
never a version made after kickoff, so the hit rates are honest."""
import datetime as dt
import numpy as np, pandas as pd
from .config import LEDGER_CSV, ROOT

COLS = ["made", "league", "date", "home", "away", "pick", "p_pick", "tier", "pH", "pD", "pA", "over25", "btts",
        "exp_total", "odds_h", "odds_d", "odds_a", "star", "star_odds", "star_p", "kickoff", "src"]
IL_TZ_OFFSET = 3   # Israel is UTC+3 in October (kickoff times from Winner are Israel local time)


def _cutoff_utc(date_str, kickoff):
    """Last moment a prediction may still be updated: 30 min before kickoff, or 10:00 Israel time on match day."""
    d = dt.datetime.fromisoformat(date_str)
    if kickoff and ":" in str(kickoff):
        hh, mm = [int(x) for x in str(kickoff).split(":")]
        return d.replace(hour=hh, minute=mm) - dt.timedelta(hours=IL_TZ_OFFSET, minutes=30)
    return d.replace(hour=10) - dt.timedelta(hours=IL_TZ_OFFSET)


def _row(r, now):
    o = r.get("odds") or {}
    st = o.get("star") or {}
    d = r.get("dist") or {}
    return dict(made=now.isoformat(timespec="minutes"), league=r["league"], date=r["date"], home=r["home"], away=r["away"],
                pick=r["pick"], p_pick=r["p_pick"], tier=r["tier"], pH=r["pH"], pD=r["pD"], pA=r["pA"],
                over25=(d.get("over") or {}).get("2.5", r.get("over25")), btts=d.get("btts", r.get("btts")),
                exp_total=d.get("exp_total", round((r.get("xg_h") or 0) + (r.get("xg_a") or 0), 2) or None), odds_h=o.get("h"), odds_d=o.get("d"), odds_a=o.get("a"),
                star=st.get("outcome", ""), star_odds=st.get("odds"), star_p=st.get("model_p"),
                kickoff=o.get("kickoff"), src="live")


def load():
    if not LEDGER_CSV.exists():
        return pd.DataFrame(columns=COLS)
    df = pd.read_csv(LEDGER_CSV)
    for c in COLS:
        if c not in df:
            df[c] = np.nan
    df["star"] = df["star"].fillna("")
    return df


def upsert(rows, m):
    """rows: exported prediction dicts. Insert new fixtures; refresh existing ones only until their cutoff."""
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    led = load()
    played = {(r.league, r.home, r.away) for r in m[m.played].itertuples()}
    idx = {(r.league, r.date, r.home, r.away): i for i, r in enumerate(led.itertuples())}
    new_rows = []
    for r in rows:
        key = (r["league"], r["date"], r["home"], r["away"])
        if (r["league"], r["home"], r["away"]) in played and key not in idx:
            pass
        row = _row(r, now)
        if key in idx:
            i = idx[key]
            old = led.iloc[i]
            ko = row["kickoff"] if isinstance(row["kickoff"], str) else old.get("kickoff")
            if now >= _cutoff_utc(r["date"], ko):
                continue            # match is (about to be) under way: freeze the published version
            for c in COLS:           # keep odds/star the cloud run cannot see
                if row[c] is None or (isinstance(row[c], float) and np.isnan(row[c])) or row[c] == "":
                    if c in ("odds_h", "odds_d", "odds_a", "star", "star_odds", "star_p", "kickoff") and not (old[c] is None or (isinstance(old[c], float) and np.isnan(old[c]))):
                        row[c] = old[c]
            for c in COLS:
                led.at[led.index[i], c] = row[c]
        else:
            if now >= _cutoff_utc(r["date"], row["kickoff"]):
                continue            # never first-log a prediction after kickoff
            new_rows.append(row)
    if new_rows:
        led = pd.concat([led, pd.DataFrame(new_rows)], ignore_index=True)
    led.to_csv(LEDGER_CSV, index=False, encoding="utf-8")
    return led


def settle(m, led=None):
    """Ledger joined with real results + per-prediction flags."""
    led = load() if led is None else led
    res = m[m.played][["league", "date", "home", "away", "hg", "ag"]].rename(columns={"date": "date_r"})
    res["date_r"] = res["date_r"].dt.date.astype(str)
    j = led.merge(res, on=["league", "home", "away"])
    j = j[(pd.to_datetime(j.date_r) - pd.to_datetime(j.date)).abs() <= pd.Timedelta(days=3)].copy()
    if j.empty:
        return j
    hg, ag = j.hg.astype(int), j.ag.astype(int)
    j["actual"] = hg.astype(str) + "-" + ag.astype(str)
    j["act_dir"] = np.where(hg > ag, "h", np.where(hg == ag, "d", "a"))
    probs = j[["pH", "pD", "pA"]].values
    j["pred_dir"] = np.array(["h", "d", "a"])[probs.argmax(1)]
    j["dir_ok"] = j.pred_dir == j.act_dir
    j["exact"] = j.pick == j.actual
    j["over_pred"] = j.over25 > 50
    j["over_ok"] = j.over_pred == ((hg + ag) >= 3)
    j["btts_pred"] = j.btts > 50
    j["btts_ok"] = j.btts_pred == ((hg > 0) & (ag > 0))
    j["total"] = hg + ag
    j["is_star"] = j.star.astype(str).isin(["h", "d", "a"])
    j["star_ok"] = np.where(j.is_star, j.star == j.act_dir, np.nan)
    return j.sort_values(["date_r", "league"], ascending=[False, True]).reset_index(drop=True)


def _pct(x):
    return None if len(x) == 0 else round(100 * float(np.mean(x)), 1)


def summary(j, since=None):
    if since is not None:
        j = j[j.date_r >= since]
    n = len(j)
    st = j[j.is_star] if n else j
    out = dict(n=int(n), direction=_pct(j.dir_ok) if n else None, exact=_pct(j.exact) if n else None,
               over=_pct(j.over_ok) if n else None, btts=_pct(j.btts_ok) if n else None,
               exact_hits=int(j.exact.sum()) if n else 0, dir_hits=int(j.dir_ok.sum()) if n else 0,
               avg_conf=round(float(j[["pH", "pD", "pA"]].max(axis=1).mean()), 1) if n else None,
               goals_actual=round(float(j.total.mean()), 2) if n else None,
               goals_model=round(float(j.exp_total.mean()), 2) if n and j.exp_total.notna().any() else None)
    out["stars"] = dict(n=int(len(st)), won=int(st.star_ok.sum()) if len(st) else 0,
                        rate=_pct(st.star_ok.astype(float)) if len(st) else None,
                        avg_odds=round(float(st.star_odds.mean()), 2) if len(st) and st.star_odds.notna().any() else None,
                        avg_model_p=round(float(st.star_p.mean()), 1) if len(st) and st.star_p.notna().any() else None)
    if out["stars"]["avg_odds"]:
        out["stars"]["breakeven"] = round(100 / out["stars"]["avg_odds"], 1)
    return out


def export_block(m):
    j = settle(m)
    if j.empty:
        return dict(overall=summary(j), recent=[], by_league={}, days=[])
    today = dt.date.today()
    by_lg = {lg: summary(g) for lg, g in j.groupby("league")}
    by_tier = {t: summary(g) for t, g in j.groupby("tier")}
    days = []
    for d, g in j.groupby("date_r", sort=False):
        days.append(dict(date=d, **summary(g)))
    recent = [dict(date=r.date_r, league=r.league, home=r.home, away=r.away, pick=r.pick, actual=r.actual, exact=bool(r.exact),
                   pred_dir=r.pred_dir, act_dir=r.act_dir, dir_ok=bool(r.dir_ok), conf=int(max(r.pH, r.pD, r.pA)),
                   over_p=None if pd.isna(r.over25) else int(round(r.over25)), over_ok=bool(r.over_ok), total=int(r.total),
                   btts_ok=bool(r.btts_ok), star=r.star if r.is_star else "", star_odds=None if pd.isna(r.star_odds) else r.star_odds,
                   star_ok=None if not r.is_star else bool(r.star_ok))
              for r in j.head(80).itertuples()]
    return dict(overall=summary(j), last7=summary(j, (today - dt.timedelta(days=7)).isoformat()), by_league=by_lg,
                by_tier=by_tier, days=days[:10], recent=recent, since=str(j.date_r.min()))


def text_report(m):
    j = settle(m)
    if j.empty:
        return "No finished predictions in the ledger yet."
    s = summary(j)
    L = [f"TRACK RECORD ({s['n']} finished predictions, since {j.date_r.min()})",
         f"  direction (winner/draw/loss): {s['dir_hits']}/{s['n']} = {s['direction']}%  (avg confidence {s['avg_conf']}%)",
         f"  exact score: {s['exact_hits']}/{s['n']} = {s['exact']}%",
         f"  over/under 2.5: {s['over']}%   both teams score: {s['btts']}%",
         f"  goals per game: actual {s['goals_actual']} vs model {s['goals_model']}",
         f"  stars: {s['stars']['won']}/{s['stars']['n']} won ({s['stars']['rate']}%), avg odds {s['stars']['avg_odds']}, break-even {s['stars'].get('breakeven')}%"]
    for lg, g in j.groupby("league"):
        t = summary(g)
        L.append(f"  {lg}: n={t['n']} direction {t['direction']}% exact {t['exact']}% over/under {t['over']}%")
    return "\n".join(L)
