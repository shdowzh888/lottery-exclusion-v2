# 数据源文档

## 一、官方接口

### 1.1 双色球 cwl.gov.cn

```
GET https://www.cwl.gov.cn/cwl_admin/front/cwlkj/search/kjxx/findDrawNotice
    ?name=ssq&issueCount=30&pageNo=1&pageSize=30&systemType=PC
返回 JSON: result[].code / date / red="01,02,.." (逗号) / blue="01"
Referer: 不需要
```

### 1.2 大乐透 webapi.sporttery.cn

```
GET https://webapi.sporttery.cn/gateway/lottery/getHistoryPageListV1.qry
    ?gameNo=85&provinceId=0&pageSize=30&isVerify=1&pageNo=1
Header: Referer: https://www.sporttery.cn/   (必须, 否则 403)
返回 JSON: value.list[].lotteryDrawNum / lotteryDrawTime /
           lotteryDrawResult="05 14 15 17 33 01 07" (空格分隔! 前5后2)
```

统一 HTTP 行为（`fetch_data._http_get`）：UA `Mozilla/5.0`，超时 30s，失败 3 次退避 2/5/8s，3 次均败抛 RuntimeError。

## 二、CSV 历史（v2 统一 5 列 schema）

路径 `data/{ssq,dlt}.csv`，两彩种同列名：

```
期号,日期,前区,后区,来源
2026108,2026-09-17(四),"[06, 11, 13, 14, 20, 28]",[16],官方接口
26106,2026-09-16,"[14, 17, 21, 25, 28]","[04, 06]",官方接口
```

1. 编码 utf-8-sig；号码 `f"{x:02d}"` 保前导零
2. 更新策略：读旧 + 拉新 → 按期号去重 → 校验 → **全量重写**（天然修复追加模式的列错位）
3. 读取层兼容旧文件（红球/蓝球列名、扩展列），首次写入即迁移
4. 期号等长（ssq 7 位 / dlt 5 位），字符串排序；doctor 检查长度一致

## 三、推荐与对账文件

| 文件 | 内容 |
|---|---|
| `outputs/{game}_latest.json` | 最近一次推荐：号码/基准期/注数/成本/形态/排除源/stale 标记 |
| `backtests/{game}_v2_*.{json,md}` | 每次回测的结构化结果与报告 |

`check` 读 outputs 推荐，fetch 最新开奖后，对基准期之后的每个新开奖期逐期结算（combo_detail 给奖级明细）。

## 四、备选数据源（主接口长期不可用时人工降级）

| 源 | URL | 说明 |
|---|---|---|
| 中彩网 | https://www.zhcw.com/ssq/ | HTML 解析 |
| 500 彩票 | https://kaijiang.500.com/ssq.shtml | HTML 解析 |
| 新浪彩票 | https://lottery.sina.com.cn/ | 双彩种 |

未编码自动切换；predict/check 在网络失败时降级本地数据并标注 stale，不阻塞使用。

## 五、数据规模（2026-09-17）

| 彩种 | 期数 | 每次拉取 |
|---|---|---|
| 双色球 | 3505（2003 起） | 30 |
| 大乐透 | 2924（2007 起） | 30 |

建议：开奖日晚 22:00 后 `fetch`；每周或调参后 `backtest --rounds 100`；规则变更时核对 config.prize 并跑 `doctor`。
