"""
Aquamind Supervisor - 主协调器

使用 Supervisor 模式协调所有子 Agent，实现 LLM 驱动的意图识别和任务分发。
采用将子 Agent 包装为 Tool 的轻量级实现方式。
支持实时数据查询和告警检测。
"""

from typing import Dict, Any, Optional, List
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from aquamind.core.llm import get_model
from aquamind.core.logger import get_logger
from aquamind.agents.toxicity import create_toxicity_agent
from aquamind.agents.turntable import create_turntable_agent
from aquamind.agents.mbr import create_mbr_agent
from aquamind.agents.regeneration import create_regeneration_agent
from aquamind.agents.diagnostic import create_diagnostic_agent
from aquamind.agents.feedback import create_feedback_agent

# 导入实时数据和告警工具
from aquamind.tools.realtime_data import (
    get_latest_plc_from_db,
    get_inhibition_trend,
    get_mbr_status,
)
from aquamind.tools.toxicity_predictor import (
    predict_toxicity_realtime,
    check_toxicity_alert,
)
# 导入 MQTT 控制工具
from aquamind.tools.mqtt_publisher import (
    set_turntable_frequency,
    control_turntable,
    control_valve,
    control_pump,
    control_fan,
    control_regeneration,
    one_key_start,
    send_plc_command,
    get_available_controls,
)

logger = get_logger(__name__)

# 全局 Agent 实例缓存
_agent_cache: Dict[str, Any] = {}


def _get_or_create_agent(agent_name: str, creator_func) -> Any:
    """获取或创建 Agent 实例（懒加载）"""
    if agent_name not in _agent_cache:
        logger.info(f"初始化 {agent_name} Agent...")
        _agent_cache[agent_name] = creator_func()
    return _agent_cache[agent_name]


def _invoke_agent(agent: Any, query: str) -> str:
    """调用 LangGraph Agent 并提取结果"""
    result = agent.invoke({"messages": [HumanMessage(content=query)]})
    # 提取最后一条消息的内容
    if "messages" in result and result["messages"]:
        last_message = result["messages"][-1]
        return last_message.content if hasattr(last_message, "content") else str(last_message)
    return str(result)


# ============ 子 Agent 包装工具 ============

@tool
def invoke_toxicity_agent(query: str) -> str:
    """调用毒性预测智能体分析和预测水质毒性。
    
    适用场景：
    - 预测水质毒性等级
    - 分析氨氮、温度、pH 对毒性的影响
    - 查询历史毒性数据和趋势
    - 评估水质风险
    
    Args:
        query: 用户关于水质毒性的问题或指令
    
    Returns:
        毒性分析结果
    """
    agent = _get_or_create_agent("toxicity", create_toxicity_agent)
    try:
        return _invoke_agent(agent, query)
    except Exception as e:
        logger.error(f"毒性预测 Agent 执行失败: {e}")
        return f"毒性预测分析失败: {str(e)}"


@tool
def invoke_turntable_agent(query: str) -> str:
    """调用转盘控制智能体管理旋转分配器。
    
    适用场景：
    - 控制转盘速度和位置
    - 调整曝气参数
    - 优化生物处理效率
    - 诊断转盘运行状态
    
    Args:
        query: 用户关于转盘控制的问题或指令
    
    Returns:
        转盘控制执行结果
    """
    agent = _get_or_create_agent("turntable", create_turntable_agent)
    try:
        return _invoke_agent(agent, query)
    except Exception as e:
        logger.error(f"转盘控制 Agent 执行失败: {e}")
        return f"转盘控制失败: {str(e)}"


@tool
def invoke_mbr_agent(query: str) -> str:
    """调用 MBR 膜系统智能体管理膜生物反应器。
    
    适用场景：
    - 监控膜污染状态
    - 控制反冲洗流程
    - 调整跨膜压差
    - 优化膜通量参数
    
    Args:
        query: 用户关于 MBR 系统的问题或指令
    
    Returns:
        MBR 系统操作结果
    """
    agent = _get_or_create_agent("mbr", create_mbr_agent)
    try:
        return _invoke_agent(agent, query)
    except Exception as e:
        logger.error(f"MBR 控制 Agent 执行失败: {e}")
        return f"MBR 系统控制失败: {str(e)}"


