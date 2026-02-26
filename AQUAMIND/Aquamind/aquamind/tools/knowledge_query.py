"""
知识库查询工具

提供设备信息、专家规则、PLC 变量的查询接口。
"""

from typing import Dict, Any, Optional, List
from datetime import datetime

from langchain_core.tools import tool


# 延迟导入知识库以避免循环导入
def _get_kb():
    from aquamind.knowledge import get_knowledge_base
    return get_knowledge_base()


@tool
def query_expert_rule(
    category: str,
    rule_name: Optional[str] = None
) -> Dict[str, Any]:
    """
    查询专家规则知识库。
    
    获取特定类别的控制专家规则，用于辅助决策。
    
    Args:
        category: 规则类别，可选值:
            - turntable_control: 转盘控制规则
            - mbr_control: MBR 控制规则
            - regeneration_control: 再生控制规则
        rule_name: 具体规则名称（可选），如 low_toxicity, medium_toxicity
    
    Returns:
        包含专家规则的字典:
        - category: 规则类别
        - rules: 规则内容
        - found: 是否找到
    
    Example:
        >>> query_expert_rule("turntable_control", "high_toxicity")
        {'category': 'turntable_control', 'rules': {...}, 'found': True}
    """
    kb = _get_kb()
    
    rules = kb.get_expert_rule(category, rule_name)
    
    if rules is None:
        return {
            "category": category,
            "rule_name": rule_name,
            "rules": None,
            "found": False,
            "message": f"未找到规则: {category}" + (f".{rule_name}" if rule_name else ""),
            "available_categories": list(kb.expert_rules.keys()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    return {
        "category": category,
        "rule_name": rule_name,
        "rules": rules,
        "found": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@tool
def query_equipment_info(equipment_name: str) -> Dict[str, Any]:
    """
    查询设备信息。
    
    获取指定设备的详细参数和配置信息。
    
    Args:
        equipment_name: 设备名称，可选值:
            - turntable_system: 活性炭转盘吸附系统
            - mbr_system: MBR 膜处理系统
            - regeneration_system: 活性炭再生系统
    
    Returns:
        包含设备信息的字典:
        - name: 设备名称
        - equipment_type: 设备类型
        - description: 设备描述
        - parameters: 设备参数
        - plc_variables: 关联的 PLC 变量列表
        - found: 是否找到
    """
    kb = _get_kb()
    
    equipment = kb.get_equipment(equipment_name)
    
    if equipment is None:
        return {
            "equipment_name": equipment_name,
            "found": False,
            "message": f"未找到设备: {equipment_name}",
            "available_equipments": list(kb.equipments.keys()),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    return {
        "equipment_name": equipment_name,
        "name": equipment.name,
        "equipment_type": equipment.equipment_type,
        "description": equipment.description,
        "parameters": equipment.parameters,
        "plc_variables": equipment.plc_variables,
        "found": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@tool
def query_plc_variable(variable_name: str) -> Dict[str, Any]:
    """
    查询 PLC 变量定义。
    
    获取指定 PLC 变量的地址、数据类型、范围等信息。
    
    Args:
        variable_name: PLC 变量名称，如:
            - turntable_frequency_1: 1号转盘频率
            - mbr_tmp: MBR 跨膜压差
            - regen_temperature: 再生炉温度
            - inlet_toxicity: 进水毒性
    
    Returns:
        包含 PLC 变量信息的字典:
        - name: 变量显示名称
        - address: PLC 地址
        - data_type: 数据类型
        - description: 描述
        - unit: 单位
        - min_value/max_value: 范围
        - read_only: 是否只读
        - found: 是否找到
    """
    kb = _get_kb()
    
    variable = kb.get_plc_variable(variable_name)
    
    if variable is None:
        # 列出部分可用变量
        sample_vars = list(kb.plc_variables.keys())[:10]
        return {
            "variable_name": variable_name,
            "found": False,
            "message": f"未找到 PLC 变量: {variable_name}",
            "sample_variables": sample_vars,
            "total_variables": len(kb.plc_variables),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    return {
        "variable_name": variable_name,
        "name": variable.name,
        "address": variable.address,
        "data_type": variable.data_type,
        "description": variable.description,
        "unit": variable.unit,
        "min_value": variable.min_value,
        "max_value": variable.max_value,
        "default_value": variable.default_value,
        "read_only": variable.read_only,
        "found": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@tool
def get_control_recommendation(
    toxicity_level: str,
    equipment_type: str
) -> Dict[str, Any]:
    """
    获取控制建议。
    
    根据毒性等级获取特定设备的控制建议。
    
    Args:
        toxicity_level: 毒性等级 (低/中/高)
        equipment_type: 设备类型 (turntable/mbr/regeneration)
    
    Returns:
        包含控制建议的字典
    """
    kb = _get_kb()
    
    recommendation = kb.get_control_recommendation(toxicity_level, equipment_type)
    
    if not recommendation:
        return {
            "toxicity_level": toxicity_level,
            "equipment_type": equipment_type,
            "found": False,
            "message": "未找到匹配的控制建议",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
    return {
        "toxicity_level": toxicity_level,
        "equipment_type": equipment_type,
        "recommendation": recommendation,
        "found": True,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
