"""Collect every source, unify team names, merge duplicates, attach xG + market-implied goal rates."""
import datetime as dt
import numpy as np, pandas as pd
from . import sources as S
from .config import DATA, MATCHES_CSV, BIG4, FIRST_SEASON, season_of
from .names import Resolver

PRIORITY = {"football-data": 0, "openfootball": 1, "espn": 2, "thesportsdb": 3, "winner": 5, "archive": 9}
NUM_EXTRA = ["o_h", "o_d", "o_a", "o_ov", "o_un"]


def _log(msg):
    print(msg, flush=True)


def collect(fast=False):
    """Pull all sources. Returns (frames dict, resolver)."""
    fr = {}
    _log("[1/7] football-data.co.uk  (results + odds, 4 leagues)")
    fr["fd"] = S.football_data()
    _log(f"      {len(fr['fd'])} rows")
    _log("[2/7] Understat            (xG per match)")
    fr["us"] = S.understat()
    _log(f"      {len(fr['us'])} rows")
    _log("[3/7] openfootball         (Champions League history)")
    fr["ofb"] = S.openfootball_cl()
    _log(f"      {len(fr['ofb'])} rows")
    _log("[4/7] ESPN                 (fixtures + results, current season, 6 competitions)")
    fr["espn"] = S.espn()
    _log(f"      {len(fr['espn'])} rows")
    _log("[5/7] TheSportsDB          (Israeli league; first run scans 3 seasons, then cached)")
    fr["tsdb"] = S.thesportsdb("IL", seasons=1 if fast else 2)
    _log(f"      {len(fr['tsdb'])} rows")
    _log("[6/7] ESPN history         (Israeli league results 2020-21 .. 2024-25; fills TheSportsDB gaps)")
    fr["espn_il"] = S.espn_history("IL", first=FIRST_SEASON)
    _log(f"      {len(fr['espn_il'])} rows")
    _log("[7/7] ESPN history         (Europa League 2020-21 .. last season; Tue-Fri only)")
    fr["espn_el"] = S.espn_history("EL", first=FIRST_SEASON, weekdays=(1, 2, 3, 4))
    _log(f"      {len(fr['espn_el'])} rows")
    return fr


def _resolve_frame(df, rs, is_pair_tagged=False):
    if df is None or df.empty:
        return df
    df = df.copy()
    df["home"] = [rs.resolve(n, lg, cc) for n, lg, cc in zip(df.home_raw, df.league, df.get("cc_h", [None] * len(df)))]
    df["away"] = [rs.resolve(n, lg, cc) for n, lg, cc in zip(df.away_raw, df.league, df.get("cc_a", [None] * len(df)))]
    return df


