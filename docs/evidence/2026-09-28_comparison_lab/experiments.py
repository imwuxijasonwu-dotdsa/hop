"""Comparison lab: verify library behaviours both designs depend on (pyqlib 0.9.7)."""
import importlib.metadata as md
import io, json, logging, os, subprocess, sys, time, warnings
from pathlib import Path

import numpy as np
import pandas as pd

LAB = Path(sys.argv[1]).resolve()
DUMP_BIN = sys.argv[2]
LAB.mkdir(parents=True, exist_ok=True)
res = {"python": sys.version.split()[0], "versions": {}}
for p in ["pyqlib", "numpy", "pandas", "mlflow", "cvxpy", "lightgbm"]:
    res["versions"][p] = md.version(p)
try:
    res["versions"]["ecos"] = md.version("ecos")
except md.PackageNotFoundError:
    res["versions"]["ecos"] = None

# --- synthetic US-like daily data -> Qlib provider via upstream dump_bin.py
dates = pd.bdate_range("2024-01-02", periods=80)
rng = np.random.default_rng(7)
csv_dir, prov = LAB / "csv", LAB / "provider"
csv_dir.mkdir(exist_ok=True)
for sym, mu in [("AAA", 0.001), ("BBB", 0.0), ("SPY", 0.0005)]:
    close = 100 * np.exp(np.cumsum(rng.normal(mu, 0.02, len(dates))))
    df = pd.DataFrame({"date": dates.strftime("%Y-%m-%d"), "symbol": sym, "open": close, "high": close * 1.01,
                       "low": close * 0.99, "close": close, "volume": 1e6})
    df["change"] = df["close"].pct_change().fillna(0.0)
    df.to_csv(csv_dir / f"{sym}.csv", index=False)
t = time.time()
cp = subprocess.run([sys.executable, DUMP_BIN, "dump_all", "--data_path", str(csv_dir), "--qlib_dir", str(prov),
                     "--include_fields", "open,high,low,close,volume,change", "--date_field_name", "date",
                     "--symbol_field_name", "symbol"], capture_output=True, text=True)
res["E0_dump_bin"] = {"exit": cp.returncode, "seconds": round(time.time() - t, 2),
                      "calendar_days": len((prov / "calendars" / "day.txt").read_text().split()) if cp.returncode == 0 else None,
                      "stderr_tail": cp.stderr[-300:] if cp.returncode else ""}

# --- E2: Qlib init + MLflow file-store Recorder (no MLFLOW_ALLOW_FILE_STORE set)
os.environ.pop("MLFLOW_ALLOW_FILE_STORE", None)
t = time.time()
import qlib
from qlib.constant import REG_US
res["import_qlib_seconds"] = round(time.time() - t, 2)
qlib.init(provider_uri=str(prov), region=REG_US,
          exp_manager={"class": "MLflowExpManager", "module_path": "qlib.workflow.expm",
                       "kwargs": {"uri": "file:" + str(LAB / "mlruns"), "default_exp_name": "lab"}})
from qlib.workflow import R
try:
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        with R.start(experiment_name="lab"):
            R.log_metrics(x=1.0)
            R.save_objects(**{"obj.pkl": {"a": 1}})
            rid = R.get_recorder().id
        loaded = R.get_recorder(recorder_id=rid, experiment_name="lab").load_object("obj.pkl")
    res["E2_mlflow_file_store"] = {"ok": loaded == {"a": 1},
                                   "warnings": sorted({str(x.category.__name__) + ": " + str(x.message)[:90] for x in w})[:3]}
except Exception as e:  # noqa: BLE001
    res["E2_mlflow_file_store"] = {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}

# --- E3: WeightStrategyBase default risk_degree scales target weights (buy-and-hold baseline pitfall)
from qlib.backtest import backtest
from qlib.contrib.strategy.signal_strategy import WeightStrategyBase


class HoldAAA(WeightStrategyBase):
    def generate_target_weight_position(self, score, current, trade_start_time, trade_end_time):
        return {"AAA": 1.0}


