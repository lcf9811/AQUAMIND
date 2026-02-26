"""
PLC 控制命令生成工具

生成可下发给 PLC 的控制指令。
"""

import math
from datetime import datetime
from typing import Dict, Any, Optional

from langchain_core.tools import tool

from aquamind.core.config import settings


def _hz_to_rpm(frequency: float, poles: int = 4) -> float:
    """频率转换为转速 (4极电机: rpm = freq * 30)"""
    return frequency * (120 / poles)


def _calculate_removal_rate(frequency: float, toxicity: float) -> float:
    """计算预期去除率"""
    k_base = 0.05
    rpm = _hz_to_rpm(frequency)
    k = k_base * (1 + rpm / 1000)
    hrt = 15.0 / 60.0  # 小时
    removal_rate = (1 - math.exp(-k * hrt * 60)) * 100
    
    if toxicity > 3.0:
        removal_rate *= 0.9
    
    return min(95.0, max(30.0, removal_rate))


@tool
def generate_turntable_command(
    toxicity: float,
    toxicity_level: str = "中",
    trend: str = "稳定"
) -> Dict[str, Any]:
    """
    生成转盘控制 PLC 命令。
    
    根据毒性等级和趋势，计算最优的转盘运行参数，生成 PLC 控制指令。
    
    Args:
        toxicity: 毒性值 (0-10)
        toxicity_level: 毒性等级 (低/中/高)
        trend: 变化趋势 (上升/稳定/下降)
    
    Returns:
        包含 PLC 控制命令的字典:
        - frequency_1/2/3: 各转盘频率设定 (Hz)
        - rpm_1/2/3: 对应转速 (rpm)
        - active_reactors: 活跃反应器数量
        - standby_triggered: 是否启用备用
        - expected_removal_rate: 预期去除率 (%)
        - plc_command: PLC 指令格式
        - decision_reason: 决策原因
    """
    # 根据毒性等级确定基础频率
    if toxicity_level == "低" or toxicity < settings.agent.toxicity_low_threshold:
        base_freq = 10.0
        reactors = 2
        reason = "低毒性运行，节能模式"
    elif toxicity_level == "高" or toxicity > settings.agent.toxicity_high_threshold:
        base_freq = 45.0
        reactors = 3
        reason = "高毒性运行，全力处理"
    else:
        base_freq = 25.0
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
    
    # 计算各转盘参数
    standby = reactors == 3
    freq_1 = adjusted_freq
    freq_2 = adjusted_freq
    freq_3 = adjusted_freq if standby else 0.0
    
    # 计算预期去除率
    removal_rate = _calculate_removal_rate(adjusted_freq, toxicity)
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 生成 PLC 命令
    plc_command = {
        "CMD_TYPE": "TURNTABLE_CONTROL",
        "TIMESTAMP": timestamp,
        "TURNTABLE_1": {
            "FREQ_SETPOINT": round(freq_1, 1),
            "ENABLE": freq_1 > 0
        },
        "TURNTABLE_2": {
            "FREQ_SETPOINT": round(freq_2, 1),
            "ENABLE": freq_2 > 0
        },
        "TURNTABLE_3": {
            "FREQ_SETPOINT": round(freq_3, 1),
            "ENABLE": standby
        },
        "ALARM_LEVEL": 3 if standby else (2 if freq_1 > 35 else 1)
    }
    
    return {
        "frequency_1": freq_1,
        "frequency_2": freq_2,
        "frequency_3": freq_3,
        "rpm_1": _hz_to_rpm(freq_1),
        "rpm_2": _hz_to_rpm(freq_2),
        "rpm_3": _hz_to_rpm(freq_3),
        "active_reactors": reactors,
        "standby_triggered": standby,
        "expected_removal_rate": round(removal_rate, 1),
        "decision_reason": reason,
        "plc_command": plc_command,
        "timestamp": timestamp
    }


