from __future__ import annotations

import os

from dotenv import load_dotenv

# 本包作为 git 依赖被其他项目引用时, 这里的文件位置在安装后并不等于调用方项目的目录,
# 所以本模块不再基于 __file__ 派生任何数据/缓存路径 —— 所有涉及文件读写的函数都要求
# 调用方显式传入 path 参数。load_dotenv() 不带参数, 按 python-dotenv 的默认规则从当前
# 工作目录向上查找 .env (调用方项目自己的 .env, 而不是本包安装位置下的 .env)。
load_dotenv()

# SEC EDGAR 要求 User-Agent 里带真实姓名 + 邮箱; 参考 .env.example 复制一份 .env 自行填写,
# 这里的默认值只是占位符, 千万不要把真实身份信息硬编码提交到仓库里
SEC_IDENTITY = os.environ.get("SEC_IDENTITY", "Your Name your.email@example.com")
