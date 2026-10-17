"""Raw fetchers. Each returns a DataFrame with: date, league, home_raw, away_raw, hg, ag, played, src (+ extras)."""
import io, json, re, datetime as dt
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, numpy as np
from . import http
from .config import LEAGUES, BIG4, FIRST_SEASON, current_season

COLS = ["date", "league", "home_raw", "away_raw", "hg", "ag", "played", "src", "cc_h", "cc_a"]


def _empty():
    return pd.DataFrame(columns=COLS)


# ------------------------------------------------ 1. football-data.co.uk (results + odds)
ODDS_1X2 = [("AvgH", "AvgD", "AvgA"), ("BbAvH", "BbAvD", "BbAvA"), ("B365H", "B365D", "B365A")]
ODDS_OU = [("Avg>2.5", "Avg<2.5"), ("BbAv>2.5", "BbAv<2.5"), ("B365>2.5", "B365<2.5")]


def _fd_frame(txt, lg, played):
    df = pd.read_csv(io.StringIO(txt), on_bad_lines="skip")
    df = df.dropna(subset=["HomeTeam", "AwayTeam"])
    d = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce", format="mixed")
    out = pd.DataFrame({"date": d, "league": lg, "home_raw": df["HomeTeam"], "away_raw": df["AwayTeam"]})
    if played:
        out["hg"], out["ag"] = df["FTHG"], df["FTAG"]
        out["played"] = True
    else:
        out["hg"] = out["ag"] = np.nan
        out["played"] = False
    for c, i in (("o_h", 0), ("o_d", 1), ("o_a", 2)):
        v = pd.Series(np.nan, index=df.index)
        for tri in ODDS_1X2:
            if tri[i] in df:
                v = v.fillna(pd.to_numeric(df[tri[i]], errors="coerce"))
        out[c] = v
    for c, i in (("o_ov", 0), ("o_un", 1)):
        v = pd.Series(np.nan, index=df.index)
        for pr in ODDS_OU:
            if pr[i] in df:
                v = v.fillna(pd.to_numeric(df[pr[i]], errors="coerce"))
        out[c] = v
    out["src"] = "football-data"
    out["cc_h"] = out["cc_a"] = None
    return out.dropna(subset=["date"]).reset_index(drop=True)


def football_data():
    parts, cur = [], current_season()
    for lg in BIG4:
        code = LEAGUES[lg]["fd"]
        for s in range(FIRST_SEASON, cur + 1):
            tag = f"{s % 100:02d}{(s + 1) % 100:02d}"
            txt = http.get(f"https://www.football-data.co.uk/mmz4281/{tag}/{code}.csv",
                           ttl_hours=None if s < cur else 3)
            if txt:
                try:
                    f = _fd_frame(txt, lg, True)
                    parts.append(f[f.hg.notna() & f.ag.notna()])
                except Exception as e:
                    print("  fd parse fail", lg, tag, e)
    txt = http.get("https://www.football-data.co.uk/fixtures.csv", ttl_hours=2)
    if txt:
        inv = {LEAGUES[lg]["fd"]: lg for lg in BIG4}
        raw = pd.read_csv(io.StringIO(txt), on_bad_lines="skip")
        raw = raw[raw["Div"].isin(inv)]
        for div, g in raw.groupby("Div"):
            parts.append(_fd_frame(g.to_csv(index=False), inv[div], False))
    return pd.concat(parts, ignore_index=True) if parts else _empty()


# ------------------------------------------------ 2. Understat (xG per match)
def understat():
    rows, cur = [], current_season()
    H = {"X-Requested-With": "XMLHttpRequest"}
    for lg in BIG4:
        us = LEAGUES[lg]["us"]
        for s in range(FIRST_SEASON, cur + 1):
            txt = http.get(f"https://understat.com/getLeagueData/{us}/{s}", headers=H, ttl_hours=None if s < cur else 6)
            if not txt:
                continue
            try:
                j = json.loads(txt)
            except Exception:
                continue
            for m in j.get("dates", []):
                if not m.get("isResult"):
                    continue
                rows.append(dict(date=pd.to_datetime(m["datetime"][:10]), league=lg, home_raw=m["h"]["title"],
                                 away_raw=m["a"]["title"], xg_h=float(m["xG"]["h"]), xg_a=float(m["xG"]["a"])))
    return pd.DataFrame(rows)


