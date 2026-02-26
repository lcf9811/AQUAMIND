"""
实时数据采集工具 - 连接 MQTT 和 PostgreSQL 获取 PLC/毒性数据

数据源配置：
- MQTT Broker: 139.196.187.10:1883 (无认证)
- PostgreSQL: pgm-bp1ksg5v1lo5z2r8eo.rwlb.rds.aliyuncs.com:5432/zhikong_data
"""

import os
import json
import threading
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List
from langchain_core.tools import tool

# MQTT 配置
MQTT_CONFIG = {
    "broker": os.getenv("MQTT_BROKER", "139.196.187.10"),
    "port": int(os.getenv("MQTT_PORT", "1883")),
    "user": os.getenv("MQTT_USER", ""),
    "password": os.getenv("MQTT_PASSWORD", ""),
    "topics": ["mess1", "mess2", "mess3", "plc/data"],
}

# PostgreSQL 配置
PG_CONFIG = {
    "host": os.getenv("PG_HOST", "pgm-bp1ksg5v1lo5z2r8eo.rwlb.rds.aliyuncs.com"),
    "port": int(os.getenv("PG_PORT", "5432")),
    "dbname": os.getenv("PG_DBNAME", "zhikong_data"),
    "user": os.getenv("PG_USER", "nju_zhikong"),
    "password": os.getenv("PG_PASSWORD", "Njucongfu!"),
}

# PLC 变量映射 (中文 -> 英文)
PLC_VARIABLE_MAP = {
    # 转盘控制
    "启动转盘1": "Start_Turntable1",
    "启动转盘2": "Start_Turntable2",
    "启动转盘3": "Start_Turntable3",
    "转盘1频率给定": "Turntable1_Frequency_Set",
    "转盘2频率给定": "Turntable2_Frequency_Set",
    "转盘3频率给定": "Turntable3_Frequency_Set",
    "转盘1频率反馈": "Turntable1_Frequency_Feedback",
    "转盘2频率反馈": "Turntable2_Frequency_Feedback",
    "转盘3频率反馈": "Turntable3_Frequency_Feedback",
    "转盘1再生时间": "Turntable1_Regen_Time",
    "转盘2再生时间": "Turntable2_Regen_Time",
    "转盘3再生时间": "Turntable3_Regen_Time",
    "转盘1水箱温度计T1": "Turntable1_Tank_Temperature_T1",
    "转盘2水箱温度计T2": "Turntable2_Tank_Temperature_T2",
    "转盘3水箱温度计T3": "Turntable3_Tank_Temperature_T3",
    
    # 毒性/抑制率
    "出水抑制率设定": "Outlet_InhibitionRate_Set",
    "1箱氨氮上限设定": "Box1_NH4_Upper_Set",
    "2箱氨氮上限设定": "Box2_NH4_Upper_Set",
    "3箱氨氮上限设定": "Box3_NH4_Upper_Set",
    
    # 温度控制
    "转盘1水箱温度1设定": "TT1_Tank_Temp1_Set",
    "转盘2水箱温度2设定": "TT2_Tank_Temp2_Set",
    "转盘3水箱温度3设定": "TT3_Tank_Temp3_Set",
    "再生水箱加热温度设定": "RegenTank_HeatingTemp_Set",
    "再生放液许可温度": "Regen_Drain_Permit_Temp",
    "再生水箱温度计T0": "Regen_Tank_Temperature_T0",
    "冷却箱温度计T4": "Cooling_Tank_Temperature_T4",
    
    # 阀门控制
    "启动进水阀VA01": "Start_Inlet_Valve_VA01",
    "启动进水阀VA02": "Start_Inlet_Valve_VA02",
    "启动进水阀VA03": "Start_Inlet_Valve_VA03",
    "启动出水阀VA04": "Start_Outlet_Valve_VA04",
    "启动出水阀VA05": "Start_Outlet_Valve_VA05",
    "启动出水阀VA06": "Start_Outlet_Valve_VA06",
    "启动排水阀VA13": "Start_Drain_Valve_VA13",
    
    # 液位
    "转盘1水箱高液位L1": "Tank1_High_Level_L1",
    "转盘1水箱低液位L1": "Tank1_Low_Level_L1",
    "转盘2水箱高液位L2": "Tank2_High_Level_L2",
    "转盘2水箱低液位L2": "Tank2_Low_Level_L2",
    "转盘3水箱高液位L3": "Tank3_High_Level_L3",
    "转盘3水箱低液位L3": "Tank3_Low_Level_L3",
}

