"""Current squads from ESPN (refreshed daily) and verification of player claims against them.

Why: the news/situation agents read web previews, and preview pages are often last season's (players who left,
old managers). The statistical model never uses players, but the written opinions do, so every player named in an
opinion must exist in the team's CURRENT roster or the claim is dropped."""
import json, re, unicodedata, difflib, datetime as dt
from . import http
from .names import norm

ESPN = "https://site.api.espn.com/apis/site/v2/sports/soccer/"
LEAGUE_SLUGS = ["uefa.europa", "uefa.champions", "uefa.europa.conf", "eng.1", "esp.1", "ita.1", "fra.1", "isr.1", "ger.1", "ned.1",
                "por.1", "tur.1", "bel.1", "aut.1", "sco.1", "gre.1", "nor.1", "slv.1", "cyp.1", "swe.1", "den.1", "sui.1"]
# our canonical name -> ESPN displayName when fuzzy matching is not enough
OVERRIDES = {"Man City": "Manchester City", "Man United": "Manchester United", "Paris SG": "Paris Saint-Germain", "Ath Madrid": "Atlético Madrid",
             "Ath Bilbao": "Athletic Club", "Betis": "Real Betis", "Sociedad": "Real Sociedad", "Espanol": "Espanyol", "Vallecano": "Rayo Vallecano",
             "Nott'm Forest": "Nottingham Forest", "Wolves": "Wolverhampton Wanderers", "Inter": "Internazionale", "Milan": "AC Milan",
             "Marseille": "Marseille", "Paris FC": "Paris FC", "Union St.-Gilloise": "Union Saint-Gilloise", "Bodo/Glimt": "Bodø/Glimt",
             "Hapoel Be'er Sheva": "Hapoel Be'er", "Hapoel Tel-Aviv": "Hapoel Tel Aviv", "Maccabi Petah Tikva": "Maccabi Petah Tikva",
             "Hapoel Kiryat Shmona": "Hapoel Ironi Kiryat Shmona", "Ashdod": "Moadon Sport Ashdod", "Maccabi Raina": "Maccabi Bnei Raina",
             "Olympiakos": "Olympiacos", "Celta": "Celta Vigo", "Leverkusen": "Bayer Leverkusen", "RB Salzburg": "Red Bull Salzburg",
             "Sporting": "Sporting CP", "Porto": "FC Porto", "Bayern": "Bayern Munich", "Dortmund": "Borussia Dortmund", "PSV": "PSV Eindhoven",
             "St Etienne": "Saint-Étienne", "Viktoria Plzeň": "Viktoria Plzen", "Beşiktaş": "Besiktas", "SK Sturm Graz": "Sturm Graz",
             "TSG Hoffenheim": "Hoffenheim", "NK Celje": "Celje", "Jagiellonia Bialystok": "Jagiellonia", "ŠK Slovan Bratislava": "Slovan Bratislava"}


_TR = str.maketrans({"ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "ß": "ss", "ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "ð": "d", "þ": "th",
                     "ı": "i", "İ": "i", "œ": "oe", "Œ": "oe"})


def _ascii(s):
    return unicodedata.normalize("NFKD", (s or "").translate(_TR)).encode("ascii", "ignore").decode().lower()


def _index():
    """{normalised espn name: (id, displayName, league slug)} across all leagues we know (cached 24h)."""
    idx = {}
    for slug in LEAGUE_SLUGS:
        txt = http.get(ESPN + slug + "/teams", ttl_hours=24, tries=1)
        if not txt:
            continue
        try:
            teams = json.loads(txt)["sports"][0]["leagues"][0]["teams"]
        except Exception:
            continue
        for t in teams:
            t = t["team"]
            for key in {t.get("displayName"), t.get("shortDisplayName"), t.get("name"), t.get("location")}:
                if key:
                    idx.setdefault(norm(key), (t["id"], t["displayName"], slug))
    return idx


_IDX = None


def resolve(team):
    """our canonical team name -> (espn id, espn display name, league slug) or None"""
    global _IDX
    if _IDX is None:
        _IDX = _index()
    cands = [OVERRIDES.get(team, team), team]
    for c in cands:
        if norm(c) in _IDX:
            return _IDX[norm(c)]
    m = difflib.get_close_matches(norm(team), list(_IDX), 1, 0.86)
    return _IDX[m[0]] if m else None


MANUAL_DIR = None


def _manual_dir():
    global MANUAL_DIR
    if MANUAL_DIR is None:
        from .config import DATA
        MANUAL_DIR = DATA / "squads_manual"
        MANUAL_DIR.mkdir(exist_ok=True)
    return MANUAL_DIR


