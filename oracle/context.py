"""Situation dossier for a fixture: venue records, form, streaks, congestion, head-to-head, table position.
Football is not only numbers: the dossier gives the situation analyst the hard facts to reason about
(home fortress? poor travellers? tired legs? chasing a title or fighting relegation?)."""
import json
import numpy as np, pandas as pd


def _rows(m, team, before):
    d = m[(m.played) & (m.date < before) & ((m.home == team) | (m.away == team))].sort_values("date")
    gf = np.where(d.home == team, d.hg, d.ag)
    ga = np.where(d.home == team, d.ag, d.hg)
    out = d.assign(venue=np.where(d.home == team, "H", "A"), gf=gf, ga=ga,
                   res=np.where(gf > ga, "W", np.where(gf == ga, "D", "L")),
                   pts=np.where(gf > ga, 3, np.where(gf == ga, 1, 0)),
                   opp=np.where(d.home == team, d.away, d.home))
    return out


def _split(d, n):
    d = d.tail(n)
    if d.empty:
        return None
    return dict(n=int(len(d)), W=int((d.res == "W").sum()), D=int((d.res == "D").sum()), L=int((d.res == "L").sum()),
                ppg=round(float(d.pts.mean()), 2), gf=round(float(d.gf.mean()), 2), ga=round(float(d.ga.mean()), 2),
                clean_sheets=int((d.ga == 0).sum()), failed_to_score=int((d.gf == 0).sum()))


def _streaks(d):
    res = list(d.res.values)[::-1]
    def run(pred):
        n = 0
        for r in res:
            if pred(r):
                n += 1
            else:
                break
        return n
    return dict(unbeaten=run(lambda r: r != "L"), winless=run(lambda r: r != "W"), winning=run(lambda r: r == "W"),
                losing=run(lambda r: r == "L"))


def table(m, league, season, before):
    d = m[(m.league == league) & (m.season == season) & m.played & (m.date < before)]
    if d.empty:
        return {}
    t = {}
    for r in d.itertuples():
        for tm, gf, ga in ((r.home, r.hg, r.ag), (r.away, r.ag, r.hg)):
            x = t.setdefault(tm, dict(P=0, pts=0, gf=0, ga=0))
            x["P"] += 1; x["gf"] += gf; x["ga"] += ga
            x["pts"] += 3 if gf > ga else (1 if gf == ga else 0)
    df = pd.DataFrame(t).T
    df["gd"] = df.gf - df.ga
    df = df.sort_values(["pts", "gd", "gf"], ascending=False)
    df["rank"] = np.arange(1, len(df) + 1)
    return df


def team_context(m, team, league, venue, before=None):
    before = before or (pd.Timestamp.now().normalize() + pd.Timedelta(days=1))
    d = _rows(m, team, before)
    if d.empty:
        return {"team": team, "note": "no history"}
    last = d.date.max()
    home = d[d.venue == "H"]; away = d[d.venue == "A"]
    cutoff = before - pd.Timedelta(days=365)
    comps = d[d.date >= before - pd.Timedelta(days=365)].league.value_counts().to_dict()
    domestic = any(k in comps for k in ("PL", "LL", "SA", "L1", "IL"))
    ctx = dict(team=team, venue_in_this_match=venue,
               data_coverage=dict(matches_last_365d_by_competition=comps,
                                  warning=None if domestic else "DOMESTIC LEAGUE NOT IN OUR DATABASE: days_since_last_match, fixture congestion, "
                                  "form and venue records below only reflect European games. Look up the domestic form and schedule on the web."),
               form_last6=" ".join(d.tail(6).res.tolist()), form_last6_detail=[f"{r.venue} {r.opp} {int(r.gf)}-{int(r.ga)} ({r.league})" for r in d.tail(6).itertuples()],
               last10=_split(d, 10),
               home_record_last10=_split(home, 10), away_record_last10=_split(away, 10),
               home_record_12m=_split(home[home.date >= cutoff], 99), away_record_12m=_split(away[away.date >= cutoff], 99),
               streaks=_streaks(d), days_since_last_match=int((before - last).days - 1),
               matches_last14d=int((d.date >= before - pd.Timedelta(days=14)).sum()),
               matches_last30d=int((d.date >= before - pd.Timedelta(days=30)).sum()))
    h12, a12 = ctx["home_record_12m"], ctx["away_record_12m"]
    if h12 and a12 and h12["n"] >= 8 and a12["n"] >= 8:
        ctx["home_away_ppg_gap_12m"] = round(h12["ppg"] - a12["ppg"], 2)
    # table position in this competition's season
    season = int(m[m.league == league].season.max()) if (m.league == league).any() else None
    if season is not None:
        tb = table(m, league, season, before)
        if len(tb) and team in tb.index:
            r = tb.loc[team]
            ctx["table"] = dict(rank=int(r["rank"]), of=int(len(tb)), pts=int(r.pts), played=int(r.P), gd=int(r.gd))
    return ctx


def league_baseline(m, league, before=None):
    before = before or pd.Timestamp.now().normalize()
    d = m[(m.league == league) & m.played & (m.date >= before - pd.Timedelta(days=730)) & (m.date < before)]
    if d.empty:
        return {}
    hp = np.where(d.hg > d.ag, 3, np.where(d.hg == d.ag, 1, 0)).mean()
    ap = np.where(d.ag > d.hg, 3, np.where(d.hg == d.ag, 1, 0)).mean()
    return dict(home_ppg=round(float(hp), 2), away_ppg=round(float(ap), 2), home_win_pct=round(100 * float((d.hg > d.ag).mean())),
                draw_pct=round(100 * float((d.hg == d.ag).mean())), away_win_pct=round(100 * float((d.ag > d.hg).mean())),
                goals_per_game=round(float((d.hg + d.ag).mean()), 2), sample=int(len(d)))


def head_to_head(m, a, b, before=None, n=6):
    before = before or (pd.Timestamp.now().normalize() + pd.Timedelta(days=1))
    d = m[m.played & (m.date < before) & (((m.home == a) & (m.away == b)) | ((m.home == b) & (m.away == a)))].sort_values("date").tail(n)
    return [f"{r.date.date()} {r.home} {int(r.hg)}-{int(r.ag)} {r.away} ({r.league})" for r in d.itertuples()]


def dossier(m, home, away, league):
    return dict(match=f"{home} vs {away}", competition=league,
                league_baseline=league_baseline(m, league),
                home_team=team_context(m, home, league, "home"),
                away_team=team_context(m, away, league, "away"),
                head_to_head_recent=head_to_head(m, home, away))


def as_text(dos):
    return json.dumps(dos, ensure_ascii=False, indent=1, default=str)
