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