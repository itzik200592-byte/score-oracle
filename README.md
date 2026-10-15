# Score Oracle

Statistical exact-score prediction for Champions League, Europa League, Israeli Premier League, Premier League, La Liga, Serie A, Ligue 1.

## Commands (run inside this folder)
- `python -m oracle update` downloads all sources (cached) and rebuilds data/matches.csv
- `python -m oracle backtest` walk-forward test, learns ensemble weights + pick rule (add --reuse to re-tune only)
- `python -m oracle predict --days 7 [--league PL IL ...]` predictions, output/predictions_*.html and .csv, saved to the ledger
- `python -m oracle review` real hit rate of past predictions
- `python -m oracle adjust "Team" --att 0.92 --def 1.0` manual news adjustment (`adjust clear` resets)
- `python -m oracle status` data coverage

## Sources
football-data.co.uk (results + odds), Understat (xG), ESPN (fixtures/results, plus Israeli league and Europa League history scanned day by day), TheSportsDB (Israel, current seasons), openfootball (Champions League history). ClubElo is optional (API unreachable on some networks); Elo is computed internally.
`update` prints every fuzzy team-name resolution it made; check that list if a team looks wrong (a loose match once merged Maccabi Haifa into Maccabi Raina).

## Models
Dixon-Coles (time decayed, ridge shrunk), DC blended with xG, pooled cross-league DC (for Champions League), Elo to goals, market-implied goal rates from odds. Competition level re-anchoring (CL/IL/EL scoring drifts upward) and a common-shock tail mixture for open games. Blended by weights learned on a walk-forward backtest; the sniper picks the exact score and tiers each match (A/B/C) by confidence.

## Agent
`.claude/agents/score-sniper.md` runs the pipeline, checks injuries and lineups, applies bounded adjustments.
