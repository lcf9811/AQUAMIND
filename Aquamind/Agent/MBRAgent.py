"""
MBR智能体 (MBRAgent)
负责MBR膜生物反应器系统的智能控制决策

功能:
1. 监控跨膜压差(TMP)和产水通量
2. 控制曝气量和产水流量
3. 判断膜污染状态和清洗需求
4. 优化膜运行效率
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
class MBRControlOutput:
    """MBR控制输出数据结构"""
    aeration_rate: float            # 曝气量 (m³/h)
    flux_setpoint: float            # 通量设定值 (LMH)
    backwash_needed: bool           # 是否需要反洗
    chemical_cleaning_needed: bool  # 是否需要化学清洗
    alarm_level: int                # 报警等级 (0-3)
    fouling_status: str             # 污染状态 (normal/warning/critical)
    decision_reason: str            # 决策原因
    recommendations: List[str]      # 操作建议
    confidence: float               # 置信度
    timestamp: str                  # 时间戳
    
    def to_plc_command(self) -> Dict[str, Any]:
        """转换为PLC命令格式"""
        return {
            "CMD_TYPE": "MBR_CONTROL",
            "TIMESTAMP": self.timestamp,
            "AERATION": {
                "RATE_SETPOINT": round(self.aeration_rate, 1),
                "AUTO_MODE": True
            },
            "MEMBRANE": {
                "FLUX_SETPOINT": round(self.flux_setpoint, 1),
                "BACKWASH_TRIGGER": self.backwash_needed,
                "CHEMICAL_CLEAN_REQ": self.chemical_cleaning_needed
            },
            "ALARM_LEVEL": self.alarm_level,
            "FOULING_STATUS": self.fouling_status.upper()
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "aeration_rate": self.aeration_rate,
            "flux_setpoint": self.flux_setpoint,
            "backwash_needed": self.backwash_needed,
            "chemical_cleaning_needed": self.chemical_cleaning_needed,
            "alarm_level": self.alarm_level,
            "fouling_status": self.fouling_status,
            "decision_reason": self.decision_reason,
            "recommendations": self.recommendations,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
            "plc_command": self.to_plc_command()
        }


class MBRAgent:
    """
    MBR智能体
    
    负责MBR膜生物反应器的智能控制，包括：
    - 跨膜压差监控
    - 曝气量调节
    - 膜污染评估
    - 清洗周期管理
    """
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一位专业的MBR膜生物反应器控制工程师 (MBRAgent)。

你的核心职责是监控MBR系统的运行状态，确保膜组件高效稳定运行。

## 设备概况
- 膜类型：PVDF中空纤维膜
- 膜面积：100 m²
- 膜孔径：0.1 μm
- 设计通量：20 LMH
- TMP预警值：30 kPa
- TMP报警值：40 kPa

## 控制原则
1. **正常运行** (TMP < 25 kPa):
   - 通量：18-20 LMH
   - 曝气：50 m³/h
   - 定期反洗

2. **污染预警** (TMP 25-35 kPa):
   - 降低通量至15 LMH
   - 增加曝气20%
   - 缩短反洗间隔

3. **严重污染** (TMP > 35 kPa):
   - 停止产水
   - 启动化学清洗
   - 检查膜完整性

## 膜保护原则
- 避免TMP急剧上升
- 防止膜干燥
- 控制MLSS在合理范围
- 避免污泥老化

请基于以上原则，给出专业的MBR控制建议。"""

    def __init__(self, llm_interface: LLMInterface = None):
        """初始化MBR智能体"""
        self.llm_interface = llm_interface or LLMInterface()
        self.kb = get_knowledge_base()
        self.chain = self._create_chain()
        
        # 获取设备参数
        equipment = self.kb.get_equipment("mbr_system")
        self.params = equipment.parameters if equipment else {
            "membrane_area": 100.0,
            "design_flux": 20.0,
            "tmp_warning": 30.0,
            "tmp_alarm": 40.0
        }
    
    def _create_chain(self):
        """创建LangChain处理链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", """
## MBR系统当前状态
{system_status}

## 运行参数
- 当前TMP：{current_tmp} kPa
- 当前通量：{current_flux} LMH
- 当前曝气量：{current_aeration} m³/h
- MLSS浓度：{mlss} g/L

