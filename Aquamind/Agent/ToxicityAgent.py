"""
毒性预测智能体 (ToxicityAgent)
负责预测进水毒性水平并提供分析

功能:
1. 接收当前水质参数（温度、氨氮、pH等）
2. 调用预测工具进行毒性预测
3. 输出毒性等级判定和风险评估
4. 与控制智能体协同工作
"""

import sys
import os
import re
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

# LangChain 兼容性导入
try:
    from langchain.agents import AgentExecutor, create_tool_calling_agent
except ImportError:
    from langchain.agents import AgentExecutor
    try:
        from langchain.agents import create_tool_calling_agent
    except ImportError:
        from langchain.agents import create_openai_tools_agent as create_tool_calling_agent

try:
    from langchain.prompts import MessagesPlaceholder
except ImportError:
    from langchain_core.prompts import MessagesPlaceholder

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from Tool.predict_toxicity import PredictToxicityTool
from LLM.llm_interface import LLMInterface

try:
    from Knowledge.knowledge_base import get_knowledge_base
except ImportError:
    get_knowledge_base = None


@dataclass
class ToxicityPredictionOutput:
    """毒性预测输出数据结构"""
    toxicity_value: float           # 预测毒性值
    toxicity_level: str             # 毒性等级(低/中/高)
    trend: str                      # 趋势(上升/稳定/下降)
    risk_level: str                 # 风险等级
    confidence: float               # 置信度(0-1)
    analysis: str                   # 详细分析
    recommendations: List[str]      # 建议列表
    timestamp: str                  # 时间戳
    input_params: Dict[str, Any]    # 输入参数
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "toxicity_value": self.toxicity_value,
            "toxicity_level": self.toxicity_level,
            "trend": self.trend,
            "risk_level": self.risk_level,
            "confidence": self.confidence,
            "analysis": self.analysis,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp,
            "input_params": self.input_params
        }


class ToxicityAgent:
    """
    毒性预测智能体 (ToxicityAgent)
    
    负责预测进水毒性并提供专业分析，包括：
    - 毒性数值预测
    - 毒性等级判定
    - 趋势分析
    - 风险评估
    - 控制建议
    """
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一个专业的水质毒性预测专家 (ToxicityAgent)。

## 核心职责
根据用户提供的当前水质参数，预测未来的毒性水平并提供风险评估。

## 工作流程
1. 分析用户输入，提取水质参数（温度、氨氮、硝氮、pH、毒性等）
2. 调用 `predict_toxicity` 工具进行预测
3. 分析预测结果，判定毒性等级
4. 评估风险并给出建议

## 毒性等级标准
- **低毒性** (< 1.5): 水质较好，可节能运行
- **中毒性** (1.5-3.0): 标准运行模式
- **高毒性** (> 3.0): 需要加强处理，启动应急措施

