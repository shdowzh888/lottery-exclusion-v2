---
description: 双色球/大乐透 推荐、对奖、回测（v2 排除法）
argument-hint: "[ssq|dlt] [predict|check|backtest|fetch|doctor] [--pool low|high] [--fuyun] [--rounds N] [--no-fetch]"
skills: lottery-exclusion-v2
---

使用 lottery-exclusion-v2 技能处理彩票请求。参数：

$ARGUMENTS

执行规则：
1. 先加载 skills/lottery-exclusion-v2/SKILL.md，按其中三条铁律与失败转移操作。
2. 在插件技能目录下运行 CLI（工作目录为本技能根目录）：
   - macOS/Linux：`python3 scripts/cli.py <game> <cmd> [选项]`
   - Windows：`python scripts/cli.py <game> <cmd> [选项]`（python3 不存在时）
   （game ∈ ssq/dlt；cmd ∈ fetch/predict/check/backtest/doctor）。
3. 用户只说"推荐/下期" → predict（默认自动 fetch）；说"中奖没/对奖/开奖没" → check；
   要验证策略 → backtest；怀疑数据 → doctor。
4. 任何推荐输出必须保留 CLI 打印的免责声明；禁止宣称策略能提高中奖率
   （100 轮回测：与随机无显著差异）。
5. 大乐透对最新期对奖时提醒用户 8 亿奖池档（--pool high）与派奖活动以官方公告为准。
