"""Sharp-bookmaker comparison via The Odds API (https://the-odds-api.com, free tier 500 requests/month).

This is the only approach with real evidence behind it: a slow retail book (Winner, margin 11-18%) sometimes pays more
than the sharp market's fair price (Pinnacle and peers). We flag a Winner selection only when its odds exceed the
sharp fair odds by a margin. Needs a key in data/odds_api_key.txt (never committed) or env ODDS_API_KEY."""
import os, json, datetime as dt
import numpy as np
from .config import DATA
from . import http
from .names import norm
from .odds import devig_power

KEY_FILE = DATA / "odds_api_key.txt"
SPORTS = {"PL": "soccer_epl", "LL": "soccer_spain_la_liga", "SA": "soccer_italy_serie_a", "L1": "soccer_france_ligue_one",
          "CL": "soccer_uefa_champs_league", "EL": "soccer_uefa_europa_league"}
SHARP_BOOKS = ("pinnacle", "betfair_ex_eu", "matchbook", "smarkets")
ALIAS = {"manchester city": "man city", "manchester united": "man united", "paris saint germain": "paris sg", "paris saint-germain": "paris sg",
         "atletico madrid": "ath madrid", "athletic bilbao": "ath bilbao", "athletic club": "ath bilbao", "real betis": "betis",
         "real sociedad": "sociedad", "espanyol": "espanol", "rayo vallecano": "vallecano", "nottingham forest": "nott'm forest",
         "wolverhampton wanderers": "wolves", "inter milan": "inter", "ac milan": "milan", "bayer leverkusen": "leverkusen",
         "olympiacos": "olympiakos", "celta vigo": "celta", "fc porto": "porto", "sporting cp": "sporting", "bayern munich": "bayern",
         "borussia dortmund": "dortmund", "psv eindhoven": "psv", "union saint-gilloise": "union st.-gilloise", "besiktas": "beşiktaş",
         "sturm graz": "sk sturm graz", "hoffenheim": "tsg hoffenheim", "red bull salzburg": "rb salzburg", "celje": "nk celje"}


def key():
    k = os.environ.get("ODDS_API_KEY")
    if not k and KEY_FILE.exists():
        k = KEY_FILE.read_text(encoding="utf-8").strip()
    return k or None


def _n(s):
    s = norm(s)
    return norm(ALIAS.get(s, s))


def fetch(leagues=None):
    """-> {(date, norm_home, norm_away): {h,d,a (sharp fair probs), books:n, sharp_odds:[...]}} ; None if no key."""
    k = key()
    if not k:
        return None
    out = {}
    for lg, sport in SPORTS.items():
        if leagues and lg not in leagues:
            continue
        txt = http.get(f"https://api.the-odds-api.com/v4/sports/{sport}/odds",
                       params={"apiKey": k, "regions": "eu", "markets": "h2h", "oddsFormat": "decimal"},
                       ttl_hours=3, tries=1, cache_key=f"oddsapi:{sport}:{dt.datetime.utcnow():%Y-%m-%d-%H}")
        if not txt:
            continue
        try:
            games = json.loads(txt)
        except Exception:
            continue
        for g in games:
            date = g["commence_time"][:10]
            h, a = g["home_team"], g["away_team"]
            probs, pinn = [], None
            for b in g.get("bookmakers", []):
                mk = next((m for m in b.get("markets", []) if m["key"] == "h2h"), None)
                if not mk:
                    continue
                o = {x["name"]: x["price"] for x in mk["outcomes"]}
                if h in o and a in o and "Draw" in o:
                    p = devig_power([o[h], o["Draw"], o[a]])
                    probs.append(p)
                    if b["key"] == "pinnacle":
                        pinn = p
            if not probs:
                continue
            # Pinnacle is the reference price; without it, the median across books resists mislabeled outliers
            p = pinn if pinn is not None else np.median(np.array(probs), axis=0)
            out[(date, _n(h), _n(a))] = dict(h=float(p[0]), d=float(p[1]), a=float(p[2]), books=len(probs),
                                           sharp=pinn is not None, league=lg)
    return out


STOP = {"fc", "cf", "afc", "club", "united", "city", "town", "de", "sc", "ac", "as", "ssc", "us", "sk", "fk", "nk", "tsg", "rb", "vfb", "sl"}


def _toks(s):
    return {t for t in _n(s).replace("-", " ").replace("'", "").split() if t not in STOP and len(t) > 1}


def _same(a, b):
    """our canonical name vs API name: exact after aliases, token containment, or close match."""
    import difflib
    na, nb = _n(a), _n(b)
    if na == nb:
        return True
    ta, tb = _toks(a), _toks(b)
    if ta and tb and (ta <= tb or tb <= ta):
        return True
    return difflib.SequenceMatcher(None, na, nb).ratio() >= 0.84


def compare(rows, sharp_map, min_edge=0.03):
    """Annotate exported prediction rows with sharp fair probs and Winner-vs-sharp edge."""
    if not sharp_map:
        return 0
    by_date = {}
    for (d, h, a), v in sharp_map.items():
        by_date.setdefault(d, []).append((h, a, v))
    n = 0
    for r in rows:
        o = r.get("odds")
        if not o:
            continue
        s = None
        for dd in (0, -1, 1):
            d2 = (dt.date.fromisoformat(r["date"]) + dt.timedelta(days=dd)).isoformat()
            for h, a, v in by_date.get(d2, []):
                if _same(r["home"], h) and _same(r["away"], a):
                    s = v
                    break
            if s:
                break
        if not s:
            continue
        edge = {k: round(100 * (s[k] * o[k] - 1), 1) for k in "hda"}
        best = max(edge, key=edge.get)
        # consistency: Winner's and the sharp market's favourite must agree and no edge may exceed +25%
        # (that size only happens when the fixture or the home/away sides are mismatched)
        w_imp = {k: 1 / o[k] for k in "hda"}
        consistent = max(w_imp, key=w_imp.get) == max("hda", key=lambda k: s[k]) and edge[best] <= 25
        r["sharp"] = dict(p={k: round(100 * s[k]) for k in "hda"}, edge=edge, books=s["books"], is_sharp=s["sharp"],
                          consistent=consistent, flag=(best if consistent and edge[best] >= 100 * min_edge else None))
        n += 1
    return n
