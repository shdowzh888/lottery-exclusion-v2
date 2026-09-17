"""v2 回测: S1 命中率 / S2 v2 vs 多轮随机 / S3 分时段稳定性。

纪律:
- 选号/评分与线上 predict 共用 lotto_core, 不另写一份
- 形态无解的期跳过并计数, 禁止用未来数据回退
- 随机基线多轮模拟, 报均值±std 与 95% 区间, 不做单样本对比
- 大乐透奖金按期号自动切新旧奖表 (默认新表 low 档; high 档/派奖活动需显式指定)
"""

from __future__ import annotations
import json
import random
import sys
from datetime import datetime
from pathlib import Path

import lotto_core as core
import prize as prize_mod


def backtest(game: str, front_k: int | None = None, back_k: int | None = None,
             train_window: int | None = None, random_rounds: int | None = None,
             pool_mode: str = "low", verbose: bool = True):
    cfg = core.load_config()
    bt = cfg["backtest"]
    target = bt["default_target_bet"][game]
    front_k = front_k or target["front_k"]
    back_k = back_k or target["back_k"]
    train_window = train_window or bt["train_window"]
    random_rounds = random_rounds or bt["random_rounds"]
    seg_count = bt["seg_count"]
    cost = core.bet_info(game, front_k, back_k)["cost"]
    g = core.game_config(game)

    history = core.read_history(game)
    n_total = len(history)
    if n_total < train_window + 50:
        raise RuntimeError(f"历史数据不足: {n_total} 期, 至少需要 {train_window + 50} 期")

    rng = random.Random(bt["random_seed"])
    front_pool_n = g["front_pool"]
    back_pool_n = g["back_pool"]

    test_idx = list(range(train_window, n_total))
    seg_size = len(test_idx) // seg_count
    seg_of = lambda t: min((t - train_window) // seg_size, seg_count - 1)

    n_run = n_skip = 0
    front_hit_total = 0
    back1_hit = back_all_hit = 0
    v2_win = v2_profit = v2_exp_sum = 0
    seg_v2_win = [0] * seg_count
    seg_n = [0] * seg_count
    # 随机基线: 每轮全局/分段 保本计数与期望和
    rnd_win_rounds = [0] * random_rounds
    rnd_exp_rounds = [0.0] * random_rounds
    seg_rnd_win = [[0] * seg_count for _ in range(random_rounds)]

    for step, t in enumerate(test_idx):
        issues = [r[0] for r in history[:t]]
        fronts = [r[2] for r in history[:t]]
        backs = [r[3] for r in history[:t]]
        act_issue, _, act_front, act_back = history[t]

        pf = core.pick_front(game, fronts, front_k)
        if pf is None:
            n_skip += 1  # 形态无解: 跳过, 不用任何回退
            continue
        pb = core.pick_back(game, backs, back_k)
        n_run += 1
        s = seg_of(t)
        seg_n[s] += 1

        front_hit_total += len(set(pf) & set(act_front))
        if any(b in act_back for b in pb):
            back1_hit += 1
        if all(b in act_back for b in pb):
            back_all_hit += 1

        weights = prize_mod.payoff_weights(game, front_k, back_k,
                                           issue=act_issue, pool_mode=pool_mode)
        v2_kf = len(set(pf) & set(act_front))
        v2_kb = len(set(pb) & set(act_back))
        v2_pay = weights[(v2_kf, v2_kb)]
        if v2_pay >= cost:
            v2_win += 1
            seg_v2_win[s] += 1
        if v2_pay > cost:
            v2_profit += 1
        v2_exp_sum += v2_pay

        act_front_set = set(act_front)
        act_back_set = set(act_back)
        for r in range(random_rounds):
            rf = rng.sample(range(1, front_pool_n + 1), front_k)
            rb = rng.sample(range(1, back_pool_n + 1), back_k)
            rp = weights[(len(act_front_set.intersection(rf)),
                          len(act_back_set.intersection(rb)))]
            rnd_exp_rounds[r] += rp
            if rp >= cost:
                rnd_win_rounds[r] += 1
                seg_rnd_win[r][s] += 1
        if verbose and (step + 1) % 500 == 0:
            print(f"  ... {step + 1}/{len(test_idx)} 期", file=sys.stderr)

    def pct(x):
        return x / n_run if n_run else 0.0

    rnd_rates = [c / n_run for c in rnd_win_rounds]
    rnd_exps = [e / n_run for e in rnd_exp_rounds]
    rnd_rate_mean = sum(rnd_rates) / random_rounds
    rnd_rate_std = (sum((x - rnd_rate_mean) ** 2 for x in rnd_rates) / random_rounds) ** 0.5
    rnd_exp_mean = sum(rnd_exps) / random_rounds
    rnd_exp_std = (sum((x - rnd_exp_mean) ** 2 for x in rnd_exps) / random_rounds) ** 0.5
    v2_rate = pct(v2_win)
    z_rate = (v2_rate - rnd_rate_mean) / rnd_rate_std if rnd_rate_std else 0.0
    v2_exp = v2_exp_sum / n_run if n_run else 0.0
    z_exp = (v2_exp - rnd_exp_mean) / rnd_exp_std if rnd_exp_std else 0.0
    sorted_rates = sorted(rnd_rates)
    ci_low = sorted_rates[int(0.025 * random_rounds)]
    ci_high = sorted_rates[min(int(0.975 * random_rounds), random_rounds - 1)]

    s3 = []
    for s in range(seg_count):
        sz = seg_n[s]
        if not sz:
            continue
        seg_round_rates = [seg_rnd_win[r][s] / sz for r in range(random_rounds)]
        m = sum(seg_round_rates) / random_rounds
        sd = (sum((x - m) ** 2 for x in seg_round_rates) / random_rounds) ** 0.5
        v = seg_v2_win[s] / sz
        s3.append({
            "seg": s, "n": sz, "v2_rate": v, "rnd_mean": m, "rnd_std": sd,
            "diff": v - m, "z": (v - m) / sd if sd else 0.0,
            "lo_issue": history[train_window + s * seg_size][0],
            "hi_issue": history[min(train_window + (s + 1) * seg_size, n_total) - 1][0],
        })

    return {
        "game": game,
        "n_total": n_total,
        "n_test_planned": len(test_idx),
        "n_run": n_run,
        "n_skip": n_skip,
        "front_k": front_k,
        "back_k": back_k,
        "cost": cost,
        "random_rounds": random_rounds,
        "pool_mode": pool_mode,
        "s1": {
            "front_avg": front_hit_total / n_run if n_run else 0,
            "front_expect": front_k * g["front_k"] / g["front_pool"],
            "back1_rate": pct(back1_hit),
            "back_all_rate": pct(back_all_hit),
        },
        "s2": {
            "v2_win_rate": v2_rate,
            "v2_profit_rate": pct(v2_profit),
            "v2_exp": v2_exp,
            "rnd_win_mean": rnd_rate_mean,
            "rnd_win_std": rnd_rate_std,
            "rnd_ci95": [ci_low, ci_high],
            "rnd_exp_mean": rnd_exp_mean,
            "rnd_exp_std": rnd_exp_std,
            "z_win": z_rate,
            "z_exp": z_exp,
            "v2_outside_ci95": not (ci_low <= v2_rate <= ci_high),
        },
        "s3": s3,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def format_report(r: dict) -> str:
    game = r["game"]
    g = core.game_config(game)
    lf, lb = ("红", "蓝") if game == "ssq" else ("前", "后")
    s1, s2 = r["s1"], r["s2"]
    if r["back_k"] == g["back_k"]:
        from math import comb
        theory = 1 / comb(g["back_pool"], g["back_k"]) * 100
        back_line = (f"后区至少中1: {s1['back1_rate'] * 100:.2f}% | "
                     f"后区全中: {s1['back_all_rate'] * 100:.2f}% (理论 {theory:.2f}%)")
    else:
        # ssq 复式选 2 蓝而只开 1 蓝, "全中"结构性恒假, 改报覆盖率
        back_line = f"蓝球覆盖开奖号: {s1['back1_rate'] * 100:.2f}%"
    lines = [
        f"\n{'=' * 64}",
        f"## {g['name_cn']} v2 排除法回测 ({r['front_k']}+{r['back_k']}, {r['cost']}元/期)",
        f"{'=' * 64}",
        f"历史 {r['n_total']} 期 | 有效回测 {r['n_run']} 期 | 形态无解跳过 {r['n_skip']} 期"
        f" | 随机基线 {r['random_rounds']} 轮 | 奖池档: {r['pool_mode']}",
        "",
        "### S1: 命中率",
        f"前区平均命中: {s1['front_avg']:.4f} (随机期望 {s1['front_expect']:.4f})",
        back_line,
        "",
        "### S2: v2 vs 随机 (多轮分布)",
        f"{'指标':<10} {'v2':>9} {'随机均值':>9} {'随机std':>8} {'95%区间':>17} {'z':>7}",
        f"{'保本率':<8} {s2['v2_win_rate']*100:>8.2f}% {s2['rnd_win_mean']*100:>8.2f}% "
        f"{s2['rnd_win_std']*100:>7.2f}% [{s2['rnd_ci95'][0]*100:>5.2f}%,{s2['rnd_ci95'][1]*100:>5.2f}%] "
        f"{s2['z_win']:>7.2f}",
        f"{'盈利率':<8} {s2['v2_profit_rate']*100:>8.2f}%",
        f"{'期望/期':<8} {s2['v2_exp']:>9.2f} {s2['rnd_exp_mean']:>9.2f} {s2['rnd_exp_std']:>8.2f}"
        f" {'':>17} {s2['z_exp']:>7.2f}",
        f"\n保本率差值 {(s2['v2_win_rate']-s2['rnd_win_mean'])*100:+.2f}pp; "
        f"v2 落在随机95%区间"
        f"{'外 ⚠️ 差异显著' if s2['v2_outside_ci95'] else '内 → 差异不显著'} (|z|>=1.96 约显著)",
        "",
        "### S3: 分时段稳定性",
        f"{'段':<4} {'期号范围':>15} {'期数':>5} {'v2':>8} {'随机':>8} {'差(pp)':>8} {'z':>6}",
    ]
    labels = ["早段", "中段", "近期", "最新"]
    for seg in r["s3"]:
        lines.append(
            f"{labels[seg['seg']]:<4} {seg['lo_issue']:>7}-{seg['hi_issue']:<7} {seg['n']:>5} "
            f"{seg['v2_rate']*100:>7.2f}% {seg['rnd_mean']*100:>7.2f}% "
            f"{seg['diff']*100:>+7.2f} {seg['z']:>6.2f}")
    pos = sum(1 for s in r["s3"] if s["diff"] > 0)
    sig = sum(1 for s in r["s3"] if abs(s["z"]) >= 1.96)
    lines.append(f"\n分段 {pos} 正 {len(r['s3']) - pos} 负; 其中 |z|>=1.96 的段: {sig}")
    return "\n".join(lines)


def save_report(r: dict) -> tuple[Path, Path]:
    out_dir = core.SKILL_DIR / core.load_config()["backtest"]["report_dir"]
    out_dir.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M")
    jp = out_dir / f"{r['game']}_v2_{ts}.json"
    mp = out_dir / f"{r['game']}_v2_{ts}.md"
    jp.write_text(json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    mp.write_text(format_report(r), encoding="utf-8")
    return jp, mp


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "ssq"
    r = backtest(game)
    print(format_report(r))
    jp, mp = save_report(r)
    print(f"\n📁 {jp}\n📁 {mp}")
