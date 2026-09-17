"""形态特征计算：和值/AC值/跨度/奇偶比。

阈值按 彩种 + 号码数 n 双键查 config (防 L9: 5/7 号码口径混淆; 防 ssq/dlt 同 n 共用阈值)。
"""

from __future__ import annotations
import json
from functools import lru_cache
from itertools import combinations
from pathlib import Path


@lru_cache(maxsize=None)
def _load_config():
    cfg_path = Path(__file__).parent.parent / "config.json"
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


def shape_features(nums: list[int]) -> dict:
    """计算一组号码的形态特征。"""
    nums = sorted(nums)
    n = len(nums)
    odd = sum(1 for x in nums if x % 2 == 1)
    diffs = {abs(b - a) for a, b in combinations(nums, 2)}
    return {
        "号码数": n,
        "和值": sum(nums),
        "AC值": len(diffs) - (n - 1),
        "跨度": nums[-1] - nums[0],
        "奇偶比": f"{odd}:{n - odd}",
        "尾数和": sum(x % 10 for x in nums),
    }


def odd_even_for_n(game: str, n: int) -> list[str]:
    """按彩种 + 号码数选合法奇偶比。"""
    cfg = _load_config()
    table = cfg["strategy"]["exclusion_v2"]["shape_filter"][game]["k_to_odd_even"]
    key = str(n)
    if key not in table:
        raise ValueError(
            f"奇偶比口径不支持 {game} n={n} (支持: {list(table.keys())}). "
            f"如需新口径, 改 config.json shape_filter.{game}.k_to_odd_even"
        )
    return table[key]


def validate_shape(nums, game: str, cfg_section=None) -> bool:
    """形态过滤：和值/AC/跨度/奇偶比 全部命中才返回 True。"""
    if cfg_section is None:
        cfg = _load_config()
        cfg_section = cfg["strategy"]["exclusion_v2"]["shape_filter"][game]
    f = shape_features(nums)
    k = str(len(nums))
    if not (cfg_section["sum_range"][k][0] <= f["和值"] <= cfg_section["sum_range"][k][1]):
        return False
    if not (cfg_section["ac_range"][k][0] <= f["AC值"] <= cfg_section["ac_range"][k][1]):
        return False
    if not (cfg_section["span_range"][k][0] <= f["跨度"] <= cfg_section["span_range"][k][1]):
        return False
    if f["奇偶比"] not in odd_even_for_n(game, len(nums)):
        return False
    return True


if __name__ == "__main__":
    for game in ("ssq", "dlt"):
        print(game, {n: odd_even_for_n(game, n) for n in (5, 6, 7, 8)})
    print("形态示例:", shape_features([3, 19, 22, 29, 30, 32, 35]))
