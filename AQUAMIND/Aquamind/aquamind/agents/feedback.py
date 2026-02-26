"""反馈智能体
"""

from typing import Any
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langgraph.prebuilt import create_react_agent

from aquamind.core.llm import get_model
from aquamind.agents.base import get_agent_prompt


# 反馈存储
_feedback_history = []


@tool
def record_feedback(feedback_content: str, feedback_type: str = "general") -> dict:
    """
    记录用户反馈。
    
    Args:
        feedback_content: 反馈内容
        feedback_type: 反馈类型 (general/suggestion/issue/praise)
    
    Returns:
        记录结果
    """
    from datetime import datetime
    
    record = {
        "content": feedback_content,
        "type": feedback_type,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id": len(_feedback_history) + 1
    }
    _feedback_history.append(record)
    
    return {
        "status": "success",
        "message": f"反馈已记录 (ID: {record['id']})",
        "record": record
    }


@tool
def get_feedback_summary() -> dict:
    """
    获取反馈统计摘要。
    
    Returns:
        反馈统计信息
    """
    if not _feedback_history:
        return {
            "total_count": 0,
            "message": "暂无反馈记录"
        }
    
    type_counts = {}
    for fb in _feedback_history:
        fb_type = fb.get("type", "general")
        type_counts[fb_type] = type_counts.get(fb_type, 0) + 1
    
    return {
        "total_count": len(_feedback_history),
        "type_distribution": type_counts,
        "recent_feedbacks": _feedback_history[-5:]
    }


def create_feedback_agent(model: BaseChatModel = None) -> Any:
    """创建反馈智能体"""
    if model is None:
        model = get_model(temperature=0.5)
    
    tools = [record_feedback, get_feedback_summary]
    system_prompt = get_agent_prompt("feedback")
    
    return create_react_agent(
        model=model,
        tools=tools,
        prompt=system_prompt,
    )
