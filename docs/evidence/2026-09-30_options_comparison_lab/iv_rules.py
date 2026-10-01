"""E14-E16: adjudicate IV-related divergences between the two options proposals (synthetic inputs only)."""
import importlib.metadata as md, json, math
import numpy as np
import QuantLib as ql
from scipy.stats import norm
from vollib.black_scholes_merton import black_scholes_merton as v_price
from vollib.black_scholes_merton.implied_volatility import implied_volatility as v_iv

out = {"versions": {p: md.version(p) for p in ["QuantLib", "vollib", "numpy", "scipy"]}}
S, r, q = 100.0, 0.045, 0.01


def vega_1pt(K, t, sig):
    d1 = (math.log(S / K) + (r - q + 0.5 * sig * sig) * t) / (sig * math.sqrt(t))
    return S * math.exp(-q * t) * norm.pdf(d1) * math.sqrt(t) * 0.01


def safe_iv(p, K, t, flag):
    try:
        return v_iv(p, S, K, t, r, q, flag)
    except Exception:
        return float("nan")


# synthetic chain with a simple quoted-spread model: max(0.05, 8% of theo), rounded to 0.01 ticks
rows = []
for days in (3, 7, 30, 90, 365):
    t = days / 365
    for K in np.arange(60, 140.1, 2.5):
        for flag in ("c", "p"):                                         # both sides: single-contract evaluation uses ITM too
            sig = float(np.clip(0.25 + 0.4 * math.log(K / S) ** 2 - 0.1 * math.log(K / S), 0.08, 1.5))
            theo = v_price(flag, S, K, t, r, sig, q)
            if theo < 0.05:
                continue
            # quoted half-spread: at least 2.5 cents, 3% of value, capped at 0.50 (illustrative, not a market model)
            half = min(0.50, max(0.025, 0.03 * theo))
            bid, ask = max(0.01, round(theo - half, 2)), round(theo + half, 2)
            mid = (bid + ask) / 2
            iv_b, iv_a, iv_m = safe_iv(bid, K, t, flag), safe_iv(ask, K, t, flag), safe_iv(mid, K, t, flag)
            v1 = vega_1pt(K, t, sig)
            rows.append(dict(days=days, K=float(K), flag=flag, theo=theo, bid=bid, ask=ask, v1=v1,
                             iv_bid=iv_b, iv_ask=iv_a, iv_mid=iv_m, true=sig))

# E14: IV of mid vs average of bid/ask IVs
d = [(abs(x["iv_mid"] - (x["iv_bid"] + x["iv_ask"]) / 2) * 100, x) for x in rows
     if not any(math.isnan(x[k]) for k in ("iv_bid", "iv_ask", "iv_mid"))]
worst = max(d, key=lambda z: z[0])
out["E14_mid_iv_vs_avg_of_side_ivs"] = {
    "n": len(d), "median_diff_volpts": round(float(np.median([z[0] for z in d])), 4),
    "max_diff_volpts": round(worst[0], 3),
    "worst_case": {k: (round(worst[1][k], 4) if isinstance(worst[1][k], float) else worst[1][k]) for k in ("days", "K", "flag", "bid", "ask")}}

# E15: fixed vega threshold (v0.1 rule) vs IV interval width from the quoted spread (v0.2 rule)
passed_fixed = [x for x in rows if x["v1"] >= 0.01]
wide = [x for x in passed_fixed if (math.isnan(x["iv_bid"]) or (x["iv_ask"] - x["iv_bid"]) * 100 > 5)]
approx = [((x["ask"] - x["bid"]) / 2 / x["v1"], (x["iv_ask"] - x["iv_bid"]) * 100 / 2) for x in rows
          if not math.isnan(x["iv_bid"]) and not math.isnan(x["iv_ask"])]
out["E15_identifiability_rules"] = {
    "chain_size": len(rows),
    "pass_fixed_vega_rule": len(passed_fixed),
    "of_which_iv_interval_wider_than_5_volpts_or_bid_unsolvable": len(wide),
    "examples": [{"days": x["days"], "K": x["K"], "flag": x["flag"], "bid": x["bid"], "ask": x["ask"],
                  "vega_per_volpt": round(x["v1"], 4),
                  "iv_interval_volpts": (None if math.isnan(x["iv_bid"]) else round((x["iv_ask"] - x["iv_bid"]) * 100, 2))}
                 for x in sorted(wide, key=lambda z: z["days"])[:4]],
    "half_spread_over_vega_vs_exact_half_width_corr": round(float(np.corrcoef(np.array(approx).T)[0, 1]), 4)}

# E16: "current" values from a vendor-like model vs a local model with different carry inputs
DC, TODAY = ql.Actual365Fixed(), ql.Date(30, 9, 2026)
ql.Settings.instance().evaluationDate = TODAY


def am_put(K, days, sig, rr, qq, spot=S):
    proc = ql.BlackScholesMertonProcess(
        ql.QuoteHandle(ql.SimpleQuote(spot)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, qq, DC)),
        ql.YieldTermStructureHandle(ql.FlatForward(TODAY, rr, DC)),
        ql.BlackVolTermStructureHandle(ql.BlackConstantVol(TODAY, ql.NullCalendar(), sig, DC)))
    o = ql.VanillaOption(ql.PlainVanillaPayoff(ql.Option.Put, K), ql.AmericanExercise(TODAY, TODAY + days))
    o.setPricingEngine(ql.FdBlackScholesVanillaEngine(proc, 400, 400))
    return o.NPV(), o.delta()


K, days, sig = 100.0, 45, 0.30
p_vendor, d_vendor = am_put(K, days, sig, 0.040, 0.005)      # stand-in for an opaque vendor model
p_local, d_local = am_put(K, days, sig, 0.045, 0.0)          # local model, different declared carry
p_local_shock, _ = am_put(K, days, sig, 0.045, 0.0, spot=S * 0.95)
p_local_1d, _ = am_put(K, days - 1, sig, 0.045, 0.0)             # time-only scenario: one day forward
out["E16_mixed_model_scenario"] = {
    "contract": "American put K=100, 45 days, vol 30%, spot 100; shock = spot -5%",
    "vendor_model_price": round(p_vendor, 4), "local_model_price": round(p_local, 4),
    "model_gap_at_zero_shock_per_contract_usd": round((p_local - p_vendor) * 100, 2),
    "consistent_local_pnl_per_contract_usd": round((p_local_shock - p_local) * 100, 2),
    "mixed_pnl_local_shock_minus_vendor_base_usd": round((p_local_shock - p_vendor) * 100, 2),
    "delta_vendor": round(d_vendor, 4), "delta_local": round(d_local, 4),
    "time_only_1d_consistent_pnl_usd": round((p_local_1d - p_local) * 100, 2),
    "time_only_1d_mixed_pnl_usd": round((p_local_1d - p_vendor) * 100, 2)}
print(json.dumps(out, indent=2))
