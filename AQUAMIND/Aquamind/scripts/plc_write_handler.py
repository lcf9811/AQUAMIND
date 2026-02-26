#!/usr/bin/env python3
"""
PLC Write Handler - plc/write 主题订阅转发程序

功能：
1. 订阅 MQTT plc/write 主题
2. 解析控制指令
3. 记录到日志文件
4. 转发到 ZMQ 或直接控制 PLC

启动方式：
    python3 plc_write_handler.py

后台运行：
    nohup python3 plc_write_handler.py > plc_write.log 2>&1 &
"""

import json
import time
import logging
from datetime import datetime
from typing import Dict, Any, Optional

import paho.mqtt.client as mqtt

# ============================================
# 配置
# ============================================

MQTT_CONFIG = {
    "broker": "127.0.0.1",
    "port": 1883,
    "subscribe_topic": "plc/write",
    "status_topic": "plc/write/status",
    "user": "",
    "password": "",
}

# 日志配置
LOG_FILE = "/root/MQTT_test/plc_write.log"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"

# ============================================
# 日志初始化
# ============================================

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================
# 控制指令处理
# ============================================

# 控制指令统计
command_stats = {
    "total_received": 0,
    "total_success": 0,
    "total_failed": 0,
    "last_command_time": None,
}


def process_plc_command(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    处理 PLC 控制指令
    
    Args:
        data: 控制指令数据，格式为 {"data": {"变量名": "值", ...}}
    
    Returns:
        处理结果
    """
    result = {
        "success": True,
        "processed_vars": [],
        "errors": [],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    if "data" not in data:
        result["success"] = False
        result["errors"].append("缺少 'data' 字段")
        return result
    
    commands = data["data"]
    
    for var_name, value in commands.items():
        try:
            # 这里可以添加实际的 PLC 控制逻辑
            # 例如：Modbus 写入、串口通信等
            
            # 目前仅记录日志
            logger.info(f"  📤 设置 [{var_name}] = {value}")
            result["processed_vars"].append({
                "variable": var_name,
                "value": value,
                "status": "ok"
            })
            
        except Exception as e:
            logger.error(f"  ❌ 设置 [{var_name}] 失败: {e}")
            result["errors"].append(f"{var_name}: {str(e)}")
            result["success"] = False
    
    return result


def forward_to_plc(data: Dict[str, Any]) -> bool:
    """
    转发指令到实际 PLC
    
    TODO: 实现实际的 PLC 通信逻辑
    - Modbus TCP/RTU
    - 串口通信
    - OPC UA
    
    Args:
        data: 控制指令
    
    Returns:
        是否成功
    """
    # 预留接口：实际 PLC 通信
    # 当前为模拟模式，仅记录日志
    return True


# ============================================
# MQTT 回调函数
# ============================================

def on_connect(client, userdata, flags, rc):
    """连接回调"""
    if rc == 0:
        logger.info(f"✅ 已连接到 MQTT Broker: {MQTT_CONFIG['broker']}:{MQTT_CONFIG['port']}")
        client.subscribe(MQTT_CONFIG["subscribe_topic"])
        logger.info(f"✅ 已订阅主题: {MQTT_CONFIG['subscribe_topic']}")
        
        # 发布上线状态
        status = {
            "status": "online",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "subscribe_topic": MQTT_CONFIG["subscribe_topic"]
        }
        client.publish(MQTT_CONFIG["status_topic"], json.dumps(status, ensure_ascii=False))
    else:
        logger.error(f"❌ 连接失败，错误码: {rc}")


def on_disconnect(client, userdata, rc):
    """断开连接回调"""
    logger.warning(f"⚠️ 与 MQTT Broker 断开连接，错误码: {rc}")
    if rc != 0:
        logger.info("🔄 尝试重新连接...")


def on_message(client, userdata, msg):
    """消息处理回调"""
    global command_stats
    
    topic = msg.topic
    payload = msg.payload.decode("utf-8", errors="replace")
    
    command_stats["total_received"] += 1
    command_stats["last_command_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    logger.info("=" * 60)
    logger.info(f"📥 收到控制指令 #{command_stats['total_received']}")
    logger.info(f"   主题: {topic}")
    logger.info(f"   时间: {command_stats['last_command_time']}")
    
    try:
        # 解析 JSON
        data = json.loads(payload)
        logger.info(f"   内容: {json.dumps(data, ensure_ascii=False)}")
        
        # 处理指令
        result = process_plc_command(data)
        
        if result["success"]:
            command_stats["total_success"] += 1
            logger.info(f"✅ 指令处理成功，已处理 {len(result['processed_vars'])} 个变量")
            
            # 转发到实际 PLC (预留)
            forward_to_plc(data)
        else:
            command_stats["total_failed"] += 1
            logger.error(f"❌ 指令处理失败: {result['errors']}")
        
        # 发布处理结果
        client.publish(
            MQTT_CONFIG["status_topic"],
            json.dumps(result, ensure_ascii=False)
        )
        
    except json.JSONDecodeError as e:
        command_stats["total_failed"] += 1
        logger.error(f"❌ JSON 解析失败: {e}")
        logger.error(f"   原始数据: {payload[:200]}")
    
    except Exception as e:
        command_stats["total_failed"] += 1
        logger.error(f"❌ 处理异常: {e}")
    
    logger.info("=" * 60)


# ============================================
# 主程序
# ============================================

def main():
    """主函数"""
    logger.info("=" * 60)
    logger.info("🚀 PLC Write Handler 启动")
    logger.info(f"   订阅主题: {MQTT_CONFIG['subscribe_topic']}")
    logger.info(f"   状态主题: {MQTT_CONFIG['status_topic']}")
    logger.info(f"   日志文件: {LOG_FILE}")
    logger.info("=" * 60)
    
    # 创建 MQTT 客户端 (使用唯一 ID)
    import uuid
    client_id = f"plc_write_handler_{uuid.uuid4().hex[:8]}"
    client = mqtt.Client(client_id=client_id, clean_session=True)
    
    # 设置回调
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    
    # 认证 (如需要)
    if MQTT_CONFIG["user"]:
        client.username_pw_set(MQTT_CONFIG["user"], MQTT_CONFIG["password"])
    
    # 连接并循环
    try:
        client.connect(MQTT_CONFIG["broker"], MQTT_CONFIG["port"], 60)
        client.loop_forever()
        
    except KeyboardInterrupt:
        logger.info("\n🛑 收到中断信号，正在退出...")
        
        # 发布离线状态
        status = {
            "status": "offline",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "stats": command_stats
        }
        client.publish(MQTT_CONFIG["status_topic"], json.dumps(status, ensure_ascii=False))
        client.disconnect()
        
        logger.info(f"📊 统计: 收到 {command_stats['total_received']} 条指令, "
                   f"成功 {command_stats['total_success']}, "
                   f"失败 {command_stats['total_failed']}")
        logger.info("👋 PLC Write Handler 已退出")
        
    except Exception as e:
        logger.error(f"❌ 运行异常: {e}")
        raise


if __name__ == "__main__":
    main()
