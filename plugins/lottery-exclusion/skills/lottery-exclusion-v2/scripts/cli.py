"""lottery-exclusion-v2 统一 CLI。

  python3 scripts/cli.py <game> <cmd> [选项]
  game ∈ {ssq, dlt}
  cmd  ∈ {fetch, predict, check, backtest, doctor}
    fetch     增量更新历史 CSV
    predict   生成下期推荐 (自动 fetch, 落盘 outputs/)
    check     对奖: 用 outputs/ 里的推荐与最新开奖结算
    backtest  S1/S2/S3 回测 (自动 fetch, 报告落盘 backtests/)
    doctor    数据自检 (范围/数量/期号/排序)
"""

from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

import lotto_core as core
import predict as predict_mod
import backtest as backtest_mod
import prize as prize_mod
import update_history
import shape as shape_mod


def cmd_fetch(game, args):
    n = (update_history.update_ssq if game == "ssq" else update_history.update_dlt)(
        core.csv_path(game), fetch_count=30)
    print(f"✅ {core.game_config(game)['name_cn']}: 新增 {n} 期")


def cmd_predict(game, args):
    p = predict_mod.predict(game, front_k=args.front_k, back_k=args.back_k,
                            auto_fetch=not args.no_fetch)
    g = core.game_config(game)
    lf, lb = ("红球", "蓝球") if game == "ssq" else ("前区", "后区")
    print(f"\n🎯 {g['name_cn']} 推荐 (基于 {p['base_issue']} 期):")
    print(f"  {lf}({p['front_k']}): {' '.join(f'{n:02d}' for n in p['front'])}")
    print(f"  {lb}({p['back_k']}): {' '.join(f'{n:02d}' for n in p['back'])}")
    print(f"  投入: {p['notes']}注 × {g['bet_price']}元 = {p['cost']}元")
    f = p["front_shape"]
    print(f"  形态: 和值{f['和值']} AC{f['AC值']} 跨度{f['跨度']} 奇偶{f['奇偶比']}")
    print(f"  排除源: {lf}{p['exclude_front']} {lb}{p['exclude_back']}")
    print(f"  📁 已保存: outputs/{game}_latest.json (check 对奖用)")
    if p["n_new"]:
        print(f"  [fetch] 新增 {p['n_new']} 期")
    if p["stale"]:
        print(f"  ⚠️ 联网更新失败, 基于本地 {p['base_issue']} 期, 数据可能过期: {p['fetch_error']}")
    print("\n⚠️ 彩票是独立随机事件, 本推荐仅为历史统计参考, 不构成中奖保证. 理性购彩量力而行.")


