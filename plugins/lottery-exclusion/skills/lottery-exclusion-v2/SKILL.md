---
name: lottery-exclusion-v2
description: Use when predicting or checking Chinese lottery numbers (双色球/大乐透) with the v2 exclusion strategy, or settling a past recommendation against the latest draw. Triggers on 用户说 "推荐/预测/选号/对奖/中奖没/开奖没/下一期" for 双色球 or 大乐透. Provides data fetch, structured number picking, payout-accurate 复式对账, and significance-tested backtests. Does NOT claim the strategy beats random — 100-round backtests show no significant edge. Pure hot/cold frequency belongs to chinese-lottery-predict; 连乘评分 belongs to lottery-ssq.
---

# lottery-exclusion-v2

v2 排除法：排除上期 → 热度+遗漏加权 → 候选池枚举 → 形态过滤；覆盖双色球 3500+ 期、大乐透 2900+ 期真实数据。

⚠️ **定位是结构化选号 + 精确对奖工具，不是中奖预测器**。100 轮随机基线回测显示，v2 保本率与随机无统计显著差异（z 均在 ±1.96 内），任何推荐都必须带免责声明，禁止说"提高中奖率"。

## CLI

```bash
cd ~/.agents/skills/lottery-exclusion-v2
python3 scripts/cli.py <game> <cmd> [选项]
# game ∈ {ssq, dlt}; cmd ∈ {fetch, predict, check, backtest, doctor}
```

| 场景 | 命令 |
|---|---|
| 推荐下期（自动 fetch，落盘 outputs/） | `python3 scripts/cli.py dlt predict` |
| 对奖（上次推荐 vs 之后新开奖期） | `python3 scripts/cli.py dlt check` |
| 更新历史 | `python3 scripts/cli.py ssq fetch` |
| 数据自检 | `python3 scripts/cli.py ssq doctor` |
| 回测（默认 100 轮随机基线） | `python3 scripts/cli.py dlt backtest` |

选项：`--front-k/--back-k` 复式大小；`--no-fetch` 离线；`--pool {low,high}` 大乐透新固定奖档；`--fuyun` 双色球福运奖；`--rounds N`。

## 三条铁律

1. **号码池/开奖个数/注数全部走 config.json + lotto_core，禁止写死、禁止用池大小反推选号个数**（大乐透 35 选 5，双色球 33 选 6）
2. **奖金走 prize.py 精确枚举，禁止 `return 5` 兜底**；复式注数不变量 C(nf,K)·C(nb,B) 必须守恒
3. **推荐默认先 fetch；网络失败降级本地数据必须显式标注 stale**；对奖/回测的奖表按期号切换（大乐透 26014 期前是旧 9 奖级）

## 推荐输出必含

- 前区 N 个 + 后区 M 个（默认 ssq 7+2=28 元 / dlt 7+2=42 元）
- 形态（和值/AC/跨度/奇偶）+ 排除源（上期号码）
- 注数与金额 + ⚠️ 免责声明 + outputs/ 落盘路径

## 失败转移

| 失败 | 不要做 | 改做 |
|---|---|---|
| 接口超时 | 反复重试 | 内置 3 次退避（2/5/8s）；失败后 predict/check 降级本地并标 stale |
| 形态无解 | 硬返回/用未来数据 | fallback 候选池 [12,14,16]；回测中跳过并计 n_skip；仍无则提示放宽 config |
| 数据格式异常 | 假装成功 | `doctor` 自检（范围/数量/重复期号/排序） |
| 规则不确定 | 自己拼 | 读 `docs/rules.md`（新旧奖表/8 亿档/福运奖） |
| 用户问"中奖没" | 让用户反复问 | `check` 一次回答：最新期已开/未开 + 逐期结算明细 |

## 详细

- 策略公式 / 回测结论 / 局限：`docs/strategy.md`
- 双彩种规则 / 三套奖表：`docs/rules.md`
- 踩坑清单：`docs/lessons_learned.md`
- 接口 / CSV schema：`docs/data_sources.md`
- 加载后 30 秒自检：`SELF_VALIDATE.md`