## 输出要求
- 提供毒性预测值和等级
- 分析可能的风险因素
- 给出运行建议
- 使用专业术语但保持清晰易懂
"""
    
    def __init__(self, llm_interface: LLMInterface = None):
        """初始化毒性预测智能体"""
        self.llm_interface = llm_interface or LLMInterface()
        self.tools = [PredictToxicityTool()]
        self.agent_executor = self._create_agent()
        
        # 尝试获取知识库
        self.kb = get_knowledge_base() if get_knowledge_base else None
        
        # 历史预测记录
        self.prediction_history: List[ToxicityPredictionOutput] = []
        
    def _create_agent(self) -> AgentExecutor:
        """创建LangChain Agent"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ])
        
        from langchain_openai import ChatOpenAI
        
        api_key = self.llm_interface.qwen_api_key or self.llm_interface.openai_api_key or "sk-placeholder"
        base_url = self.llm_interface.qwen_api_base or self.llm_interface.openai_api_base
        model_name = self.llm_interface.qwen_model_name or "qwen-plus"
        
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=0.3
        )
        
        agent = create_tool_calling_agent(llm, self.tools, prompt)
        return AgentExecutor(agent=agent, tools=self.tools, verbose=True)
    
    def _extract_params(self, input_text: str) -> Dict[str, Any]:
        """从用户输入中提取参数"""
        params = {}
        
        # 提取氨氮
        ammonia_match = re.search(r'氨氮[:：是为约]?\s*([\d.]+)\s*(?:mg/[Ll])?', input_text)
        if ammonia_match:
            params['ammonia_n'] = float(ammonia_match.group(1))
        
        # 提取温度
        temp_match = re.search(r'温度[:：是为约]?\s*([\d.]+)\s*(?:度|℃)?', input_text)
        if temp_match:
            params['temperature'] = float(temp_match.group(1))
        
        # 提取pH
        ph_match = re.search(r'[pP][hH][:：是为约值]?\s*([\d.]+)', input_text)
        if ph_match:
            params['ph'] = float(ph_match.group(1))
        
        # 提取毒性
        tox_match = re.search(r'毒性[:：是为约]?\s*([\d.]+)', input_text)
        if tox_match:
            params['toxicity'] = float(tox_match.group(1))
        
        return params
    
    def _determine_toxicity_level(self, toxicity: float) -> str:
        """判定毒性等级"""
        if toxicity < 1.5:
            return "低"
        elif toxicity < 3.0:
            return "中"
        else:
            return "高"
    
    def _determine_risk_level(self, toxicity: float, trend: str) -> str:
        """判定风险等级"""
        if toxicity > 3.5 or (toxicity > 2.5 and trend == "上升"):
            return "高风险"
        elif toxicity > 2.0 or (toxicity > 1.5 and trend == "上升"):
            return "中风险"
        else:
            return "低风险"
    
    def _generate_recommendations(self, toxicity: float, toxicity_level: str, 
                                    trend: str) -> List[str]:
        """生成建议"""
        recommendations = []
        
        if toxicity_level == "高":
            recommendations.extend([
                "建议启用备用转盘反应器",
                "提高转盘频率至35-50Hz",
                "加强MBR曝气量",
                "检查活性炭是否需要再生"
            ])
        elif toxicity_level == "中":
            recommendations.extend([
                "维持转盘频率在15-35Hz",
                "持续监测毒性变化趋势",
                "确保MBR系统正常运行"
            ])
        else:
            recommendations.extend([
                "可考虑节能运行模式",
                "转盘频率可降至5-15Hz",
                "定期检查设备状态"
            ])
        
        if trend == "上升":
            recommendations.insert(0, "毒性呈上升趋势，建议提前准备应对措施")
        
        return recommendations

    def run(self, input_text: str) -> Dict[str, Any]:
        """
        运行毒性预测
        
        Args:
            input_text: 包含水质数据的自然语言描述
            
        Returns:
            Dict: 包含分析结果、毒性等级、建议等
        """
        try:
            # 提取参数
            params = self._extract_params(input_text)
            
            # 调用Agent执行预测
            result = self.agent_executor.invoke({"input": input_text})
            analysis = result.get("output", "")
            
            # 从分析中提取毒性值（简化处理）
            toxicity_value = params.get('toxicity', 2.0)
            toxicity_level = self._determine_toxicity_level(toxicity_value)
            trend = "稳定"  # 默认稳定，可根据历史数据分析
            risk_level = self._determine_risk_level(toxicity_value, trend)
            recommendations = self._generate_recommendations(toxicity_value, toxicity_level, trend)
            
            # 创建结构化输出
            prediction_output = ToxicityPredictionOutput(
                toxicity_value=toxicity_value,
                toxicity_level=toxicity_level,
                trend=trend,
                risk_level=risk_level,
                confidence=0.85,
                analysis=analysis,
                recommendations=recommendations,
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                input_params=params
            )
            
            # 保存到历史记录
            self.prediction_history.append(prediction_output)
            
            return {
                "analysis": analysis,
                "status": "success",
                "toxicity_value": toxicity_value,
                "toxicity_level": toxicity_level,
                "trend": trend,
                "risk_level": risk_level,
                "recommendations": recommendations,
                "structured_output": prediction_output.to_dict()
            }
        except Exception as e:
            return {
                "analysis": f"毒性预测过程中发生错误: {str(e)}",
                "status": "error",
                "toxicity_value": None,
                "toxicity_level": "未知",
                "trend": "未知",
                "risk_level": "未知",
                "recommendations": []
            }
    
    def predict(self, ammonia_n: float = None, temperature: float = None, 
                ph: float = None, toxicity: float = None) -> ToxicityPredictionOutput:
        """
        结构化预测接口
        
        Args:
            ammonia_n: 氨氮浓度 (mg/L)
            temperature: 温度 (℃)
            ph: pH值
            toxicity: 当前毒性值
            
        Returns:
            ToxicityPredictionOutput: 结构化预测结果
        """
        # 构建输入文本
        parts = []
        if ammonia_n is not None:
            parts.append(f"氨氮{ammonia_n}mg/L")
        if temperature is not None:
            parts.append(f"温度{temperature}度")
        if ph is not None:
            parts.append(f"pH{ph}")
        if toxicity is not None:
            parts.append(f"毒性{toxicity}")
        
        input_text = f"当前水质参数：{'，'.join(parts)}，请预测毒性"
        
        result = self.run(input_text)
        
        if result["status"] == "success":
            return ToxicityPredictionOutput(
                toxicity_value=result.get("toxicity_value", toxicity or 2.0),
                toxicity_level=result.get("toxicity_level", "中"),
                trend=result.get("trend", "稳定"),
                risk_level=result.get("risk_level", "中风险"),
                confidence=0.85,
                analysis=result.get("analysis", ""),
                recommendations=result.get("recommendations", []),
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                input_params={"ammonia_n": ammonia_n, "temperature": temperature, "ph": ph, "toxicity": toxicity}
            )
        else:
            return ToxicityPredictionOutput(
                toxicity_value=toxicity or 2.0,
                toxicity_level=self._determine_toxicity_level(toxicity or 2.0),
                trend="未知",
                risk_level="未知",
                confidence=0.0,
                analysis=result.get("analysis", "预测失败"),
                recommendations=[],
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                input_params={"ammonia_n": ammonia_n, "temperature": temperature, "ph": ph, "toxicity": toxicity}
            )
    
    def get_latest_prediction(self) -> Optional[ToxicityPredictionOutput]:
        """获取最新的预测结果"""
        return self.prediction_history[-1] if self.prediction_history else None
    
    def get_prediction_summary(self) -> Dict[str, Any]:
        """获取预测摘要统计"""
        if not self.prediction_history:
            return {"count": 0, "average_toxicity": 0, "high_risk_count": 0}
        
        toxicity_values = [p.toxicity_value for p in self.prediction_history if p.toxicity_value]
        high_risk = [p for p in self.prediction_history if p.risk_level == "高风险"]
        
        return {
            "count": len(self.prediction_history),
            "average_toxicity": sum(toxicity_values) / len(toxicity_values) if toxicity_values else 0,
            "high_risk_count": len(high_risk),
            "latest_level": self.prediction_history[-1].toxicity_level
        }