def build(fast=False):
    fr = collect(fast)
    rs = Resolver()
    # canonical namespaces: football-data names for the big 4, TheSportsDB (aliased) for Israel
    for lg, g in fr["fd"].groupby("league"):
        for n in pd.unique(pd.concat([g.home_raw, g.away_raw])):
            rs.register(n, lg)
    il = fr["tsdb"]
    if not il.empty:
        # exact aliases only: fuzzy-resolving here once merged Maccabi Haifa into Maccabi Raina
        for n in pd.unique(pd.concat([il.home_raw, il.away_raw])):
            rs.register(rs.canonical(n), "IL")
    # Israeli teams seen only in the ESPN history (relegated before TheSportsDB coverage starts)
    eh = fr["espn_il"]
    if eh is not None and not eh.empty:
        for n in pd.unique(pd.concat([eh.home_raw, eh.away_raw])):
            if rs.resolve(n, "IL") not in rs.by_league.get("IL", {}).values():
                rs.cache.pop((n, "IL"), None)
                rs.register(rs.canonical(n), "IL")
    # CL: big-4 teams resolve to fd names through country tags; the rest register as CL-only
    ofb = fr["ofb"]
    for df in (ofb,):
        if df.empty:
            continue
        for n, cc in list(zip(df.home_raw, df.cc_h)) + list(zip(df.away_raw, df.cc_a)):
            r = rs.resolve(n, "CL", cc)
            from .names import CC_LG
            if CC_LG.get(cc) is None:
                rs.register(r, "CL")

    # last line of defence: played matches from the previous build (survives a dead source or an empty cache,
    # e.g. the cloud runner that has no TheSportsDB history)
    if MATCHES_CSV.exists():
        try:
            old = pd.read_csv(MATCHES_CSV, parse_dates=["date"])
            old = old[old.played.astype(bool)][["date", "league", "home", "away", "hg", "ag"]].copy()
            old["home_raw"], old["away_raw"] = old.home, old.away
            old["played"], old["src"], old["cc_h"], old["cc_a"] = True, "archive", None, None
            for n in pd.unique(pd.concat([old.home, old.away])):
                pass
            fr["archive"] = old
            _log(f"[archive] {len(old)} played matches from the previous build kept as fallback")
        except Exception as ex:
            _log(f"archive fallback skipped: {ex}")
    parts = []
    for key in ("fd", "ofb", "espn", "espn_il", "espn_el", "tsdb", "archive"):
        df = fr[key]
        if df is None or df.empty:
            continue
        if key == "archive":
            df = df.copy(); df["home"], df["away"] = df.home_raw, df.away_raw
        else:
            df = _resolve_frame(df, rs)
        parts.append(df)
    allm = pd.concat(parts, ignore_index=True)
    allm["prio"] = allm.src.map(PRIORITY)
    allm = allm.sort_values(["prio", "date"]).reset_index(drop=True)
    for c in NUM_EXTRA:
        if c not in allm:
            allm[c] = np.nan

    # ---- de-duplicate across sources (same fixture within +-3 days)
    kept, conflicts = [], 0
    index = {}  # (league, home, away) -> list of positions in kept
    for r in allm.itertuples(index=False):
        k = (r.league, r.home, r.away)
        hit = None
        for pos in index.get(k, []):
            if abs((kept[pos]["date"] - r.date).days) <= 3:
                hit = pos
                break
        d = r._asdict()
        if hit is None:
            d["n_src"] = 1
            index.setdefault(k, []).append(len(kept))
            kept.append(d)
        else:
            t = kept[hit]
            t["n_src"] += 1
            if r.played and not t["played"]:
                t.update(date=r.date, hg=r.hg, ag=r.ag, played=True)
            elif r.played and t["played"] and (r.hg != t["hg"] or r.ag != t["ag"]):
                conflicts += 1
            for c in NUM_EXTRA:
                if pd.isna(t.get(c)) and not pd.isna(d.get(c)):
                    t[c] = d[c]
    # fixtures that Winner lists but the free schedule sources miss (written by oracle.winner)
    extra = DATA / "extra_fixtures.json"
    if extra.exists():
        import json as _json
        try:
            for x in _json.loads(extra.read_text(encoding="utf-8")):
                x = dict(x, home=rs.resolve(x["home"], x["league"]), away=rs.resolve(x["away"], x["league"]))
                dts = pd.Timestamp(x["date"])
                hit = [pos for pos in index.get((x["league"], x["home"], x["away"]), []) if abs((kept[pos]["date"] - dts).days) <= 3]
                if hit:
                    k0 = kept[hit[0]]
                    if not k0["played"] and k0["date"] != dts:
                        k0["date"] = dts        # the bookmaker's live schedule beats a stale fixture list
                    continue
                d0 = dict(date=dts, league=x["league"], home=x["home"], away=x["away"], hg=np.nan, ag=np.nan,
                          played=False, src="winner", n_src=1)
                index.setdefault((x["league"], x["home"], x["away"]), []).append(len(kept))
                kept.append(d0)
        except Exception as ex:
            _log(f"extra fixtures skipped: {ex}")
    m = pd.DataFrame(kept)
    _log(f"merged -> {len(m)} matches ({int(m.played.sum())} played), score conflicts between sources: {conflicts}")
    if rs.fuzzy_log:
        seen = sorted(set(rs.fuzzy_log), key=str)
        _log("fuzzy name resolutions (check these if a team looks wrong): " + "; ".join(f"{a} -> {b} [{lg}]" for a, b, lg in seen))

    # ---- Understat xG
    us = fr["us"]
    m["xg_h"] = np.nan
    m["xg_a"] = np.nan
    if not us.empty:
        us = us.copy()
        us["home"] = [rs.resolve(n, lg) for n, lg in zip(us.home_raw, us.league)]
        us["away"] = [rs.resolve(n, lg) for n, lg in zip(us.away_raw, us.league)]
        usd = {}
        for r in us.itertuples(index=False):
            usd.setdefault((r.league, r.home, r.away), []).append((r.date, r.xg_h, r.xg_a))
        hits = 0
        for i, r in enumerate(m.itertuples(index=False)):
            if not r.played or r.league not in BIG4:
                continue
            for d, xh, xa in usd.get((r.league, r.home, r.away), []):
                if abs((d - r.date).days) <= 1:
                    m.iat[i, m.columns.get_loc("xg_h")] = xh
                    m.iat[i, m.columns.get_loc("xg_a")] = xa
                    hits += 1
                    break
        _log(f"xG attached to {hits} matches")

    m = m.drop(columns=["prio", "home_raw", "away_raw", "cc_h", "cc_a"], errors="ignore")
    m["date"] = pd.to_datetime(m["date"])
    m["season"] = [season_of(d) for d in m["date"]]
    m = m.sort_values(["date", "league", "home"]).reset_index(drop=True)

    # ---- market-implied goal rates (from odds)
    from .models import market_lambdas
    lam = market_lambdas(m)
    m["lm_h"], m["lm_a"] = lam[:, 0], lam[:, 1]
    m.to_csv(MATCHES_CSV, index=False, encoding="utf-8")
    _log(f"saved {MATCHES_CSV}")
    return m


def load():
    if not MATCHES_CSV.exists():
        raise SystemExit("No data yet. Run:  python -m oracle update")
    m = pd.read_csv(MATCHES_CSV, parse_dates=["date"])
    m["played"] = m["played"].astype(bool)
    return m


def quality_report(m):
    lines = []
    for lg, g in m.groupby("league"):
        p = g[g.played]
        lines.append(f"{lg}: {len(p)} played, {int((~g.played).sum())} upcoming, "
                     f"teams={len(set(g.home) | set(g.away))}, last result={p.date.max().date() if len(p) else '-'}, "
                     f"xG rows={int(p.xg_h.notna().sum())}, odds rows={int(p.o_h.notna().sum())}")
    return "\n".join(lines)
