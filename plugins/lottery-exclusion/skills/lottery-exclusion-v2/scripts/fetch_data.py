"""双彩种数据获取。

防 L5: 体彩必须 Referer
防 L6: 体彩结果用空格分隔, 不是逗号
"""

from __future__ import annotations
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

def _force_utf8_io():
    """Windows 管道默认 cp936, emoji/特殊字符 print 会崩, 强制 utf-8。"""
    import sys
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

_force_utf8_io()



def _http_get(url: str, referer: str | None = None, timeout: int = 30, retries: int = 3):
    """统一 HTTP GET, 带 Referer 头部 + 失败重试。"""
    headers = {"User-Agent": "Mozilla/5.0"}
    if referer:
        headers["Referer"] = referer
    last_err = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode("utf-8")
        except Exception as e:
            last_err = e
            if i < retries - 1:
                import time
                time.sleep(2 + i * 3)  # 退避: 2s, 5s, 8s
    raise RuntimeError(f"HTTP失败 {retries}次: {last_err}\nURL: {url}")


def fetch_ssq(count: int = 30) -> list[dict]:
    """双色球: cwl.gov.cn, JSON 格式, 字段 red/blue 逗号分隔。"""
    cfg = _load_config()
    base = cfg["games"]["ssq"]["fetch_url"]
    params = dict(cfg["games"]["ssq"]["fetch_params"])
    params["issueCount"] = count
    url = base + "?" + urllib.parse.urlencode(params)
    body = _http_get(url)
    data = json.loads(body)
    rows = data.get("result", [])
    out = []
    for d in rows:
        reds = [int(x) for x in d["red"].split(",")]
        blue = int(d["blue"])
        out.append({
            "code": d["code"],
            "date": d["date"],
            "reds": sorted(reds),
            "blue": blue,
        })
    return out


def fetch_dlt(count: int = 30) -> list[dict]:
    """大乐透: webapi.sporttery.cn, 必须 Referer, 结果字段 lotteryDrawResult 空格分隔.

    防 L5: 必须 Referer (无 Referer 会 403)
    防 L6: lotteryDrawResult 是 "01 02 03 04 05 06 07" 空格分隔, 不能 split(",")
    """
    cfg = _load_config()
    base = cfg["games"]["dlt"]["fetch_url"]
    params = dict(cfg["games"]["dlt"]["fetch_params"])
    params["pageSize"] = str(count)
    url = base + "?" + urllib.parse.urlencode(params)
    body = _http_get(url, referer=cfg["games"]["dlt"]["fetch_referer"])
    data = json.loads(body)
    rows = data.get("value", {}).get("list", [])
    out = []
    for d in rows:
        nums = d["lotteryDrawResult"].split()  # ← 空格, 不是逗号 (L6)
        if len(nums) != 7:
            raise RuntimeError(f"大乐透结果格式异常: {d['lotteryDrawResult']} (期望7个号)")
        front = sorted(int(x) for x in nums[:5])
        back = sorted(int(x) for x in nums[5:])
        out.append({
            "code": d["lotteryDrawNum"],
            "date": d.get("lotteryDrawTime", "")[:10],
            "front": front,
            "back": back,
        })
    return out


def _load_config():
    cfg_path = Path(__file__).parent.parent / "config.json"
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


if __name__ == "__main__":
    game = sys.argv[1] if len(sys.argv) > 1 else "ssq"
    count = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    if game == "ssq":
        for d in fetch_ssq(count):
            print(f"SSQ {d['code']} {d['date']}: 红{d['reds']} 蓝{d['blue']:02d}")
    elif game == "dlt":
        for d in fetch_dlt(count):
            print(f"DLT {d['code']} {d['date']}: 前{d['front']} 后{d['back']}")
    else:
        sys.exit(f"未知彩种: {game}")
