"""CSV 历史数据: 增量拉取 + 合并去重 + 全量重写 + 数据自检 (doctor)。

统一 schema (两彩种同列名, 5 列): 期号,日期,前区,后区,来源
兼容读取旧文件的 红球/蓝球 与扩展列, 首次写入时自动迁移。
防 L7: 前导零用 f"{x:02d}" 保留, utf-8-sig 读写
防 L8: 同彩种期号等长, 按字符串排序
"""

from __future__ import annotations
import csv
import sys
from pathlib import Path

import fetch_data
import lotto_core as core

FIELDNAMES = ["期号", "日期", "前区", "后区", "来源"]


def _validate_row(game: str, code: str, front: list, back: list) -> str | None:
    """返回错误信息; 合法返回 None。"""
    g = core.game_config(game)
    if len(front) != g["front_k"]:
        return f"{code} 前区数量={len(front)} (应 {g['front_k']})"
    if len(back) != g["back_k"]:
        return f"{code} 后区数量={len(back)} (应 {g['back_k']})"
    if any(x < 1 or x > g["front_pool"] for x in front):
        return f"{code} 前区超范围: {front} (1-{g['front_pool']})"
    if any(x < 1 or x > g["back_pool"] for x in back):
        return f"{code} 后区超范围: {back} (1-{g['back_pool']})"
    if len(set(front)) != len(front) or len(set(back)) != len(back):
        return f"{code} 号码重复: {front} / {back}"
    return None


def _fmt(nums: list) -> str:
    return "[" + ", ".join(f"{x:02d}" for x in nums) + "]"


def _read_existing_raw(game: str, path: Path) -> dict:
    """读已有行 (保留来源列); 兼容旧列名 红球/蓝球。"""
    out = {}
    if not path.exists():
        return out
    with open(path, encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            front = core._parse_num_field(row.get("前区") or row.get("红球"))
            back = core._parse_num_field(row.get("后区") or row.get("蓝球"))
            out[row["期号"].strip()] = (
                row.get("日期", "").strip(), front, back, row.get("来源", "").strip() or "历史迁移")
    return out


def _merge_and_write(game: str, path: Path, fetched: list[dict]) -> int:
    """读旧数据(兼容旧列名) + 新数据, 去重校验后全量重写统一 schema。返回新增条数。"""
    by_issue = _read_existing_raw(game, path)
    n_new = 0
    for r in fetched:
        if r["code"] in by_issue:
            continue
        front = r.get("reds", r.get("front"))
        back = [r["blue"]] if "blue" in r else r["back"]
        err = _validate_row(game, r["code"], front, back)
        if err:
            raise RuntimeError(f"接口脏数据: {err}")
        by_issue[r["code"]] = (r["date"], front, back, "官方接口")
        n_new += 1
    items = sorted(by_issue.items(), key=lambda kv: kv[0])
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(FIELDNAMES)
        for issue, (date, front, back, src) in items:
            w.writerow([issue, date, _fmt(front), _fmt(back), src])
    return n_new


def update_ssq(csv_path: Path, fetch_count: int = 30) -> int:
    rows = fetch_data.fetch_ssq(fetch_count)
    return _merge_and_write("ssq", csv_path, rows)


def update_dlt(csv_path: Path, fetch_count: int = 30) -> int:
    rows = fetch_data.fetch_dlt(fetch_count)
    return _merge_and_write("dlt", csv_path, rows)


def doctor(game: str) -> dict:
    """数据自检: 存在性/数量/范围/重复号/期号重复/期号长度一致/排序。"""
    path = core.csv_path(game)
    if not path.exists():
        return {"status": "missing", "total": 0, "issues": [f"数据文件不存在: {path}"]}
    issues = []
    history = core.read_history(game)
    seen = set()
    lengths = set()
    prev = None
    for issue, date, front, back in history:
        lengths.add(len(issue))
        err = _validate_row(game, issue, front, back)
        if err:
            issues.append(err)
        if issue in seen:
            issues.append(f"{issue} 期号重复")
        seen.add(issue)
        if prev is not None and issue < prev:
            issues.append(f"{issue} 排序错乱 (位于 {prev} 之后)")
        prev = issue
    if len(lengths) > 1:
        issues.append(f"期号长度不一致: {sorted(lengths)}")
    last = history[-1] if history else None
    return {
        "status": "ok" if not issues else "errors",
        "total": len(history),
        "last_code": last[0] if last else None,
        "last_date": last[1] if last else None,
        "issues": issues[:20],
        "n_issues": len(issues),
    }


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "ssq"
    cmd = sys.argv[2] if len(sys.argv) > 2 else "update"
    path = core.csv_path(game)
    if cmd == "update":
        n = update_ssq(path) if game == "ssq" else update_dlt(path)
        print(f"{game}: 新增 {n} 期")
    elif cmd == "doctor":
        import json
        print(json.dumps(doctor(game), ensure_ascii=False, indent=2))
