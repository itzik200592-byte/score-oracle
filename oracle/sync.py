"""One-shot pipeline meant to run on the user's own PC (e.g. every couple of hours on match days):
refresh data -> collect Winner odds -> predict -> export docs/data.json -> commit and push so the phone site updates."""
import subprocess, datetime as dt, sys
import pandas as pd
from .config import ROOT, OUT
from . import data as D, winner, predict as P
from .export import export


def _git(*args, check=True):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=check)


def run(m, push=True, full=True):
    stamp = dt.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    if full:
        print(f"[{stamp}] refreshing data (cached sources, fast)")
        m = D.build()
    print("collecting Winner odds ...")
    try:
        info = winner.collect(m)
    except winner.Blocked as e:
        print("ODDS SKIPPED:", e)
        info = None
    if info and info.get("missing") and full:
        print(f"  Winner lists {len(info['missing'])} fixtures our schedule lacks -> rebuilding with them")
        m = D.build()
        info = winner.collect(m)
    if info:
        print(f"  winner events {info['winner_events']}, matched to fixtures {info['matched']}, "
              f"learned names {len(info['learned'])}, unmapped {len(info['unmapped'])}")
        for u in info["unmapped"][:15]:
            print("   unmapped:", u)
    if not full:
        return
    fx = P.upcoming(m, 8)
    pred = P.predict_fixtures(m, fx)
    P.ledger_add(pred)
    pred.to_csv(OUT / "predictions_latest.csv", index=False, encoding="utf-8")
    print("site data:", export(m, pred))
    if push:
        _git("add", "docs/data.json", "data/ledger.csv", "data/matches.csv", "data/odds_live.json",
             "data/team_he_learned.json", check=False)
        if _git("diff", "--cached", "--quiet", check=False).returncode != 0:
            _git("commit", "-m", f"sync {stamp} (PC: data + Winner odds + predictions)")
            _git("pull", "--rebase", "-X", "theirs", check=False)
            r = _git("push", check=False)
            print("pushed to GitHub" if r.returncode == 0 else f"push failed: {r.stderr.strip()[:200]}")
        else:
            print("nothing changed, no push")
