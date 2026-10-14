import datetime as dt
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CACHE = DATA / "cache"
OUT = ROOT / "output"
MATCHES_CSV = DATA / "matches.csv"
LEDGER_CSV = DATA / "ledger.csv"
ADJ_JSON = DATA / "adjustments.json"
WEIGHTS_JSON = DATA / "ensemble.json"
for p in (DATA, CACHE, OUT):
    p.mkdir(parents=True, exist_ok=True)

# fd = football-data.co.uk code, us = Understat, espn = ESPN slug, tsdb = TheSportsDB id
LEAGUES = {
    "PL": dict(name="Premier League", he="פרמיירליג אנגלית", fd="E0", us="EPL", espn="eng.1", tsdb=4328, cc="ENG"),
    "LL": dict(name="La Liga", he="לה ליגה ספרדית", fd="SP1", us="La_liga", espn="esp.1", tsdb=4335, cc="ESP"),
    "SA": dict(name="Serie A", he="סריה A איטלקית", fd="I1", us="Serie_A", espn="ita.1", tsdb=4332, cc="ITA"),
    "L1": dict(name="Ligue 1", he="ליגה 1 צרפתית", fd="F1", us="Ligue_1", espn="fra.1", tsdb=4334, cc="FRA"),
    "IL": dict(name="Israeli Premier League", he="ליגת העל", fd=None, us=None, espn="isr.1", tsdb=4644, cc="ISR"),
    "CL": dict(name="Champions League", he="ליגת האלופות", fd=None, us=None, espn="uefa.champions", tsdb=4480, cc=None),
}
BIG4 = ["PL", "LL", "SA", "L1"]
CC2LG = {v["cc"]: k for k, v in LEAGUES.items() if v["cc"]}
FIRST_SEASON = 2020  # start year of the oldest season we load


def season_of(d) -> int:
    d = dt.date(d.year, d.month, d.day)
    return d.year if d.month >= 7 else d.year - 1


def current_season() -> int:
    return season_of(dt.date.today())