# 英文 -> 中文的反向映射
ENGLISH_TO_CHINESE = {v: k for k, v in PLC_VARIABLE_MAP.items()}

# 全局数据缓存
_latest_data: Dict[str, Any] = {}
_data_lock = threading.Lock()
_mqtt_client = None


def _parse_plc_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    解析 PLC 原始数据，将中文标签转换为英文字段
    
    Args:
        raw_data: 原始 JSON 数据
        
    Returns:
        转换后的字典，键为英文字段名
    """
    parsed = {}
    for key, value in raw_data.items():
        # 处理 "默认分组-" 前缀
        cn_key = key[5:].strip() if key.startswith("默认分组-") else key.strip()
        
        # 查找英文映射
        en_key = PLC_VARIABLE_MAP.get(cn_key)
        if en_key:
            parsed[en_key.lower()] = value
        else:
            # 未映射的字段保留原样
            parsed[cn_key] = value
    
    return parsed


def _on_mqtt_message(client, userdata, msg):
    """MQTT 消息回调"""
    global _latest_data
    
    try:
        payload = msg.payload.decode("utf-8", errors="replace")
        data = json.loads(payload)
        parsed = _parse_plc_data(data)
        
        with _data_lock:
            _latest_data.update(parsed)
            _latest_data["_last_update"] = datetime.now().isoformat()
            _latest_data["_topic"] = msg.topic
            
    except Exception as e:
        print(f"[MQTT] 消息解析错误: {e}")


def start_mqtt_subscription() -> bool:
    """
    启动 MQTT 订阅，后台接收实时数据
    
    Returns:
        是否成功启动
    """
    global _mqtt_client
    
    try:
        import paho.mqtt.client as mqtt
    except ImportError:
        print("[ERROR] paho-mqtt 未安装，请执行: pip install paho-mqtt")
        return False
    
    if _mqtt_client is not None:
        print("[MQTT] 订阅已在运行中")
        return True
    
    try:
        _mqtt_client = mqtt.Client()
        
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                print(f"[MQTT] 已连接到 {MQTT_CONFIG['broker']}:{MQTT_CONFIG['port']}")
                for topic in MQTT_CONFIG["topics"]:
                    client.subscribe(topic)
                    print(f"[MQTT] 订阅主题: {topic}")
            else:
                print(f"[MQTT] 连接失败, rc={rc}")
        
        _mqtt_client.on_connect = on_connect
        _mqtt_client.on_message = _on_mqtt_message
        
        if MQTT_CONFIG["user"]:
            _mqtt_client.username_pw_set(MQTT_CONFIG["user"], MQTT_CONFIG["password"])
        
        _mqtt_client.connect(MQTT_CONFIG["broker"], MQTT_CONFIG["port"], 60)
        _mqtt_client.loop_start()
        
        return True
        
    except Exception as e:
        print(f"[MQTT] 启动失败: {e}")
        _mqtt_client = None
        return False


def stop_mqtt_subscription():
    """停止 MQTT 订阅"""
    global _mqtt_client
    
    if _mqtt_client:
        _mqtt_client.loop_stop()
        _mqtt_client.disconnect()
        _mqtt_client = None
        print("[MQTT] 已断开连接")


@tool
def get_realtime_plc_data(variable_names: Optional[List[str]] = None) -> str:
    """
    获取实时 PLC 数据
    
    Args:
        variable_names: 要获取的变量名列表 (英文)，为空则返回所有缓存数据
        
    Returns:
        JSON 格式的 PLC 数据
    """
    with _data_lock:
        if not _latest_data:
            return json.dumps({"error": "暂无数据，请确保 MQTT 订阅已启动", "hint": "调用 start_mqtt_subscription()"}, ensure_ascii=False)
        
        if variable_names:
            result = {k: _latest_data.get(k.lower(), "N/A") for k in variable_names}
        else:
            result = dict(_latest_data)
        
        return json.dumps(result, ensure_ascii=False, indent=2)


@tool
def get_turntable_status(turntable_id: int = 1) -> str:
    """
    获取指定转盘的实时状态
    
    Args:
        turntable_id: 转盘编号 (1, 2, 或 3)
        
    Returns:
        转盘状态信息 (频率、温度、液位等)
    """
    if turntable_id not in [1, 2, 3]:
        return json.dumps({"error": "无效的转盘编号，请使用 1, 2, 或 3"}, ensure_ascii=False)
    
    prefix = f"turntable{turntable_id}"
    tank_prefix = f"tank{turntable_id}"
    tt_prefix = f"tt{turntable_id}"
    
    with _data_lock:
        status = {
            "turntable_id": turntable_id,
            "frequency_set": _latest_data.get(f"{prefix}_frequency_set", "N/A"),
            "frequency_feedback": _latest_data.get(f"{prefix}_frequency_feedback", "N/A"),
            "regen_time": _latest_data.get(f"{prefix}_regen_time", "N/A"),
            "temperature": _latest_data.get(f"{prefix}_tank_temperature_t{turntable_id}", "N/A"),
            "temp_setpoint": _latest_data.get(f"{tt_prefix}_tank_temp{turntable_id}_set", "N/A"),
            "high_level": _latest_data.get(f"{tank_prefix}_high_level_l{turntable_id}", "N/A"),
            "low_level": _latest_data.get(f"{tank_prefix}_low_level_l{turntable_id}", "N/A"),
            "last_update": _latest_data.get("_last_update", "N/A"),
        }
    
    return json.dumps(status, ensure_ascii=False, indent=2)


@tool
def get_inhibition_rate() -> str:
    """
    获取当前出水抑制率设定值
    
    Returns:
        抑制率信息
    """
    with _data_lock:
        result = {
            "outlet_inhibition_rate_set": _latest_data.get("outlet_inhibitionrate_set", "N/A"),
            "box1_nh4_upper": _latest_data.get("box1_nh4_upper_set", "N/A"),
            "box2_nh4_upper": _latest_data.get("box2_nh4_upper_set", "N/A"),
            "box3_nh4_upper": _latest_data.get("box3_nh4_upper_set", "N/A"),
            "last_update": _latest_data.get("_last_update", "N/A"),
        }
    
    return json.dumps(result, ensure_ascii=False, indent=2)


def query_historical_data(
    table_name: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    从 PostgreSQL 查询历史数据
    
    Args:
        table_name: 表名
        start_time: 开始时间 (ISO 格式)
        end_time: 结束时间 (ISO 格式)
        limit: 返回记录数限制
        
    Returns:
        查询结果列表
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return [{"error": "psycopg2 未安装，请执行: pip install psycopg2-binary"}]
    
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 构建查询
        query = f"SELECT * FROM {table_name}"
        conditions = []
        params = []
        
        if start_time:
            conditions.append("created_at >= %s")
            params.append(start_time)
        if end_time:
            conditions.append("created_at <= %s")
            params.append(end_time)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += f" ORDER BY created_at DESC LIMIT {limit}"
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        
        conn.close()
        return [dict(row) for row in results]
        
    except Exception as e:
        return [{"error": f"数据库查询失败: {e}"}]


@tool
def list_database_tables() -> str:
    """
    列出 PostgreSQL 数据库中的所有表
    
    Returns:
        表名列表
    """
    try:
        import psycopg2
    except ImportError:
        return json.dumps({"error": "psycopg2 未安装"}, ensure_ascii=False)
    
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()
        
        return json.dumps({"tables": tables, "count": len(tables)}, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"查询失败: {e}"}, ensure_ascii=False)


@tool
def get_latest_plc_from_db() -> str:
    """
    从 PostgreSQL 数据库获取最新的 PLC 数据 (每 20 秒更新)
    
    Returns:
        最新的 PLC 数据，包含抶制率、氨氮、pH、MBR 参数等
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return json.dumps({"error": "psycopg2 未安装"}, ensure_ascii=False)
    
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM plc_data ORDER BY id DESC LIMIT 1')
        row = cursor.fetchone()
        conn.close()
        
        if row:
            # 转换为可序列化的格式
            result = {k: (str(v) if hasattr(v, 'isoformat') else v) for k, v in dict(row).items()}
            return json.dumps(result, ensure_ascii=False, indent=2)
        else:
            return json.dumps({"error": "无数据"}, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"error": f"查询失败: {e}"}, ensure_ascii=False)


