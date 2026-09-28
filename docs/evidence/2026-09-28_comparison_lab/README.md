# 两方案对比实验室（2026-09-28）

用途：为《Pi Quant 两套方案全景对比》中有分歧的库行为提供可复现证据。这些是**库行为实验**，不是任何一方 package 的运行验收。

## 环境

- Linux x86_64（Modal 沙箱），uv 0.9.28
- CPython 3.11.14 与 3.12.12（uv 管理）
- `pyqlib==0.9.7`，约束文件 `constraints.txt`（取自 Qlib 主干 CI：`mlflow<3.13`、`filelock>=3.16.0,<3.30`、`plotly<7`）
- 解析结果（两个版本一致，除 numpy/scipy 小版本外）：numpy 2.4.6／2.5.3、pandas 2.3.3、mlflow 3.12.0、cvxpy 1.9.3、lightgbm 4.7.0、gym 0.26.2；**未安装** ecos、plotly；`uv pip check` 通过（191／190 个包）；单个环境 `du` 约 0.97 GB
- 数据：合成的美股式日线（AAA、BBB、SPY，80 个交易日），经上游 `scripts/dump_bin.py`（Qlib 主干 `be72549`）写成 Qlib provider

## 复现

```bash
uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python "pyqlib==0.9.7" -c constraints.txt
.venv/bin/python experiments.py ./run <qlib仓库>/scripts/dump_bin.py   # E0、E2–E6，输出 results-py3XX.json
bash relocate.sh /tmp/lab-reloc                                        # E1、E5b，输出见 relocate_output.txt
```

## 结果

| 编号 | 问题 | 结果（3.11 与 3.12 相同） |
| --- | --- | --- |
| E0 | 上游 `dump_bin.py` 能否配合 pyqlib 0.9.7 写入 provider | 成功，80 个交易日 |
| E1 | venv 在临时路径构建后改名（旧路径不存在） | `python -m` 可用，`sys.prefix` 指向新路径；控制台脚本 `qrun` 失败（exit 127，shebang 指向旧路径）；`uv venv --relocatable` 构建的环境改名后 `qrun` 正常 |
| E2 | MLflow 文件存储（mlflow 3.12.0，未设 `MLFLOW_ALLOW_FILE_STORE`） | Recorder 读写成功；出现 `FutureWarning`：文件系统跟踪后端自 2026 年 2 月弃用 |
| E3 | `WeightStrategyBase` 默认 `risk_degree` 下的"全仓持有 AAA" | 实际投入 94.96%；显式 `risk_degree=1.0` 时为 100% |
| E4 | 收益序列 [−10%, 0, +2%] 的最大回撤 | Qlib `risk_analysis` 的 product 与 sum 模式均为 0；含初始资产 A₀ 的净值口径为 −10% |
| E5 | `EnhancedIndexingOptimizer`（期初 w0 全零）在 cvxpy 1.9.3、无 ecos 时 | 日志 "trial 1 failed The solver ECOS is not installed" 与 "optimization failed, will return current holding weight"，返回全零权重（即全现金），不抛异常 |
| E5b | 同上，但显式安装 ecos 2.0.14 | 正常求解，权重 [0.26, 0.26, 0.24, 0.24] |
| E6 | `CSZScoreNorm(fields_group="label")`（Alpha158／Alpha360 默认学习处理器） | 单标的：5／5 个标签变为 NaN；两标的：0 个 NaN |
| — | 新进程导入耗时（热文件缓存） | 裸解释器 0.02 s；`import numpy, pandas` 0.33 s；`import qlib` 约 0.5 s；`import qlib.backtest` 1.33 s |

## 局限

只在 Linux x86_64 上测试，未覆盖 macOS；未连接 IBKR；未运行 Pi 本体；数据为合成数据。E5 只针对 `EnhancedIndexingOptimizer` 的求解器选择，不代表 Qlib 其他优化路径。
