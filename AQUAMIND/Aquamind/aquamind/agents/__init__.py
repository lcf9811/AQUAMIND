"""
Agents 模块 - 智能体定义

使用 LangChain create_agent + Supervisor 模式实现多智能体系统。
"""

from aquamind.agents.supervisor import create_aquamind_supervisor, AquamindSupervisor
from aquamind.agents.toxicity import create_toxicity_agent
from aquamind.agents.turntable import create_turntable_agent
from aquamind.agents.mbr import create_mbr_agent
from aquamind.agents.regeneration import create_regeneration_agent
from aquamind.agents.diagnostic import create_diagnostic_agent
from aquamind.agents.feedback import create_feedback_agent

__all__ = [
    # Supervisor
    "create_aquamind_supervisor",
    "AquamindSupervisor",
    # 子 Agent 创建函数
    "create_toxicity_agent",
    "create_turntable_agent",
    "create_mbr_agent",
    "create_regeneration_agent",
    "create_diagnostic_agent",
    "create_feedback_agent",
]