@tool
def get_inhibition_trend(hours: int = 24) -> str:
    """
    获取过去 N 小时的抶制率趋势数据
    
    Args:
        hours: 查询过去多少小时的数据 (默认 24 小时)
        
    Returns:
        抶制率趋势数据 (每小时平均值)
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return json.dumps({"error": "psycopg2 未安装"}, ensure_ascii=False)
    
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute(f"""
            SELECT 
                date_trunc('hour', record_time) as hour,
                AVG(inlet_inhibition_ratio) as avg_inlet_inhibition,
                AVG(outlet_inhibition_ratio) as avg_outlet_inhibition,
                AVG(outlet_ammonia_nitrogen) as avg_outlet_ammonia,
                COUNT(*) as sample_count
            FROM plc_data 
            WHERE record_time > NOW() - INTERVAL '{hours} hours'
            GROUP BY date_trunc('hour', record_time)
            ORDER BY hour DESC
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        result = {
            "hours_queried": hours,
            "data_points": len(rows),
            "trend": [
                {
                    "hour": str(r["hour"]),
                    "inlet_inhibition": round(r["avg_inlet_inhibition"], 2) if r["avg_inlet_inhibition"] else None,
                    "outlet_inhibition": round(r["avg_outlet_inhibition"], 2) if r["avg_outlet_inhibition"] else None,
                    "outlet_ammonia": round(r["avg_outlet_ammonia"], 3) if r["avg_outlet_ammonia"] else None,
                    "samples": r["sample_count"]
                }
                for r in rows
            ]
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
        
    except Exception as e:
        return json.dumps({"error": f"查询失败: {e}"}, ensure_ascii=False)


@tool
def get_mbr_status() -> str:
    """
    获取 MBR 膜系统的最新状态
    
    Returns:
        MBR 系统参数 (跨膜压力、温度、溶解氧)
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return json.dumps({"error": "psycopg2 未安装"}, ensure_ascii=False)
    
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute("""
            SELECT 
                record_time,
                mbr_transmembrane_pressure,
                mbr_tank_temperature,
                mbr_dissolved_oxygen
            FROM plc_data 
            ORDER BY id DESC LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return json.dumps({
                "record_time": str(row["record_time"]),
                "transmembrane_pressure": row["mbr_transmembrane_pressure"],
                "tank_temperature": row["mbr_tank_temperature"],
                "dissolved_oxygen": row["mbr_dissolved_oxygen"],
            }, ensure_ascii=False, indent=2)
        else:
            return json.dumps({"error": "无数据"}, ensure_ascii=False)
            
    except Exception as e:
        return json.dumps({"error": f"查询失败: {e}"}, ensure_ascii=False)


# 导出的工具列表
REALTIME_TOOLS = [
    get_realtime_plc_data,
    get_turntable_status,
    get_inhibition_rate,
    list_database_tables,
    get_latest_plc_from_db,
    get_inhibition_trend,
    get_mbr_status,
]


if __name__ == "__main__":
    # 测试代码
    print("启动 MQTT 订阅...")
    if start_mqtt_subscription():
        import time
        print("等待数据 (10秒)...")
        time.sleep(10)
        
        print("\n当前数据:")
        print(get_realtime_plc_data.invoke({}))
        
        print("\n转盘1状态:")
        print(get_turntable_status.invoke({"turntable_id": 1}))
        
        print("\n抑制率:")
        print(get_inhibition_rate.invoke({}))
        
        stop_mqtt_subscription()
    else:
        print("MQTT 启动失败")
