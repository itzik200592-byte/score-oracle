"""Goal models. Every model returns (lambda_home, lambda_away, rho) for a fixture; matrices are built in one place."""
import numpy as np, pandas as pd
from scipy.optimize import minimize, least_squares
from scipy.special import gammaln

G = 11                      # scorelines 0..10
K = np.arange(G)
LOGFACT = gammaln(K + 1)
BIG4 = ["PL", "LL", "SA", "L1"]
DEFAULT_RHO = -0.04
LEVEL_LEAGUES = {"CL", "IL", "EL"}   # competitions whose scoring level drifts (the big 4 are already well anchored)


def pois(lam):
    lam = max(float(lam), 1e-4)
    return np.exp(K * np.log(lam) - lam - LOGFACT)


def score_matrix(lh, la, rho=DEFAULT_RHO):
    """Dixon-Coles joint distribution over (home goals, away goals)."""
    M = np.outer(pois(lh), pois(la))
    if rho:
        M[0, 0] *= max(1 - lh * la * rho, 0.01)
        M[0, 1] *= max(1 + lh * rho, 0.01)
        M[1, 0] *= max(1 + la * rho, 0.01)
        M[1, 1] *= max(1 - rho, 0.01)
    return M / M.sum()


def score_matrix_disp(lh, la, rho=DEFAULT_RHO, disp=0.0):
    """Common-shock mixture: the match 'tempo' scales BOTH rates by (1-d, 1, 1+d) with weights (.25, .5, .25).
    Gives fatter tails (open games with many goals, blowouts) than independent Poisson. disp=0 is plain Dixon-Coles."""
    if not disp:
        return score_matrix(lh, la, rho)
    M = 0.5 * score_matrix(lh, la, rho)
    M += 0.25 * score_matrix(lh * (1 - disp), la * (1 - disp), rho)
    M += 0.25 * score_matrix(lh * (1 + disp), la * (1 + disp), rho)
    return M / M.sum()


def outcome_probs(M):
    return np.tril(M, -1).sum(), np.trace(M), np.triu(M, 1).sum()   # home, draw, away


_I, _J = np.meshgrid(K, K, indexing="ij")
_OVER = (_I + _J) >= 3
_BTTS = (_I > 0) & (_J > 0)


def over25(M):
    return M[_OVER].sum()


def btts(M):
    return M[_BTTS].sum()


# ------------------------------------------------------------------ market-implied goal rates
def market_lambdas(m: pd.DataFrame):
    """Invert 1X2 (+ over/under 2.5) odds into expected goals for every row that has odds."""
    out = np.full((len(m), 2), np.nan)
    oh, od, oa = m.o_h.values, m.o_d.values, m.o_a.values
    ov, un = m.o_ov.values, m.o_un.values
    for i in range(len(m)):
        if not (oh[i] > 1 and od[i] > 1 and oa[i] > 1):
            continue
        p = 1 / np.array([oh[i], od[i], oa[i]])
        p = p / p.sum()
        target = list(p)
        use_ou = ov[i] > 1 and un[i] > 1
        if use_ou:
            q = (1 / ov[i]) / (1 / ov[i] + 1 / un[i])
            target.append(q)
        target = np.array(target)

        def res(x):
            M = score_matrix(np.exp(x[0]), np.exp(x[1]), DEFAULT_RHO)
            r = list(outcome_probs(M))
            if use_ou:
                r.append(over25(M))
            return np.array(r) - target

        x0 = np.log([1.5, 1.1]) if not use_ou else np.log([max(0.4, 2.7 * (p[0] + p[1] / 2)), max(0.4, 2.7 * (p[2] + p[1] / 2))])
        try:
            s = least_squares(res, x0, bounds=(np.log(0.15), np.log(5.0)))
            out[i] = np.exp(s.x)
        except Exception:
            pass
    return out


