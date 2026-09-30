"""E11-E13: option pricing / implied-vol library checks for the options package framework (synthetic inputs only)."""
import importlib.metadata as md, json, math, time
import numpy as np
import QuantLib as ql
from scipy.optimize import brentq
from scipy.stats import norm
from vollib.black_scholes_merton import black_scholes_merton as v_price
from vollib.black_scholes_merton.implied_volatility import implied_volatility as v_iv

out = {"versions": {p: md.version(p) for p in ["QuantLib", "vollib", "numpy", "scipy"]}}
DC = ql.Actual365Fixed()
TODAY = ql.Date(30, 9, 2026)
ql.Settings.instance().evaluationDate = TODAY


def bsm_price(flag, S, K, t, r, q, sig):
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * t) / (sig * math.sqrt(t))
    d2 = d1 - sig * math.sqrt(t)
    if flag == "c":
        return S * math.exp(-q * t) * norm.cdf(d1) - K * math.exp(-r * t) * norm.cdf(d2)
    return K * math.exp(-r * t) * norm.cdf(-d2) - S * math.exp(-q * t) * norm.cdf(-d1)


def ql_process(S, r, q, sig):
    return ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(S)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, q, DC)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r, DC)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, ql.NullCalendar(), sig, DC)))


def ql_option(flag, K, days, american):
    mat = TODAY + days
    ex = ql.AmericanExercise(TODAY, mat) if american else ql.EuropeanExercise(mat)
    return ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Call if flag == "c" else ql.Option.Put, K), ex)


# ---- synthetic chain grid (European BSM ground truth)
rng = np.random.default_rng(20260930)
S, r, q = 100.0, 0.045, 0.01
grid = []
for days in (2, 7, 30, 90, 365, 730):
    for K in np.linspace(60, 140, 41):
        for flag in "cp":
            sig = float(np.clip(0.25 + 0.4 * (math.log(K / S)) ** 2 - 0.1 * math.log(K / S), 0.08, 1.5))
            grid.append((flag, float(K), days, sig))
t_of = lambda d: d / 365.0
prices = [bsm_price(f, S, K, t_of(d), r, q, s) for f, K, d, s in grid]
keep = [i for i, p in enumerate(prices) if p > 0.005]           # ignore sub-half-cent quotes, as on a real chain
out["E11_grid"] = {"options_total": len(grid), "priced_above_0.005": len(keep)}

# E11a accuracy: recover sigma from the BSM price
errs_v, errs_ql, fails = [], [], {"vollib": 0, "quantlib": 0}
t0 = time.perf_counter()
for i in keep:
    f, K, d, s = grid[i]
    try:
        errs_v.append(abs(v_iv(prices[i], S, K, t_of(d), r, q, f) - s))
    except Exception:
        fails["vollib"] += 1
t_v = time.perf_counter() - t0
proc_cache = ql_process(S, r, q, 0.2)
t0 = time.perf_counter()
for i in keep:
    f, K, d, s = grid[i]
    try:
        opt = ql_option(f, K, d, False)
        errs_ql.append(abs(opt.impliedVolatility(prices[i], proc_cache, 1e-10, 500, 1e-4, 5.0) - s))
    except Exception:
        fails["quantlib"] += 1
t_ql = time.perf_counter() - t0
def vega_1pt(f, K, d, s):
    t = t_of(d)
    d1 = (math.log(S / K) + (r - q + 0.5 * s * s) * t) / (s * math.sqrt(t))
    return S * math.exp(-q * t) * norm.pdf(d1) * math.sqrt(t) * 0.01      # price change for +1 vol point

split = {"identifiable(vega_1pt>=0.01)": [], "not_identifiable(vega_1pt<0.01)": []}
fail_by_class = {"identifiable(vega_1pt>=0.01)": 0, "not_identifiable(vega_1pt<0.01)": 0}
for i in keep:
    f, K, d, s = grid[i]
    cls = "identifiable(vega_1pt>=0.01)" if vega_1pt(f, K, d, s) >= 0.01 else "not_identifiable(vega_1pt<0.01)"
    try:
        split[cls].append(abs(v_iv(prices[i], S, K, t_of(d), r, q, f) - s))
    except Exception:
        fail_by_class[cls] += 1
out["E11a_european_iv_recovery"] = {
    "vollib_lets_be_rational": {"max_abs_err_volpts_all": round(float(np.max(errs_v) * 100), 4), "ms_per_option": round(1000 * t_v / len(keep), 3)},
    "quantlib_analytic": {"max_abs_err_volpts_all": round(float(np.max(errs_ql) * 100), 4), "ms_per_option": round(1000 * t_ql / len(keep), 3)},
    "failures_all": fails,
    "vollib_by_identifiability": {k: {"n_solved": len(v), "n_failed": fail_by_class[k],
                                      "max_abs_err_volpts": (round(float(np.max(v) * 100), 8) if v else None)}
                                  for k, v in split.items()}}

