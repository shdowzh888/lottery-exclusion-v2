"""v2 排除法推荐: 排除上期 → 热度+遗漏加权 → 候选池枚举 → 形态过滤。

防 L1: 号码池/开奖个数从 config 读取 (大乐透 35 选 5)
防 L3: 默认先增量 fetch; 网络失败时降级用本地数据并标注 stale
防 L13: 形态过滤无解时按 fallback 扩候选池, 仍无则 RuntimeError
推荐结果落盘 outputs/{game}_latest.json, 供 check 对奖。
"""

from __future__ import annotations
import json
import sys
from datetime import datetime
from pathlib import Path

import lotto_core as core
import shape as shape_mod


def predict(game: str, front_k: int | None = None, back_k: int | None = None,
            auto_fetch: bool = True):
    """生成下期推荐, 返回结果 dict (同时落盘 outputs/{game}_latest.json)。"""
    cfg = core.load_config()
    target = cfg["backtest"]["default_target_bet"][game]
    front_k = front_k or target["front_k"]
    back_k = back_k or target["back_k"]

    stale, fetch_err, n_new = False, None, 0
    if auto_fetch:
        try:
            import update_history
            updater = update_history.update_ssq if game == "ssq" else update_history.update_dlt
            n_new = updater(core.csv_path(game), fetch_count=30)
        except Exception as e:  # 网络失败不致命: 降级本地数据
            stale, fetch_err = True, str(e)

    history = core.read_history(game)
    if not history:
        raise RuntimeError(f"历史为空, 请先联网 fetch: cli.py {game} fetch")

    issues = [r[0] for r in history]
    fronts = [r[2] for r in history]
    backs = [r[3] for r in history]
    base_issue, base_date = issues[-1], history[-1][1]

    pred_front = core.pick_front(game, fronts, front_k)
    if pred_front is None:
        raise RuntimeError(
            f"形态过滤在候选池 {cfg['strategy']['exclusion_v2']['candidate_fallback_sizes']} 内无解. "
            f"请放宽 config.json shape_filter.{game} 阈值"
        )
    pred_back = core.pick_back(game, backs, back_k)
    info = core.bet_info(game, front_k, back_k)

    result = {
        "game": game,
        "base_issue": base_issue,
        "base_date": base_date,
        "front": pred_front,
        "back": pred_back,
        "front_k": front_k,
        "back_k": back_k,
        "notes": info["notes"],
        "cost": info["cost"],
        "exclude_front": fronts[-1],
        "exclude_back": backs[-1],
        "front_shape": shape_mod.shape_features(pred_front),
        "stale": stale,
        "fetch_error": fetch_err,
        "n_new": n_new,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    out_dir = core.outputs_dir()
    (out_dir / f"{game}_latest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "ssq"
    p = predict(game)
    g = core.game_config(game)
    lf, lb = ("红球", "蓝球") if game == "ssq" else ("前区", "后区")
    print(f"\n🎯 {g['name_cn']} 推荐 (基于 {p['base_issue']} 期):")
    print(f"  {lf}({p['front_k']}): {' '.join(f'{n:02d}' for n in p['front'])}")
    print(f"  {lb}({p['back_k']}): {' '.join(f'{n:02d}' for n in p['back'])}")
    print(f"  投入: {p['notes']}注 × {g['bet_price']}元 = {p['cost']}元")
    f = p["front_shape"]
    print(f"  形态: 和值{f['和值']} AC{f['AC值']} 跨度{f['跨度']} 奇偶{f['奇偶比']}")
    print(f"  排除源: {lf}{p['exclude_front']} {lb}{p['exclude_back']}")
    if p["stale"]:
        print(f"  ⚠️ 联网更新失败, 基于本地 {p['base_issue']} 期, 数据可能过期: {p['fetch_error']}")
