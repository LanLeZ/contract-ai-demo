"""
app.services 包初始化。

说明：
- 本项目内各模块一般使用 `from app.services.xxx import Yyy` 的方式直接导入子模块。
- 为避免在导入 `app.services.*` 时触发额外依赖（例如 LLM/向量库）加载，本文件保持轻量，不做子模块聚合导入。
"""

__all__: list[str] = []

