"""
MQTT 发布工具 - PLC 设备控制

通过 MQTT 协议向 PLC 发送控制指令，实现设备远程控制。

发布主题: plc/write
消息格式: {"data": {"变量中文名": "值", ...}}

可控装置变量:
- 阀门: VA01-VA14 (启/停)
- 泵: B01-B06 (启/停)
- 转盘: 1/2/3 (启/停, 频率 5-50Hz)
- 加热棒: HT00-HT03 (启/停)
- 再生系统: 1/2/3 (启/停)
- 风机 (启/停)
"""

import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from langchain_core.tools import tool

# MQTT 配置
MQTT_CONFIG = {
    "broker": "139.196.187.10",
    "port": 1883,
    "write_topic": "plc/write",
}

# PLC 可控变量映射 (中文名 -> 英文标识)
PLC_VARIABLES = {
    # 一键启动
    "一键启动": "OneKey_Start",
    
    # 线路选择
    "启动1号线路进水": "Start_Line1_Inlet",
    "启动2号线路进水": "Start_Line2_Inlet",
    "启动3号线路进水": "Start_Line3_Inlet",
    
    # 阀门控制 (VA01-VA14)
    "启动进水阀VA01": "Start_Inlet_Valve_VA01",
    "启动进水阀VA02": "Start_Inlet_Valve_VA02",
    "启动进水阀VA03": "Start_Inlet_Valve_VA03",
    "启动出水阀VA04": "Start_Outlet_Valve_VA04",
    "启动出水阀VA05": "Start_Outlet_Valve_VA05",
    "启动出水阀VA06": "Start_Outlet_Valve_VA06",
    "启动再生水进水阀VA07": "Start_RegenWater_Inlet_VA07",
    "启动出入水双向选择阀VA08": "Start_BiDir_Valve_VA08",
    "启动出入水双向选择阀VA09": "Start_BiDir_Valve_VA09",
    "启动出入水双向选择阀VA10": "Start_BiDir_Valve_VA10",
    "启动冷却水箱进水阀VA11": "Start_CoolingTank_Inlet_VA11",
    "启动冷却水箱中转阀VA12": "Start_CoolingTank_Transfer_VA12",
    "启动排水阀VA13": "Start_Drain_Valve_VA13",
    "启动再生水箱进水阀VA14": "Start_RegenTank_Inlet_VA14",
    
    # 泵控制 (B01-B06)
    "启动供液泵B01": "Start_SupplyPump_B01",
    "启动供液泵B02": "Start_SupplyPump_B02",
    "启动供液泵B03": "Start_SupplyPump_B03",
    "启动供液泵B04": "Start_SupplyPump_B04",
    "启动供液泵B05": "Start_SupplyPump_B05",
    "启动取液泵B06": "Start_ExtractPump_B06",
    
    # 转盘控制
    "启动转盘1": "Start_Turntable1",
    "启动转盘2": "Start_Turntable2",
    "启动转盘3": "Start_Turntable3",
    "转盘1频率给定": "Turntable1_Frequency_Set",
    "转盘2频率给定": "Turntable2_Frequency_Set",
    "转盘3频率给定": "Turntable3_Frequency_Set",
    
    # 加热棒控制 (HT00-HT03)
    "启动再生水箱加热棒HT00": "Start_RegenTank_Heater_HT00",
    "启动转盘1水箱加热棒HT01": "Start_TT1_Heater_HT01",
    "启动转盘2水箱加热棒HT02": "Start_TT2_Heater_HT02",
    "启动转盘3水箱加热棒HT03": "Start_TT3_Heater_HT03",
    
    # 再生系统
    "启动再生1": "Start_Regeneration1",
    "启动再生2": "Start_Regeneration2",
    "启动再生3": "Start_Regeneration3",
    
    # 风机
    "风机启动": "Start_Fan",
}