# ------------------------------------------------------------------ Dixon-Coles (time-decayed, ridge-shrunk)
class DC:
    def __init__(self, half_life=330, ridge=3.0, xw=0.0, pooled=False, years=4, name="dc", newcomer=(-0.15, -0.20), level_hl=None, level_k=20.0):
        self.half_life, self.ridge, self.xw, self.pooled, self.years, self.name = half_life, ridge, xw, pooled, years, name
        self.level_hl, self.level_k = level_hl, level_k
        self.newcomer = newcomer
        self.ok = False

    def fit(self, df, as_of, leagues=None):
        d = df[df.played & (df.date < as_of) & (df.date >= as_of - pd.Timedelta(days=365 * self.years))]
        if leagues is not None:
            d = d[d.league.isin(leagues)]
        if len(d) < 60:
            self.ok = False
            return self
        age = (as_of - d.date).dt.days.values.astype(float)
        w = 0.5 ** (age / self.half_life)
        gh, ga = d.hg.values.astype(float), d.ag.values.astype(float)
        if self.xw > 0:
            hx = d.xg_h.notna().values
            gh = np.where(hx, (1 - self.xw) * gh + self.xw * d.xg_h.fillna(0).values, gh)
            ga = np.where(hx, (1 - self.xw) * ga + self.xw * d.xg_a.fillna(0).values, ga)
        teams = sorted(set(d.home) | set(d.away))
        self.tix = {t: i for i, t in enumerate(teams)}
        nT = len(teams)
        H = d.home.map(self.tix).values
        A = d.away.map(self.tix).values
        # league of competition
        lgs = sorted(set(d.league))
        self.lix = {l: i for i, l in enumerate(lgs)}
        nL = len(lgs)
        Lm = d.league.map(self.lix).values
        # each team's domestic league (most frequent non-CL competition), used for pooled offsets
        dom = {}
        for lg_, hh, aa in zip(d.league.values, d.home.values, d.away.values):
            if lg_ != "CL":
                for t in (hh, aa):
                    dom.setdefault(t, {}).setdefault(lg_, 0)
                    dom[t][lg_] += 1
        self.dom = {t: max(c, key=c.get) for t, c in dom.items()}
        olgs = sorted(set(self.dom.values()) | {"OTH"})
        self.olix = {l: i for i, l in enumerate(olgs)}
        nO = len(olgs)
        tl = np.array([self.olix[self.dom.get(t, "OTH")] for t in teams])
        self.tl = tl
        pooled = self.pooled
        r, r_lo = self.ridge, 0.4
        n_par = 2 * nL + 2 * nT + (2 * nO if pooled else 0)

        def unpack(x):
            mu, hfa = x[:nL], x[nL:2 * nL]
            a, dd = x[2 * nL:2 * nL + nT], x[2 * nL + nT:2 * nL + 2 * nT]
            if pooled:
                Ao, Do = x[2 * nL + 2 * nT:2 * nL + 2 * nT + nO], x[2 * nL + 2 * nT + nO:]
            else:
                Ao = Do = None
            return mu, hfa, a, dd, Ao, Do

        def f(x):
            mu, hfa, a, dd, Ao, Do = unpack(x)
            ae = a + (Ao[tl] if pooled else 0)
            de = dd + (Do[tl] if pooled else 0)
            lh = np.exp(mu[Lm] + hfa[Lm] + ae[H] - de[A])
            la = np.exp(mu[Lm] + ae[A] - de[H])
            nll = -np.sum(w * (gh * np.log(lh) - lh + ga * np.log(la) - la))
            nll += r * (a @ a + dd @ dd)
            gh_, ga_ = w * (gh - lh), w * (ga - la)
            g_mu = -np.bincount(Lm, gh_ + ga_, nL)
            g_hfa = -np.bincount(Lm, gh_, nL)
            g_ae = -(np.bincount(H, gh_, nT) + np.bincount(A, ga_, nT))
            g_de = np.bincount(A, gh_, nT) + np.bincount(H, ga_, nT)
            parts = [g_mu, g_hfa, g_ae + 2 * r * a, g_de + 2 * r * dd]
            if pooled:
                nll += r_lo * (Ao @ Ao + Do @ Do)
                parts += [np.bincount(tl, g_ae, nO) + 2 * r_lo * Ao, np.bincount(tl, g_de, nO) + 2 * r_lo * Do]
            return nll, np.concatenate(parts)

        x0 = np.zeros(n_par)
        x0[:nL] = np.log(max(np.average(gh, weights=w), 0.3))
        x0[nL:2 * nL] = 0.2
        sol = minimize(f, x0, jac=True, method="L-BFGS-B", options={"maxiter": 400})
        self.mu, self.hfa, self.a, self.d, self.Ao, self.Do = unpack(sol.x)
        # rho from low scores
        ae = self.a + (self.Ao[tl] if pooled else 0)
        de = self.d + (self.Do[tl] if pooled else 0)
        lh = np.exp(self.mu[Lm] + self.hfa[Lm] + ae[H] - de[A])
        la = np.exp(self.mu[Lm] + ae[A] - de[H])
        hi, ai = d.hg.values, d.ag.values
        best, brho = -1e18, DEFAULT_RHO
        for rho in np.arange(-0.20, 0.081, 0.02):
            t = np.ones(len(d))
            m00 = (hi == 0) & (ai == 0); m01 = (hi == 0) & (ai == 1); m10 = (hi == 1) & (ai == 0); m11 = (hi == 1) & (ai == 1)
            t[m00] = 1 - lh[m00] * la[m00] * rho
            t[m01] = 1 + lh[m01] * rho
            t[m10] = 1 + la[m10] * rho
            t[m11] = 1 - rho
            if (t <= 0).any():
                continue
            ll = np.sum(w * np.log(t))
            if ll > best:
                best, brho = ll, rho
        self.rho = brho
        if self.level_hl:
            # re-anchor each competition's goal level to the RECENT actual level (scoring environments drift:
            # CL averaged 2.98 goals in 2022 and 3.44+ now). Shrunk toward 'no change' by level_k.
            wr = 0.5 ** (age / self.level_hl)
            tot_act, tot_exp = gh + ga, lh + la
            for lname, li in self.lix.items():
                if lname not in LEVEL_LEAGUES:
                    continue
                sel = Lm == li
                A = np.sum(wr[sel] * tot_act[sel]); E = np.sum(wr[sel] * tot_exp[sel])
                self.mu[li] += np.log((A + self.level_k) / (E + self.level_k))
        self.ok = True
        return self

    def lam(self, home, away, league):
        if not self.ok or league not in self.lix:
            return None
        li = self.lix[league]
        def eff(t):
            if t in self.tix:
                i = self.tix[t]
                a, dd = self.a[i], self.d[i]
                if self.pooled:
                    a += self.Ao[self.tl[i]]; dd += self.Do[self.tl[i]]
                return a, dd
            a, dd = (self.newcomer if league != "CL" else (0.0, 0.0))
            if self.pooled:
                a += self.Ao[self.olix["OTH"]]; dd += self.Do[self.olix["OTH"]]
            return a, dd
        ah, dh = eff(home); aa, da = eff(away)
        lh = np.exp(self.mu[li] + self.hfa[li] + ah - da)
        la = np.exp(self.mu[li] + aa - dh)
        return float(lh), float(la), float(self.rho)


