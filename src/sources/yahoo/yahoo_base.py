from __future__ import annotations

from abc import ABC, abstractmethod

@abstractmethod
class YahooBase(ABC):

    """Yahoo 数据抓取 基类
    
    包含: 
        1. 加载标的
        2. 按照要求抓取数据
        3. 顺手存入 parquet 文件
        
    """
    