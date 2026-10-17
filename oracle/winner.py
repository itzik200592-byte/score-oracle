"""Collect Winner.co.il odds from its public line endpoint (one plain GET, ~3 MB).

Runs from the user's own computer only: Winner's bot protection (Imperva) blocks cloud IPs such as GitHub Actions
with HTTP 403. We never try to get around that; if a request is blocked we stop and say so."""
import json, datetime as dt
import requests
import pandas as pd
from .config import DATA
from . import team_he
from .names import norm

URL = "https://api.winner.co.il/v2/publicapi/GetCMobileLine?lineChecksum=0"
HEAD = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
        "Origin": "https://www.winner.co.il", "Referer": "https://www.winner.co.il/"}
LEAGUES = {"הליגה האירופית": "EL", "ליגת האלופות": "CL", "פרמייר ליג": "PL", "ספרדית ראשונה": "LL",
           "איטלקית ראשונה": "SA", "צרפתית ראשונה": "L1", "ליגת Winner": "IL"}


class Blocked(RuntimeError):
    pass


def fetch():
    r = requests.get(URL, headers=HEAD, timeout=90)
    if r.status_code == 403 or not r.text.startswith("{"):
        raise Blocked(f"Winner returned HTTP {r.status_code}: blocked (bot protection). Not retrying or working around it.")
    r.raise_for_status()
    return r.json()


def _price(o):
    try:
        return float(o["price"])
    except Exception:
        return None


def parse(j):
    """-> list of events {league, date, time, home_he, away_he, h, d, a, over25, under25, btts_yes, btts_no, cs{score:price}}"""
    by_event = {}
    for m in j.get("markets", []):
        lg = LEAGUES.get(m.get("league"))
        if not lg or m.get("sId") != 240 or " - " not in (m.get("desc") or ""):
            continue
        mp = team_he.clean(m.get("mp"))
        e = by_event.setdefault(m["eId"], {"league": lg, "desc": m["desc"], "date": str(m["e_date"]), "hour": m.get("m_hour")})
        outs = m.get("outcomes") or []
        if mp.startswith("1X2") and "תוצאת סיום" in mp and "ללא הארכות" in mp and len(outs) == 3:
            e["h"], e["d"], e["a"] = (_price(o) for o in outs)
        elif mp.startswith("מעל/מתחת שערים") and "תוצאת סיום" in mp:
            for o in outs:
                if "2.5" in o.get("desc", ""):
                    e["over25" if "מעל" in o["desc"] else "under25"] = _price(o)
        elif mp.startswith("האם כל קבוצה תבקיע") and "תוצאת סיום" in mp:
            for o in outs:
                e["btts_yes" if o.get("desc", "").strip() == "כן" else "btts_no"] = _price(o)
        elif mp.startswith("תוצאה מדויקת") and "תוצאת סיום" in mp:
            e["cs"] = {team_he.clean(o["desc"]).replace(" ", ""): _price(o) for o in outs if " - " in o.get("desc", "")}
    out = []
    for e in by_event.values():
        if e.get("h") and e.get("d") and e.get("a"):
            h, a = [team_he.clean(x) for x in e["desc"].split(" - ", 1)]
            d = e["date"]
            hr = e["hour"] or "0000"
            out.append(dict(e, home_he=h, away_he=a, date=f"20{d[:2]}-{d[2:4]}-{d[4:]}", time=f"{hr[:2]}:{hr[2:]}"))
    return out


