# 期权方案对比实验室（2026-09-30）

用途：为《Pi 期权 package 两套方案全景对比》中有分歧的事实提供可复现证据。这些是**库行为、客户端与数值实验**，不是任何一方 package 的运行验收；没有连接 IBKR。

## 环境

- Linux x86_64（Modal 沙箱），CPython 3.12.12，QuantLib 1.43，vollib 1.0.11，numpy 2.5.3，scipy 1.18.1
- 官方 TWS API：`twsapi_macunix.1050.02.zip`（interactivebrokers.github.io，2026-09-29 发布的 Stable 版）
- ib_async 2.1.0 wheel（PyPI）

## 复现

```bash
bash client_facts.sh /tmp/ibclient-facts        # S1–S3，输出见 client_facts.txt
<装有 QuantLib 与 vollib 的 python> iv_rules.py   # E14–E16，输出见 iv_rules.json
```

## 结果

| 编号 | 问题 | 结果 |
| --- | --- | --- |
| S1 | 官方 Python 客户端 `ibapi` 的许可、依赖与协议 | 10.50.2；**许可为 GPL-3.0-or-later**（LICENSE 文件为 GPLv3）；`install_requires=["protobuf==5.29.5"]`（精确锁定）；`MAX_CLIENT_VER=226`；能解析 `settlementMethod`（走 protobuf 路径）；基于线程的 `EReader`，没有 asyncio 接口；zip 可直接下载（HTTP 200） |
| S2 | PyPI 上名为 `ibapi` 的包 | 只有 9.81.1 和 9.81.1.post1（2020 年），**不是**当前的官方客户端；直接 `pip install ibapi` 会装到过时版本 |
| S3 | ib_async 2.1.0 | BSD 许可；`MaxClientVersion=178`（官方为 226）；**不解析 `settlementMethod`**，也不含 protobuf；默认分支最后一次提交在 2025-12-06，PyPI 最后一次上传在 2025-12-08 |
| E14 | "中间价对应的 IV"与"买价 IV 和卖价 IV 的平均"有多大差别（合成链 142 个可解合约，报价半价差 = max(2.5 美分, 3% 价值)，上限 0.50） | 中位数差 0.003 个波动率点；最大 2.24 点（30 天、K=110 的实值看跌，报价 9.70/10.29） |
| E15 | 固定阈值规则（每个波动率点价格变化 ≥ 1 美分）与"价差 ÷ vega"规则的差别（246 个合约，含实值与虚值） | 164 个合约通过固定阈值，其中 **40 个**的 IV 区间（按买价、卖价分别反解）宽于 5 个波动率点，或买价低于可解下限。例如 3 天到期、K=97.5 的看涨，报价 2.60/2.76，vega 为 0.019/点，IV 区间宽 8.6 点。"半价差 ÷ vega"与精确半宽的相关系数为 0.996 |
| E16 | 情景基准混用两个模型的误差（美式看跌 K=100，45 天，30% 波动率；"供应商模型"用 r=4.0%、q=0.5%，本地模型用 r=4.5%、q=0） | 零冲击时两个模型每张合约相差 −4.94 美元。标的 −5% 的情景：同一模型算出 +281.27 美元，混用两个模型得 +276.33 美元。仅时间推进 1 天的情景：同一模型为 −4.16 美元，混用为 −9.10 美元（误差超过 100%） |

## 局限

E14–E16 使用合成的报价模型，只用于说明方法差异的方向与量级；S1–S3 只核对静态制品，没有验证与真实 TWS/Gateway 的协议兼容性。