def cmd_check(game, args):
    """对奖: 推荐基准期之后新开的期, 逐期结算。"""
    g = core.game_config(game)
    rec_path = core.SKILL_DIR / "outputs" / f"{game}_latest.json"
    if not rec_path.exists():
        sys.exit(f"❌ 没有找到推荐记录 {rec_path}\n   请先运行: python3 scripts/cli.py {game} predict")
    rec = json.loads(rec_path.read_text(encoding="utf-8"))

    stale = False
    if not args.no_fetch:
        try:
            (update_history.update_ssq if game == "ssq" else update_history.update_dlt)(
                core.csv_path(game), fetch_count=30)
        except Exception as e:
            stale = True
            print(f"⚠️ 联网更新失败, 用本地数据对奖: {e}")
    history = core.read_history(game)
    later = [r for r in history if r[0] > rec["base_issue"]]
    lf, lb = ("红球", "蓝球") if game == "ssq" else ("前区", "后区")

    print(f"\n🎫 {g['name_cn']} 对奖")
    print(f"  推荐基于 {rec['base_issue']} 期, {lf}{rec['front']} {lb}{rec['back']}"
          f" ({rec['front_k']}+{rec['back_k']}, {rec['cost']}元)")
    if not later:
        latest = history[-1]
        print(f"  📌 {rec['base_issue']} 期之后尚未开奖 (本地最新 {latest[0]} 期 {latest[1]})")
        if stale:
            print("  ⚠️ 当前为离线状态, 联网后重跑本命令确认")
        return

    total_pay = 0
    for issue, date, act_front, act_back in later:
        d = prize_mod.combo_detail(game, rec["front"], rec["back"], act_front, act_back,
                                   issue=issue, pool_mode=args.pool, fuyun=args.fuyun)
        print(f"\n  📅 {issue} 期 ({date}) 开奖: {lf}{act_front} {lb}{act_back}")
        print(f"     命中: {lf}{d['hit_front'] or '无'} {lb}{d['hit_back'] or '无'}")
        if d["tiers"]:
            for t in d["tiers"]:
                print(f"     {t['i']}+{t['j']}: {t['notes']}注 × {t['unit']}元 = {t['subtotal']}元")
            print(f"     合计奖金: {d['total_payoff']} 元")
        else:
            print("     未中奖")
        total_pay += d["total_payoff"]
    net = total_pay - rec["cost"] * len(later)
    print(f"\n  累计投入: {rec['cost'] * len(later)} 元 | 累计奖金: {total_pay} 元 | 净盈亏: {net:+d} 元")
    if game == "dlt":
        print("  ⚠️ 大乐透固定奖按奖池 8 亿分档, 本结算用 "
              f"{'high(6666/380/200/18/7)' if args.pool == 'high' else 'low(5000/300/150/15/5)'} 档;"
              "浮动奖与派奖活动以官方公告为准")
    if args.fuyun:
        print("  ℹ️ 已计入福运奖(3+0=5元), 请确认当期福运奖处于生效状态")


def cmd_backtest(game, args):
    if not args.no_fetch:
        cmd_fetch(game, args)
    print(f"回测中 (随机 {args.rounds or core.load_config()['backtest']['random_rounds']} 轮)...",
          file=sys.stderr)
    r = backtest_mod.backtest(game, front_k=args.front_k, back_k=args.back_k,
                              random_rounds=args.rounds, pool_mode=args.pool)
    print(backtest_mod.format_report(r))
    jp, mp = backtest_mod.save_report(r)
    print(f"\n📁 {jp}\n📁 {mp}")


def cmd_doctor(game, args):
    r = update_history.doctor(game)
    g = core.game_config(game)
    print(f"\n📋 {g['name_cn']} 数据自检")
    print(f"  文件: {core.csv_path(game)}")
    print(f"  总期数: {r['total']}")
    if r.get("last_code"):
        print(f"  最新期: {r['last_code']} ({r.get('last_date')})")
    if r["status"] == "ok":
        print("  ✅ 全部合法")
    else:
        print(f"  ❌ {r.get('n_issues', len(r['issues']))} 条问题:")
        for issue in r["issues"]:
            print(f"    - {issue}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(prog="cli.py", description="lottery-exclusion-v2")
    parser.add_argument("game", choices=["ssq", "dlt"])
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("fetch", "predict", "check", "backtest", "doctor"):
        p = sub.add_parser(name)
        if name in ("predict", "backtest"):
            p.add_argument("--front-k", type=int, default=None)
            p.add_argument("--back-k", type=int, default=None)
            p.add_argument("--no-fetch", action="store_true")
        if name in ("check", "backtest"):
            p.add_argument("--pool", choices=["low", "high"], default="low",
                           help="大乐透新固定奖档: low=<8亿(默认), high=>=8亿")
        if name == "check":
            p.add_argument("--no-fetch", action="store_true")
            p.add_argument("--fuyun", action="store_true", help="计入双色球福运奖(3+0=5)")
        if name == "backtest":
            p.add_argument("--rounds", type=int, default=None, help="随机基线轮数")
    args = parser.parse_args()
    {"fetch": cmd_fetch, "predict": cmd_predict, "check": cmd_check,
     "backtest": cmd_backtest, "doctor": cmd_doctor}[args.cmd](args.game, args)


if __name__ == "__main__":
    main()
