## 资源加载配置示例

1. Yahoo 数据源抓取加存 parquet 文件加以 Multindex 形式读取数据
2. universe 数据抓取, 以 csv 文件格式保存
3. SEC EDGAR 数据抓取
---
### 快速开始
推荐使用`uv` 管理环境
```bash
uv sync
```

测试代码是否有效
```bash
uv run python main.py
```

运行自动化测试
```bash
uv run pytest
```

---
### 作为 GitHub 包在其他项目中使用

本仓库不发布到 PyPI，只放在 GitHub 上，通过 git 依赖的方式被其他项目引用即可。

**在使用 `uv` 管理的项目中：**
```bash
uv add git+https://github.com/20070316lbw-netizen/sources.git
```

**在使用 `pip` 的项目中：**
```bash
pip install git+https://github.com/20070316lbw-netizen/sources.git
```

建议固定到某个 commit 或 tag，避免 `main` 分支更新后被引用方意外拉取到不兼容的改动，例如：
```bash
uv add git+https://github.com/20070316lbw-netizen/sources.git@<commit-or-tag>
```

安装后即可直接导入使用：
```python
from sources.yahoo.fetch import fetch_prices, save_prices
from sources.yahoo.load import load_prices
from sources.universe.fetch import fetch_sp500_universe, load_cached_universe
from sources.sec.fetch import init_edgar, fetch_filing_metrics, fetch_sp500_fundamentals, to_daily_pit
from sources.error import QuantLabError, DataFetchError, YahooFetchError, EdgarFetchError
```

注意：使用 `sources.sec` 模块前需要按 `.env.example` 的说明配置 `SEC_IDENTITY`（SEC EDGAR 要求 User-Agent 携带真实姓名与邮箱），否则请求可能被拒绝。

**关于路径**：`sources.config` 里不再有基于包自身安装位置 (`Path(__file__)`) 派生的路径——一旦作为 git 依赖被其他项目安装，包文件所在位置和调用方项目目录是两回事，用包安装位置拼出来的路径在调用方那边毫无意义。所有涉及文件读写的函数（`load_cached_universe` / `load_sp500_list` / `save_prices` / `load_prices` / `save_fundamentals` / `load_fundamentals` / `fetch_sec` 的 `save_path` 等）的 `path` 参数都是**相对路径**，默认值形如 `"data/sp500_ticker.csv"`——按 Python 的一般约定，相对路径以调用方进程的当前工作目录为起点，也就是调用方项目自己在 `data/` 下的缓存位置（前提是像 `uv run python xxx.py` 这样从项目根目录运行）。不想用默认位置的话，随时可以传入自己的 `path=...` 覆盖。