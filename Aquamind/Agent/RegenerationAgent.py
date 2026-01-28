"""
再生智能体 (RegenerationAgent)
负责活性炭再生系统的智能控制决策

功能:
1. 监测活性炭吸附能力
2. 判断是否需要再生
3. 控制再生炉运行参数
4. 优化再生效率和能耗
"""

import sys
import os
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
class RegenerationControlOutput:
    """再生控制输出数据结构"""
    regeneration_needed: bool       # 是否需要再生
    furnace_temperature: float      # 再生炉温度 (°C)
    feed_rate: float                # 进料速度 (kg/h)
    regeneration_mode: str          # 再生模式 (normal/intensive/energy_saving)
    estimated_duration: float       # 预计再生时长 (h)
    carbon_recovery_rate: float     # 预计回收率 (%)
    decision_reason: str            # 决策原因
    recommendations: List[str]      # 操作建议
    confidence: float               # 置信度
    timestamp: str                  # 时间戳
    
    def to_plc_command(self) -> Dict[str, Any]:
        """转换为PLC命令格式"""
        return {
            "CMD_TYPE": "REGENERATION_CONTROL",
            "TIMESTAMP": self.timestamp,
            "FURNACE": {
                "TEMP_SETPOINT": round(self.furnace_temperature, 0),
                "FEED_RATE": round(self.feed_rate, 1),
                "ENABLE": self.regeneration_needed
            },
            "MODE": self.regeneration_mode.upper(),
            "ESTIMATED_DURATION_H": round(self.estimated_duration, 1)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "regeneration_needed": self.regeneration_needed,
            "furnace_temperature": self.furnace_temperature,
            "feed_rate": self.feed_rate,
            "regeneration_mode": self.regeneration_mode,
            "estimated_duration": self.estimated_duration,
            "carbon_recovery_rate": self.carbon_recovery_rate,
            "decision_reason": self.decision_reason,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "plc_command": self.to_plc_command()
        }


class RegenerationAgent:
    """
    再生智能体
    
    负责活性炭再生系统的智能控制，包括：
    - 再生时机判断
    - 温度/进料速度控制
    - 再生模式选择
    - 能耗优化
    """
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一位专业的活性炭再生工艺工程师 (RegenerationAgent)。

你的核心职责是监测活性炭的吸附能力，判断何时需要进行再生，并控制再生炉的运行参数。

## 设备概况
- 再生炉类型：回转窑
- 设计处理能力：50 kg/h
- 标准再生温度：800°C
- 停留时间：约30分钟
- 回收率：约95%

## 再生判断标准
1. **需要再生的情况**:
   - 吸附能力下降超过20%
   - 毒性去除率明显降低
   - 运行时间超过规定周期
   - 出水毒性持续偏高

2. **再生模式选择**:
   - 正常再生：温度800°C，进料30 kg/h
   - 强化再生：温度850°C，进料40 kg/h（活性炭严重饱和时）
   - 节能模式：温度750°C，进料25 kg/h（轻度再生需求）

## 控制原则
- 优先保证再生效果
- 在满足效果的前提下节约能耗
- 避免过度再生导致活性炭损耗

请基于以上原则，给出专业的再生控制建议。"""

    def __init__(self, llm_interface: LLMInterface = None):
        """初始化再生智能体"""
        self.llm_interface = llm_interface or LLMInterface()
        self.kb = get_knowledge_base()
        self.chain = self._create_chain()
        
        # 获取设备参数
        equipment = self.kb.get_equipment("regeneration_system")
        self.params = equipment.parameters if equipment else {
            "design_capacity": 50.0,
            "regen_temperature": 800.0,
            "residence_time": 30.0,
            "recovery_rate": 0.95
        }
    
    def _create_chain(self):
        """创建LangChain处理链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", """
## 当前系统状态
{system_status}

## 活性炭状态
- 累计运行时间：{operating_hours} 小时
- 当前吸附效率：{adsorption_efficiency}%
- 毒性去除率：{removal_rate}%

