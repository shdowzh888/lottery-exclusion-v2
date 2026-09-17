# Self-Validate Check List

> agent 加载本 skill 后按此顺序快速验证关键能力。全部离线可跑, 约 30 秒。

## 必读（按顺序）

1. `SKILL.md` — 主入口（CLI 列表 + 铁律 + 失败转移）
2. `config.json` — 彩种参数 / 三套奖表 / 形态阈值 / 回测参数
3. `docs/rules.md` — 双彩种规则对照（号码池/开奖个数/奖表分档）
4. `docs/lessons_learned.md` — 踩坑清单（防重蹈覆辙）

## 自检（30 秒）

```bash
cd ~/.agents/skills/lottery-exclusion-v2

# 1. 数据自检（范围/数量/重复期号/排序/期号长度）
python3 scripts/cli.py ssq doctor
python3 scripts/cli.py dlt doctor
# 期望: "✅ 全部合法"

# 2. 奖金引擎核心断言（注数不变量 + 新旧奖表 + 福运奖）
python3 scripts/prize.py
# 期望: ssq/dlt 枚举注数 14/21, 无 AssertionError

# 3. 双彩种推荐可生成且落盘（离线模式, 不联网）
python3 scripts/cli.py ssq predict --no-fetch | grep -E "投入|形态"
python3 scripts/cli.py dlt predict --no-fetch | grep -E "投入|形态"
# 期望: 双色球 14 注/28元, 大乐透 21 注/42元; outputs/{game}_latest.json 已生成

# 4. 对奖闭环（推荐基于最新期时应为"尚未开奖"）
python3 scripts/cli.py ssq check --no-fetch | grep -E "尚未开奖|合计奖金"
```

## 关键不变量（改代码后必须复核）

- **复式注数守恒**: 任意复式与任意命中结构, `combo_detail().total_notes == C(nf,K)*C(nb,B)`
  （ssq 7+2=14, 8+1=28; dlt 7+2=21, 8+2=56）。prize.py 内置断言。
- **头奖不漏算**: ssq 7+2 中 6+1 必须包含 1 注一等（500 万）; dlt 中 5+2 必须包含 1 注一等。
- **predict 与 backtest 同源**: 评分/选号只允许走 `lotto_core.py`, 两份代码不得各写一份。
- **回测无未来数据**: 形态无解的期只计数跳过 (`n_skip`), 禁止回退到任何数据。
- **回测显著性**: 多轮随机 (默认 100), v2 必须与随机分布的 95% 区间和 z 值一起报告;
  落在区间内即"不显著", 不得宣称策略有效。

## 失败信号

| 现象 | 排查方向 |
|---|---|
| doctor 报 issues | 看 docs/rules.md 号码范围/期号格式; 重跑 fetch |
| predict 形态无解 | 放宽 config shape_filter.{game}; 扩 candidate_fallback_sizes |
| 大乐透号码 ≤33 | config 被改坏——games.dlt.front_pool 必须 35 |
| 注数 ≠ 14/21 | prize 枚举重写——对照"关键不变量" |
| 对奖金额异常 | 检查奖表版本: 旧期(<26014)/新低档/新高档(--pool high); 福运奖 --fuyun |
| 回测 n_skip 很多 | 形态阈值过严, 看 config shape_filter |
| 联网失败 | fetch 自动重试 3 次 (2/5/8s); predict/check 会降级本地并标 stale |

## 命令快查

```bash
python3 scripts/cli.py {ssq|dlt} {fetch|predict|check|backtest|doctor}
  predict/backtest 可选 --front-k N --back-k M
  check/backtest   可选 --pool {low,high}   # 大乐透新固定奖档
  check            可选 --fuyun             # 计入双色球福运奖
  backtest         可选 --rounds N          # 随机基线轮数(默认100)
  predict/check/backtest 加 --no-fetch      # 纯离线
```

## 版本

- v2.0.1 (2026-09-18) — 可变数据重定向到 `~/.lottery-exclusion-v2`（插件更新不丢）；GitHub 市场发布
- v2.0.0 (2026-09-17) — 修复复式奖金枚举 P0、predict/backtest 同源、对奖闭环、
  三套奖表、多轮随机显著性、统一 CSV schema。旧版回测数字因奖金 bug 全部作废重算
- v1.0.0 (2026-09-17) — 初版