# ------------------------------------------------------------------ Elo -> goals
INIT_ELO = {"PL": 1650, "LL": 1630, "SA": 1600, "L1": 1560, "IL": 1380, "CL": 1500, "OTH": 1500}


class Elo:
    def __init__(self, k=20.0, hfa=65.0, name="elo", map_hl=900, level_hl=None, level_k=20.0):
        self.k, self.hfa, self.name, self.map_hl = k, hfa, name, map_hl
        self.level_hl, self.level_k = level_hl, level_k
        self.ok = False

    def fit(self, df, as_of):
        d = df[df.played & (df.date < as_of)].sort_values("date")
        dom = {}
        for lg_, hh, aa in zip(d.league.values, d.home.values, d.away.values):
            if lg_ != "CL":
                dom[hh] = lg_; dom[aa] = lg_
        self.dom = dom
        R = {}
        pre = np.zeros(len(d))
        for n, (lg_, hh, aa, x, y) in enumerate(zip(d.league.values, d.home.values, d.away.values, d.hg.values, d.ag.values)):
            rh = R.setdefault(hh, INIT_ELO.get(dom.get(hh, "OTH"), 1500))
            ra = R.setdefault(aa, INIT_ELO.get(dom.get(aa, "OTH"), 1500))
            diff = rh - ra
            pre[n] = diff
            we = 1 / (1 + 10 ** (-(diff + self.hfa) / 400))
            s = 1.0 if x > y else (0.5 if x == y else 0.0)
            gd = abs(x - y)
            mult = 1.0 if gd <= 1 else (1.5 if gd == 2 else (11 + gd) / 8)
            delta = self.k * mult * (s - we)
            R[hh] = rh + delta
            R[aa] = ra - delta
        self.R = R
        # map rating difference -> goal rates (per competition intercept)
        lgs = sorted(set(d.league))
        self.lix = {l: i for i, l in enumerate(lgs)}
        Lm = d.league.map(self.lix).values
        x = (pre + self.hfa) / 400
        gh, ga = d.hg.values.astype(float), d.ag.values.astype(float)
        age = (as_of - d.date).dt.days.values
        w = 0.5 ** (age / self.map_hl)
        nL = len(lgs)

        def nll(p):
            c0, c1, c2 = p[:nL], p[nL], p[nL + 1]
            lh = np.exp(c0[Lm] + c2 + c1 * x)
            la = np.exp(c0[Lm] - c1 * x)
            return -np.sum(w * (gh * np.log(lh) - lh + ga * np.log(la) - la))

        p0 = np.concatenate([np.full(nL, 0.1), [0.5, 0.0]])
        sol = minimize(nll, p0, method="L-BFGS-B")
        self.c0, self.c1, self.c2 = sol.x[:nL], sol.x[nL], sol.x[nL + 1]
        if self.level_hl:
            lh = np.exp(self.c0[Lm] + self.c2 + self.c1 * x); la = np.exp(self.c0[Lm] - self.c1 * x)
            wr = 0.5 ** (age / self.level_hl)
            for lname, li in self.lix.items():
                if lname not in LEVEL_LEAGUES:
                    continue
                sel = Lm == li
                A = np.sum(wr[sel] * (gh + ga)[sel]); E = np.sum(wr[sel] * (lh + la)[sel])
                self.c0[li] += np.log((A + self.level_k) / (E + self.level_k))
        self.ok = len(d) > 100
        return self

    def rating(self, t):
        return self.R.get(t, INIT_ELO.get(self.dom.get(t, "OTH"), 1500) - (60 if t not in self.dom else 0))

    def lam(self, home, away, league):
        if not self.ok or league not in self.lix:
            return None
        x = (self.rating(home) - self.rating(away) + self.hfa) / 400
        li = self.lix[league]
        return float(np.exp(self.c0[li] + self.c2 + self.c1 * x)), float(np.exp(self.c0[li] - self.c1 * x)), DEFAULT_RHO