# E12 American vs European: IV bias when a European formula is applied to American prices
bias_rows = []
for flag, days in (("p", 182), ("p", 365), ("c", 365)):
    for K in (80, 90, 100, 110, 120, 130):
        sig = 0.30
        proc = ql_process(S, r, 0.0 if flag == "p" else 0.03, sig)
        am = ql_option(flag, K, days, True)
        am.setPricingEngine(ql.FdBlackScholesVanillaEngine(proc, 400, 400))
        p_am = am.NPV()
        qq = 0.0 if flag == "p" else 0.03
        try:
            iv_eu = v_iv(p_am, S, K, t_of(days), r, qq, flag)
        except Exception as e:
            iv_eu = float("nan")
        bias_rows.append({"flag": flag, "days": days, "K": K, "q": qq, "true_vol": sig,
                          "american_price": round(p_am, 4), "european_iv_from_american_price": round(iv_eu, 4),
                          "bias_volpts": round((iv_eu - sig) * 100, 2)})
out["E12_american_vs_european_iv_bias"] = bias_rows

# E13 American engines: agreement and speed (puts, r=4.5%, q=0, 30% vol)
engines = {
    "fd_400x400": lambda p: ql.FdBlackScholesVanillaEngine(p, 400, 400),
    "binomial_crr_801": lambda p: ql.BinomialVanillaEngine(p, "crr", 801),
    "barone_adesi_whaley": lambda p: ql.BaroneAdesiWhaleyApproximationEngine(p),
    "bjerksund_stensland": lambda p: ql.BjerksundStenslandApproximationEngine(p),
}
proc = ql_process(S, r, 0.0, 0.30)
cases = [(K, d) for d in (30, 182, 365) for K in (80, 90, 100, 110, 120, 130)]
ref = {}
e13 = {}
for name, mk in engines.items():
    t0 = time.perf_counter()
    vals = []
    for K, d in cases:
        o = ql_option("p", K, d, True)
        o.setPricingEngine(mk(proc))
        vals.append(o.NPV())
    dt = time.perf_counter() - t0
    if name == "fd_400x400":
        ref = vals
    e13[name] = {"ms_per_price": round(1000 * dt / len(cases), 3),
                 "max_abs_diff_vs_fd": round(float(np.max(np.abs(np.array(vals) - np.array(ref)))), 5)}
# American IV (QuantLib picks an FD engine internally for American exercise)
t0 = time.perf_counter()
iv_err, not_identifiable = [], []
for K, d in cases:
    o = ql_option("p", K, d, True)
    o.setPricingEngine(ql.FdBlackScholesVanillaEngine(proc, 400, 400))
    target = o.NPV()
    try:
        v = o.impliedVolatility(target, proc, 1e-8, 500, 1e-4, 5.0)
        iv_err.append(abs(v - 0.30))
        if abs(v - 0.30) > 0.001:
            not_identifiable.append({"K": K, "days": d, "builtin_iv_err_volpts": round((v - 0.30) * 100, 3),
                                     "price_minus_intrinsic": round(target - max(K - S, 0.0), 6)})
    except RuntimeError as e:
        # price at (or numerically at) intrinsic: early exercise is optimal now, so no unique implied vol
        not_identifiable.append({"K": K, "days": d, "price": round(target, 6), "intrinsic": max(K - S, 0.0),
                                 "error": str(e)[:60]})
builtin_elapsed = time.perf_counter() - t0
per_case = []
t1 = time.perf_counter()
for K, d in cases:
    o = ql_option("p", K, d, True)
    o.setPricingEngine(ql.FdBlackScholesVanillaEngine(proc, 400, 400))
    target = o.NPV()
    def f_sig(sig):
        pr = ql_process(S, r, 0.0, sig)
        oo = ql_option("p", K, d, True)
        oo.setPricingEngine(ql.FdBlackScholesVanillaEngine(pr, 400, 400))
        return oo.NPV() - target
    try:
        est = brentq(f_sig, 0.01, 3.0, xtol=1e-7)
        per_case.append({"K": K, "days": d, "consistent_engine_iv_err_volpts": round((est - 0.30) * 100, 5),
                         "price_minus_intrinsic": round(target - max(K - S, 0.0), 6)})
    except ValueError:
        per_case.append({"K": K, "days": d, "consistent_engine_iv_err_volpts": None})
e13["american_iv_consistent_fd_rootfind"] = {"ms_per_option": round(1000 * (time.perf_counter() - t1) / len(cases), 1),
    "max_abs_err_volpts_when_solved": round(max(abs(x["consistent_engine_iv_err_volpts"]) for x in per_case if x["consistent_engine_iv_err_volpts"] is not None), 5),
    "unsolved": [x for x in per_case if x["consistent_engine_iv_err_volpts"] is None],
    "cases_with_err_over_0.01volpt": [x for x in per_case if x["consistent_engine_iv_err_volpts"] is not None and abs(x["consistent_engine_iv_err_volpts"]) > 0.01]}
e13["american_iv_via_quantlib"] = {"ms_per_option": round(1000 * builtin_elapsed / len(cases), 2),
                                   "solved": len(iv_err), "of": len(cases),
                                   "max_abs_err_volpts_when_solved": round(float(np.max(iv_err)) * 100, 4),
                                   "not_identifiable": not_identifiable}
out["E13_american_engines"] = e13
print(json.dumps(out, indent=2))