# ------------------------------------------------ 3. ESPN scoreboard (all 6 competitions, day by day)
def _espn_day(lg, day, today):
    slug = LEAGUES[lg]["espn"]
    ttl = None if day < today - dt.timedelta(days=3) else (1 if day <= today else 3)
    txt = http.get(f"https://site.api.espn.com/apis/site/v2/sports/soccer/{slug}/scoreboard",
                   params={"dates": day.strftime("%Y%m%d")}, ttl_hours=ttl)
    out = []
    if not txt:
        return out
    try:
        j = json.loads(txt)
    except Exception:
        return out
    for e in j.get("events", []):
        try:
            c = e["competitions"][0]["competitors"]
            h = next(x for x in c if x["homeAway"] == "home")
            a = next(x for x in c if x["homeAway"] == "away")
            st = e["status"]["type"]
            if st.get("name") in ("STATUS_ABANDONED", "STATUS_POSTPONED", "STATUS_CANCELED", "STATUS_SUSPENDED"):
                continue   # not a fixture we can settle; otherwise it would look like a missing result
            played = st.get("state") == "post" and st.get("name") in ("STATUS_FULL_TIME", "STATUS_FINAL")
            out.append(dict(date=pd.to_datetime(e["date"][:10]), league=lg, home_raw=h["team"]["displayName"],
                            away_raw=a["team"]["displayName"], hg=float(h["score"]) if played else np.nan,
                            ag=float(a["score"]) if played else np.nan, played=played, src="espn",
                            cc_h=None, cc_a=None))
        except Exception:
            continue
    return out


def espn(leagues=None, start=None, end=None, weekdays=None):
    today = dt.date.today()
    start = start or dt.date(current_season(), 8, 1)
    end = end or today + dt.timedelta(days=14)
    days = [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]
    if weekdays is not None:
        days = [d for d in days if d.weekday() in weekdays]
    jobs = [(lg, d) for lg in (leagues or list(LEAGUES)) for d in days]
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(lambda a: _espn_day(a[0], a[1], today), jobs))
    rows = [r for rr in res for r in rr]
    return pd.DataFrame(rows) if rows else _empty()


def espn_history(lg="IL", first=FIRST_SEASON, weekdays=None, months=None):
    """Past seasons of one competition from the ESPN scoreboard, day by day (cached forever once fetched).
    Only seasons that ended before the current one; ESPN's Israeli coverage runs 2020-21 .. 2024-25."""
    cur = current_season()
    parts = []
    for s in range(first, cur):
        df = espn([lg], start=dt.date(s, 8, 1), end=dt.date(s + 1, 7, 31), weekdays=weekdays)
        if not df.empty:
            parts.append(df[df.played])
    return pd.concat(parts, ignore_index=True) if parts else _empty()


# ------------------------------------------------ 4. TheSportsDB (Israel: results + fixtures)
# The free key is rate limited, so a run makes only a handful of requests: the league's last 15 results and next 15
# fixtures (2 calls), plus the last 10 days day-by-day (cached). Older days are read from the cache only; the deep
# history comes from the ESPN history scan. Cache keys do not contain the API key, so a key change never refetches.
TSDB = "https://www.thesportsdb.com/api/v1/json/123/"


def _tsdb_rows(events, lg):
    rows = []
    for e in events or []:
        try:
            hs, as_ = e.get("intHomeScore"), e.get("intAwayScore")
            played = hs not in (None, "") and as_ not in (None, "")
            rows.append(dict(date=pd.to_datetime(e["dateEvent"]), league=lg, home_raw=e["strHomeTeam"],
                             away_raw=e["strAwayTeam"], hg=float(hs) if played else np.nan,
                             ag=float(as_) if played else np.nan, played=played, src="thesportsdb",
                             cc_h=None, cc_a=None))
        except Exception:
            continue
    return rows


