"""Live bookmaker odds (collected from Winner.co.il etc. into data/odds_live.json) used two ways:
1) shown next to each match with the model edge / star flag (export.py);
2) blended INTO the prediction for competitions that have no odds history (CL/EL/IL), because in the big 4 the market
   proved to be the single best model (weight 0.88 in the backtest). Retail odds carry a large margin (Winner ~15-18%),
   so they are de-vigged with the power method (less biased on long shots than proportional scaling)."""
import json
import numpy as np
from scipy.optimize import brentq, least_squares
from .config import ROOT
from .names import norm
from .models import score_matrix, outcome_probs, DEFAULT_RHO

ODDS_LIVE = ROOT / "data" / "odds_live.json"
LIVE_MARKET_WEIGHT = 0.6   # not backtestable (no historical retail odds); big-4 backtest says market >= 0.88 when sharp


def load_live():
    """-> ({(date, norm_home, norm_away): entry}, fetched_at)"""
    if not ODDS_LIVE.exists():
        return {}, None
    try:
        j = json.loads(ODDS_LIVE.read_text(encoding="utf-8"))
    except Exception:
        return {}, None
    out = {}
    for e in j.get("matches", []):
        if e.get("h") and e.get("d") and e.get("a"):
            out[(e["date"], norm(e["home"]), norm(e["away"]))] = e
    return out, j.get("fetched_at")


def p_over_from(o):
    """Two-way de-vig of over/under 2.5 -> P(over), or None."""
    ov, un = o.get("over25"), o.get("under25")
    if ov and un and ov > 1 and un > 1:
        return float(devig_power([ov, un])[0])
    return None


def devig_power(odds):
    inv = 1 / np.asarray(odds, float)
    if inv.sum() <= 1.0:
        return inv / inv.sum()
    k = brentq(lambda k: (inv ** k).sum() - 1, 1.0, 12.0)
    p = inv ** k
    return p / p.sum()


def lambdas_from_probs(p, total_hint, p_over=None):
    """Goal rates whose 1X2 matches the (de-vigged) market. If the over/under 2.5 price is known it pins the total;
    otherwise the total is softly anchored to the model's expectation (1X2 alone does not determine it)."""
    from .models import over25 as _over25

    def res(x):
        lh, la = np.exp(x)
        M = score_matrix(lh, la, DEFAULT_RHO)
        r = list(np.array(outcome_probs(M)) - p)
        if p_over is not None:
            r.append(_over25(M) - p_over)
        else:
            r.append(0.25 * (np.log(lh + la) - np.log(total_hint)))
        return np.array(r)
    s = least_squares(res, np.log([max(total_hint * 0.55, 0.3), max(total_hint * 0.45, 0.3)]),
                      bounds=(np.log(0.15), np.log(5.0)))
    return float(np.exp(s.x[0])), float(np.exp(s.x[1]))
