"""
Tools 模块 - LangChain 工具定义

包含：
- 实时数据采集 (PostgreSQL + MQTT)
- 毒性预测与告警
- MQTT 设备控制
- PLC 指令生成
- 知识库查询
"""

# 实时数据采集
from aquamind.tools.realtime_data import (
    get_latest_plc_from_db,
    get_inhibition_trend,
    get_mbr_status,
)

# 毒性预测与告警
from aquamind.tools.toxicity_predictor import (
    predict_toxicity,
    get_historical_stats,
    predict_toxicity_realtime,
    check_toxicity_alert,
)

# MQTT 设备控制
from aquamind.tools.mqtt_publisher import (
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
)

# PLC 指令生成
from aquamind.tools.plc_commands import (
    generate_turntable_command,
    generate_mbr_command,
    generate_regeneration_command,
)

# 知识库查询
from aquamind.tools.knowledge_query import (
    query_expert_rule,
    query_equipment_info,
    query_plc_variable,
)

__all__ = [
    # 实时数据
    "get_latest_plc_from_db",
    "get_inhibition_trend",
    "get_mbr_status",
    # 毒性预测
    "predict_toxicity",
    "get_historical_stats",
    "predict_toxicity_realtime",
    "check_toxicity_alert",
    # MQTT 控制
    "set_turntable_frequency",
    "control_turntable",
    "control_valve",
    "control_pump",
    "control_heater",
    "control_fan",
    "control_regeneration",
    "one_key_start",
    "send_plc_command",
    "get_available_controls",
    # PLC 指令生成
    "generate_turntable_command",
    "generate_mbr_command",
    "generate_regeneration_command",
    # 知识查询
    "query_expert_rule",
    "query_equipment_info",
    "query_plc_variable",
]
