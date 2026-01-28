"""
工艺控制智能体 (ControlAgent)
负责综合控制决策，整合转盘/MBR/再生等子系统控制

功能:
1. 接收毒性预测结果
2. 调度各子控制智能体（转盘、MBR、再生）
3. 生成综合控制方案
4. 输出PLC控制命令
"""

import sys
import os
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from LLM.llm_interface import LLMInterface

# 尝试导入子控制智能体
try:
    from Agent.TurntableAgent import TurntableAgent
    from Agent.MBRAgent import MBRAgent
    from Agent.RegenerationAgent import RegenerationAgent
    from Knowledge.knowledge_base import get_knowledge_base
    HAS_SUB_AGENTS = True
except ImportError:
    HAS_SUB_AGENTS = False
    get_knowledge_base = None


@dataclass
class ControlDecision:
    """控制决策输出数据结构"""
    decision_type: str              # 决策类型(turntable/mbr/regeneration/comprehensive)
    turntable_params: Dict[str, Any] = field(default_factory=dict)   # 转盘参数
    mbr_params: Dict[str, Any] = field(default_factory=dict)         # MBR参数
    regeneration_params: Dict[str, Any] = field(default_factory=dict)  # 再生参数
    suggestion: str = ""            # 综合建议
    priority: str = "normal"        # 优先级(low/normal/high/urgent)
    timestamp: str = ""             # 时间戳
    confidence: float = 0.85        # 置信度
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision_type": self.decision_type,
            "turntable_params": self.turntable_params,
            "mbr_params": self.mbr_params,
            "regeneration_params": self.regeneration_params,
            "suggestion": self.suggestion,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "confidence": self.confidence
        }
    
    def to_plc_commands(self) -> List[Dict[str, Any]]:
        """转换为PLC命令列表"""
        commands = []
        
        if self.turntable_params:
            commands.append({
                "CMD_TYPE": "TURNTABLE_CONTROL",
                "TIMESTAMP": self.timestamp,
                **self.turntable_params
            })
        
        if self.mbr_params:
            commands.append({
                "CMD_TYPE": "MBR_CONTROL",
                "TIMESTAMP": self.timestamp,
                **self.mbr_params
            })
        
        if self.regeneration_params:
            commands.append({
                "CMD_TYPE": "REGENERATION_CONTROL",
                "TIMESTAMP": self.timestamp,
                **self.regeneration_params
            })
        
        return commands


class ControlAgent:
    """
    工艺控制智能体 (ControlAgent)
    
    作为综合控制决策的中心，负责：
    - 接收毒性分析结果
    - 调度各子控制智能体
    - 生成综合控制方案
    - 输出PLC控制指令
    """
    
    SYSTEM_PROMPT = """你是一名经验丰富的污水处理厂工艺工程师 (ControlAgent)。
你熟悉各种污水处理工艺（如AAO, SBR, 氧化沟, MBR等）及其运行参数。

## 核心职责
1. 接收 ToxicityAgent 提供的毒性预测结果和分析
2. 结合当前运行工艺和设备状态
3. 调度各子控制智能体（转盘、MBR、再生）
4. 生成综合控制方案

## 控制原则
如果预测毒性较高(毒性值 > 3.0)：
- 提出具体的应急措施（调整转盘频率、增加曝气、启用备用设备等）
- 针对特定工艺给出针对性建议

如果预测毒性中等(1.5-3.0)：
- 维持标准运行模式
- 持续监控毒性变化

如果预测毒性较低(< 1.5)：
- 建议节能运行模式
- 降低设备运行强度

请保持输出专业、条理清晰，包含具体的参数设定值。"""
    
    def __init__(self, llm_interface: LLMInterface = None):
        """初始化控制智能体"""
        self.llm_interface = llm_interface or LLMInterface()
        self.chain = self._create_chain()
        
        # 初始化子控制智能体
        if HAS_SUB_AGENTS:
            self.turntable_agent = TurntableAgent(self.llm_interface)
            self.mbr_agent = MBRAgent(self.llm_interface)
            self.regeneration_agent = RegenerationAgent(self.llm_interface)
            self.kb = get_knowledge_base() if get_knowledge_base else None
        else:
            self.turntable_agent = None
            self.mbr_agent = None
            self.regeneration_agent = None
            self.kb = None
        
        # 系统状态
        self.system_state = {
            "turntable_frequency": 25.0,
            "mbr_tmp": 20.0,
            "carbon_efficiency": 85.0
        }
    
    def _create_chain(self):
        """创建处理建议生成链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", """
