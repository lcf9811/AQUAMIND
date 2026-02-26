"""
Core 模块 - 配置、日志、异常、LLM 接口
"""

from aquamind.core.config import settings
from aquamind.core.llm import get_model
from aquamind.core.logger import get_logger
from aquamind.core.exceptions import AquamindError

__all__ = [
    "settings",
    "get_model",
    "get_logger",
    "AquamindError",
]
