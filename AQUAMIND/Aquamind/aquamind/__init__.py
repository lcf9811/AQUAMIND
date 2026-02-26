"""
Aquamind - 智能水处理系统

基于 LangChain 的多智能体水处理控制系统。
"""

__version__ = "2.0.0"
__author__ = "Aquamind Team"

from aquamind.agents.supervisor import (
    AquamindSupervisor,
    create_aquamind_supervisor,
    quick_chat,
)

__all__ = [
    "AquamindSupervisor",
    "create_aquamind_supervisor",
    "quick_chat",
    "__version__",
]