@tool
def generate_mbr_command(
    current_tmp: float = 20.0,
    toxicity_level: str = "中"
) -> Dict[str, Any]:
    """
    生成 MBR 控制 PLC 命令。
    
    根据跨膜压差 (TMP) 和毒性等级，生成 MBR 膜系统的控制参数。
    
    Args:
        current_tmp: 当前跨膜压差 (kPa)，正常 < 25，警告 25-35，危险 > 35
        toxicity_level: 毒性等级 (低/中/高)
    
    Returns:
        包含 MBR 控制参数的字典:
        - aeration_rate: 曝气量 (m³/h)
        - flux_setpoint: 通量设定 (LMH)
        - fouling_status: 污染状态
        - backwash_needed: 是否需要反洗
        - chemical_cleaning_needed: 是否需要化学清洗
        - plc_command: PLC 指令格式
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 根据 TMP 判断污染状态
    if current_tmp < settings.agent.mbr_tmp_normal:
        fouling_status = "正常"
        aeration_rate = 50.0
        flux = settings.agent.mbr_max_flux
        backwash = False
        chemical_clean = False
        reason = "膜运行正常"
    elif current_tmp < settings.agent.mbr_tmp_warning:
        fouling_status = "轻度污染"
        aeration_rate = 55.0
        flux = 18.0
        backwash = False
        chemical_clean = False
        reason = "TMP 略高，增加曝气"
    elif current_tmp < 40:
        fouling_status = "中度污染"
        aeration_rate = 70.0
        flux = settings.agent.mbr_min_flux
        backwash = True
        chemical_clean = False
        reason = "TMP 偏高，需要反洗"
    else:
        fouling_status = "严重污染"
        aeration_rate = 70.0
        flux = settings.agent.mbr_min_flux
        backwash = True
        chemical_clean = True
        reason = "TMP 过高，需要化学清洗"
    
    # 高毒性时增加曝气
    if toxicity_level == "高":
        aeration_rate += 10.0
        reason += "，高毒性加强曝气"
    
    plc_command = {
        "CMD_TYPE": "MBR_CONTROL",
        "TIMESTAMP": timestamp,
        "AERATION": {
            "RATE_SETPOINT": round(aeration_rate, 1),
            "UNIT": "m3/h"
        },
        "FLUX": {
            "SETPOINT": round(flux, 1),
            "UNIT": "LMH"
        },
        "BACKWASH": {
            "TRIGGER": backwash,
            "MODE": "AUTO"
        },
        "ALARM_LEVEL": 3 if chemical_clean else (2 if backwash else 1)
    }
    
    return {
        "aeration_rate": aeration_rate,
        "flux_setpoint": flux,
        "current_tmp": current_tmp,
        "fouling_status": fouling_status,
        "backwash_needed": backwash,
        "chemical_cleaning_needed": chemical_clean,
        "decision_reason": reason,
        "plc_command": plc_command,
        "timestamp": timestamp
    }


@tool
def generate_regeneration_command(
    adsorption_efficiency: float = 85.0,
    carbon_age_days: int = 30
) -> Dict[str, Any]:
    """
    生成活性炭再生控制 PLC 命令。
    
    根据吸附效率和活性炭使用时间，判断是否需要再生及再生参数。
    
    Args:
        adsorption_efficiency: 当前吸附效率 (%)，低于 70% 需要再生
        carbon_age_days: 活性炭使用天数
    
    Returns:
        包含再生控制参数的字典:
        - regeneration_needed: 是否需要再生
        - regeneration_mode: 再生模式 (待机/正常/强化)
        - furnace_temperature: 炉温设定 (°C)
        - feed_rate: 进料速度 (kg/h)
        - plc_command: PLC 指令格式
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    threshold = settings.agent.carbon_efficiency_threshold
    
    if adsorption_efficiency >= threshold:
        # 不需要再生
        regen_needed = False
        mode = "待机"
        temp = 0.0
        feed_rate = 0.0
        reason = f"吸附效率 {adsorption_efficiency:.1f}% 正常，无需再生"
    elif adsorption_efficiency >= threshold - 10:
        # 正常再生
        regen_needed = True
        mode = "正常再生"
        temp = settings.agent.regeneration_temp
        feed_rate = settings.agent.regeneration_feed_rate
        reason = f"吸附效率 {adsorption_efficiency:.1f}% 偏低，启动正常再生"
    else:
        # 强化再生
        regen_needed = True
        mode = "强化再生"
        temp = settings.agent.regeneration_temp + 50
        feed_rate = settings.agent.regeneration_feed_rate * 1.2
        reason = f"吸附效率 {adsorption_efficiency:.1f}% 过低，启动强化再生"
    
    # 使用时间过长也需要再生
    if carbon_age_days > 60 and not regen_needed:
        regen_needed = True
        mode = "定期再生"
        temp = settings.agent.regeneration_temp
        feed_rate = settings.agent.regeneration_feed_rate * 0.8
        reason = f"活性炭已使用 {carbon_age_days} 天，建议定期再生"
    
    plc_command = {
        "CMD_TYPE": "REGENERATION_CONTROL",
        "TIMESTAMP": timestamp,
        "FURNACE": {
            "TEMP_SETPOINT": round(temp, 0),
            "ENABLE": regen_needed
        },
        "FEED": {
            "RATE_SETPOINT": round(feed_rate, 1),
            "UNIT": "kg/h"
        },
        "MODE": mode,
        "ALARM_LEVEL": 2 if regen_needed else 1
    }
    
    return {
        "regeneration_needed": regen_needed,
        "regeneration_mode": mode,
        "furnace_temperature": temp,
        "feed_rate": feed_rate,
        "adsorption_efficiency": adsorption_efficiency,
        "carbon_age_days": carbon_age_days,
        "decision_reason": reason,
        "plc_command": plc_command,
        "timestamp": timestamp
    }