@tool
def invoke_regeneration_agent(query: str) -> str:
    """调用活性炭再生智能体管理炭再生流程。
    
    适用场景：
    - 评估活性炭吸附饱和度
    - 控制再生加热温度
    - 管理再生周期
    - 监控再生效果
    
    Args:
        query: 用户关于活性炭再生的问题或指令
    
    Returns:
        再生控制执行结果
    """
    agent = _get_or_create_agent("regeneration", create_regeneration_agent)
    try:
        return _invoke_agent(agent, query)
    except Exception as e:
        logger.error(f"再生控制 Agent 执行失败: {e}")
        return f"活性炭再生控制失败: {str(e)}"


@tool
def invoke_diagnostic_agent(query: str) -> str:
    """调用系统诊断智能体进行故障诊断和健康检查。
    
    适用场景：
    - 诊断系统异常
    - 分析报警原因
    - 执行健康检查
    - 提供维护建议
    
    Args:
        query: 用户关于系统诊断的问题或指令
    
    Returns:
        诊断分析结果
    """
    agent = _get_or_create_agent("diagnostic", create_diagnostic_agent)
    try:
        return _invoke_agent(agent, query)
    except Exception as e:
        logger.error(f"诊断 Agent 执行失败: {e}")
        return f"系统诊断失败: {str(e)}"


@tool
def invoke_feedback_agent(query: str) -> str:
    """调用反馈优化智能体分析系统反馈并优化运行策略。
    
    适用场景：
    - 分析运行数据趋势
    - 提供优化建议
    - 调整控制策略
    - 生成性能报告
    
    Args:
        query: 用户关于系统优化的问题或指令
    
    Returns:
        优化建议或分析结果
    """
    agent = _get_or_create_agent("feedback", create_feedback_agent)
    try:
        return _invoke_agent(agent, query)
    except Exception as e:
        logger.error(f"反馈 Agent 执行失败: {e}")
        return f"反馈分析失败: {str(e)}"


# ============ Supervisor 系统提示词 ============

SUPERVISOR_SYSTEM_PROMPT = """你是 Aquamind 智能水处理系统的主协调器 (Supervisor)。

## 你的职责
1. 理解用户的意图和需求
2. 将任务分发给合适的专业智能体处理
3. 整合各智能体的结果，给出完整的回答
4. 在需要时协调多个智能体协同工作

## 可用的专业智能体

1. **毒性预测智能体** (`invoke_toxicity_agent`)
   - 预测水质毒性等级
   - 分析氨氮、温度、pH 的影响
   - 查询历史毒性数据
   - **支持实时数据预测和告警检测**

2. **转盘控制智能体** (`invoke_turntable_agent`)
   - 控制旋转分配器
   - 调整曝气参数
   - 优化生物处理

3. **MBR 膜系统智能体** (`invoke_mbr_agent`)
   - 监控膜污染
   - 控制反冲洗
   - 管理跨膜压差

4. **活性炭再生智能体** (`invoke_regeneration_agent`)
   - 评估吸附饱和度
   - 控制再生流程
   - 监控再生效果

5. **系统诊断智能体** (`invoke_diagnostic_agent`)
   - 故障诊断
   - 健康检查
   - 维护建议

6. **反馈优化智能体** (`invoke_feedback_agent`)
   - 趋势分析
   - 策略优化
   - 性能报告

## 实时数据工具 (直接可用)

- `get_latest_plc_from_db`: 获取最新 PLC 数据 (每 20 秒更新)
- `get_inhibition_trend`: 获取抑制率历史趋势
- `get_mbr_status`: 获取 MBR 膜系统状态
- `predict_toxicity_realtime`: 基于实时数据预测毒性
- `check_toxicity_alert`: 检查告警状态

## 设备控制工具 (直接可用，通过 MQTT 下发)

- `set_turntable_frequency`: 设置转盘频率 (1/2/3, 5-50Hz)
- `control_turntable`: 启停转盘
- `control_valve`: 控制阀门 (VA01-VA14)
- `control_pump`: 控制泵 (B01-B06)
- `control_fan`: 启停风机
- `control_regeneration`: 启停再生系统
- `one_key_start`: 一键启动系统
- `send_plc_command`: 发送自定义 PLC 指令
- `get_available_controls`: 查看所有可控变量

## 工作原则

1. **意图识别**：仔细分析用户问题，确定需要调用哪些智能体
2. **任务分解**：复杂任务可能需要多个智能体协作
3. **结果整合**：将各智能体的输出整合为清晰、连贯的回答
4. **主动询问**：如果信息不足，主动向用户询问必要参数

## 回答格式

- 简洁明了，直接回答用户问题
- 如有具体数值或建议，清晰列出
- 如涉及风险或警告，明确标注
- 对于控制操作，说明执行状态

现在请处理用户的请求。
"""


