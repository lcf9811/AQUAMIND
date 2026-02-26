"""诊断智能体
"""

from typing import Any
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent

from aquamind.core.llm import get_model
from aquamind.agents.base import get_agent_prompt
from aquamind.tools.knowledge_query import (
    query_expert_rule,
    query_equipment_info,
    query_plc_variable,
)


def create_diagnostic_agent(model: BaseChatModel = None) -> Any:
    """创建诊断智能体"""
    if model is None:
        model = get_model(temperature=0.3)
    
    tools = [query_expert_rule, query_equipment_info, query_plc_variable]
    system_prompt = get_agent_prompt("diagnostic")
    
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
    )
