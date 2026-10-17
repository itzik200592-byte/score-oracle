import argparse, sys, json
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from . import data as D
from .config import OUT, LEAGUES, ROOT


def main():
    ap = argparse.ArgumentParser(prog="oracle", description="Football score prediction system")
    sub = ap.add_subparsers(dest="cmd", required=True)
    u = sub.add_parser("update", help="download all sources and rebuild the match table")
    u.add_argument("--fast", action="store_true", help="Israeli league: scan one season only")
    b = sub.add_parser("backtest", help="walk-forward backtest, learn ensemble weights and pick rule")
    b.add_argument("--days", type=int, default=540)
    b.add_argument("--step", type=int, default=14)
    b.add_argument("--reuse", action="store_true", help="re-tune from the saved backtest without refitting")
    p = sub.add_parser("predict", help="predict upcoming fixtures")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--league", nargs="*", choices=list(LEAGUES))
    p.add_argument("--no-ledger", action="store_true")
    p.add_argument("--export", action="store_true", help="also write docs/data.json for the mobile site")
    mm = sub.add_parser("match", help="predict a single match (any two teams from the same competition)")
    mm.add_argument("home"); mm.add_argument("away"); mm.add_argument("league", choices=list(LEAGUES))
    sub.add_parser("review", help="score past predictions against real results")
    sq = sub.add_parser("squad", help="current squad from ESPN (verified source for player claims)")
    sq.add_argument("teams", nargs="+")
    ss = sub.add_parser("squad-save", help="store a squad read from a public page (for clubs ESPN lacks): oracle squad-save \"Team\" --source sofascore --players \"A, B, C\"")
    ss.add_argument("team"); ss.add_argument("--source", required=True); ss.add_argument("--players", required=True, help="comma separated full names")
    vo = sub.add_parser("verify-opinions", help="check every player named in data/opinions/*.json against current ESPN squads")
    vo.add_argument("--date", default=None, help="only files for this date (YYYY-MM-DD)")
    cx = sub.add_parser("context", help="situation dossier for a fixture (venue records, form, congestion, H2H, table)")
    cx.add_argument("home"); cx.add_argument("away"); cx.add_argument("league", choices=list(LEAGUES))
    o = sub.add_parser("odds-sync", help="collect Winner odds from THIS computer (cloud IPs are blocked by Winner)")
    sy = sub.add_parser("sync", help="update data + collect odds + predict + export + push to GitHub (run on this PC)")
    sy.add_argument("--no-push", action="store_true")
    sub.add_parser("status", help="data coverage report")
    adj = sub.add_parser("adjust", help="manual news adjustment: oracle adjust Arsenal --att 0.9 --def 1.0 ; 'clear' removes all")
    adj.add_argument("team"); adj.add_argument("--until", default=None, help="last day the news applies (YYYY-MM-DD), default today"); adj.add_argument("--att", type=float, default=1.0); adj.add_argument("--def", dest="deff", type=float, default=1.0)
    a = ap.parse_args()

    if a.cmd == "update":
        m = D.build(fast=a.fast)
        print(D.quality_report(m))
        return
    m = D.load()
    if a.cmd == "status":
        print(D.quality_report(m)); return
    if a.cmd == "backtest":
        from . import evaluate as E
        bt = E.load_backtest() if a.reuse else E.run_backtest(m, a.days, a.step)
        rep = E.tune_everything(bt)
        print(E.format_report(rep))
        (OUT / "backtest_report.json").write_text(json.dumps(rep, indent=2, default=str), encoding="utf-8")
        return
    from . import predict as P
    if a.cmd in ("odds-sync", "sync"):
        from . import sync as SY
        SY.run(m, push=(a.cmd == "sync" and not a.no_push), full=(a.cmd == "sync"))
        return
    if a.cmd == "squad":
        from . import squads
        for t in a.teams:
            print(squads.squad_text(t)); print()
        return
    if a.cmd == "squad-save":
        from . import squads
        f = squads.save_manual(a.team, a.players.split(","), a.source)
        print("saved", f, "players:", len(a.players.split(",")))
        return
    if a.cmd == "verify-opinions":
        from . import squads
        import glob, json as _j
        bad = 0
        for f in sorted(glob.glob(str(ROOT / "data" / "opinions" / "*.json"))):
            if a.date and a.date not in f:
                continue
            j = _j.loads(open(f, encoding="utf-8").read())
            for e in j.get("matches", []):
                squads.verify_opinion(e)
                v = e["verification"]
                flag = "OK " if v["status"] == "ok" else ("?? " if v["status"] == "unverified" else "BAD")
                print(f"{flag} {e['date']} {e['home']} - {e['away']}: {v['checked']} players checked" + (f", NOT IN CURRENT SQUAD: {v['unknown']}" if v["unknown"] else "") + ("  (no structured player list)" if v["status"] == "unverified" else ""))
                bad += bool(v["unknown"])
            open(f, "w", encoding="utf-8").write(_j.dumps(j, ensure_ascii=False, indent=1))
        print(f"\n{bad} opinion(s) with players not in the current squad")
        return
    if a.cmd == "context":
        from . import context as CX
        print(CX.as_text(CX.dossier(m, a.home, a.away, a.league))); return
    if a.cmd == "review":
        from . import track
        print(track.text_report(m)); return
    if a.cmd == "adjust":
        from .config import ADJ_JSON
        cur = P.load_adj()
        if a.team.lower() == "clear":
            cur = {}
        else:
            import datetime as _dt
            cur[a.team] = {"att": a.att, "def": a.deff, "until": a.until or _dt.date.today().isoformat()}
        ADJ_JSON.write_text(json.dumps(cur, indent=2), encoding="utf-8")
        print("adjustments:", cur); return
    if a.cmd == "predict":
        fx = P.upcoming(m, a.days, a.league)
        if fx.empty:
            print("No upcoming fixtures in that window."); return
        pred = P.predict_fixtures(m, fx)
        cols = ["date", "league", "home", "away", "pick", "p_pick", "tier", "pH", "pD", "pA"]
        show = pred[cols].copy()
        for c in ("p_pick", "pH", "pD", "pA"):
            show[c] = (100 * show[c]).round(1)
        with pd.option_context("display.width", 200, "display.max_rows", 500):
            print(show.to_string(index=False))
        pred.to_csv(OUT / "predictions_latest.csv", index=False, encoding="utf-8")
        print("html:", P.html_report(pred))
        if a.export:
            from .export import export
            print("site data:", export(m, pred, ledger=not a.no_ledger))
        return
    if a.cmd == "match":
        from .models import Suite
        from .evaluate import blend, group_of
        from .sniper import pick, top_k
        cfg = P.load_cfg()
        row = pd.DataFrame([dict(date=pd.Timestamp.now().normalize(), league=a.league, home=a.home, away=a.away,
                                 lm_h=float("nan"), lm_a=float("nan"))])
        pred = P.predict_fixtures(m, row, cfg)
        print(pred.T.to_string())


if __name__ == "__main__":
    main()
