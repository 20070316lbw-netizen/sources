# sources 重构进度

本分支整理 `sources` 的包结构和面向下游项目的接口。重构按市场组织：底层组件放在对应市场目录，市场类组合这些组件并提供默认标的名单。A 股实现已迁入 `ashare/`，原 `sources.cn` 路径作为兼容入口保留。

## 目标结构

```text
src/sources/
├── __init__.py
├── sp500/
│   ├── __init__.py
│   ├── daily.py           # DailySp500
│   ├── hourly.py          # HourSp500
│   ├── cache/             # S&P 500 成员名单缓存
│   │   └── changelog/     # 历史成分股名单和变更记录
│   ├── prices.py
│   ├── riskfree.py
│   ├── sec/
│   └── constituents.py
└── ashare/
    ├── __init__.py
    ├── daily.py           # DailyAShare
    ├── hourly.py          # HourAShare
    ├── cache/             # A 股成员名单缓存
    ├── prices.py
    ├── intraday.py
    ├── calendar.py
    ├── constituents.py
    ├── stock_basic.py
    └── _baostock.py
```

公开入口目标：

```python
from sources import DailySp500, HourSp500, DailyAShare, HourAShare
```

市场类默认从缓存成员名单取得标的，也允许调用方显式传入股票代码。成员名单缓存与行情结果缓存是不同职责；本次整理的默认名单缓存不代表行情数据也由本包持久化。

缓存文件缺失时会从对应数据源抓取；后续默认复用缓存，调用 `members(refresh=True)` 显式刷新。S&P 500 当前名单与历史成分共用一份缓存，默认放在包内 `sp500/cache/changelog/data/`；A 股成分名单写入 `~/.cache/sources/ashare/`。设置 `SOURCES_DATA_DIR` 可统一指定可写缓存目录。

```python
from sources import DailySp500, HourSp500, DailyAShare, HourAShare

daily_sp500 = DailySp500()
daily_prices = daily_sp500.prices()  # 默认最近十年, 使用缓存的当前成分股

hour_ashare = HourAShare()
hour_prices = hour_ashare.prices(start="2026-01-01")  # BaoStock 60 分钟线
```

A 股默认名单目前是 BaoStock 支持的沪深 300 成分快照。S&P 500 十年价格请求仍受 Yahoo Finance 可用历史范围限制；当前成分名单回抓历史数据仍有幸存者偏差。

## 盘点结果

### 可复用组件

| 当前模块 | 目标位置/用途 | 状态 |
| --- | --- | --- |
| 原 `sources.prices` | `sp500/prices.py`：Yahoo Finance 行情及清洗 | 已迁移；旧路径兼容 |
| 原 `sources.riskfree` | `sp500/riskfree.py` | 已迁移；旧路径兼容 |
| 原 `sources.sec` | `sp500/sec/`：SEC 基本面抓取与标准化 | 已迁移；旧路径兼容 |
| 原 `sources.constituents`、`sources.constituents_changelog` | `sp500/constituents.py`、`sp500/cache/changelog/` | 已迁移；旧路径兼容 |
| 原 `sources.cn._baostock`、`sources.cn.codes` | `ashare/_baostock.py`、`ashare/codes.py` | 已迁移；旧路径兼容 |
| 原 `sources.cn.prices` | `ashare/prices.py`：日线、停牌和 ST 字段清洗 | 已迁移，口径保留 |
| 原 `sources.cn.intraday` | `ashare/intraday.py`：分钟线及 60 分钟数据 | 已迁移，清洗口径保留 |
| 原 `sources.cn.trade_calendar` | `ashare/calendar.py` | 已迁移；旧路径兼容 |
| 原 `sources.cn.index_members` | `ashare/constituents.py` | 已迁移；名单缓存单独提供 |
| 原 `sources.cn.stock_basic` | `ashare/stock_basic.py` | 已迁移；旧路径兼容 |

### A 股分钟线清洗约定

小时类使用 BaoStock `freq="60"`；底层仍保留 5、15、30、60 分钟频率能力。迁移必须保留这些行为：

- 规范化代码；校验频率；一次批次复用 BaoStock 登录会话。
- 合并不复权 OHLCV 与后复权收盘价；数值字段转换为数值类型。
- 将 BaoStock 时间字段解析为无时区 `ts`，并将其定义为 bar 结束时间。
- 丢弃时间戳无法解析或 `close` 缺失的行；保留后复权价缺失的行。
- 单只证券失败或无数据时跳过；最终按 `(ticker, ts)` 排序。
- 无结果时仍返回固定列结构。

对应实现为 `src/sources/ashare/intraday.py`；旧 `sources.cn` 入口仍由 `test/test_cn.py` 覆盖。

## 重构步骤

- [x] 确认 `main` 与 `origin/main` 同步；当前无需补推代码。
- [x] 创建工作分支 `codex/package-refactor-plan`。
- [x] 盘点现有模块、清洗逻辑和相关测试。
- [x] 将原使用文档保留到 `docs/usage.md`。
- [x] 建立市场目录入口，并增加四个市场/频率组合类。
- [x] 建立成员名单缓存入口；缺失时抓取，显式刷新，失败时不写入空缓存。
- [x] 将 A 股底层实现迁入 `ashare/`，保留 `sources.cn` 兼容导入。
- [x] 将 S&P 500 行情、基本面、成分股与历史缓存实现迁入 `sp500/`，保留旧导入路径。
- [ ] 明确缓存过期策略；当前缓存不会自动过期。
- [x] 从 `sources` 顶层导出四个类；旧函数导入路径暂时保留。
- [ ] 补齐 S&P 500 交易日历组件；当前仓库没有独立的交易日历实现。
- [ ] 将旧版使用文档逐步更新为组合类示例。
- [x] 为四个组合类和 S&P 500 成员缓存增加专门测试；全套 133 项测试通过。
- [x] 用 `DailySp500` 执行一次真实日线抓取，记录返回数据范围与完整度。

## 数据范围说明

S&P 500 价格接口将尽量支持请求最近十年的数据，实际可用区间受 Yahoo Finance 限制。使用当前成员名单回抓历史价格仍会有幸存者偏差；目前保留这一限制并明确记录，不宣称十年行情消除了该偏差。

## 抓取验证记录

2026-09-29 通过 `DailySp500().prices()` 实际抓取了一次当前名单的十年日线：名单 503 只，返回 1,221,537 行，覆盖 501 只，日期范围为 2016-09-29 至 2026-09-29。Yahoo Finance 对 ADSK 和 KLAC 返回无行情；接口会保留其他股票的数据并跳过无数据标的。日线结果只返回给调用方，本次没有保存行情缓存。

同日运行测试套件：133 项全部通过，包含组合类默认行为、成员缓存、A 股清洗逻辑和旧导入路径兼容性。Ruff 检查通过。
