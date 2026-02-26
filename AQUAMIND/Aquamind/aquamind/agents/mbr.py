"""
MBR 控制智能体
"""

from typing import Any
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from aquamind.core.llm import get_model
from aquamind.agents.base import get_agent_prompt
from aquamind.tools.plc_commands import generate_mbr_command
from aquamind.tools.knowledge_query import query_expert_rule, query_equipment_info


def create_mbr_agent(model: BaseChatModel = None) -> Any:
    """创建 MBR 控制智能体"""
    if model is None:
        model = get_model(temperature=0.3)
    
    tools = [generate_mbr_command, query_expert_rule, query_equipment_info]
    system_prompt = get_agent_prompt("mbr")
    
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
    )
