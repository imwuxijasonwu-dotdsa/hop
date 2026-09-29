# v2.1 审计实验室（2026-09-29）

用途：核实 A v2.1 新写入的外部事实，并为《Pi Quant v2.1 一致性审计》中的细节建议提供可复现证据。这些是**库行为与统计实验**，不是任何一方 package 的运行验收。

## 环境

- Linux x86_64（Modal 沙箱，overlay 文件系统），uv 0.9.28，CPython 3.12.12
- `pyqlib==0.9.7` 环境沿用 `../2026-09-28_comparison_lab/`（cvxpy 1.9.3、numpy 2.5.3、scipy 1.18.1）
- `ib_async==2.1.0` 安装在独立 venv 中；**未连接真实 TWS／Gateway**，E7 全部使用桩对象

## 复现

```bash
python3 pypi_wheels.py                                                    # 求解器 wheel 覆盖（查询 PyPI 元数据）
<ib_async 2.1.0 的 python> ib_async_offline.py                            # E7a–c
<pyqlib 0.9.7 的 python> stats_checks.py                                  # E10a–c
bash solver_env_checks.sh <pyqlib 0.9.7 的 python> ../2026-09-28_comparison_lab/constraints.txt /tmp/e9   # E8、E9
```

## 结果

| 编号 | 问题 | 结果 |
| --- | --- | --- |
| E7a | `IB.connectAsync` 在启动时会发出哪些请求 | 默认：positions、open orders、completed orders、account updates、account updates multi、executions。`readonly=True` 且 `fetchFields=StartupFetchNONE` 时**仍会发出 `reqPositions`**（`ib.py:2056` 无条件执行；`StartupFetch.POSITIONS` 标志未被检查） |
| E7b | `reqHistoricalDataAsync(timeout=0.2)` 在无响应时的行为 | 返回长度为 0 的 `BarDataList`，不抛异常，并已发出 `cancelHistoricalData(reqId)` |
| E7c | 收到 1102（连接恢复）时 | 默认会触发 `reqAccountSummaryAsync`；执行 `ib.errorEvent -= ib._onError` 后不再触发 |
| E8 | CVXPY 1.9.3 的求解器与求解证据 | `installed_solvers()` = CLARABEL、SCS、SCIPY、HIGHS、OSQP（无 ECOS）；`solver_stats` 给出 solver_name（OSQP）、num_iters、solve_time；显式指定 ECOS 时抛 `SolverError: The solver ECOS is not installed.` |
| E9 | uv 缓存已热、同一文件系统下再建一个同锁 runtime | 两次构建分别为 4.4 s、1.7 s；单个环境逻辑大小 973 MB；按硬链接去重后，每个环境的物理增量约 2.9 MB（numpy 核心 .so 链接数为 4） |
| E10a | k 个零效应候选，在评价期按点估计选最优，朴素单侧 5% 下界 > 0 即判"支持" | ρ=0：k=3 为 14.2%，k=5 为 22.6%，k=10 为 40.1%；ρ=0.5：k=5 为 16.6%；ρ=0.8：k=5 为 11.7%；Bonferroni 校正后全部 ≤ 5% |
| E10b | 5 日重叠收益均值的 90% 区间覆盖率（T=252，20 000 次） | 朴素 iid：53.1%；Newey–West（lag 4）：81.3% |
| E10c | 小样本 Agent 评测能多精确地估计误判率（Clopper–Pearson 95%） | 1/20：0.13%–24.9%；2/50：0.49%–13.7%；10/200：2.4%–9.0%；50/1000：3.7%–6.5% |
| — | 求解器 wheel 覆盖（`pypi_wheels.txt`） | ECOS 2.0.14 在 macOS 上只有 x86_64 wheel，**PyPI 历史上没有任何版本提供 macOS arm64 或 universal2 wheel**；Clarabel 0.11.1、OSQP 1.1.3、CVXPY 1.9.3 都有 macOS arm64 与 x86_64 wheel；SCS 3.3.1 的 cp312 在 macOS 上只有 arm64 wheel（有 cp312 macOS x86_64 wheel 的最新版本为 3.2.8） |

## 局限

E7 是桩测试，只证明 ib_async 客户端会**发出**哪些请求，不代表 Gateway 的真实响应；E9 只在 Linux overlay 文件系统上测量（macOS APFS 上 uv 默认用 clone，跨文件系统时会回退为复制）；E10 使用正态或 MA 合成序列，仅用于说明区间方法与选择效应的量级。
