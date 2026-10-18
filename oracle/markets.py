"""Every market we can price from one score matrix P (home goals x away goals), each with a plain label.
MARKETS[key] = (hebrew label, fn(home_goals, away_goals) -> bool) so the SAME definition prices the future
(sum of matrix cells) and settles the past (backtest, ledger)."""
import numpy as np

_I, _J = np.meshgrid(np.arange(11), np.arange(11), indexing="ij")


def _o(line):
    return lambda h, a: h + a > line


def _u(line):
    return lambda h, a: h + a < line


MARKETS = {
    # result
    "1": ("ניצחון בית", lambda h, a: h > a),
    "x": ("תיקו", lambda h, a: h == a),
    "2": ("ניצחון חוץ", lambda h, a: a > h),
    "1x": ("בית לא מפסידה (1X)", lambda h, a: h >= a),
    "x2": ("חוץ לא מפסידה (X2)", lambda h, a: a >= h),
    "12": ("יהיה מנצח (בלי תיקו)", lambda h, a: h != a),
    # total goals
    "o05": ("מעל 0.5 שערים", _o(0.5)),
    "o15": ("מעל 1.5 שערים", _o(1.5)),
    "o25": ("מעל 2.5 שערים", _o(2.5)),
    "o35": ("מעל 3.5 שערים", _o(3.5)),
    "u15": ("מתחת 1.5 שערים", _u(1.5)),
    "u25": ("מתחת 2.5 שערים", _u(2.5)),
    "u35": ("מתחת 3.5 שערים", _u(3.5)),
    "u45": ("מתחת 4.5 שערים", _u(4.5)),
    "tg01": ("0 עד 1 שערים", lambda h, a: h + a <= 1),
    "tg23": ("2 עד 3 שערים", lambda h, a: 2 <= h + a <= 3),
    "tg4p": ("4 שערים ומעלה", lambda h, a: h + a >= 4),
    # teams to score
    "btts": ("שתיהן מבקיעות", lambda h, a: h > 0 and a > 0),
    "nobtts": ("לפחות אחת לא מבקיעה", lambda h, a: h == 0 or a == 0),
    "h_scores": ("הבית מבקיעה", lambda h, a: h > 0),
    "a_scores": ("החוץ מבקיעה", lambda h, a: a > 0),
    "h_o15": ("הבית מבקיעה 2+", lambda h, a: h >= 2),
    "a_o15": ("החוץ מבקיעה 2+", lambda h, a: a >= 2),
    "h_cs": ("הבית שומרת על רשת נקייה", lambda h, a: a == 0),
    "a_cs": ("החוץ שומרת על רשת נקייה", lambda h, a: h == 0),
    # win combos (the 'team wins AND over a goal' family)
    "1_o15": ("בית מנצחת ומעל 1.5 שערים", lambda h, a: h > a and h + a >= 2),
    "2_o15": ("חוץ מנצחת ומעל 1.5 שערים", lambda h, a: a > h and h + a >= 2),
    "1_o25": ("בית מנצחת ומעל 2.5 שערים", lambda h, a: h > a and h + a >= 3),
    "2_o25": ("חוץ מנצחת ומעל 2.5 שערים", lambda h, a: a > h and h + a >= 3),
    "1x_o05": ("בית לא מפסידה ומעל 0.5", lambda h, a: h >= a and h + a >= 1),
    "x2_o05": ("חוץ לא מפסידה ומעל 0.5", lambda h, a: a >= h and h + a >= 1),
    "1x_u45": ("בית לא מפסידה ומתחת 4.5", lambda h, a: h >= a and h + a <= 4),
    "x2_u45": ("חוץ לא מפסידה ומתחת 4.5", lambda h, a: a >= h and h + a <= 4),
    "1_cs": ("בית מנצחת בלי לספוג", lambda h, a: h > a and a == 0),
    "2_cs": ("חוץ מנצחת בלי לספוג", lambda h, a: a > h and h == 0),
    "h_by2": ("בית מנצחת בהפרש 2+", lambda h, a: h - a >= 2),
    "a_by2": ("חוץ מנצחת בהפרש 2+", lambda h, a: a - h >= 2),
}

# which of our markets Winner actually sells (verified against the live line, 18 Oct 2026)
ON_WINNER = {"1", "x", "2", "o25", "u25", "tg01", "tg23", "tg4p", "btts", "nobtts"}


def market_probs(P):
    out = {}
    for k, (_, fn) in MARKETS.items():
        mask = np.zeros_like(P, dtype=bool)
        for h in range(11):
            for a in range(11):
                if fn(h, a):
                    mask[h, a] = True
        out[k] = float(P[mask].sum())
    return out


_MASKS = {k: np.array([[fn(h, a) for a in range(11)] for h in range(11)]) for k, (_, fn) in MARKETS.items()}


def market_probs_fast(P):
    return {k: float(P[m].sum()) for k, m in _MASKS.items()}
