"""公共核心: config / CSV 历史 / 评分 / 选号, predict 与 backtest 唯一实现来源。

防漂移: 线上推荐与历史回测必须走本模块同一套函数, 不允许复制后各改一份。
防 L1: 号码池/开奖个数全部从 config 读取 (大乐透 35 选 5, 双色球 33 选 6)。
"""

from __future__ import annotations
import csv
import itertools
import json
import os
import shutil
from collections import Counter
from functools import lru_cache
from pathlib import Path

import shape as shape_mod


def _force_utf8_io():
    """Windows 管道默认 cp936, emoji/特殊字符 print 会崩, 强制 utf-8。"""
    import sys
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

_force_utf8_io()


SKILL_DIR = Path(__file__).parent.parent


def user_data_dir() -> Path:
    """可变数据目录(跨插件更新不丢): 可用环境变量 LOTTERY_DATA_DIR 覆盖,
    否则 ~/.lottery-exclusion-v2 (Mac/Windows 均成立)。"""
    d = Path(os.environ.get("LOTTERY_DATA_DIR") or (Path.home() / ".lottery-exclusion-v2"))
    (d / "outputs").mkdir(parents=True, exist_ok=True)
    (d / "backtests").mkdir(parents=True, exist_ok=True)
    return d


def outputs_dir() -> Path:
    return user_data_dir() / "outputs"


def backtests_dir() -> Path:
    return user_data_dir() / "backtests"


@lru_cache(maxsize=None)
def load_config():
    with open(SKILL_DIR / "config.json", encoding="utf-8") as f:
        return json.load(f)


def game_config(game: str) -> dict:
    return load_config()["games"][game]


def strat_config() -> dict:
    return load_config()["strategy"]["exclusion_v2"]


def csv_path(game: str) -> Path:
    """用户数据目录下的 CSV; 首次使用时从包内种子复制 (插件更新不覆盖用户数据)。"""
    rel = game_config(game)["data_csv"]
    user_file = user_data_dir() / rel
    if not user_file.exists():
        seed = SKILL_DIR / rel
        if seed.exists():
            user_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(seed, user_file)
    return user_file


def read_history(game: str):
    """读历史 CSV, 返回 [(issue, date, front[list], back[list]), ...] 按期号升序。"""
    path = csv_path(game)
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            front = _parse_num_field(row.get("前区") or row.get("红球"))
            back = _parse_num_field(row.get("后区") or row.get("蓝球"))
            rows.append((row["期号"].strip(), row.get("日期", "").strip(), front, back))
    rows.sort(key=lambda r: r[0])
    return rows


def _parse_num_field(s: str) -> list:
    if s is None:
        return []
    return [int(x.strip()) for x in s.strip().strip("[]").split(",") if x.strip()]


def miss_len(history: list, n: int) -> int:
    """n 的遗漏期数 (距上次出现); 从未出现返回全部期数。"""
    for i in range(len(history) - 1, -1, -1):
        if n in history[i]:
            return len(history) - 1 - i
    return len(history)


def score_front(game: str, front_history: list, exclude: set) -> dict:
    """前区/红球: 近期热度加权 + 遗漏回补。"""
    cfg = strat_config()
    w = cfg["front_recent_weights"]
    miss_w = cfg["miss_weight_per_pool"]
    pool_size = game_config(game)["front_pool"]
    pool = [n for n in range(1, pool_size + 1) if n not in exclude]
    c30 = Counter(n for ns in front_history[-30:] for n in ns)
    c10 = Counter(n for ns in front_history[-10:] for n in ns)
    c_all = Counter(n for ns in front_history for n in ns)
    miss = {n: miss_len(front_history, n) for n in pool}
    return {
        n: c30.get(n, 0) * w["h30"]
        + c10.get(n, 0) * w["h10"]
        + c_all.get(n, 0) * w["all"]
        + (miss[n] / pool_size) * miss_w
        for n in pool
    }


def score_back(game: str, back_history: list, exclude: set) -> dict:
    """后区/蓝球: 全期热度 + 近 10 期热度 (predict/backtest 唯一实现)。"""
    cfg = strat_config()
    w = cfg["back_recent_weights"]
    pool_size = game_config(game)["back_pool"]
    pool = [n for n in range(1, pool_size + 1) if n not in exclude]
    c_all = Counter(b for pair in back_history for b in pair)
    c10 = Counter(b for pair in back_history[-10:] for b in pair)
    return {n: c_all.get(n, 0) * w["all"] + c10.get(n, 0) * w["h10"] for n in pool}


def pick_front(game: str, front_history: list, k: int, fallback_sizes: list | None = None):
    """排除最后一期 -> 评分 -> 候选池枚举 -> 形态过滤取最高分。无解返回 None。"""
    if fallback_sizes is None:
        fallback_sizes = strat_config()["candidate_fallback_sizes"]
    exclude = set(front_history[-1])
    score = score_front(game, front_history[:-1], exclude)
    ranked = sorted(score, key=lambda n: -score[n])
    for cand_size in fallback_sizes:
        top = ranked[:cand_size]
        best, best_sum = None, -1
        for combo in itertools.combinations(top, k):
            if not shape_mod.validate_shape(list(combo), game):
                continue
            s = sum(score[n] for n in combo)
            if s > best_sum:
                best, best_sum = combo, s
        if best:
            return sorted(best)
    return None


def pick_back(game: str, back_history: list, k: int) -> list:
    """后区/蓝球直接评分取 TOP k (排除最后一期)。"""
    exclude = set(back_history[-1])
    score = score_back(game, back_history[:-1], exclude)
    ranked = sorted(score, key=lambda n: -score[n])
    return sorted(ranked[:k])


def bet_info(game: str, front_k: int, back_k: int) -> dict:
    """复式注数与成本。开奖个数从 config 读, 不用号码池大小反推。"""
    from math import comb
    g = game_config(game)
    notes = comb(front_k, g["front_k"]) * comb(back_k, g["back_k"])
    return {"notes": notes, "cost": notes * g["bet_price"]}