def save_manual(team, players, source, max_age_days=30):
    """Store a squad read by a person/agent from a public page (e.g. Sofascore in the browser) for clubs ESPN lacks."""
    f = _manual_dir() / (re.sub(r"[^A-Za-z0-9]+", "_", team).strip("_") + ".json")
    f.write_text(json.dumps(dict(team=team, source=source, fetched=dt.date.today().isoformat(), max_age_days=max_age_days,
                                 players=[dict(name=n.strip(), pos=None, age=None, jersey=None) for n in players if n.strip()]),
                            ensure_ascii=False, indent=1), encoding="utf-8")
    return f


def _manual(team):
    f = _manual_dir() / (re.sub(r"[^A-Za-z0-9]+", "_", team).strip("_") + ".json")
    if not f.exists():
        return None
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except Exception:
        return None
    age = (dt.date.today() - dt.date.fromisoformat(j["fetched"])).days
    if age > j.get("max_age_days", 30):
        return None
    return dict(team=team, espn_name=f"{j['source']} (manual, {j['fetched']})", league="manual", fetched=j["fetched"], players=j["players"])


def roster(team):
    """-> dict(team, espn_name, fetched, players=[{name, pos, age, jersey}]) or None. ESPN first, manual file as fallback."""
    r = resolve(team)
    if not r:
        return _manual(team)
    tid, disp, slug = r
    txt = http.get(ESPN + f"{slug}/teams/{tid}/roster", ttl_hours=24, tries=2)
    if not txt:
        return None
    try:
        ath = json.loads(txt).get("athletes", [])
    except Exception:
        return None
    pl = [dict(name=a.get("fullName") or a.get("displayName"), pos=(a.get("position") or {}).get("abbreviation"),
               age=a.get("age"), jersey=a.get("jersey")) for a in ath]
    if not pl:
        return _manual(team)
    return dict(team=team, espn_name=disp, league=slug, fetched=dt.date.today().isoformat(), players=pl)


def _tokens(name):
    return [t for t in re.split(r"[\s\-']+", _ascii(name)) if len(t) >= 3]


def verify_names(team, names):
    """Check player surnames/first names against the current roster. Returns dict(ok=[...], unknown=[...], roster_size, espn_name)."""
    ro = roster(team)
    if not ro:
        return dict(ok=[], unknown=list(names), roster_size=0, espn_name=None, note="team not found on ESPN")
    full = [_ascii(p["name"]) for p in ro["players"]]
    ok, unknown = [], []
    for n in names:
        toks = _tokens(n)
        hit = any(all(t in f for t in toks[-1:]) for f in full) if toks else False
        if not hit and toks:   # typo tolerance on the surname
            last = toks[-1]
            hit = any(difflib.SequenceMatcher(None, last, f.split()[-1]).ratio() >= 0.85 for f in full if f.split())
        (ok if hit else unknown).append(n)
    return dict(ok=ok, unknown=unknown, roster_size=len(full), espn_name=ro["espn_name"])


def verify_opinion(entry):
    """entry = one match dict from data/opinions/*.json with 'players': [{team, name, ...}]. Adds entry['verification']."""
    players = entry.get("players") or []
    by_team = {}
    for p in players:
        if p.get("team") and p.get("name"):
            by_team.setdefault(p["team"], []).append(p["name"])
    res = {}
    all_unknown = []
    for team, names in by_team.items():
        v = verify_names(team, names)
        res[team] = v
        all_unknown += [f"{team}: {n}" for n in v["unknown"]]
    entry["verification"] = dict(checked=sum(len(v) for v in by_team.values()), unknown=all_unknown, teams=res,
                                 checked_at=dt.datetime.now().isoformat(timespec="minutes"),
                                 status="unverified" if not players else ("ok" if not all_unknown else "problems"))
    return entry


def squad_text(team):
    ro = roster(team)
    if not ro:
        return f"{team}: not found on ESPN"
    L = [f"{team}  (ESPN: {ro['espn_name']}, {ro['league']}, fetched {ro['fetched']}, {len(ro['players'])} players)"]
    for pos in ("G", "D", "M", "F"):
        ps = [p for p in ro["players"] if p["pos"] == pos]
        if ps:
            L.append(f"  {pos}: " + ", ".join(f"{p['name']}{' #' + str(p['jersey']) if p.get('jersey') else ''}{' (' + str(p['age']) + ')' if p.get('age') else ''}" for p in ps))
    other = [p for p in ro["players"] if p["pos"] not in ("G", "D", "M", "F")]
    if other:
        L.append("  ?: " + ", ".join(p["name"] for p in other))
    return "\n".join(L)
