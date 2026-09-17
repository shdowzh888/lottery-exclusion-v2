# lottery-exclusion-v2

基于历史数据的 v2 排除法选号与对奖工具，覆盖**双色球**和**大乐透**。

⚠️ **这不是中奖预测器**。2026-09-18 的 100 轮随机基线回测表明，v2 保本率与随机选号**无统计显著差异**（双色球 z=−0.83，大乐透 z=+0.67）。工具的价值是结构化选号、精确复式成本/对奖、可复现的诚实回测。

## 快速开始

```bash
cd ~/.agents/skills/lottery-exclusion-v2

python3 scripts/cli.py ssq fetch        # 更新历史
python3 scripts/cli.py ssq predict      # 推荐（自动 fetch，落盘 outputs/）
python3 scripts/cli.py ssq check        # 对奖（推荐 vs 之后新开奖期）
python3 scripts/cli.py ssq doctor       # 数据自检
python3 scripts/cli.py ssq backtest     # S1/S2/S3 回测（100 轮随机基线）
```

复式大小：`predict --front-k 8 --back-k 1`；离线：`--no-fetch`；
大乐透 8 亿奖池档：`check --pool high`；双色球福运奖：`check --fuyun`。

## 推荐输出示例

```
🎯 大乐透 推荐 (基于 26106 期):
  前区(7): 03 22 29 30 32 33 35
  后区(2): 07 10
  投入: 21注 × 2元 = 42元
  形态: 和值184 AC11 跨度32 奇偶4:3
  排除源: 前区[14, 17, 21, 25, 28] 后区[4, 6]
  📁 已保存: outputs/dlt_latest.json (check 对奖用)
```

## 回测结果（100 轮随机，2026-09-18）

| 彩种/复式 | v2 保本率 | 随机均值 (95% 区间) | z | 结论 |
|---|---|---|---|---|
| 双色球 7+2（28元） | 12.85% | 13.39%（12.21–14.81%） | −0.83 | 不显著 |
| 大乐透 7+2（42元） | 31.39% | 30.76%（28.84–32.59%） | +0.67 | 不显著 |

大乐透最新 606 期分段 +3.30pp（z=1.98）仅处显著边界，样本有限，列为观察点而非证据。
详见 `docs/strategy.md` 与 `backtests/` 下报告。v1 的旧回测数字因复式奖金枚举 bug 已全部作废。

## 文件结构

```
lottery-exclusion-v2/
├── SKILL.md            # agent 主入口
├── README.md / SELF_VALIDATE.md
├── config.json         # 彩种参数/三套奖表/形态阈值/回测参数（唯一配置源）
├── scripts/
│   ├── cli.py          # argparse 入口: fetch/predict/check/backtest/doctor
│   ├── lotto_core.py   # 公共核心: 读取/评分/选号（predict/backtest 唯一来源）
│   ├── prize.py        # 复式奖金精确枚举 + 注数不变量断言
│   ├── shape.py        # 形态特征（阈值按彩种+n）
│   ├── fetch_data.py   # 官方接口
│   ├── update_history.py  # CSV 全量合并重写 + doctor
│   ├── predict.py / backtest.py
├── data/               # 统一 5 列 CSV
├── outputs/            # 最近推荐（对奖输入）
├── backtests/          # 回测 json+md
└── docs/               # strategy / rules / lessons_learned / data_sources
```

## 免责声明

彩票是独立随机事件，本工具仅做历史统计与结构化参考，**不构成中奖保证**。理性购彩，量力而行。
