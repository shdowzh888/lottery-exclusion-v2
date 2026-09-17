"""奖级映射 + 复式奖金枚举。按 config.json 精确查表, 禁止默认兜底。

复式枚举数学 (K/B = 当期开奖个数, 从 config 读, 不是复式选号长度):
  复式选 nf 个前区, 其中 kf 个命中; 恰好覆盖 i 个开奖号的注数 = C(kf,i) * C(nf-kf, K-i)
  后区同理: C(kb,j) * C(nb-kb, B-j)
  总注数恒等于 C(nf,K) * C(nb,B), 可作自检。

大乐透奖表按期号切换: <26014 旧 9 奖级; >=26014 新 7 奖级, 再按奖池 8 亿分 low/high 档。
"""

from __future__ import annotations
from functools import lru_cache
from pathlib import Path
import json


@lru_cache(maxsize=None)
def _load_config():
    with open(Path(__file__).parent.parent / "config.json", encoding="utf-8") as f:
        return json.load(f)


def _comb(n: int, k: int) -> int:
    """C(n,k), k 越界返回 0 (不抛异常, 枚举循环直接跳过)。"""
    if k < 0 or k > n or n < 0:
        return 0
    from math import comb
    return comb(n, k)


def _table_ssq(cfg: dict, fuyun: bool) -> dict:
    table = {(r["i"], r["j"]): r["amount"] for r in cfg["prize"]["ssq"]["table"]}
    if fuyun:
        for r in cfg["prize"]["ssq"].get("extra_rules", []):
            if r.get("name") == "福运奖":
                table[(r["i"], r["j"])] = r["amount"]
    return table


def _table_dlt(cfg: dict, issue: str | None, pool_mode: str) -> dict:
    versions = cfg["prize"]["dlt"]["rule_versions"]
    if issue is not None and issue <= next(v["until_issue"] for v in versions if "until_issue" in v):
        ver = next(v for v in versions if v.get("name") == "old_9tier")
    else:
        want = "new_7tier_high_pool" if pool_mode == "high" else "new_7tier_low_pool"
        ver = next(v for v in versions if v.get("name") == want)
    return {(r["i"], r["j"]): r["amount"] for r in ver["table"]}


@lru_cache(maxsize=None)
def prize_table(game: str, issue: str | None = None, pool_mode: str = "low", fuyun: bool = False) -> dict:
    cfg = _load_config()
    if game == "ssq":
        return _table_ssq(cfg, fuyun)
    return _table_dlt(cfg, issue, pool_mode)


def prize(game: str, i: int, j: int, issue: str | None = None,
          pool_mode: str = "low", fuyun: bool = False) -> int:
    """查询单注奖金。未中奖返回 0, 无兜底。"""
    return prize_table(game, issue, pool_mode, fuyun).get((i, j), 0)


def _iter_lines(game, my_front, my_back, act_front, act_back, issue, pool_mode, fuyun):
    """生成 (i, j, notes, unit_amount)。notes=该(i,j)对应注数。"""
    cfg = _load_config()
    g = cfg["games"][game]
    K, B = g["front_k"], g["back_k"]
    nf, nb = len(my_front), len(my_back)
    kf = len(set(my_front) & set(act_front))
    kb = len(set(my_back) & set(act_back))
    table = prize_table(game, issue, pool_mode, fuyun)
    for i in range(K + 1):
        c_i = _comb(kf, i) * _comb(nf - kf, K - i)
        if c_i == 0:
            continue
        for j in range(B + 1):
            c_j = _comb(kb, j) * _comb(nb - kb, B - j)
            notes = c_i * c_j
            if notes:
                yield i, j, notes, table.get((i, j), 0)


def payoff_weights(game: str, nf: int, nb: int, issue: str | None = None,
                   pool_mode: str = "low", fuyun: bool = False) -> dict:
    """预算 (kf, kb) -> 复式总奖金 的权重表 (每期只算一次, 回测多轮复用)。"""
    cfg = _load_config()
    K, B = cfg["games"][game]["front_k"], cfg["games"][game]["back_k"]
    table = prize_table(game, issue, pool_mode, fuyun)
    w = {}
    for kf in range(nf + 1):
        for kb in range(nb + 1):
            total = 0
            for i in range(K + 1):
                ci = _comb(kf, i) * _comb(nf - kf, K - i)
                if ci == 0:
                    continue
                for j in range(B + 1):
                    amount = table.get((i, j), 0)
                    if amount:
                        cj = _comb(kb, j) * _comb(nb - kb, B - j)
                        total += ci * cj * amount
            w[(kf, kb)] = total
    return w


def combo_payoff(game: str, my_front: list, my_back: list, act_front: list, act_back: list,
                 issue: str | None = None, pool_mode: str = "low", fuyun: bool = False) -> int:
    """复式总奖金。未中奖组合奖金 0, 不计入。"""
    kf = len(set(my_front) & set(act_front))
    kb = len(set(my_back) & set(act_back))
    return payoff_weights(game, len(my_front), len(my_back), issue, pool_mode, fuyun)[(kf, kb)]


def combo_detail(game: str, my_front: list, my_back: list, act_front: list, act_back: list,
                 issue: str | None = None, pool_mode: str = "low", fuyun: bool = False) -> dict:
    """对奖明细: 总注数自检 + 各有奖档的注数/单注奖金/小计。"""
    cfg = _load_config()
    g = cfg["games"][game]
    K, B = g["front_k"], g["back_k"]
    tiers = []
    for i, j, notes, amount in _iter_lines(
            game, my_front, my_back, act_front, act_back, issue, pool_mode, fuyun):
        if amount > 0:
            tiers.append({"i": i, "j": j, "notes": notes, "unit": amount, "subtotal": notes * amount})
    total_notes = _comb(len(my_front), K) * _comb(len(my_back), B)
    return {
        "total_notes": total_notes,
        "hit_front": sorted(set(my_front) & set(act_front)),
        "hit_back": sorted(set(my_back) & set(act_back)),
        "total_payoff": sum(t["subtotal"] for t in tiers),
        "tiers": tiers,
    }


if __name__ == "__main__":
    # 自检断言: 全档置 1 时枚举注数必须等于复式总注数
    import lotto_core
    for game, nf, nb, expect in (("ssq", 7, 2, 14), ("dlt", 7, 2, 21)):
        g = _load_config()["games"][game]
        af = list(range(1, g["front_k"] + 1))
        ab = list(range(1, g["back_k"] + 1))
        counted = sum(notes for _, _, notes, _ in
                      _iter_lines(game, list(range(1, nf + 1)), list(range(1, nb + 1)),
                                  af, ab, None, "low", False))
        assert counted == expect, f"{game} 枚举 {counted} != {expect}"
        print(f"✅ {game} {nf}+{nb} 枚举注数 {counted}")
    print("ssq 6+1 =", prize("ssq", 6, 1), "| ssq 0+0 =", prize("ssq", 0, 0))
    print("dlt 旧 5+0 =", prize("dlt", 5, 0, "26013"), "(应10000)")
    print("dlt 新 5+0 low =", prize("dlt", 5, 0, "26014"), "high =", prize("dlt", 5, 0, "26014", "high"))