def create_aquamind_supervisor(
    model: BaseChatModel = None,
    verbose: bool = True,
    max_iterations: int = 10,
) -> Any:
    """创建 Aquamind 主协调器 (Supervisor)
    
    Args:
        model: 语言模型实例，默认使用配置中的模型
        verbose: 是否输出详细日志
        max_iterations: 最大迭代次数
    
    Returns:
        配置好的 Supervisor CompiledGraph
    """
    if model is None:
        model = get_model(temperature=0.5)  # Supervisor 需要一定创造性
    
    # 收集所有子 Agent 工具
    tools = [
        # 子 Agent 工具
        invoke_toxicity_agent,
        invoke_turntable_agent,
        invoke_mbr_agent,
        invoke_regeneration_agent,
        invoke_diagnostic_agent,
        invoke_feedback_agent,
        # 实时数据工具 (直接调用，无需经过子 Agent)
        get_latest_plc_from_db,
        get_inhibition_trend,
        get_mbr_status,
        predict_toxicity_realtime,
        check_toxicity_alert,
        # MQTT 控制工具 (直接下发 PLC 指令)
        set_turntable_frequency,
        control_turntable,
        control_valve,
        control_pump,
        control_fan,
        control_regeneration,
        one_key_start,
        send_plc_command,
        get_available_controls,
    ]
    
    # 创建 Supervisor Agent（使用 LangGraph）
    supervisor = create_react_agent(
        model=model,
        tools=tools,
        prompt=SUPERVISOR_SYSTEM_PROMPT,
    )
    
    logger.info("Aquamind Supervisor 初始化完成")
    return supervisor


class AquamindSupervisor:
    """Aquamind 主协调器类封装
    
    提供更友好的 API 接口和状态管理。
    """
    
    def __init__(
        self,
        model: BaseChatModel = None,
        verbose: bool = True,
        max_iterations: int = 10,
    ):
        """初始化 Supervisor
        
        Args:
            model: 语言模型实例
            verbose: 是否输出详细日志
            max_iterations: 最大迭代次数
        """
        self.executor = create_aquamind_supervisor(
            model=model,
            verbose=verbose,
            max_iterations=max_iterations,
        )
        self._conversation_history: List[Dict[str, str]] = []
        logger.info("AquamindSupervisor 实例创建成功")
    
    def chat(self, message: str) -> str:
        """处理用户消息
        
        Args:
            message: 用户输入消息
        
        Returns:
            系统响应
        """
        logger.info(f"收到用户消息: {message[:50]}...")
        
        try:
            response = _invoke_agent(self.executor, message)
            
            # 记录对话历史
            self._conversation_history.append({
                "role": "user",
                "content": message,
            })
            self._conversation_history.append({
                "role": "assistant",
                "content": response,
            })
            
            return response
            
        except Exception as e:
            logger.error(f"处理消息失败: {e}")
            return f"抱歉，处理您的请求时发生错误: {str(e)}"
    
    def get_history(self) -> List[Dict[str, str]]:
        """获取对话历史"""
        return self._conversation_history.copy()
    
    def clear_history(self):
        """清除对话历史"""
        self._conversation_history.clear()
        logger.info("对话历史已清除")
    
    def reset_agents(self):
        """重置所有子 Agent 缓存"""
        global _agent_cache
        _agent_cache.clear()
        logger.info("所有子 Agent 缓存已清除")


# 便捷函数
def quick_chat(message: str) -> str:
    """快速对话函数（一次性使用）
    
    Args:
        message: 用户消息
    
    Returns:
        系统响应
    """
    supervisor = create_aquamind_supervisor(verbose=False)
    return _invoke_agent(supervisor, message)
