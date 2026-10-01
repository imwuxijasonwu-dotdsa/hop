"""E17: scenario base rule (calibrate local vol to the leg's mark, then shock in the same model) and grid cost."""
import importlib.metadata as md, json, time
import QuantLib as ql
from scipy.optimize import brentq

DC, TODAY = ql.Actual365Fixed(), ql.Date(30, 9, 2026)
ql.Settings.instance().evaluationDate = TODAY
out = {"versions": {p: md.version(p) for p in ["QuantLib", "scipy"]}}


def price(right, K, days, sig, r, q, spot, engine="fd"):
    proc = ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(spot)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, q, DC)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, r, DC)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, ql.NullCalendar(), sig, DC)))
    opt = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put if right == "P" else ql.Option.Call, K),
                           ql.AmericanExercise(TODAY, TODAY + days))
    eng = ql.FdBlackScholesVanillaEngine(proc, 400, 400) if engine == "fd" else ql.BinomialVanillaEngine(proc, "crr", 801)
    opt.setPricingEngine(eng)
    return opt.NPV()


def calibrate(right, K, days, mark, r, q, spot):
    """Local vol that reproduces the mark in the local model; None when the mark carries no vol information."""
    intrinsic = max(K - spot, 0.0) if right == "P" else max(spot - K, 0.0)
    if mark <= intrinsic + 1e-6:
        return None, "not_identifiable(mark_at_or_below_intrinsic)"
    try:
        return brentq(lambda s: price(right, K, days, s, r, q, spot) - mark, 0.01, 3.0, xtol=1e-8), "ok"
    except ValueError:
        return None, "not_identifiable(no_root_in_bounds)"


S, MULT = 100.0, 100
VENDOR = dict(r=0.040, q=0.005)        # stand-in for an opaque vendor model that produced the observed mark
LOCAL = dict(r=0.045, q=0.0)           # declared local inputs
K, DAYS, TRUE_VOL = 100.0, 45, 0.30
mark = price("P", K, DAYS, TRUE_VOL, spot=S, **VENDOR)
cal_vol, status = calibrate("P", K, DAYS, mark, spot=S, **LOCAL)
scen = {"time_plus_1d": dict(days=DAYS - 1, dvol=0.0, spot=S),
        "spot_minus_5pct": dict(days=DAYS, dvol=0.0, spot=S * 0.95),
        "vol_plus_5pts": dict(days=DAYS, dvol=0.05, spot=S)}
rows = {}
for name, sc in scen.items():
    local_uncal = lambda v_shift=0.0, d=DAYS, sp=S: price("P", K, d, TRUE_VOL + v_shift, spot=sp, **LOCAL)
    shocked_uncal = local_uncal(sc["dvol"], sc["days"], sc["spot"])
    shocked_cal = price("P", K, sc["days"], cal_vol + sc["dvol"], spot=sc["spot"], **LOCAL)
    base_cal = price("P", K, DAYS, cal_vol, spot=S, **LOCAL)
    rows[name] = {
        "mixed(base=mark, shock=uncalibrated local)": round((shocked_uncal - mark) * MULT, 2),
        "consistent_uncalibrated(base, shock both local@30%)": round((shocked_uncal - local_uncal()) * MULT, 2),
        "calibrated_to_mark(base, shock both local@cal_vol)": round((shocked_cal - base_cal) * MULT, 2),
        "vendor_reference(base, shock both vendor model)": round(
            (price("P", K, sc["days"], TRUE_VOL + sc["dvol"], spot=sc["spot"], **VENDOR) - mark) * MULT, 2)}
out["E17a_scenario_base_rule"] = {
    "contract": "American put K=100, 45 days, spot 100; mark from vendor-like model (r=4.0%, q=0.5%, vol 30%)",
    "mark": round(mark, 4), "calibrated_local_vol": round(cal_vol, 5), "calibration_status": status,
    "calibrated_base_minus_mark_usd": round((price("P", K, DAYS, cal_vol, spot=S, **LOCAL) - mark) * MULT, 6),
    "scenario_pnl_per_contract_usd": rows}

# E17b: a leg whose mark sits at intrinsic cannot be calibrated -> flagged, not silently priced
deep_mark = price("P", 130.0, 30, TRUE_VOL, spot=S, **VENDOR)
out["E17b_non_identifiable_leg"] = {"contract": "American put K=130, 30 days", "mark": round(deep_mark, 6),
                                    "status": calibrate("P", 130.0, 30, deep_mark, spot=S, **LOCAL)[1]}

# E17c: grid cost for a two-leg bull put spread (short 100P, long 95P, 45 days)
legs = [("P", 100.0, -1), ("P", 95.0, +1)]
grid = [(sp, dv, dd) for sp in (-0.10, -0.05, 0.0, 0.05, 0.10) for dv in (-0.05, 0.0, 0.05) for dd in (0, 14, 28)]
timing = {}
for engine in ("fd", "crr"):
    t0 = time.perf_counter()
    vols = {}
    for right, k, _ in legs:
        m = price(right, k, DAYS, TRUE_VOL, spot=S, **VENDOR)
        vols[k] = calibrate(right, k, DAYS, m, spot=S, **LOCAL)[0]
    t_cal = time.perf_counter() - t0
    t1 = time.perf_counter()
    n = 0
    for sp, dv, dd in grid:
        for right, k, qty in legs:
            price(right, k, DAYS - dd, vols[k] + dv, spot=S * (1 + sp), engine=engine, **LOCAL)
            n += 1
    t_grid = time.perf_counter() - t1
    timing[engine] = {"calibration_ms_total": round(1000 * t_cal, 1), "grid_pricings": n,
                      "grid_ms_total": round(1000 * t_grid, 1), "ms_per_pricing": round(1000 * t_grid / n, 2)}
out["E17c_bull_put_spread_grid_cost"] = {"grid": "spot {-10,-5,0,5,10}% x vol {-5,0,+5} pts x days {0,14,28}",
                                          "note": "calibration always uses the FD engine", "timing": timing}
print(json.dumps(out, indent=2))