sig = pd.Series(1.0, index=pd.MultiIndex.from_product([dates, ["AAA", "BBB"]], names=["datetime", "instrument"]))
executor = {"class": "SimulatorExecutor", "module_path": "qlib.backtest.executor",
            "kwargs": {"time_per_step": "day", "generate_portfolio_metrics": True}}
exk = {"freq": "day", "deal_price": "close", "open_cost": 0.0, "close_cost": 0.0, "min_cost": 0.0,
       "limit_threshold": None, "codes": ["AAA", "BBB"]}
e3 = {}
for label, kw in [("default", {}), ("risk_degree_1.0", {"risk_degree": 1.0})]:
    pm, _ = backtest(start_time=dates[5], end_time=dates[-3], strategy=HoldAAA(signal=sig, **kw), executor=executor,
                     benchmark="SPY", account=100000, exchange_kwargs=exk)
    rep = pm["1day"][0]
    e3[label] = round(float((rep["value"] / rep["account"]).iloc[3]), 4)
res["E3_invested_fraction_buy_and_hold"] = e3

# --- E4: max drawdown ignores the initial capital A0 when the first period loses
from qlib.contrib.evaluate import risk_analysis
r = pd.Series([-0.10, 0.0, 0.02], index=pd.bdate_range("2024-01-02", periods=3))
nav = np.concatenate([[1.0], (1 + r).cumprod().values])
res["E4_max_drawdown"] = {
    "returns": r.tolist(),
    "qlib_product_mode": round(float(risk_analysis(r, N=252, mode="product").loc["max_drawdown"].iloc[0]), 4),
    "qlib_sum_mode": round(float(risk_analysis(r, freq="day").loc["max_drawdown"].iloc[0]), 4),
    "nav_including_A0": round(float((nav / np.maximum.accumulate(nav) - 1).min()), 4),
}

# --- E5: EnhancedIndexingOptimizer hard-codes cp.ECOS; CVXPY>=1.6 no longer installs ECOS by default
from qlib.contrib.strategy.optimizer import EnhancedIndexingOptimizer
log_buf = io.StringIO()
handler = logging.StreamHandler(log_buf)
for name in list(logging.root.manager.loggerDict):
    if "enhanced_indexing" in name or name.endswith("optimizer"):
        logging.getLogger(name).addHandler(handler)
n = 4
w0 = np.zeros(n)
wopt = EnhancedIndexingOptimizer(delta=0.2)(r=np.array([0.02, 0.01, 0.0, -0.01]), F=np.ones((n, 1)),
                                           cov_b=np.array([[0.0004]]), var_u=np.full(n, 1e-4), w0=w0,
                                           wb=np.full(n, 0.25))
res["E5_enhanced_indexing"] = {"ecos_installed": res["versions"]["ecos"] is not None,
                               "returned_weights": np.round(np.asarray(wopt, dtype=float), 4).tolist(),
                               "returned_w0_unchanged": bool(np.allclose(wopt, w0)),
                               "log_tail": log_buf.getvalue().strip().splitlines()[-2:]}

# --- E6: Alpha158/Alpha360 default label processor CSZScoreNorm on a single instrument
from qlib.data.dataset.processor import CSZScoreNorm
e6 = {}
for names in (["AAA"], ["AAA", "BBB"]):
    idx = pd.MultiIndex.from_product([pd.bdate_range("2024-01-02", periods=5), names], names=["datetime", "instrument"])
    df = pd.DataFrame({("feature", "f1"): np.arange(len(idx), dtype=float),
                       ("label", "LABEL0"): rng.normal(0, 0.02, len(idx))}, index=idx)
    out = CSZScoreNorm(fields_group="label")(df.copy())
    lab = out[("label", "LABEL0")]
    e6[f"{len(names)}_instrument"] = {"rows": len(lab), "nan_labels": int(lab.isna().sum()),
                                      "distinct_values": int(lab.round(6).nunique())}
res["E6_cszscore_label"] = e6

out_path = LAB / f"results-py{sys.version_info.major}{sys.version_info.minor}.json"
out_path.write_text(json.dumps(res, indent=2, ensure_ascii=False))
print(json.dumps(res, indent=2, ensure_ascii=False))
