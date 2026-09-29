"""E10: statistical details behind suggestions D-2 / D-3 (numpy/scipy only, deterministic seeds)."""
import json
import numpy as np
from scipy import stats

rng = np.random.default_rng(20260929)
out = {}

# E10a winner's curse: k null candidates, pick best on the evaluation window, naive one-sided 5% lower bound > 0.
T, reps, z = 252, 200_000, stats.norm.ppf(0.95)
wc = {}
for rho in (0.0, 0.5, 0.8):
    for k in (1, 3, 5, 10):
        common = rng.standard_normal((reps, 1))
        idio = rng.standard_normal((reps, k))
        zstat = np.sqrt(rho) * common + np.sqrt(1 - rho) * idio      # standardized mean estimates, true effect 0
        best = zstat.max(axis=1)
        naive = float((best > z).mean())
        bonf = float((best > stats.norm.ppf(1 - 0.05 / k)).mean())
        wc[f"rho={rho},k={k}"] = {"naive_false_support": round(naive, 4), "bonferroni": round(bonf, 4)}
out["E10a_selected_best_false_support"] = wc

# E10b coverage of a 90% CI for the mean of overlapping h-day returns (MA(h-1)), T=252.
h, reps_b = 5, 20_000
e = rng.standard_normal((reps_b, T + h - 1))
c = np.cumsum(np.concatenate([np.zeros((reps_b, 1)), e], axis=1), axis=1)
y = c[:, h:] - c[:, :-h]                                             # y_t = e_t + ... + e_{t+h-1}, true mean 0
m = y.mean(axis=1)
yc = y - m[:, None]
g0 = (yc * yc).mean(axis=1)
naive_se = np.sqrt(g0 / T)
lrv = g0.copy()
for j in range(1, h):
    gj = (yc[:, j:] * yc[:, :-j]).mean(axis=1) * (T - j) / T
    lrv += 2 * (1 - j / h) * gj                                       # Bartlett / Newey-West, lag h-1
nw_se = np.sqrt(np.maximum(lrv, 1e-12) / T)
zc = stats.norm.ppf(0.95)
out["E10b_coverage_90pct_overlapping_h5"] = {
    "naive_iid": round(float((np.abs(m) < zc * naive_se).mean()), 4),
    "newey_west_lag4": round(float((np.abs(m) < zc * nw_se).mean()), 4),
}

# E10c how precisely an agent-level eval can estimate a false-support rate (Clopper-Pearson 95%).
cp = {}
for n, x in ((20, 1), (50, 2), (200, 10), (1000, 50)):
    lo = 0.0 if x == 0 else stats.beta.ppf(0.025, x, n - x + 1)
    hi = stats.beta.ppf(0.975, x + 1, n - x)
    cp[f"{x}/{n}"] = [round(float(lo), 4), round(float(hi), 4)]
out["E10c_clopper_pearson_95"] = cp
print(json.dumps(out, indent=2))