# 简化的变量别名 (便于智能体调用)
VARIABLE_ALIASES = {
    # 转盘频率
    "turntable1_freq": "转盘1频率给定",
    "turntable2_freq": "转盘2频率给定",
    "turntable3_freq": "转盘3频率给定",
    # 转盘启停
    "turntable1": "启动转盘1",
    "turntable2": "启动转盘2",
    "turntable3": "启动转盘3",
    # 风机
    "fan": "风机启动",
    # 阀门
    "va01": "启动进水阀VA01",
    "va02": "启动进水阀VA02",
    "va03": "启动进水阀VA03",
    "va04": "启动出水阀VA04",
    "va05": "启动出水阀VA05",
    "va06": "启动出水阀VA06",
    # 泵
    "pump_b01": "启动供液泵B01",
    "pump_b02": "启动供液泵B02",
    "pump_b03": "启动供液泵B03",
    # 再生
    "regen1": "启动再生1",
    "regen2": "启动再生2",
    "regen3": "启动再生3",
    # 加热棒
    "heater_ht00": "启动再生水箱加热棒HT00",
    "heater_ht01": "启动转盘1水箱加热棒HT01",
    "heater_ht02": "启动转盘2水箱加热棒HT02",
    "heater_ht03": "启动转盘3水箱加热棒HT03",
}


def _resolve_variable_name(name: str) -> str:
    """解析变量名，支持别名和中文名"""
    # 先检查别名
    if name.lower() in VARIABLE_ALIASES:
        return VARIABLE_ALIASES[name.lower()]
    # 直接返回（假设是中文名）
    return name


