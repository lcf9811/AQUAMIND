"""
转盘智能体 (TurntableAgent)
负责活性炭转盘吸附反应器的智能控制决策

功能:
1. 根据毒性预测结果生成转盘控制参数
2. 计算最优运行频率和转速
3. 判断是否需要启用备用线路
4. 生成可直接下发给PLC的控制指令
"""

import sys
import os
import math
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from datetime import datetime

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from LLM.llm_interface import LLMInterface
from Knowledge.knowledge_base import get_knowledge_base


@dataclass
class TurntableControlOutput:
    """转盘控制输出数据结构"""
    frequency_1: float          # 1号转盘频率 (Hz)
    frequency_2: float          # 2号转盘频率 (Hz)
    frequency_3: float          # 3号转盘频率 (Hz, 备用)
    rpm_1: float                # 1号转盘转速 (rpm)
    rpm_2: float                # 2号转盘转速 (rpm)
    rpm_3: float                # 3号转盘转速 (rpm)
    active_reactors: int        # 活跃反应器数量
    standby_triggered: bool     # 是否触发备用
    expected_removal_rate: float  # 预计去除率 (%)
    decision_reason: str        # 决策原因
    confidence: float           # 置信度
    timestamp: str              # 时间戳
    
    def to_plc_command(self) -> Dict[str, Any]:
        """转换为PLC命令格式"""
        return {
            "CMD_TYPE": "TURNTABLE_CONTROL",
            "TIMESTAMP": self.timestamp,
            "TURNTABLE_1": {
                "FREQ_SETPOINT": round(self.frequency_1, 1),
                "ENABLE": self.frequency_1 > 0
            },
            "TURNTABLE_2": {
                "FREQ_SETPOINT": round(self.frequency_2, 1),
                "ENABLE": self.frequency_2 > 0
            },
            "TURNTABLE_3": {
                "FREQ_SETPOINT": round(self.frequency_3, 1),
                "ENABLE": self.standby_triggered
            },
            "ALARM_LEVEL": 3 if self.standby_triggered else (2 if self.frequency_1 > 35 else 1)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "frequency_1": self.frequency_1,
            "frequency_2": self.frequency_2,
            "frequency_3": self.frequency_3,
            "rpm_1": self.rpm_1,
            "rpm_2": self.rpm_2,
            "rpm_3": self.rpm_3,
            "active_reactors": self.active_reactors,
            "standby_triggered": self.standby_triggered,
            "expected_removal_rate": self.expected_removal_rate,
            "decision_reason": self.decision_reason,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "plc_command": self.to_plc_command()
        }


class TurntableAgent:
    """
    转盘智能体
    
    负责活性炭转盘吸附反应器的智能控制，包括：
    - 频率/转速控制
    - 多反应器协调
    - 备用线路触发
    - 吸附效率优化
    """
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一位专业的活性炭转盘吸附反应器控制工程师 (TurntableAgent)。

你的核心职责是根据毒性预测智能体提供的毒性分析结果，生成最优的转盘运行控制参数。

## 设备概况
- 系统配置：3条转盘线路（2条常规运行 + 1条备用）
- 水箱尺寸：29.7cm × 27.7cm × 35cm (水深)
- 频率范围：0-50 Hz
- 活性炭：10-20目椰壳活性炭
- 转速换算：4极电机，rpm = 频率 × 30

## 控制原则
1. **低毒性 (< 1.5)**: 频率 5-15 Hz，2台运行，节能优先
2. **中毒性 (1.5-3.0)**: 频率 15-35 Hz，2台运行，标准模式
3. **高毒性 (> 3.0)**: 频率 35-50 Hz，3台运行，启用备用

## 趋势调整
- 上升趋势：频率 +15%
- 稳定趋势：保持当前
- 下降趋势：频率 -10%

