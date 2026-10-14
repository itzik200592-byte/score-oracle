"""The 'sniper': turns a full score distribution into one exact-score pick, plus confidence.

The honest maths of exact scores: even a perfect model rarely gives the single best scoreline more than
~12-18% probability, so the sniper's edge comes from (1) the best possible distribution (ensemble),
(2) choosing the pick rule that maximises exact hits in backtests, and (3) knowing WHEN to shoot
(only matches whose top-score probability is high are flagged as 'sniper shots')."""
import numpy as np
from .models import outcome_probs, G

_I, _J = np.meshgrid(np.arange(G), np.arange(G), indexing="ij")
_MASK_H, _MASK_D, _MASK_A = _I > _J, _I == _J, _I < _J


def outcome_mass(M):
    pH, pD, pA = outcome_probs(M)
    return pH * _MASK_H + pD * _MASK_D + pA * _MASK_A


def pick(M, beta=0.0):
    """beta=0: pure mode. Larger beta pulls the pick toward the most likely 1X2 outcome."""
    S = M + beta * outcome_mass(M) if beta else M
    i = int(np.argmax(S))
    return i // G, i % G


def top_k(M, k=5):
    idx = np.argsort(M.ravel())[::-1][:k]
    return [((int(i) // G, int(i) % G), float(M.ravel()[i])) for i in idx]


def tier(p_top, cuts):
    """cuts = (c1, c2) learned from backtest: top-score probability thresholds for 'shot' / 'strong shot'."""
    if p_top >= cuts[1]:
        return "A"   # strong shot
    if p_top >= cuts[0]:
        return "B"   # shot
    return "C"       # low-information match: score is a coin-toss among several scorelines