def _publish_mqtt(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    发布 MQTT 消息到 PLC
    
    Args:
        payload: {"data": {"变量名": "值", ...}}
    
    Returns:
        发布结果
    """
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        return {
            "success": False,
            "error": "paho-mqtt 未安装，请执行: pip install paho-mqtt"
        }
    
    try:
        client = mqtt.Client()
        client.connect(MQTT_CONFIG["broker"], MQTT_CONFIG["port"], 60)
        
        payload_json = json.dumps(payload, ensure_ascii=False)
        result = client.publish(MQTT_CONFIG["write_topic"], payload_json.encode("utf-8"))
        client.disconnect()
        
        if result.rc == mqtt.MQTT_ERR_SUCCESS:
            return {
                "success": True,
                "topic": MQTT_CONFIG["write_topic"],
                "payload": payload,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        else:
            return {
                "success": False,
                "error": f"MQTT 发布失败，错误码: {result.rc}"
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@tool
def set_turntable_frequency(
    turntable_id: int,
    frequency: float
) -> Dict[str, Any]:
    """
    设置转盘运行频率。
    
    Args:
        turntable_id: 转盘编号 (1, 2, 3)
        frequency: 频率值 (5-50 Hz)
    
    Returns:
        控制结果，包含 success 状态和详细信息
    
    Example:
        >>> set_turntable_frequency(1, 25.0)
        {"success": True, "turntable": 1, "frequency": 25.0, ...}
    """
    if turntable_id not in [1, 2, 3]:
        return {"success": False, "error": "转盘编号必须为 1, 2 或 3"}
    
    if not (5 <= frequency <= 50):
        return {"success": False, "error": "频率必须在 5-50 Hz 范围内"}
    
    var_name = f"转盘{turntable_id}频率给定"
    payload = {"data": {var_name: str(int(frequency))}}
    
    result = _publish_mqtt(payload)
    result["turntable"] = turntable_id
    result["frequency"] = frequency
    result["variable"] = var_name
    
    return result


@tool
def control_turntable(
    turntable_id: int,
    action: str
) -> Dict[str, Any]:
    """
    启动或停止转盘。
    
    Args:
        turntable_id: 转盘编号 (1, 2, 3)
        action: 动作 ("start" 启动, "stop" 停止)
    
    Returns:
        控制结果
    """
    if turntable_id not in [1, 2, 3]:
        return {"success": False, "error": "转盘编号必须为 1, 2 或 3"}
    
    if action.lower() not in ["start", "stop"]:
        return {"success": False, "error": "动作必须为 'start' 或 'stop'"}
    
    var_name = f"启动转盘{turntable_id}"
    value = "1" if action.lower() == "start" else "0"
    payload = {"data": {var_name: value}}
    
    result = _publish_mqtt(payload)
    result["turntable"] = turntable_id
    result["action"] = action
    result["variable"] = var_name
    
    return result


@tool
def control_valve(
    valve_id: str,
    action: str
) -> Dict[str, Any]:
    """
    控制阀门开关。
    
    Args:
        valve_id: 阀门编号 (VA01-VA14)
        action: 动作 ("open" 打开, "close" 关闭)
    
    Returns:
        控制结果
    
    阀门说明:
        - VA01-VA03: 进水阀
        - VA04-VA06: 出水阀
        - VA07: 再生水进水阀
        - VA08-VA10: 双向选择阀
        - VA11: 冷却水箱进水阀
        - VA12: 冷却水箱中转阀
        - VA13: 排水阀
        - VA14: 再生水箱进水阀
    """
    valve_id = valve_id.upper()
    if not valve_id.startswith("VA"):
        valve_id = f"VA{valve_id.zfill(2)}"
    
    # 查找对应的变量名
    var_name = None
    for cn_name in PLC_VARIABLES:
        if valve_id in cn_name:
            var_name = cn_name
            break
    
    if var_name is None:
        return {"success": False, "error": f"未找到阀门 {valve_id}"}
    
    if action.lower() not in ["open", "close"]:
        return {"success": False, "error": "动作必须为 'open' 或 'close'"}
    
    value = "1" if action.lower() == "open" else "0"
    payload = {"data": {var_name: value}}
    
    result = _publish_mqtt(payload)
    result["valve"] = valve_id
    result["action"] = action
    result["variable"] = var_name
    
    return result


@tool
def control_pump(
    pump_id: str,
    action: str
) -> Dict[str, Any]:
    """
    控制泵启停。
    
    Args:
        pump_id: 泵编号 (B01-B06)
        action: 动作 ("start" 启动, "stop" 停止)
    
    Returns:
        控制结果
    
    泵说明:
        - B01-B05: 供液泵
        - B06: 取液泵
    """
    pump_id = pump_id.upper()
    if not pump_id.startswith("B"):
        pump_id = f"B{pump_id.zfill(2)}"
    
    # 查找对应的变量名
    var_name = None
    for cn_name in PLC_VARIABLES:
        if pump_id in cn_name:
            var_name = cn_name
            break
    
    if var_name is None:
        return {"success": False, "error": f"未找到泵 {pump_id}"}
    
    if action.lower() not in ["start", "stop"]:
        return {"success": False, "error": "动作必须为 'start' 或 'stop'"}
    
    value = "1" if action.lower() == "start" else "0"
    payload = {"data": {var_name: value}}
    
    result = _publish_mqtt(payload)
    result["pump"] = pump_id
    result["action"] = action
    result["variable"] = var_name
    
    return result


@tool
def control_heater(
    heater_id: str,
    action: str
) -> Dict[str, Any]:
    """
    控制加热棒启停。
    
    Args:
        heater_id: 加热棒编号 (HT00-HT03)
        action: 动作 ("start" 启动, "stop" 停止)
    
    Returns:
        控制结果
    
    加热棒说明:
        - HT00: 再生水箱加热棒
        - HT01: 转盘1水箱加热棒
        - HT02: 转盘2水箱加热棒
        - HT03: 转盘3水箱加热棒
    """
    heater_id = heater_id.upper()
    if not heater_id.startswith("HT"):
        heater_id = f"HT{heater_id.zfill(2)}"
    
    # 查找对应的变量名
    var_name = None
    for cn_name in PLC_VARIABLES:
        if heater_id in cn_name:
            var_name = cn_name
            break
    
    if var_name is None:
        return {"success": False, "error": f"未找到加热棒 {heater_id}"}
    
    if action.lower() not in ["start", "stop"]:
        return {"success": False, "error": "动作必须为 'start' 或 'stop'"}
    
    value = "1" if action.lower() == "start" else "0"
    payload = {"data": {var_name: value}}
    
    result = _publish_mqtt(payload)
    result["heater"] = heater_id
    result["action"] = action
    result["variable"] = var_name
    
    return result


@tool
def control_fan(action: str) -> Dict[str, Any]:
    """
    控制风机启停。
    
    Args:
        action: 动作 ("start" 启动, "stop" 停止)
    
    Returns:
        控制结果
    """
    if action.lower() not in ["start", "stop"]:
        return {"success": False, "error": "动作必须为 'start' 或 'stop'"}
    
    var_name = "风机启动"
    value = "1" if action.lower() == "start" else "0"
    payload = {"data": {var_name: value}}
    
    result = _publish_mqtt(payload)
    result["device"] = "fan"
    result["action"] = action
    result["variable"] = var_name
    
    return result


@tool
def control_regeneration(
    regen_id: int,
    action: str
) -> Dict[str, Any]:
    """
    控制再生系统启停。
    
    Args:
        regen_id: 再生系统编号 (1, 2, 3)
        action: 动作 ("start" 启动, "stop" 停止)
    
    Returns:
        控制结果
    """
    if regen_id not in [1, 2, 3]:
        return {"success": False, "error": "再生系统编号必须为 1, 2 或 3"}
    
    if action.lower() not in ["start", "stop"]:
        return {"success": False, "error": "动作必须为 'start' 或 'stop'"}
    
    var_name = f"启动再生{regen_id}"
    value = "1" if action.lower() == "start" else "0"
    payload = {"data": {var_name: value}}
    
    result = _publish_mqtt(payload)
    result["regeneration"] = regen_id
    result["action"] = action
    result["variable"] = var_name
    
    return result


@tool
def one_key_start() -> Dict[str, Any]:
    """
    一键启动系统。
    
    启动整个污水处理系统的默认配置。
    
    Returns:
        控制结果
    """
    var_name = "一键启动"
    payload = {"data": {var_name: "1"}}
    
    result = _publish_mqtt(payload)
    result["device"] = "one_key_start"
    result["action"] = "start"
    result["variable"] = var_name
    
    return result


@tool
def send_plc_command(
    commands: Dict[str, str]
) -> Dict[str, Any]:
    """
    发送自定义 PLC 控制命令 (批量控制)。
    
    Args:
        commands: 变量名到值的映射，如 {"转盘1频率给定": "30", "风机启动": "1"}
    
    Returns:
        控制结果
    
    Example:
        >>> send_plc_command({"转盘1频率给定": "30", "转盘2频率给定": "30", "风机启动": "1"})
    """
    # 验证所有变量名
    invalid_vars = []
    for var_name in commands:
        resolved = _resolve_variable_name(var_name)
        if resolved not in PLC_VARIABLES:
            invalid_vars.append(var_name)
    
    if invalid_vars:
        return {
            "success": False,
            "error": f"未知变量: {invalid_vars}",
            "available_variables": list(PLC_VARIABLES.keys())[:10]  # 返回部分示例
        }
    
    # 解析变量名
    resolved_commands = {}
    for var_name, value in commands.items():
        resolved = _resolve_variable_name(var_name)
        resolved_commands[resolved] = str(value)
    
    payload = {"data": resolved_commands}
    
    result = _publish_mqtt(payload)
    result["commands"] = resolved_commands
    result["command_count"] = len(resolved_commands)
    
    return result


@tool
def get_available_controls() -> Dict[str, Any]:
    """
    获取所有可控装置变量列表。
    
    Returns:
        可控变量分类列表
    """
    return {
        "转盘控制": {
            "启停": ["启动转盘1", "启动转盘2", "启动转盘3"],
            "频率": ["转盘1频率给定", "转盘2频率给定", "转盘3频率给定"],
            "频率范围": "5-50 Hz"
        },
        "阀门控制": {
            "进水阀": ["启动进水阀VA01", "启动进水阀VA02", "启动进水阀VA03"],
            "出水阀": ["启动出水阀VA04", "启动出水阀VA05", "启动出水阀VA06"],
            "其他阀": ["VA07-VA14"]
        },
        "泵控制": {
            "供液泵": ["启动供液泵B01", "启动供液泵B02", "启动供液泵B03", "启动供液泵B04", "启动供液泵B05"],
            "取液泵": ["启动取液泵B06"]
        },
        "加热棒": ["HT00 (再生水箱)", "HT01-HT03 (转盘水箱)"],
        "再生系统": ["启动再生1", "启动再生2", "启动再生3"],
        "风机": ["风机启动"],
        "一键启动": ["一键启动"],
        "total_variables": len(PLC_VARIABLES)
    }


# 导出工具列表
MQTT_CONTROL_TOOLS = [
    set_turntable_frequency,
    control_turntable,
    control_valve,
    control_pump,
    control_heater,
    control_fan,
    control_regeneration,
    one_key_start,
    send_plc_command,
    get_available_controls,
]