def _tsdb_day(lid, day, today):
    recent = day >= today - dt.timedelta(days=10)
    txt = http.get(TSDB + "eventsday.php", params={"d": day.isoformat(), "l": lid},
                   ttl_hours=(2 if day >= today - dt.timedelta(days=4) else None), sleep=1.5 if recent else 0,
                   cache_key=f"tsdb:eventsday:{lid}:{day.isoformat()}", offline=not recent, tries=2)
    try:
        return (json.loads(txt).get("events") or []) if txt else []
    except Exception:
        return []


def thesportsdb(lg="IL", seasons=2, forward_days=14):
    lid = LEAGUES[lg]["tsdb"]
    today = dt.date.today()
    cur = current_season()
    days = []
    for s in range(cur - seasons + 1, cur + 1):
        d, b = dt.date(s, 8, 10), dt.date(s + 1, 6, 5)
        while d <= min(b, today + dt.timedelta(days=forward_days)):
            days.append(d)
            d += dt.timedelta(days=1)
    rows = []
    for d in days:
        rows += _tsdb_rows(_tsdb_day(lid, d, today), lg)
    # two cheap calls that always reflect the latest state (last 15 results, next 15 fixtures)
    for ep in ("eventspastleague.php", "eventsnextleague.php"):
        txt = http.get(TSDB + ep, params={"id": lid}, ttl_hours=1, sleep=1.5, cache_key=f"tsdb:{ep}:{lid}", tries=2)
        try:
            rows += _tsdb_rows(json.loads(txt).get("events") if txt else [], lg)
        except Exception:
            pass
    if not rows:
        return _empty()
    df = pd.DataFrame(rows)
    # the same fixture can appear from several calls: keep the row with a result
    df = df.sort_values("played", ascending=False).drop_duplicates(["date", "home_raw", "away_raw"], keep="first")
    return df.reset_index(drop=True)


# ------------------------------------------------ 5. openfootball (Champions League history, plain text)
_DAY = re.compile(r"^\s{2}(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_MATCH = re.compile(r"^\s+(?:\d{1,2}[:.]\d{2}\s+)?(.+?)\s+v\s+(.+?)\s{2,}(\d+)-(\d+)(.*)$")
_CC = re.compile(r"\(([A-Z]{3})\)\s*$")
_FT90 = re.compile(r"\((\d+)-(\d+),\s*\d+-\d+\)")
_MON = {m: i + 1 for i, m in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def _parse_ofb(txt, season):
    rows, cur = [], None
    for ln in txt.splitlines():
        m = _DAY.match(ln)
        if m:
            mo = _MON[m.group(1)]
            y = int(m.group(3)) if m.group(3) else (season if mo >= 7 else season + 1)
            cur = dt.date(y, mo, int(m.group(2)))
            continue
        m = _MATCH.match(ln)
        if m and cur:
            h, a, hg, ag, rest = m.group(1).strip(), m.group(2).strip(), int(m.group(3)), int(m.group(4)), m.group(5)
            if "a.e.t." in rest or "pen." in rest:  # we predict the 90-minute score
                f = _FT90.search(rest)
                if not f:
                    continue
                hg, ag = int(f.group(1)), int(f.group(2))
            ch, ca = _CC.search(h), _CC.search(a)
            rows.append(dict(date=pd.Timestamp(cur), league="CL", home_raw=_CC.sub("", h).strip(),
                             away_raw=_CC.sub("", a).strip(), hg=float(hg), ag=float(ag), played=True,
                             src="openfootball", cc_h=ch.group(1) if ch else None, cc_a=ca.group(1) if ca else None))
    return rows


def openfootball_cl():
    rows = []
    for s in range(FIRST_SEASON, current_season() + 1):
        txt = http.get(f"https://raw.githubusercontent.com/openfootball/europe-champions-league/master/{s}-{(s + 1) % 100:02d}/cl.txt",
                       ttl_hours=None if s < current_season() else 12, tries=1)
        if txt and not txt.startswith("404"):
            rows += _parse_ofb(txt, s)
    return pd.DataFrame(rows) if rows else _empty()


# ------------------------------------------------ 6. ClubElo (optional; its API host is unreachable on some networks)
def clubelo(date=None):
    date = date or dt.date.today()
    txt = http.get(f"http://api.clubelo.com/{date.isoformat()}", ttl_hours=12, tries=1)
    if not txt or "Club" not in txt[:50]:
        return None
    return pd.read_csv(io.StringIO(txt))
