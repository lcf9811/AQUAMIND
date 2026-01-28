"""Agent package initialization

Aquamind 智能体模块

包含以下智能体:
- MainOrchestrator: 总智能体/协调器
- ToxicityAgent: 毒性预测智能体
- TurntableAgent: 转盘控制智能体
- RegenerationAgent: 再生控制智能体
- MBRAgent: MBR膜控制智能体
- DiagnosticAgent: 诊断评估智能体
- FeedbackAgent: 反馈智能体
- ControlAgent: 工艺控制智能体(兼容旧版)
"""

from .MainOrchestrator import MainOrchestrator
from .ToxicityAgent import ToxicityAgent
from .TurntableAgent import TurntableAgent
from .RegenerationAgent import RegenerationAgent
from .MBRAgent import MBRAgent
from .DiagnosticAgent import DiagnosticAgent
from .FeedbackAgent import FeedbackAgent
from .ControlAgent import ControlAgent

__all__ = [
    'MainOrchestrator',
    'ToxicityAgent',
    'TurntableAgent',
    'RegenerationAgent',
    'MBRAgent',
    'DiagnosticAgent',
    'FeedbackAgent',
    'ControlAgent'
]

