"""转盘控制智能体

支持生成控制命令和通过 MQTT 直接控制转盘设备。
"""

from typing import Any
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from aquamind.core.llm import get_model
from aquamind.agents.base import get_agent_prompt
from aquamind.tools.plc_commands import generate_turntable_command
from aquamind.tools.knowledge_query import query_expert_rule, query_equipment_info
from aquamind.tools.mqtt_publisher import (
    set_turntable_frequency,
    control_turntable,
    control_fan,
)


def create_turntable_agent(model: BaseChatModel = None) -> Any:
    """创建转盘控制智能体"""
    if model is None:
        model = get_model(temperature=0.3)
    
    tools = [
        # 控制命令生成
        generate_turntable_command,
        # MQTT 直接控制
        set_turntable_frequency,
        control_turntable,
        control_fan,
        # 知识查询
        query_expert_rule,
        query_equipment_info,
    ]
    system_prompt = get_agent_prompt("turntable")
    
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
    )
