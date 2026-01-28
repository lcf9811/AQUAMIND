"""
Aquamind Systems - 智能水质预测与控制系统
===========================================

一个基于LangChain的多智能体水处理系统，专为污水处理厂设计。

主要功能:
- 水质毒性预测
- 工艺参数控制
- 系统健康诊断
- 实时决策支持

快速开始:
    >>> from Aquamind import MainOrchestrator
    >>> orchestrator = MainOrchestrator()
    >>> result = orchestrator.run("请预测毒性，氨氮20mg/L")

"""

__version__ = "2.0.0"
__author__ = "Aquamind Team"
__license__ = "MIT"

# 核心配置
from .config import (
    llm_config,
    system_config,
    log_config,
    agent_config,
    validate_config
)

# 日志系统
from .logger import (
    get_logger,
    PerformanceLogger,
    AgentLogger
)

# 异常系统
from .exceptions import (
    AquamindException,
    ConfigurationError,
    LLMError,
    AgentError,
    DataError,
    ControlError
)

# 核心组件
from .LLM.llm_interface import LLMInterface
from .Knowledge.knowledge_base import get_knowledge_base

# 智能体
from .Agent.MainOrchestrator import MainOrchestrator
from .Agent.ToxicityAgent import ToxicityAgent
from .Agent.ControlAgent import ControlAgent
from .Agent.TurntableAgent import TurntableAgent
from .Agent.MBRAgent import MBRAgent
from .Agent.RegenerationAgent import RegenerationAgent
from .Agent.DiagnosticAgent import DiagnosticAgent
from .Agent.FeedbackAgent import FeedbackAgent

# 工具
from .Tool.predict_toxicity import PredictToxicityTool

# 暴露公共API
__all__ = [
    # 版本信息
    "__version__",
    "__author__",
    "__license__",
    
    # 配置
    "llm_config",
    "system_config",
    "log_config",
    "agent_config",
    "validate_config",
    
    # 日志
    "get_logger",
    "PerformanceLogger",
    "AgentLogger",
    
    # 异常
    "AquamindException",
    "ConfigurationError",
    "LLMError",
    "AgentError",
    "DataError",
    "ControlError",
    
    # 核心组件
    "LLMInterface",
    "get_knowledge_base",
    
    # 智能体
    "MainOrchestrator",
    "ToxicityAgent",
    "ControlAgent",
    "TurntableAgent",
    "MBRAgent",
    "RegenerationAgent",
    "DiagnosticAgent",
    "FeedbackAgent",
    
    # 工具
    "PredictToxicityTool",
]


def get_version():
    """获取系统版本"""
    return __version__


def initialize():
    """初始化系统"""
    logger = get_logger("aquamind")
    logger.info(f"Aquamind Systems v{__version__} 初始化中...")
    
    # 验证配置
    if validate_config():
        logger.info("配置验证通过")
        return True
    else:
        logger.error("配置验证失败")
        return False


# 自动初始化
# initialize()  # 可选：如果希望在导入时自动初始化，取消注释此行