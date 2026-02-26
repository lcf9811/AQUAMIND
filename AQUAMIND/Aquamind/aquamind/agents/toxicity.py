"""毒性预测智能体

使用 LangGraph create_react_agent API 创建。
支持实时数据预测和告警检测。
"""

from typing import Any
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from aquamind.core.llm import get_model
from aquamind.agents.base import get_agent_prompt
from aquamind.tools.toxicity_predictor import (
    predict_toxicity, 
    get_historical_stats,
    predict_toxicity_realtime,
    check_toxicity_alert,
)
from aquamind.tools.realtime_data import (
    get_latest_plc_from_db,
    get_inhibition_trend,
    get_mbr_status,
)


def create_toxicity_agent(model: BaseChatModel = None) -> Any:
    """
    创建毒性预测智能体
    
    Args:
        model: LLM 模型实例，默认使用配置的模型
    
    Returns:
        CompiledGraph: 可执行的 Agent
    """
    if model is None:
        model = get_model(temperature=0.3)
    
    # 定义工具 - 包含实时数据和告警功能
    tools = [
        # 实时数据工具
        predict_toxicity_realtime,     # 基于实时数据预测
        check_toxicity_alert,          # 告警检测
        get_latest_plc_from_db,        # 获取最新 PLC 数据
        get_inhibition_trend,          # 抑制率趋势
        get_mbr_status,                # MBR 状态
        # 历史数据工具
        predict_toxicity,              # 基于参数预测
        get_historical_stats,          # 历史统计
    ]
    
    # 获取系统提示词
    system_prompt = get_agent_prompt("toxicity")
    
    # 创建 Agent（使用 LangGraph）
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
    )