## 运行信息
- **运行工艺**: {treatment_process}
- **预测时间范围**: {time_frame}

## 毒性预测与分析报告
{toxicity_analysis}

## 请给出综合控制建议
包括：
1. 转盘控制参数（频率、转速）
2. MBR控制参数（曝气量、通量）
3. 再生系统建议
4. 总体操作指导
""")
        ])
        
        api_key = self.llm_interface.qwen_api_key or self.llm_interface.openai_api_key or "sk-placeholder"
        base_url = self.llm_interface.qwen_api_base or self.llm_interface.openai_api_base
        model_name = self.llm_interface.qwen_model_name or "qwen-plus"
        
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=0.5
        )
        
        return prompt | llm | StrOutputParser()
    
    def _parse_toxicity_level(self, analysis: str) -> str:
        """从分析文本中提取毒性等级"""
        if "高毒性" in analysis or "高风险" in analysis:
            return "高"
        elif "低毒性" in analysis or "低风险" in analysis:
            return "低"
        else:
            return "中"
    
    def _parse_toxicity_value(self, analysis: str) -> float:
        """从分析文本中提取毒性值"""
        import re
        match = re.search(r'毒性[:：值为是]?\s*([\d.]+)', analysis)
        if match:
            return float(match.group(1))
        return 2.0  # 默认中等毒性
    
    def run(self, toxicity_analysis: str, treatment_process: str, 
            time_frame: str = "24小时") -> Dict[str, Any]:
        """
        生成综合控制建议
        
        Args:
            toxicity_analysis: 毒性预测分析文本
            treatment_process: 运行工艺名称
            time_frame: 预测时间范围
            
        Returns:
            Dict: 包含控制建议、参数设定、PLC命令等
        """
        try:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 解析毒性信息
            toxicity_level = self._parse_toxicity_level(toxicity_analysis)
            toxicity_value = self._parse_toxicity_value(toxicity_analysis)
            
            # 调用子控制智能体生成参数
            turntable_params = {}
            mbr_params = {}
            regeneration_params = {}
            
            if self.turntable_agent:
                turntable_output = self.turntable_agent.generate_control_output(
                    toxicity=toxicity_value,
                    toxicity_level=toxicity_level,
                    trend="稳定"
                )
                turntable_params = turntable_output.to_dict()
            
            if self.mbr_agent:
                mbr_output = self.mbr_agent.generate_control_output(
                    current_tmp=self.system_state.get("mbr_tmp", 20.0)
                )
                mbr_params = mbr_output.to_dict()
            
            if self.regeneration_agent:
                regen_output = self.regeneration_agent.generate_control_output(
                    adsorption_efficiency=self.system_state.get("carbon_efficiency", 85.0)
                )
                regeneration_params = regen_output.to_dict()
            
            # 调用LLM生成综合建议
            suggestion = self.chain.invoke({
                "toxicity_analysis": toxicity_analysis,
                "treatment_process": treatment_process,
                "time_frame": time_frame
            })
            
            # 确定优先级
            if toxicity_level == "高":
                priority = "urgent"
            elif toxicity_level == "中":
                priority = "normal"
            else:
                priority = "low"
            
            # 创建控制决策对象
            decision = ControlDecision(
                decision_type="comprehensive",
                turntable_params=turntable_params,
                mbr_params=mbr_params,
                regeneration_params=regeneration_params,
                suggestion=suggestion,
                priority=priority,
                timestamp=timestamp,
                confidence=0.85
            )
            
            return {
                "suggestion": suggestion,
                "status": "success",
                "toxicity_level": toxicity_level,
                "priority": priority,
                "turntable_params": turntable_params,
                "mbr_params": mbr_params,
                "regeneration_params": regeneration_params,
                "plc_commands": decision.to_plc_commands(),
                "structured_output": decision.to_dict()
            }
        except Exception as e:
            return {
                "suggestion": f"生成控制建议时发生错误: {str(e)}",
                "status": "error",
                "toxicity_level": "未知",
                "priority": "normal",
                "turntable_params": {},
                "mbr_params": {},
                "regeneration_params": {},
                "plc_commands": []
            }
    
    def generate_turntable_control(self, toxicity: float, toxicity_level: str = None) -> Dict[str, Any]:
        """
        生成转盘控制参数
        
        Args:
            toxicity: 毒性值
            toxicity_level: 毒性等级
        """
        if self.turntable_agent:
            level = toxicity_level or self._get_toxicity_level(toxicity)
            output = self.turntable_agent.generate_control_output(
                toxicity=toxicity,
                toxicity_level=level,
                trend="稳定"
            )
            return output.to_dict()
        else:
            # 回退逻辑
            return self._fallback_turntable_control(toxicity)
    
    def generate_mbr_control(self, tmp: float = 20.0) -> Dict[str, Any]:
        """
        生成MBR控制参数
        
        Args:
            tmp: 当前跨膜压 (kPa)
        """
        if self.mbr_agent:
            output = self.mbr_agent.generate_control_output(current_tmp=tmp)
            return output.to_dict()
        else:
            # 回退逻辑
            return self._fallback_mbr_control(tmp)
    
    def generate_regeneration_control(self, efficiency: float = 85.0) -> Dict[str, Any]:
        """
        生成再生控制参数
        
        Args:
            efficiency: 当前吸附效率 (%)
        """
        if self.regeneration_agent:
            output = self.regeneration_agent.generate_control_output(adsorption_efficiency=efficiency)
            return output.to_dict()
        else:
            # 回退逻辑
            return self._fallback_regeneration_control(efficiency)
    
    def _get_toxicity_level(self, toxicity: float) -> str:
        """根据毒性值判定等级"""
        if toxicity < 1.5:
            return "低"
        elif toxicity < 3.0:
            return "中"
        else:
            return "高"
    
    def _fallback_turntable_control(self, toxicity: float) -> Dict[str, Any]:
        """回退转盘控制逻辑"""
        if toxicity > 3.0:
            frequency = 40.0
        elif toxicity > 1.5:
            frequency = 25.0
        else:
            frequency = 10.0
        
        return {
            "frequency_1": frequency,
            "frequency_2": frequency,
            "rpm_1": frequency * 30,
            "rpm_2": frequency * 30,
            "active_reactors": 3 if toxicity > 3.0 else 2
        }
    
    def _fallback_mbr_control(self, tmp: float) -> Dict[str, Any]:
        """回退MBR控制逻辑"""
        if tmp > 30:
            aeration = 70.0
            flux = 15.0
        elif tmp > 20:
            aeration = 55.0
            flux = 18.0
        else:
            aeration = 50.0
            flux = 20.0
        
        return {
            "aeration_rate": aeration,
            "flux_setpoint": flux,
            "backwash_needed": tmp > 30
        }
    
    def _fallback_regeneration_control(self, efficiency: float) -> Dict[str, Any]:
        """回退再生控制逻辑"""
        need_regen = efficiency < 70
        return {
            "regeneration_needed": need_regen,
            "regeneration_mode": "thermal" if need_regen else "standby",
            "furnace_temperature": 800.0 if need_regen else 0,
            "feed_rate": 30.0 if need_regen else 0
        }
    
    def update_system_state(self, **kwargs):
        """更新系统状态"""
        for key, value in kwargs.items():
            if key in self.system_state:
                self.system_state[key] = value