请基于以上原则，结合当前毒性情况，给出专业的控制建议和参数设定。
输出应包含具体的频率设定值、预期效果和操作理由。"""

    def __init__(self, llm_interface: LLMInterface = None):
        """初始化转盘智能体"""
        self.llm_interface = llm_interface or LLMInterface()
        self.kb = get_knowledge_base()
        self.chain = self._create_chain()
        
        # 获取设备参数
        equipment = self.kb.get_equipment("turntable_system")
        self.params = equipment.parameters if equipment else {
            "rpm_per_hz": 30.0,
            "carbon_loading": 15.0
        }
    
    def _create_chain(self):
        """创建LangChain处理链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", """
## 当前毒性分析
{toxicity_analysis}

## 当前运行参数
- 当前频率：{current_frequency} Hz
- 当前转速：{current_rpm} rpm
- 活跃反应器：{active_reactors} 台

## 请生成控制决策
请给出：
1. 推荐的频率设定值（1号、2号、3号转盘）
2. 是否需要启用备用线路
3. 预期的毒性去除效果
4. 操作理由和注意事项
""")
        ])
        
        api_key = self.llm_interface.qwen_api_key or self.llm_interface.openai_api_key
        base_url = self.llm_interface.qwen_api_base or self.llm_interface.openai_api_base
        model_name = self.llm_interface.qwen_model_name or "qwen-plus"
        
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=0.3
        )
        
        return prompt | llm | StrOutputParser()
    
    def _hz_to_rpm(self, frequency: float) -> float:
        """频率转换为转速"""
        return frequency * self.params.get("rpm_per_hz", 30.0)
    
    def _calculate_removal_rate(self, frequency: float, toxicity: float) -> float:
        """计算预期去除率"""
        # 基于一阶动力学模型简化计算
        # η = 1 - exp(-k * HRT)
        # k随频率增加而增加（传质效率提升）
        k_base = 0.05
        rpm = self._hz_to_rpm(frequency)
        k = k_base * (1 + rpm / 1000)  # 频率越高，传质系数越大
        
        # 假设HRT约15分钟
        hrt = 15.0 / 60.0  # 小时
        removal_rate = (1 - math.exp(-k * hrt * 60)) * 100  # 转为百分比
        
        # 高毒性时去除效率略降
        if toxicity > 3.0:
            removal_rate *= 0.9
        
        return min(95.0, max(30.0, removal_rate))
    
    def _determine_control_params(self, toxicity: float, toxicity_level: str, 
                                   trend: str = "稳定") -> Dict[str, Any]:
        """确定控制参数"""
        # 获取专家规则
        rules = self.kb.get_expert_rule("turntable_control")
        
        # 根据毒性等级确定基础参数
        if toxicity_level == "低" or toxicity < 1.5:
            base_freq = rules.get("low_toxicity", {}).get("target_frequency", 10.0)
            reactors = 2
            reason = "低毒性运行，节能模式"
        elif toxicity_level == "高" or toxicity > 3.0:
            base_freq = rules.get("high_toxicity", {}).get("target_frequency", 45.0)
            reactors = 3
            reason = "高毒性运行，全力处理"
        else:
            base_freq = rules.get("medium_toxicity", {}).get("target_frequency", 25.0)
            reactors = 2
            reason = "中毒性运行，标准模式"
        
        # 趋势调整
        trend_factors = {"上升": 1.15, "稳定": 1.0, "下降": 0.90}
        factor = trend_factors.get(trend, 1.0)
        adjusted_freq = min(50.0, max(5.0, base_freq * factor))
        
        if trend == "上升":
            reason += "，毒性上升趋势，提高频率"
        elif trend == "下降":
            reason += "，毒性下降趋势，适当降低频率"
        
        return {
            "frequency": adjusted_freq,
            "reactors": reactors,
            "standby": reactors == 3,
            "reason": reason
        }
    
    def run(self, toxicity_analysis: str, current_frequency: float = 25.0,
            active_reactors: int = 2) -> Dict[str, Any]:
        """
        运行转盘智能体
        
        Args:
            toxicity_analysis: 毒性分析文本（来自ToxicityAgent）
            current_frequency: 当前运行频率
            active_reactors: 当前活跃反应器数量
            
        Returns:
            Dict: 包含控制决策和LLM建议
        """
        try:
            # 调用LLM生成专业建议
            llm_response = self.chain.invoke({
                "toxicity_analysis": toxicity_analysis,
                "current_frequency": current_frequency,
                "current_rpm": self._hz_to_rpm(current_frequency),
                "active_reactors": active_reactors
            })
            
            return {
                "status": "success",
                "suggestion": llm_response,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {
                "status": "error",
                "suggestion": f"转盘控制决策生成失败: {str(e)}",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def generate_control_output(self, toxicity: float, toxicity_level: str,
                                trend: str = "稳定") -> TurntableControlOutput:
        """
        生成结构化控制输出（可直接下发PLC）
        
        Args:
            toxicity: 毒性值
            toxicity_level: 毒性等级 (低/中/高)
            trend: 变化趋势 (上升/稳定/下降)
            
        Returns:
            TurntableControlOutput: 结构化控制输出
        """
        # 确定控制参数
        params = self._determine_control_params(toxicity, toxicity_level, trend)
        
        frequency = params["frequency"]
        reactors = params["reactors"]
        standby = params["standby"]
        reason = params["reason"]
        
        # 计算各转盘参数
        freq_1 = frequency
        freq_2 = frequency
        freq_3 = frequency if standby else 0.0
        
        # 计算预期去除率
        removal_rate = self._calculate_removal_rate(frequency, toxicity)
        
        # 计算置信度
        confidence = 0.85
        if toxicity_level == "高":
            confidence = 0.80
        if trend == "上升":
            confidence -= 0.05
        
        return TurntableControlOutput(
            frequency_1=freq_1,
            frequency_2=freq_2,
            frequency_3=freq_3,
            rpm_1=self._hz_to_rpm(freq_1),
            rpm_2=self._hz_to_rpm(freq_2),
            rpm_3=self._hz_to_rpm(freq_3),
            active_reactors=reactors,
            standby_triggered=standby,
            expected_removal_rate=round(removal_rate, 1),
            decision_reason=reason,
            confidence=confidence,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def get_plc_command(self, toxicity: float, toxicity_level: str,
                        trend: str = "稳定") -> Dict[str, Any]:
        """
        获取PLC控制命令
        
        Args:
            toxicity: 毒性值
            toxicity_level: 毒性等级
            trend: 变化趋势
            
        Returns:
            Dict: PLC命令格式
        """
        output = self.generate_control_output(toxicity, toxicity_level, trend)
        return output.to_plc_command()


if __name__ == "__main__":
    # 测试转盘智能体
    print("=== 转盘智能体测试 ===")
    
    agent = TurntableAgent()
    
    # 测试场景1：低毒性
    print("\n场景1：低毒性")
    output1 = agent.generate_control_output(1.0, "低", "稳定")
    print(f"  频率: {output1.frequency_1} Hz")
    print(f"  转速: {output1.rpm_1} rpm")
    print(f"  反应器: {output1.active_reactors} 台")
    print(f"  原因: {output1.decision_reason}")
    
    # 测试场景2：中毒性上升
    print("\n场景2：中毒性上升")
    output2 = agent.generate_control_output(2.5, "中", "上升")
    print(f"  频率: {output2.frequency_1} Hz")
    print(f"  反应器: {output2.active_reactors} 台")
    print(f"  原因: {output2.decision_reason}")
    
    # 测试场景3：高毒性
    print("\n场景3：高毒性")
    output3 = agent.generate_control_output(4.0, "高", "上升")
    print(f"  频率: {output3.frequency_1} Hz")
    print(f"  备用触发: {output3.standby_triggered}")
    print(f"  PLC命令: {output3.to_plc_command()}")
