# AQUAMIND 实时数据服务器配置 (已验证)

## 服务器基本信息

| 项目 | 值 |
|------|-----|
| IP 地址 | 139.196.187.10 |
| 平台 | 阿里云轻量服务器 |
| SSH 用户名 | root |
| SSH 密码 | Njucongfu! |
| Web 服务器 | nginx/1.21.5 |

## 数据源配置 (已验证)

### 1. MQTT Broker

| 配置项 | 值 |
|--------|-----|
| Broker | 139.196.187.10 (外网) / 127.0.0.1 (内网) |
| Port | 1883 |
| 认证 | 无 (user/password 为空) |
| Broker 类型 | Mosquitto |

**订阅主题**：
- `mess1`, `mess2`, `mess3` - 传感器消息
- `plc/data` - PLC 实时数据

**发布主题**：
- `smart/data` - 智能处理后的数据

### 2. PostgreSQL 数据库

| 配置项 | 值 |
|--------|-----|
| Host | pgm-bp1ksg5v1lo5z2r8eo.rwlb.rds.aliyuncs.com |
| Port | 5432 |
| Database | zhikong_data |
| User | nju_zhikong |
| Password | Njucongfu! |

## PLC 变量映射 (部分关键变量)

### 转盘控制
| 中文标签 | 英文字段 |
|----------|----------|
| 启动转盘1/2/3 | Start_Turntable1/2/3 |
| 转盘1/2/3频率给定 | Turntable1/2/3_Frequency_Set |
| 转盘1/2/3频率反馈 | Turntable1/2/3_Frequency_Feedback |
| 转盘1/2/3再生时间 | Turntable1/2/3_Regen_Time |
| 转盘1/2/3水箱温度计 | Turntable1/2/3_Tank_Temperature_T1/2/3 |

### 毒性/抑制率
| 中文标签 | 英文字段 |
|----------|----------|
| 出水抑制率设定 | Outlet_InhibitionRate_Set |
| 1/2/3箱氨氮上限设定 | Box1/2/3_NH4_Upper_Set |

### 温度控制
| 中文标签 | 英文字段 |
|----------|----------|
| 转盘1/2/3水箱温度设定 | TT1/2/3_Tank_Temp1/2/3_Set |
| 再生水箱加热温度设定 | RegenTank_HeatingTemp_Set |
| 再生放液许可温度 | Regen_Drain_Permit_Temp |

### 阀门控制
| 中文标签 | 英文字段 |
|----------|----------|
| 启动进水阀VA01/02/03 | Start_Inlet_Valve_VA01/02/03 |
| 启动出水阀VA04/05/06 | Start_Outlet_Valve_VA04/05/06 |
| 启动排水阀VA13 | Start_Drain_Valve_VA13 |

## 连接代码示例

### Python MQTT 订阅

```python
import paho.mqtt.client as mqtt
import json

MQTT_BROKER = "139.196.187.10"
MQTT_PORT = 1883
TOPICS = ["mess1", "mess2", "mess3", "plc/data"]

def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    for topic in TOPICS:
        client.subscribe(topic)
        print(f"Subscribed to {topic}")

def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode('utf-8'))
        print(f"Topic: {msg.topic}")
        print(f"Data: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Error: {e}")

client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)
client.loop_forever()
```

### PostgreSQL 连接

```python
import psycopg2

conn = psycopg2.connect(
    host="pgm-bp1ksg5v1lo5z2r8eo.rwlb.rds.aliyuncs.com",
    port=5432,
    dbname="zhikong_data",
    user="nju_zhikong",
    password="Njucongfu!"
)
cursor = conn.cursor()
cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
for table in cursor.fetchall():
    print(table[0])
conn.close()
```

## 服务器关键目录

| 目录 | 说明 |
|------|------|
| /root/ACMT/ | 主项目代码 (含 mqtt_demo.py, mqtt_tools.py) |
| /root/MQTT_test/ | MQTT 测试工具 (含 list_mqtt_topics.py) |
| /root/ECOMATS/ | ECOMATS 项目 |

## Docker 服务

| 容器名 | 镜像 | 端口 | 用途 |
|--------|------|------|------|
| docker-mysql-1 | mysql:8.0.39 | 5455 | MySQL |
| docker-es01-1 | elasticsearch:8.11.3 | 1200 | Elasticsearch |
| docker-redis-1 | valkey/valkey:8 | 6379 | Redis |
| docker-minio-1 | minio | 9000-9001 | 对象存储 |
| docker-ragflow-cpu-1 | ragflow | 8888, 9380-9382 | RAG 流程 |
| mongodb | mongo:latest | 27017 (内部) | MongoDB |