def match_to_fixtures(events, m, days=10):
    """Pair Winner events with our upcoming fixtures. Returns (matches for odds_live.json, unmapped description list)."""
    names = team_he.load()
    today = pd.Timestamp.now().normalize()
    up = m[(~m.played) & (m.date >= today - pd.Timedelta(days=1)) & (m.date <= today + pd.Timedelta(days=days))]
    fx = {}
    for r in up.itertuples(index=False):
        fx.setdefault(r.league, []).append(r)
    used, learned, out, unmapped, missing = set(), {}, [], [], []

    def find(lg, home, away, date):
        for r in fx.get(lg, []):
            if (r.home, r.away) == (home, away) and abs((r.date - pd.Timestamp(date)).days) <= 3 and (r.league, r.home, r.away) not in used:
                return r
        return None

    pending = []
    for e in events:
        if (e["date"] < (today - pd.Timedelta(days=1)).date().isoformat()) or e["date"] > (today + pd.Timedelta(days=days)).date().isoformat():
            continue
        lg = e["league"]
        hn, an = names.get(e["home_he"]), names.get(e["away_he"])
        r = find(lg, hn, an, e["date"]) if hn and an else None
        if r is not None:
            used.add((r.league, r.home, r.away))
            out.append(_entry(e, r))
            if (not r.played) and r.date.date().isoformat() != e["date"]:
                missing.append(dict(league=lg, date=e["date"], home=r.home, away=r.away, fix=True))   # schedule moved
        else:
            pending.append((e, hn, an))
    # self-learning: one side known -> the other side is the opposing team of that fixture; or a single leftover pair
    for e, hn, an in pending:
        lg = e["league"]
        cands = [r for r in fx.get(lg, []) if (r.league, r.home, r.away) not in used and abs((r.date - pd.Timestamp(e["date"])).days) <= 3]
        pick = None
        if hn and not an:
            c = [r for r in cands if r.home == hn]
            if len(c) == 1:
                pick = c[0]; learned[e["away_he"]] = pick.away
        elif an and not hn:
            c = [r for r in cands if r.away == an]
            if len(c) == 1:
                pick = c[0]; learned[e["home_he"]] = pick.home
        if pick is not None:
            used.add((pick.league, pick.home, pick.away))
            out.append(_entry(e, pick))
        elif hn and an and lg in ("IL", "PL", "LL", "SA", "L1", "EL", "CL"):
            missing.append(dict(league=lg, date=e["date"], home=hn, away=an))   # Winner knows a fixture our sources lack
        else:
            unmapped.append(f"{lg} {e['date']} {e['home_he']} - {e['away_he']}")
    if missing:
        EXTRA_JSON.write_text(json.dumps(_merge_extra(missing), ensure_ascii=False, indent=1), encoding="utf-8")
    if learned:
        team_he.save_learned(learned)
    if unmapped:
        team_he.UNMAPPED_TXT.write_text("\n".join(unmapped) + "\n", encoding="utf-8")
    return out, unmapped, learned, missing


def _kick(t):
    h, mi = int(t[:2]), int(t[3:])
    mi += 1
    if mi == 60:
        h, mi = (h + 1) % 24, 0
    return f"{h:02d}:{mi:02d}"


def _entry(e, r):
    # Winner prints scores right-to-left ("away - home"); normalise to home-away
    cs = {}
    for k, v in (e.get("cs") or {}).items():
        try:
            a_, h_ = k.replace(" ", "").split("-")
            cs[f"{h_}-{a_}"] = v
        except ValueError:
            continue
    return {"date": e["date"], "home": r.home, "away": r.away, "h": e["h"], "d": e["d"], "a": e["a"],
            "over25": e.get("over25"), "under25": e.get("under25"), "btts_yes": e.get("btts_yes"), "btts_no": e.get("btts_no"),
            "cs": cs, "kickoff": _kick(e["time"]), "source": "Winner.co.il", "bookmakers": "Winner (single bookmaker)"}


EXTRA_JSON = DATA / "extra_fixtures.json"


def _merge_extra(new):
    cur = []
    if EXTRA_JSON.exists():
        try:
            cur = json.loads(EXTRA_JSON.read_text(encoding="utf-8"))
        except Exception:
            cur = []
    keep = [c for c in cur if c["date"] >= (dt.date.today() - dt.timedelta(days=3)).isoformat()]
    have = {(c["league"], c["date"], c["home"], c["away"]) for c in keep}
    return keep + [n for n in new if (n["league"], n["date"], n["home"], n["away"]) not in have]


def collect(m, days=10):
    events = parse(fetch())
    matches, unmapped, learned, missing = match_to_fixtures(events, m, days)
    stamp = dt.datetime.now().astimezone().isoformat(timespec="minutes")
    (DATA / "odds_live.json").write_text(json.dumps({"fetched_at": stamp, "matches": matches}, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    return dict(winner_events=len(events), matched=len(matches), unmapped=unmapped, learned=learned, missing=missing, fetched_at=stamp)