## 请评估MBR运行状态
请给出：
1. 膜污染状态评估
2. 推荐的控制参数调整
3. 是否需要清洗操作
4. 操作建议和注意事项
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
    
    def _assess_fouling_status(self, tmp: float, flux: float) -> Dict[str, Any]:
        """评估膜污染状态"""
        tmp_warning = self.params.get("tmp_warning", 30.0)
        tmp_alarm = self.params.get("tmp_alarm", 40.0)
        
        if tmp >= tmp_alarm:
            return {
                "status": "critical",
                "alarm_level": 3,
                "reason": "TMP严重超标，需要立即化学清洗",
                "action": "chemical_cleaning"
            }
        elif tmp >= tmp_warning:
            return {
                "status": "warning",
                "alarm_level": 2,
                "reason": "TMP偏高，存在膜污染，需要增强反洗",
                "action": "enhanced_backwash"
            }
        elif tmp >= tmp_warning * 0.8:
            return {
                "status": "attention",
                "alarm_level": 1,
                "reason": "TMP接近预警值，需要关注",
                "action": "increase_aeration"
            }
        else:
            return {
                "status": "normal",
                "alarm_level": 0,
                "reason": "膜运行正常",
                "action": "maintain"
            }
    
    def _calculate_control_params(self, tmp: float, current_aeration: float,
                                   current_flux: float) -> Dict[str, float]:
        """计算控制参数"""
        assessment = self._assess_fouling_status(tmp, current_flux)
        status = assessment["status"]
        
        design_flux = self.params.get("design_flux", 20.0)
        
        if status == "critical":
            return {
                "aeration_rate": current_aeration * 1.5,  # 大幅增加曝气
                "flux_setpoint": 0.0,  # 停止产水
                "backwash": True,
                "chemical_clean": True
            }
        elif status == "warning":
            return {
                "aeration_rate": current_aeration * 1.2,  # 增加曝气20%
                "flux_setpoint": design_flux * 0.75,  # 降低通量25%
                "backwash": True,
                "chemical_clean": False
            }
        elif status == "attention":
            return {
                "aeration_rate": current_aeration * 1.1,  # 增加曝气10%
                "flux_setpoint": design_flux * 0.9,  # 略降通量
                "backwash": False,
                "chemical_clean": False
            }
        else:
            return {
                "aeration_rate": current_aeration,
                "flux_setpoint": design_flux,
                "backwash": False,
                "chemical_clean": False
            }
    
    def run(self, system_status: str, current_tmp: float = 20.0,
            current_flux: float = 18.0, current_aeration: float = 50.0,
            mlss: float = 8.0) -> Dict[str, Any]:
        """
        运行MBR智能体
        
        Args:
            system_status: 系统状态描述
            current_tmp: 当前跨膜压差 (kPa)
            current_flux: 当前通量 (LMH)
            current_aeration: 当前曝气量 (m³/h)
            mlss: MLSS浓度 (g/L)
            
        Returns:
            Dict: 包含控制决策和LLM建议
        """
        try:
            llm_response = self.chain.invoke({
                "system_status": system_status,
                "current_tmp": current_tmp,
                "current_flux": current_flux,
                "current_aeration": current_aeration,
                "mlss": mlss
            })
            
            return {
                "status": "success",
                "suggestion": llm_response,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {
                "status": "error",
                "suggestion": f"MBR控制决策生成失败: {str(e)}",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def generate_control_output(self, current_tmp: float = 20.0,
                                current_flux: float = 18.0,
                                current_aeration: float = 50.0) -> MBRControlOutput:
        """
        生成结构化控制输出
        
        Args:
            current_tmp: 当前跨膜压差 (kPa)
            current_flux: 当前通量 (LMH)
            current_aeration: 当前曝气量 (m³/h)
            
        Returns:
            MBRControlOutput: 结构化控制输出
        """
        # 评估污染状态
        assessment = self._assess_fouling_status(current_tmp, current_flux)
        
        # 计算控制参数
        params = self._calculate_control_params(current_tmp, current_aeration, current_flux)
        
        # 生成建议列表
        recommendations = []
        if assessment["status"] == "critical":
            recommendations.extend([
                "立即停止产水",
                "启动化学清洗程序",
                "检查膜完整性",
                "清洗后进行通量恢复测试"
            ])
        elif assessment["status"] == "warning":
            recommendations.extend([
                f"增加曝气量至{params['aeration_rate']:.0f} m³/h",
                f"降低通量至{params['flux_setpoint']:.0f} LMH",
                "缩短反洗间隔至30分钟",
                "准备化学清洗备用"
            ])
        elif assessment["status"] == "attention":
            recommendations.extend([
                "加强监测TMP变化",
                "适当增加曝气量",
                "检查MLSS浓度"
            ])
        else:
            recommendations.extend([
                "保持当前运行参数",
                "定期执行反洗",
                "监测TMP趋势"
            ])
        
        # 计算置信度
        confidence = 0.85
        if assessment["status"] == "critical":
            confidence = 0.90
        
        return MBRControlOutput(
            aeration_rate=params["aeration_rate"],
            flux_setpoint=params["flux_setpoint"],
            backwash_needed=params["backwash"],
            chemical_cleaning_needed=params["chemical_clean"],
            alarm_level=assessment["alarm_level"],
            fouling_status=assessment["status"],
            decision_reason=assessment["reason"],
            recommendations=recommendations,
            confidence=confidence,
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def get_plc_command(self, current_tmp: float = 20.0,
                        current_flux: float = 18.0,
                        current_aeration: float = 50.0) -> Dict[str, Any]:
        """获取PLC控制命令"""
        output = self.generate_control_output(current_tmp, current_flux, current_aeration)
        return output.to_plc_command()


if __name__ == "__main__":
    # 测试MBR智能体
    print("=== MBR智能体测试 ===")
    
    agent = MBRAgent()
    
    # 测试场景1：正常运行
    print("\n场景1：正常运行")
    output1 = agent.generate_control_output(
        current_tmp=18.0,
        current_flux=18.0,
        current_aeration=50.0
    )
    print(f"  污染状态: {output1.fouling_status}")
    print(f"  曝气量: {output1.aeration_rate} m³/h")
    print(f"  原因: {output1.decision_reason}")
    
    # 测试场景2：TMP偏高
    print("\n场景2：TMP偏高")
    output2 = agent.generate_control_output(
        current_tmp=32.0,
        current_flux=16.0,
        current_aeration=50.0
    )
    print(f"  污染状态: {output2.fouling_status}")
    print(f"  需要反洗: {output2.backwash_needed}")
    print(f"  原因: {output2.decision_reason}")
    
    # 测试场景3：严重污染
    print("\n场景3：严重污染")
    output3 = agent.generate_control_output(
        current_tmp=42.0,
        current_flux=10.0,
        current_aeration=50.0
    )
    print(f"  污染状态: {output3.fouling_status}")
    print(f"  需要化学清洗: {output3.chemical_cleaning_needed}")
    print(f"  PLC命令: {output3.to_plc_command()}")
