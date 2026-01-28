"""
知识库模块 - 存储PLC变量、设备信息和专家知识
"""

import os
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field


@dataclass
class PLCVariable:
    """PLC变量定义"""
    name: str
    address: str
    data_type: str
    description: str
    unit: str = ""
    min_value: float = None
    max_value: float = None
    default_value: float = None
    read_only: bool = True


@dataclass
class Equipment:
    """设备定义"""
    name: str
    equipment_type: str
    description: str
    plc_variables: List[str] = field(default_factory=list)
    parameters: Dict[str, Any] = field(default_factory=dict)


class KnowledgeBase:
    """
    知识库基类 - 管理系统知识和配置
    """
    
    def __init__(self):
        self.plc_variables: Dict[str, PLCVariable] = {}
        self.equipments: Dict[str, Equipment] = {}
        self.expert_rules: Dict[str, Dict] = {}
        self._load_default_knowledge()
    
    def _load_default_knowledge(self):
        """加载默认知识"""
        # 转盘设备PLC变量
        self._add_turntable_knowledge()
        # MBR设备PLC变量
        self._add_mbr_knowledge()
        # 再生设备PLC变量
        self._add_regeneration_knowledge()
        # 通用监测变量
        self._add_monitoring_knowledge()
    
    def _add_turntable_knowledge(self):
        """添加转盘设备知识"""
        # 转盘频率控制
        self.plc_variables["turntable_frequency_1"] = PLCVariable(
            name="转盘1运行频率",
            address="DB100.DBD0",
            data_type="REAL",
            description="1号活性炭转盘运行频率",
            unit="Hz",
            min_value=0.0,
            max_value=50.0,
            default_value=25.0,
            read_only=False
        )
        self.plc_variables["turntable_frequency_2"] = PLCVariable(
            name="转盘2运行频率",
            address="DB100.DBD4",
            data_type="REAL",
            description="2号活性炭转盘运行频率",
            unit="Hz",
            min_value=0.0,
            max_value=50.0,
            default_value=25.0,
            read_only=False
        )
        self.plc_variables["turntable_frequency_3"] = PLCVariable(
            name="转盘3运行频率(备用)",
            address="DB100.DBD8",
            data_type="REAL",
            description="3号活性炭转盘运行频率(备用线路)",
            unit="Hz",
            min_value=0.0,
            max_value=50.0,
            default_value=0.0,
            read_only=False
        )
        
        # 转盘运行状态
        self.plc_variables["turntable_running_1"] = PLCVariable(
            name="转盘1运行状态",
            address="DB100.DBX20.0",
            data_type="BOOL",
            description="1号转盘运行状态",
            read_only=True
        )
        self.plc_variables["turntable_running_2"] = PLCVariable(
            name="转盘2运行状态",
            address="DB100.DBX20.1",
            data_type="BOOL",
            description="2号转盘运行状态",
            read_only=True
        )
        self.plc_variables["turntable_running_3"] = PLCVariable(
            name="转盘3运行状态",
            address="DB100.DBX20.2",
            data_type="BOOL",
            description="3号转盘运行状态(备用)",
            read_only=True
        )
        
        # 转盘设备
        self.equipments["turntable_system"] = Equipment(
            name="活性炭转盘吸附系统",
            equipment_type="adsorption",
            description="活性炭转盘吸附反应器系统，包含3条线路(2运行+1备用)",
            plc_variables=[
                "turntable_frequency_1", "turntable_frequency_2", "turntable_frequency_3",
                "turntable_running_1", "turntable_running_2", "turntable_running_3"
            ],
            parameters={
                "tank_length": 0.297,  # m
                "tank_width": 0.277,   # m
                "water_depth": 0.35,   # m
                "carbon_type": "10-20目椰壳活性炭",
                "carbon_loading": 15.0,  # kg/m³
                "motor_poles": 4,
                "rpm_per_hz": 30.0
            }
        )
        
        # 转盘专家规则
        self.expert_rules["turntable_control"] = {
            "low_toxicity": {
                "frequency_range": (5.0, 15.0),
                "target_frequency": 10.0,
                "reactors_needed": 2,
                "description": "低毒性时，降低频率节能运行"
            },
            "medium_toxicity": {
                "frequency_range": (15.0, 35.0),
                "target_frequency": 25.0,
                "reactors_needed": 2,
                "description": "中毒性时，标准频率运行"
            },
            "high_toxicity": {
                "frequency_range": (35.0, 50.0),
                "target_frequency": 45.0,
                "reactors_needed": 3,
                "description": "高毒性时，提高频率并启用备用线路"
            }
        }
    
    def _add_mbr_knowledge(self):
        """添加MBR设备知识"""
        # MBR膜压力
        self.plc_variables["mbr_tmp"] = PLCVariable(
            name="MBR跨膜压差",
            address="DB200.DBD0",
            data_type="REAL",
            description="MBR膜跨膜压差",
            unit="kPa",
            min_value=0.0,
            max_value=50.0,
            read_only=True
        )
        
        # MBR产水流量
        self.plc_variables["mbr_flux"] = PLCVariable(
            name="MBR产水通量",
            address="DB200.DBD4",
            data_type="REAL",
            description="MBR膜产水通量",
            unit="LMH",
            min_value=0.0,
            max_value=30.0,
            read_only=True
        )
        
        # MBR曝气量
        self.plc_variables["mbr_aeration"] = PLCVariable(
            name="MBR曝气量",
            address="DB200.DBD8",
            data_type="REAL",
            description="MBR膜下曝气量",
            unit="m³/h",
            min_value=0.0,
            max_value=100.0,
            default_value=50.0,
            read_only=False
        )
        
        # MBR反洗状态
        self.plc_variables["mbr_backwash"] = PLCVariable(
            name="MBR反洗状态",
            address="DB200.DBX20.0",
            data_type="BOOL",
            description="MBR膜反洗运行状态",
            read_only=True
        )
        
        # MBR设备
        self.equipments["mbr_system"] = Equipment(
            name="MBR膜处理系统",
            equipment_type="membrane",
            description="MBR膜生物反应器系统",
            plc_variables=["mbr_tmp", "mbr_flux", "mbr_aeration", "mbr_backwash"],
            parameters={
                "membrane_area": 100.0,  # m²
                "membrane_type": "PVDF中空纤维膜",
                "pore_size": 0.1,  # μm
                "design_flux": 20.0,  # LMH
                "tmp_warning": 30.0,  # kPa
                "tmp_alarm": 40.0     # kPa
            }
        )
        
        # MBR专家规则
        self.expert_rules["mbr_control"] = {
            "normal_operation": {
                "tmp_range": (5.0, 25.0),
                "flux_target": 18.0,
                "aeration_rate": 50.0,
                "description": "正常运行参数"
            },
            "fouling_warning": {
                "tmp_threshold": 30.0,
                "action": "increase_aeration",
                "aeration_increase": 20.0,
                "description": "膜污染预警，增加曝气"
            },
            "cleaning_required": {
                "tmp_threshold": 40.0,
                "action": "chemical_cleaning",
                "description": "需要化学清洗"
            }
        }
    
    def _add_regeneration_knowledge(self):
        """添加再生设备知识"""
        # 再生温度
        self.plc_variables["regen_temperature"] = PLCVariable(
            name="再生炉温度",
            address="DB300.DBD0",
            data_type="REAL",
            description="活性炭再生炉温度",
            unit="°C",
            min_value=0.0,
            max_value=1000.0,
            default_value=800.0,
            read_only=False
        )
        
        # 再生进料速度
        self.plc_variables["regen_feed_rate"] = PLCVariable(
            name="再生进料速度",
            address="DB300.DBD4",
            data_type="REAL",
            description="活性炭进料速度",
            unit="kg/h",
            min_value=0.0,
            max_value=100.0,
            default_value=30.0,
            read_only=False
        )
        
        # 再生运行状态
        self.plc_variables["regen_running"] = PLCVariable(
            name="再生炉运行状态",
            address="DB300.DBX20.0",
            data_type="BOOL",
            description="再生炉运行状态",
            read_only=True
        )
        
        # 再生设备
        self.equipments["regeneration_system"] = Equipment(
            name="活性炭再生系统",
            equipment_type="regeneration",
            description="活性炭热再生系统",
            plc_variables=["regen_temperature", "regen_feed_rate", "regen_running"],
            parameters={
                "furnace_type": "回转窑",
                "design_capacity": 50.0,  # kg/h
                "regen_temperature": 800.0,  # °C
                "residence_time": 30.0,  # min
                "recovery_rate": 0.95
            }
        )
        
        # 再生专家规则
        self.expert_rules["regeneration_control"] = {
            "normal_regeneration": {
                "temperature": 800.0,
                "feed_rate": 30.0,
                "description": "正常再生参数"
            },
            "intensive_regeneration": {
                "temperature": 850.0,
                "feed_rate": 40.0,
                "description": "强化再生（活性炭吸附能力下降时）"
            },
            "energy_saving": {
                "temperature": 750.0,
                "feed_rate": 25.0,
                "description": "节能模式"
            }
        }
    
    def _add_monitoring_knowledge(self):
        """添加监测变量知识"""
        # 进水毒性
        self.plc_variables["inlet_toxicity"] = PLCVariable(
            name="进水毒性",
            address="DB400.DBD0",
            data_type="REAL",
            description="进水综合毒性指标",
            unit="TU",
            min_value=0.0,
            max_value=100.0,
            read_only=True
        )
        
        # 出水毒性
        self.plc_variables["outlet_toxicity"] = PLCVariable(
            name="出水毒性",
            address="DB400.DBD4",
            data_type="REAL",
            description="出水综合毒性指标",
            unit="TU",
            min_value=0.0,
            max_value=100.0,
            read_only=True
        )
        
        # 进水流量
        self.plc_variables["inlet_flow"] = PLCVariable(
            name="进水流量",
            address="DB400.DBD8",
            data_type="REAL",
            description="总进水流量",
            unit="m³/h",
            min_value=0.0,
            max_value=1000.0,
            read_only=True
        )
        
        # 进水氨氮
        self.plc_variables["inlet_ammonia"] = PLCVariable(
            name="进水氨氮",
            address="DB400.DBD12",
            data_type="REAL",
            description="进水氨氮浓度",
            unit="mg/L",
            min_value=0.0,
            max_value=100.0,
            read_only=True
        )
        
        # 进水pH
        self.plc_variables["inlet_ph"] = PLCVariable(
            name="进水pH",
            address="DB400.DBD16",
            data_type="REAL",
            description="进水pH值",
            unit="",
            min_value=0.0,
            max_value=14.0,
            read_only=True
        )
        
        # 水温
        self.plc_variables["water_temperature"] = PLCVariable(
            name="水温",
            address="DB400.DBD20",
            data_type="REAL",
            description="进水温度",
            unit="°C",
            min_value=0.0,
            max_value=50.0,
            read_only=True
        )
    
    def get_plc_variable(self, name: str) -> Optional[PLCVariable]:
        """获取PLC变量"""
        return self.plc_variables.get(name)
    
    def get_equipment(self, name: str) -> Optional[Equipment]:
        """获取设备信息"""
        return self.equipments.get(name)
    
    def get_expert_rule(self, category: str, rule_name: str = None) -> Optional[Dict]:
        """获取专家规则"""
        if category not in self.expert_rules:
            return None
        if rule_name:
            return self.expert_rules[category].get(rule_name)
        return self.expert_rules[category]
    
    def get_control_recommendation(self, toxicity_level: str, equipment_type: str) -> Dict:
        """根据毒性等级获取控制建议"""
        recommendations = {
            "turntable": self.expert_rules.get("turntable_control", {}),
            "mbr": self.expert_rules.get("mbr_control", {}),
            "regeneration": self.expert_rules.get("regeneration_control", {})
        }
        
        rule_key = f"{toxicity_level.lower()}_toxicity"
        if equipment_type in recommendations:
            return recommendations[equipment_type].get(rule_key, {})
        return {}
    
    def to_dict(self) -> Dict:
        """导出知识库为字典"""
        return {
            "plc_variables": {k: v.__dict__ for k, v in self.plc_variables.items()},
            "equipments": {k: {**v.__dict__, "plc_variables": v.plc_variables} 
                          for k, v in self.equipments.items()},
            "expert_rules": self.expert_rules
        }


# 全局知识库实例
KNOWLEDGE_BASE = KnowledgeBase()


def get_knowledge_base() -> KnowledgeBase:
    """获取知识库实例"""
    return KNOWLEDGE_BASE


if __name__ == "__main__":
    # 测试知识库
    kb = KnowledgeBase()
    print("=== 知识库测试 ===")
    print(f"PLC变量数量: {len(kb.plc_variables)}")
    print(f"设备数量: {len(kb.equipments)}")
    print(f"专家规则类别: {list(kb.expert_rules.keys())}")
    
    print("\n转盘设备信息:")
    turntable = kb.get_equipment("turntable_system")
    if turntable:
        print(f"  名称: {turntable.name}")
        print(f"  类型: {turntable.equipment_type}")
        print(f"  参数: {turntable.parameters}")
