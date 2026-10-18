"""Team-name normalisation across sources (football-data is the canonical namespace for the big 4)."""
import re, unicodedata, difflib

STOP = {"fc", "afc", "cf", "sc", "ssc", "fk", "sk", "ud", "cd", "rc", "us", "ca", "club", "de", "la", "el",
        "the", "1909", "1899", "calcio", "bk", "sv", "ac", "as", "ogc", "losc", "ssd", "sd", "real"}


def norm(s: str) -> str:
    s = re.sub(r"\s*\([A-Z]{3}\)\s*$", "", s or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("'", "").replace(".", " ")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    toks = [t for t in s.split() if t not in STOP]
    return " ".join(toks)


_ALIAS_RAW = {
    "Manchester United": "Man United", "Manchester City": "Man City", "Nottingham Forest": "Nott'm Forest",
    "Wolverhampton Wanderers": "Wolves", "Wolverhampton": "Wolves", "Tottenham Hotspur": "Tottenham",
    "Newcastle United": "Newcastle", "Brighton and Hove Albion": "Brighton", "West Ham United": "West Ham",
    "Leeds United": "Leeds", "Leicester City": "Leicester", "Sheffield Utd": "Sheffield United",
    "Athletic Club": "Ath Bilbao", "Athletic Bilbao": "Ath Bilbao", "Atletico Madrid": "Ath Madrid",
    "Club Atletico de Madrid": "Ath Madrid", "Real Betis": "Betis", "Celta Vigo": "Celta", "RC Celta": "Celta",
    "Espanyol": "Espanol", "RCD Espanyol": "Espanol", "Real Sociedad": "Sociedad", "Rayo Vallecano": "Vallecano",
    "Deportivo Alaves": "Alaves", "Real Oviedo": "Oviedo", "Real Valladolid": "Valladolid", "Cadiz CF": "Cadiz",
    "Internazionale": "Inter", "Inter Milan": "Inter", "FC Internazionale Milano": "Inter", "AC Milan": "Milan",
    "Hellas Verona": "Verona", "Paris Saint-Germain": "Paris SG", "Paris Saint Germain": "Paris SG", "PSG": "Paris SG",
    "Saint-Etienne": "St Etienne", "AS Saint-Etienne": "St Etienne", "Olympique de Marseille": "Marseille",
    "Olympique Marseille": "Marseille", "Olympique Lyonnais": "Lyon", "Stade Rennais": "Rennes",
    "Stade Brestois": "Brest", "Stade de Reims": "Reims", "Olympique Lyon": "Lyon",
    "Brighton & Hove Albion": "Brighton", "Bayern Munich": "Bayern", "West Bromwich Albion": "West Brom",
    "Hull City": "Hull", "Sheffield Wednesday": "Sheffield Weds",
    "Hapoel Ironi Kiryat Shmona": "Hapoel Kiryat Shmona", "Maccabi Bnei Raina": "Maccabi Raina",
    "FC Ashdod": "Ashdod", "Moadon Sport Ashdod": "Ashdod", "MS Ashdod": "Ashdod",
    "Hapoel Beer Sheva": "Hapoel Be'er Sheva", "Hapoel Be'er": "Hapoel Be'er Sheva",
    "Sporting CP": "Sporting", "Sporting Clube de Portugal": "Sporting", "Sport Lisboa e Benfica": "Benfica",
    "SL Benfica": "Benfica", "FC Porto": "Porto", "PAE Olympiakos SFP": "Olympiakos", "Olympiacos": "Olympiakos",
    "Royale Union Saint-Gilloise": "Union SG", "Union Saint-Gilloise": "Union SG", "FC Bayern Munchen": "Bayern",
    "FC Bayern Munich": "Bayern", "Borussia Dortmund": "Dortmund", "Bayer 04 Leverkusen": "Leverkusen",
    "Bayer Leverkusen": "Leverkusen", "Eintracht Frankfurt": "Frankfurt",
    "PSV Eindhoven": "PSV", "AFC Ajax": "Ajax", "Galatasaray SK": "Galatasaray", "Club Brugge KV": "Club Brugge",
    "FC Copenhagen": "Copenhagen", "FC Kobenhavn": "Copenhagen", "Qarabag Agdam FK": "Qarabag",
    "SK Slavia Praha": "Slavia Praha", "FK Bodo/Glimt": "Bodo/Glimt", "Bodo Glimt": "Bodo/Glimt",
    "La Coruna": "Deportivo", "Deportivo La Coruna": "Deportivo", "RC Deportivo": "Deportivo", "Ferencvarosi TC": "Ferencvaros", "Lokomotiv Moskva": "Lokomotiv Moscow", "Paphos FC": "Paphos", "FC Kairat Almaty": "Kairat", "Kairat Almaty": "Kairat", "Pafos": "Paphos",
    "FK Kairat": "Kairat", "Sporting Clube de Braga": "Braga", "SC Braga": "Braga", "Rangers FC": "Rangers",
    "Glasgow Rangers": "Rangers", "FC Red Bull Salzburg": "RB Salzburg", "Red Bull Salzburg": "RB Salzburg",
    "Olympiakos Piraeus": "Olympiakos", "Olympiacos Piraeus": "Olympiakos", "Slavia Prague": "Slavia Praha",
    "FK Bodø/Glimt": "Bodo/Glimt", "Bodø/Glimt": "Bodo/Glimt", "Celtic FC": "Celtic", "Feyenoord Rotterdam": "Feyenoord",
    "FC København": "Copenhagen", "Fenerbahçe SK": "Fenerbahce", "Fenerbahçe": "Fenerbahce", "AC Sparta Praha": "Sparta Praha",
    "Sparta Prague": "Sparta Praha", "FK Crvena Zvezda": "Crvena Zvezda", "Red Star Belgrade": "Crvena Zvezda",
    "Bor. Mönchengladbach": "Monchengladbach", "Borussia Monchengladbach": "Monchengladbach",
    "Borussia Mönchengladbach": "Monchengladbach", "GNK Dinamo Zagreb": "Dinamo Zagreb", "Dinamo Kiev": "Dynamo Kyiv",
    "Dynamo Kyiv": "Dynamo Kyiv", "BSC Young Boys": "Young Boys", "Shakhtar Donetsk": "Shakhtar", "FC Shakhtar Donetsk": "Shakhtar",
    "Maccabi Petach Tikva": "Maccabi Petah Tikva", "Maccabi Petah-Tikva": "Maccabi Petah Tikva",
}
ALIAS = {norm(k): v for k, v in _ALIAS_RAW.items()}
CC_LG = {"ENG": "PL", "ESP": "LL", "ITA": "SA", "FRA": "L1", "ISR": "IL"}


FUZZY_CUTOFF = 0.87   # 0.80 merged "Maccabi Haifa" into "Maccabi Raina" (ratio 0.846) and "Hapoel Haifa"/"Hapoel Hadera" (0.80)


class Resolver:
    def __init__(self):
        self.by_league = {}  # lg -> {norm: canonical}
        self.cache = {}
        self.fuzzy_log = []  # (raw, canonical, league) for every non-exact resolution, printed by `update`

    def register(self, name, lg):
        self.by_league.setdefault(lg, {})[norm(name)] = name

    def canonical(self, name):
        """Exact alias only (no fuzzy matching): used when a source's own names become the canonical namespace."""
        return ALIAS.get(norm(name), name)

    def _pool(self, lg):
        if lg in ("PL", "LL", "SA", "L1", "IL"):
            return self.by_league.get(lg, {})
        out = {}
        for d in self.by_league.values():
            out.update(d)
        return out

    def resolve(self, name, lg=None, cc=None):
        """lg = competition of the match; cc = country tag of the team (CL files)."""
        pool_lg = CC_LG.get(cc) if cc else lg
        # a country-tagged team from outside our 5 domestic leagues must never match a domestic club
        # (0.80 fuzzy once turned "Rangers FC (SCO)" into Angers and Braga into Sporting)
        only_cl = bool(cc) and pool_lg is None
        k = (name, pool_lg, only_cl)
        if k in self.cache:
            return self.cache[k]
        n = norm(name)
        pool = self.by_league.get("CL", {}) if only_cl else self._pool(pool_lg)
        res = None
        if n in ALIAS and (ALIAS[n] in pool.values() or not pool):
            res = ALIAS[n]
        if res is None and n in pool:
            res = pool[n]
        if res is None and n in ALIAS:
            res = ALIAS[n]
        if res is None and pool:
            keys = list(pool)
            m = difflib.get_close_matches(n, keys, 1, FUZZY_CUTOFF)
            if m:
                res = pool[m[0]]
            else:
                for kk in keys:  # whole-token containment, e.g. "tottenham" + "tottenham hotspur" (not "angers" in "rangers")
                    if len(kk) >= 5 and len(n) >= 5 and (n.startswith(kk + " ") or n.endswith(" " + kk)
                                                         or kk.startswith(n + " ") or kk.endswith(" " + n)):
                        res = pool[kk]
                        break
            if res is not None:
                self.fuzzy_log.append((name, res, pool_lg))
        if res is None:
            # unknown club: the first spelling seen becomes canonical, later spellings (case, accents) map to it
            auto = self.by_league.setdefault("_auto", {})
            if n in auto:
                res = auto[n]
            else:
                res = re.sub(r"\s*\([A-Z]{3}\)\s*$", "", name).strip()
                if res.isupper() and len(res) > 3:      # 'VIKING FK' -> 'Viking Fk' is worse; keep title case only for all-caps
                    res = res.title().replace(" Fk", " FK").replace(" Fc", " FC").replace(" Sk", " SK")
                auto[n] = res
        self.cache[k] = res
        return res
