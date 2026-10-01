# 期权方案 v0.2 实验室（2026-10-01）

用途：验证 Claude v0.2 新写入的两项设计——官方 IBKR 客户端的可复现安装路线，以及情景引擎的"校准到标记价"规则——并量化典型情景网格的计算量。这些是**库行为与数值实验**，不是 package 的运行验收；没有连接 IBKR。

## 环境

Linux x86_64（Modal 沙箱），uv 0.9.28，CPython 3.12.12，QuantLib 1.43，scipy 1.18.1；官方 TWS API Stable 1050（`twsapi_macunix.1050.02.zip`）。

## 复现

```bash
bash install_check.sh /tmp/opt-install-check     # S4，输出见 install_check.txt
<装有 QuantLib 与 scipy 的 python> scenario_check.py > scenario_check.json   # E17
```

## 结果

| 编号 | 问题 | 结果 |
| --- | --- | --- |
| S4a | 能否把官方 zip 直接写成 URL 依赖（`ibapi @ <zip>#subdirectory=IBJts/source/pythonclient`） | **不能**：uv 解压失败，报错 "Bad compressed size (got 00000000, expected 00000002) for file: META-INF/"。zip 中的 `META-INF/` 条目大小字段不一致；Python `zipfile.testzip()` 与系统 unzip 都能容忍 |
| S4b | 备选路线：下载 → 校验 sha256 → 用 Python `zipfile` 解压 `IBJts/source/pythonclient` → `uv build --wheel` → `uv pip compile --find-links --generate-hashes` → `uv pip sync --require-hashes` | **可行**：构建出 `ibapi-10.50.2-py3-none-any.whl`；锁定 5 个包（ibapi 10.50.2、protobuf 5.29.5、QuantLib 1.43、numpy 2.5.3、scipy 1.18.1）；`uv pip check` 通过；`ibapi` 的元数据许可为 GPL-3.0-or-later；官方附带的 `TWSSyncWrapper` 自带 `place_order_sync`、`cancel_order_sync` |
| E17a | 情景基准规则：美式看跌 K=100、45 天、标的 100；"标记价"由供应商式模型（r=4.0%、q=0.5%、波动率 30%）给出，本地模型声明 r=4.5%、q=0 | 校准后的本地波动率为 30.355%，校准后基准与标记价相差 3×10⁻⁶ 美元/张。每张合约的情景盈亏：时间推进 1 天，校准法 −4.21，供应商参照 −4.26，未校准的本地法 −4.16，混用两个模型 −9.10；标的 −5%，校准法 280.64，参照 282.25，混用 276.33；波动率 +5 点，校准法 69.56，参照 69.63，混用 64.62 |
| E17b | 标记价等于内在价值的腿（美式看跌 K=130、30 天，标记价 30.00） | 校准拒绝，状态为 `not_identifiable(mark_at_or_below_intrinsic)`，不静默定价 |
| E17c | 两腿牛市看跌价差（卖 100P、买 95P，45 天）的情景网格：标的 {−10, −5, 0, 5, 10}% × 波动率 {−5, 0, +5} 点 × 时间 {0, 14, 28} 天，共 90 次美式定价 | 校准两条腿约 129 ms（FD）；网格 FD 400×400 约 683 ms（7.6 ms/次），CRR 801 步约 310 ms（3.4 ms/次） |

## 局限

S4 只在 Linux x86_64 上验证，macOS arm64 需在 OP0 重做；E17 使用合成的"供应商模型"作为标记价来源，真实标记价含买卖价差与报价噪声；计时为单线程。