## 请评估再生需求
请给出：
1. 是否需要进行再生
2. 推荐的再生模式和参数
3. 预计再生时长和效果
4. 操作注意事项
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
    
    def _assess_regeneration_need(self, adsorption_efficiency: float, 
                                   removal_rate: float,
                                   operating_hours: float) -> Dict[str, Any]:
        """评估再生需求"""
        # 再生判断阈值
        EFFICIENCY_THRESHOLD = 80.0  # 吸附效率低于80%需要再生
        REMOVAL_THRESHOLD = 60.0      # 去除率低于60%需要再生
        HOURS_THRESHOLD = 720.0       # 运行超过720小时需要再生
        
        need_regen = False
        mode = "normal"
        reason = ""
        urgency = "low"
        
        # 判断是否需要再生
        if adsorption_efficiency < 60.0 or removal_rate < 40.0:
            need_regen = True
            mode = "intensive"
            reason = "活性炭严重饱和，需要强化再生"
            urgency = "high"
        elif adsorption_efficiency < EFFICIENCY_THRESHOLD or removal_rate < REMOVAL_THRESHOLD:
            need_regen = True
            mode = "normal"
            reason = "吸附能力下降，需要常规再生"
            urgency = "medium"
        elif operating_hours > HOURS_THRESHOLD:
            need_regen = True
            mode = "normal"
            reason = "已达到周期性再生时间"
            urgency = "medium"
        elif operating_hours > HOURS_THRESHOLD * 0.8:
            # 预防性再生
            need_regen = True
            mode = "energy_saving"
            reason = "预防性再生，节能模式"
            urgency = "low"
        else:
            reason = "活性炭状态良好，无需再生"
        
        return {
            "need_regeneration": need_regen,
            "mode": mode,
            "reason": reason,
            "urgency": urgency
        }
    
    def _get_mode_parameters(self, mode: str) -> Dict[str, float]:
        """获取再生模式参数"""
        rules = self.kb.get_expert_rule("regeneration_control")
        
        mode_params = {
            "normal": {
                "temperature": rules.get("normal_regeneration", {}).get("temperature", 800.0),
                "feed_rate": rules.get("normal_regeneration", {}).get("feed_rate", 30.0),
                "duration": 8.0
            },
            "intensive": {
                "temperature": rules.get("intensive_regeneration", {}).get("temperature", 850.0),
                "feed_rate": rules.get("intensive_regeneration", {}).get("feed_rate", 40.0),
                "duration": 6.0
            },
            "energy_saving": {
                "temperature": rules.get("energy_saving", {}).get("temperature", 750.0),
                "feed_rate": rules.get("energy_saving", {}).get("feed_rate", 25.0),
                "duration": 10.0
            }
        }
        
        return mode_params.get(mode, mode_params["normal"])
    
    def run(self, system_status: str, operating_hours: float = 500,
            adsorption_efficiency: float = 85.0,
            removal_rate: float = 70.0) -> Dict[str, Any]:
        """
        运行再生智能体
        
        Args:
            system_status: 系统状态描述
            operating_hours: 累计运行小时数
            adsorption_efficiency: 当前吸附效率 (%)
            removal_rate: 当前毒性去除率 (%)
            
        Returns:
            Dict: 包含再生决策和LLM建议
        """
        try:
            # 调用LLM生成专业建议
            llm_response = self.chain.invoke({
                "system_status": system_status,
                "operating_hours": operating_hours,
                "adsorption_efficiency": adsorption_efficiency,
                "removal_rate": removal_rate
            })
            
            return {
                "status": "success",
                "suggestion": llm_response,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {
                "status": "error",
                "suggestion": f"再生控制决策生成失败: {str(e)}",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def generate_control_output(self, adsorption_efficiency: float = 85.0,
                                removal_rate: float = 70.0,
                                operating_hours: float = 500) -> RegenerationControlOutput:
        """
        生成结构化控制输出
        
        Args:
            adsorption_efficiency: 当前吸附效率 (%)
            removal_rate: 当前毒性去除率 (%)
            operating_hours: 累计运行小时数
            
        Returns:
            RegenerationControlOutput: 结构化控制输出
        """
        # 评估再生需求
        assessment = self._assess_regeneration_need(
            adsorption_efficiency, removal_rate, operating_hours
        )
        
        need_regen = assessment["need_regeneration"]
        mode = assessment["mode"]
        reason = assessment["reason"]
        
        # 获取模式参数
        params = self._get_mode_parameters(mode)
        
        # 生成建议列表
        recommendations = []
        if need_regen:
            recommendations.append(f"启动{mode}模式再生")
            recommendations.append(f"设定炉温至{params['temperature']}°C")
            recommendations.append(f"进料速度设定为{params['feed_rate']} kg/h")
            if mode == "intensive":
                recommendations.append("注意监控炉温，防止过热")
                recommendations.append("再生后测试活性炭碘值")
        else:
            recommendations.append("继续正常运行")
            recommendations.append("定期监测吸附效率")
        
        # 计算置信度
        confidence = 0.85
        if assessment["urgency"] == "high":
            confidence = 0.90
        elif assessment["urgency"] == "low":
            confidence = 0.80
        
        return RegenerationControlOutput(
            regeneration_needed=need_regen,
            furnace_temperature=params["temperature"] if need_regen else 0.0,
            feed_rate=params["feed_rate"] if need_regen else 0.0,
            regeneration_mode=mode if need_regen else "standby",
            estimated_duration=params["duration"] if need_regen else 0.0,
            carbon_recovery_rate=self.params.get("recovery_rate", 0.95) * 100,
            decision_reason=reason,
            recommendations=recommendations,
            confidence=confidence,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def get_plc_command(self, adsorption_efficiency: float = 85.0,
                        removal_rate: float = 70.0,
                        operating_hours: float = 500) -> Dict[str, Any]:
        """获取PLC控制命令"""
        output = self.generate_control_output(
            adsorption_efficiency, removal_rate, operating_hours
        )
        return output.to_plc_command()


if __name__ == "__main__":
    # 测试再生智能体
    print("=== 再生智能体测试 ===")
    
    agent = RegenerationAgent()
    
    # 测试场景1：正常状态
    print("\n场景1：活性炭状态良好")
    output1 = agent.generate_control_output(
        adsorption_efficiency=90.0,
        removal_rate=80.0,
        operating_hours=200
    )
    print(f"  需要再生: {output1.regeneration_needed}")
    print(f"  原因: {output1.decision_reason}")
    
    # 测试场景2：效率下降
    print("\n场景2：吸附效率下降")
    output2 = agent.generate_control_output(
        adsorption_efficiency=70.0,
        removal_rate=55.0,
        operating_hours=600
    )
    print(f"  需要再生: {output2.regeneration_needed}")
    print(f"  再生模式: {output2.regeneration_mode}")
    print(f"  炉温: {output2.furnace_temperature}°C")
    print(f"  原因: {output2.decision_reason}")
    
    # 测试场景3：严重饱和
    print("\n场景3：活性炭严重饱和")
    output3 = agent.generate_control_output(
        adsorption_efficiency=50.0,
        removal_rate=35.0,
        operating_hours=800
    )
    print(f"  需要再生: {output3.regeneration_needed}")
    print(f"  再生模式: {output3.regeneration_mode}")
    print(f"  预计时长: {output3.estimated_duration} 小时")
    print(f"  PLC命令: {output3.to_plc_command()}")