# ------------------------------------------------------------------ the suite
COMPONENTS = ["dc", "dcx", "pool", "elo", "mkt"]


class Suite:
    """All component models fitted on data strictly before `as_of`."""

    def __init__(self, params=None):
        p = dict(dc_hl=330, dc_ridge=3.0, dcx_hl=200, dcx_ridge=3.0, dcx_w=0.5, pool_hl=420, pool_ridge=3.0, elo_k=20.0, elo_map_hl=900, level_hl=120, level_k=20.0, disp={"CL": 0.3, "IL": 0.3, "EL": 0.3})
        p.update(params or {})
        self.p = p

    def fit(self, m, as_of):
        p = self.p
        self.dc, self.dcx = {}, {}
        for lg in BIG4 + ["IL"]:
            self.dc[lg] = DC(p["dc_hl"], p["dc_ridge"], 0.0, False, 4, "dc", level_hl=p["level_hl"], level_k=p["level_k"]).fit(m, as_of, [lg])
        for lg in BIG4:
            self.dcx[lg] = DC(p["dcx_hl"], p["dcx_ridge"], p["dcx_w"], False, 3, "dcx", level_hl=p["level_hl"], level_k=p["level_k"]).fit(m, as_of, [lg])
        self.pool = DC(p["pool_hl"], p["pool_ridge"], 0.0, True, 4, "pool", level_hl=p["level_hl"], level_k=p["level_k"]).fit(m, as_of)
        self.elo = Elo(p["elo_k"], map_hl=p["elo_map_hl"], level_hl=p["level_hl"], level_k=p["level_k"]).fit(m, as_of)
        return self

    def lams(self, row, adj=None):
        """row: object with home, away, league, lm_h, lm_a. Returns {component: (lh, la, rho)}."""
        out = {}
        h, a, lg = row.home, row.away, row.league
        if lg in self.dc:
            out["dc"] = self.dc[lg].lam(h, a, lg)
        if lg in self.dcx:
            out["dcx"] = self.dcx[lg].lam(h, a, lg)
        out["pool"] = self.pool.lam(h, a, lg)
        out["elo"] = self.elo.lam(h, a, lg)
        if not (np.isnan(row.lm_h) or np.isnan(row.lm_a)):
            out["mkt"] = (float(row.lm_h), float(row.lm_a), DEFAULT_RHO)
        res = {}
        for k, v in out.items():
            if v is None:
                continue
            lh, la, rho = v
            if adj:
                lh *= adj.get(h, {}).get("att", 1.0) * adj.get(a, {}).get("def", 1.0)
                la *= adj.get(a, {}).get("att", 1.0) * adj.get(h, {}).get("def", 1.0)
            res[k] = (lh, la, rho)
        return res

    def matrices(self, rows, adj=None):
        """rows: DataFrame. Returns dict comp -> array (n, G, G) with NaN where the component is unavailable."""
        n = len(rows)
        out = {c: np.full((n, G, G), np.nan) for c in COMPONENTS}
        for i, row in enumerate(rows.itertuples(index=False)):
            d = self.p["disp"].get(row.league, 0.0)
            for c, (lh, la, rho) in self.lams(row, adj).items():
                out[c][i] = score_matrix_disp(lh, la, rho, d if c != "mkt" else 0.0)
        return out
