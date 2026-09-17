# lottery-exclusion · ZCode 插件市场

双色球/大乐透 v2 排除法：结构化选号 + 精确复式对奖 + 显著性回测。纯 Python 标准库（**无第三方依赖**），自带 3500+/2900+ 期历史数据，离线可用，macOS / Windows 通用。

⚠️ 回测结论（100 轮随机基线，2026-09-18）：v2 与随机选号**无统计显著差异**（双色球 z=−0.83，大乐透 z=+0.67）。这是选号/对奖工具，不是中奖预测器。

## 在 ZCode 里安装（Mac 和 Windows 步骤相同）

1. 打开 **设置 → 插件管理（Plugin Management）→ 发现 / Discover**
2. 点 **`+`** 添加市场，选 **GitHub 仓库**，填：`shdowzh888/lottery-exclusion-v2`
3. 市场加载后，在卡片上点 **Get / 安装**（新插件默认启用）
4. 新开一个会话，输入 `/lottery dlt doctor` 验证

前置条件：系统装有 **Python ≥ 3.9**。
- macOS 一般自带 `python3`
- Windows 若 `python3` 不可用，用 `python`（Microsoft Store 版或 python.org 安装均可）；技能里的命令写的是 `python3`，agent 会自动改用可用的解释器

> 本仓库同时是一个合法的**本地市场**：也可以在 `+` 里选"本地目录"直接指向本仓库根目录（不经过 GitHub）。

## 用法

```
/lottery <ssq|dlt> <predict|check|backtest|fetch|doctor> [选项]
```

| 想做什么 | 命令 |
|---|---|
| 推荐下期（自动拉最新开奖） | `/lottery ssq predict` |
| 上次推荐对奖 | `/lottery ssq check` |
| 100 轮随机基线回测 | `/lottery dlt backtest` |
| 更新历史 / 数据自检 | `/lottery dlt fetch`、`/lottery dlt doctor` |

选项：`--front-k/--back-k` 复式大小、`--no-fetch` 离线、`--pool high` 大乐透 8 亿奖池档（6666/380/200/18/7）、`--fuyun` 双色球福运奖、`--rounds N`。

大乐透 26014 期起奖级有新旧之分、奖池 8 亿上下固定奖不同，对最新期对奖时一般用 `--pool high`；浮动奖与派奖活动以官方公告为准。

## 仓库结构

```
.
├── marketplace.json                    # 市场清单（ZCode 读取，插件源必须 github+path）
└── plugins/lottery-exclusion/
    ├── .zcode-plugin/plugin.json       # 插件清单
    ├── commands/lottery.md             # /lottery 斜杠命令
    └── skills/lottery-exclusion-v2/    # 技能本体
        ├── SKILL.md / README.md / SELF_VALIDATE.md
        ├── config.json                 # 彩种参数/三套奖表/阈值（唯一配置源）
        ├── scripts/                    # cli / lotto_core / prize / backtest ...
        ├── data/                       # 历史 CSV（自带，首次无需联网）
        ├── outputs/                    # 最近推荐（check 的输入）
        ├── backtests/                  # 回测报告
        └── docs/                       # 策略/规则/踩坑/数据源
```

## 数据目录

插件更新会替换程序文件，但历史数据不丢：首次运行自动把包内种子 CSV 复制到用户目录，之后所有 fetch/推荐/回测都读写该处：

- macOS/Linux：`~/.lottery-exclusion-v2/`
- Windows：`C:\Users\<用户>\.lottery-exclusion-v2\`
- 可用环境变量 `LOTTERY_DATA_DIR` 覆盖

## 更新发布（开发者）

技能本体就在仓库 `plugins/lottery-exclusion/skills/lottery-exclusion-v2/` 内，直接在这份上改（CLI 路径相对自身，可独立运行）。发布三步：

```bash
# 1. 三处版本号一起 bump（技能 _meta.json、plugin.json、marketplace.json）
# 2. 提交推送
git add -A && git commit -m "..." && git push
# 3. 各设备在插件管理 Discover 刷新市场 → 更新插件（客户端按 version 识别更新）
```

## 跨平台说明

- 路径全部走 `pathlib`，CSV 用 utf-8-sig 且写入 `newline=""`，无硬编码分隔符
- Windows 管道默认 GBK，脚本入口已强制 stdout/stderr 为 UTF-8，emoji 输出不会崩
- 不使用任何 Unix 专属模块（fcntl/signal/pty）
