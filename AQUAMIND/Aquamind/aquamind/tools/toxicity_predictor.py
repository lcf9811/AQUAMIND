"""
毒性预测工具

使用 LangChain @tool 装饰器定义，可被 Agent 直接调用。
支持实时数据和历史数据两种模式。
"""

import math
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd
import numpy as np
from langchain_core.tools import tool

from aquamind.core.config import settings, DATA_DIR


# 历史数据缓存
_historical_data_cache: Optional[pd.DataFrame] = None

# 告警阈值配置
ALERT_THRESHOLDS = {
    "inlet_inhibition_high": 50.0,      # 进水抑制率高阈值 (%)
    "inlet_inhibition_warning": 40.0,   # 进水抑制率警告阈值 (%)
    "outlet_inhibition_high": 10.0,     # 出水抑制率高阈值 (%)
    "outlet_inhibition_warning": 5.0,   # 出水抑制率警告阈值 (%)
    "ammonia_high": 2.0,                # 氨氮高阈值 (mg/L)
    "ammonia_warning": 1.5,             # 氨氮警告阈值 (mg/L)
    "ph_low": 6.0,                       # pH 低阈值
    "ph_high": 8.5,                      # pH 高阈值
}


def _load_historical_data() -> pd.DataFrame:
    """加载历史毒性数据"""
    global _historical_data_cache
    
    if _historical_data_cache is not None:
        return _historical_data_cache
    
    csv_path = DATA_DIR / "Toxicity.csv"
    
    if not csv_path.exists():
        # 生成模拟数据
        _historical_data_cache = _generate_mock_data()
        return _historical_data_cache
    
    try:
        df = pd.read_csv(csv_path, encoding="utf-8")
        
        # 列名映射
        column_mapping = {}
        
        # 日期列
        if "Date" in df.columns:
            column_mapping["Date"] = "date"
        
        # 毒性列
        toxicity_cols = [
            "Inhibition",
            "inflow_inhibition_rate（进水抑制率）",
            "box1_toxicity（1箱毒性）"
        ]
        for col in toxicity_cols:
            if col in df.columns:
                column_mapping[col] = "toxicity"
                break
        
        # 温度列
        temp_cols = ["日最高温", "总进水温度", "逐小时气温 (°C)"]
        for col in temp_cols:
            if col in df.columns:
                column_mapping[col] = "temperature"
                break
        
        # 氨氮列
        if "total_inflow_ammonia（总进水氨氮）" in df.columns:
            column_mapping["total_inflow_ammonia（总进水氨氮）"] = "ammonia_n"
        
        # pH列
        if "total_inflow_ph（总进水pH）" in df.columns:
            column_mapping["total_inflow_ph（总进水pH）"] = "ph"
        
        df = df.rename(columns=column_mapping)
        
        # 处理日期
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
        else:
            df["date"] = pd.date_range(start="2025-01-01", periods=len(df), freq="H")
        
        # 选择相关列
        cols = ["date", "toxicity", "temperature", "ammonia_n", "ph"]
        available_cols = [c for c in cols if c in df.columns]
        df = df[available_cols].ffill().bfill()
        
        _historical_data_cache = df
        return df
        
    except Exception as e:
        print(f"加载历史数据失败: {e}，使用模拟数据")
        _historical_data_cache = _generate_mock_data()
        return _historical_data_cache


def _generate_mock_data() -> pd.DataFrame:
    """生成模拟历史数据"""
    dates = pd.date_range(
        start=datetime.now() - timedelta(days=30),
        periods=720,  # 30天 * 24小时
        freq="H"
    )
    
    return pd.DataFrame({
        "date": dates,
        "temperature": np.random.normal(25, 5, len(dates)),
        "ammonia_n": np.random.normal(15, 5, len(dates)),
        "ph": np.random.normal(7.2, 0.3, len(dates)),
        "toxicity": np.random.normal(2.0, 0.8, len(dates)).clip(0.1, 5.0)
    })


def _calculate_toxicity_trend(toxicity_values: np.ndarray) -> str:
    """计算毒性趋势"""
    if len(toxicity_values) < 3:
        return "稳定"
    
    # 线性回归斜率
    x = np.arange(len(toxicity_values))
    coeffs = np.polyfit(x, toxicity_values, 1)
    slope = coeffs[0]
    
    if slope > 0.1:
        return "上升"
    elif slope < -0.1:
        return "下降"
    else:
        return "稳定"


@tool
def predict_toxicity_realtime() -> Dict[str, Any]:
    """
    基于实时数据预测毒性。
    
    从 PostgreSQL 获取最新的 PLC 数据，并基于当前抑制率和水质参数进行毒性预测。
    
    Returns:
        包含实时毒性预测结果的字典
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return {"error": "psycopg2 未安装，无法获取实时数据"}
    
    # 从 realtime_data 导入配置
    try:
        from aquamind.tools.realtime_data import PG_CONFIG
    except ImportError:
        PG_CONFIG = {
            "host": "pgm-bp1ksg5v1lo5z2r8eo.rwlb.rds.aliyuncs.com",
            "port": 5432,
            "dbname": "zhikong_data",
            "user": "nju_zhikong",
            "password": "Njucongfu!",
        }
    
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 获取最新数据
        cursor.execute('SELECT * FROM plc_data ORDER BY id DESC LIMIT 1')
        latest = cursor.fetchone()
        
        # 获取过去 6 小时的趋势
        cursor.execute("""
            SELECT 
                AVG(inlet_inhibition_ratio) as avg_inlet,
                AVG(outlet_inhibition_ratio) as avg_outlet,
                AVG(outlet_ammonia_nitrogen) as avg_ammonia
            FROM plc_data 
            WHERE record_time > NOW() - INTERVAL '6 hours'
        """)
        trend_data = cursor.fetchone()
        
        conn.close()
        
        if not latest:
            return {"error": "无数据"}
        
        # 提取关键参数
        inlet_inhibition = latest.get("inlet_inhibition_ratio", 0) or 0
        outlet_inhibition = latest.get("outlet_inhibition_ratio", 0) or 0
        outlet_ammonia = latest.get("outlet_ammonia_nitrogen", 0) or 0
        inlet_ph = latest.get("inlet_ph", 7.0) or 7.0
        outlet_ph = latest.get("outlet_ph", 7.0) or 7.0
        
        # 计算趋势
        avg_inlet = trend_data.get("avg_inlet", inlet_inhibition) or inlet_inhibition
        trend = "上升" if inlet_inhibition > avg_inlet * 1.1 else (
            "下降" if inlet_inhibition < avg_inlet * 0.9 else "稳定"
        )
        
        # 风险评估
        risk_factors = []
        risk_level = "低风险"
        
        if inlet_inhibition >= ALERT_THRESHOLDS["inlet_inhibition_high"]:
            risk_factors.append(f"进水抑制率超高 ({inlet_inhibition:.1f}%)")
            risk_level = "高风险"
        elif inlet_inhibition >= ALERT_THRESHOLDS["inlet_inhibition_warning"]:
            risk_factors.append(f"进水抑制率偏高 ({inlet_inhibition:.1f}%)")
            risk_level = "中风险"
        
        if outlet_inhibition >= ALERT_THRESHOLDS["outlet_inhibition_high"]:
            risk_factors.append(f"出水抑制率超高 ({outlet_inhibition:.1f}%)")
            risk_level = "高风险"
        elif outlet_inhibition >= ALERT_THRESHOLDS["outlet_inhibition_warning"]:
            risk_factors.append(f"出水抑制率偏高 ({outlet_inhibition:.1f}%)")
            if risk_level != "高风险":
                risk_level = "中风险"
        
        if outlet_ammonia >= ALERT_THRESHOLDS["ammonia_high"]:
            risk_factors.append(f"出水氨氮偏高 ({outlet_ammonia:.2f} mg/L)")
            if risk_level == "低风险":
                risk_level = "中风险"
        
        if outlet_ph < ALERT_THRESHOLDS["ph_low"] or outlet_ph > ALERT_THRESHOLDS["ph_high"]:
            risk_factors.append(f"pH 异常 ({outlet_ph:.2f})")
        
        # 生成建议
        recommendations = []
        if risk_level == "高风险":
            recommendations = [
                "立即检查进水水质，确认是否有毒性物质流入",
                "提高转盘频率至 40-50 Hz",
                "加强 MBR 系统曝气",
                "考虑启用备用处理单元",
            ]
        elif risk_level == "中风险":
            recommendations = [
                "密切监控抑制率变化趋势",
                "适当提高转盘频率 (25-35 Hz)",
                "检查活性炭系统状态",
            ]
        else:
            recommendations = [
                "维持当前运行参数",
                "定期巡检设备状态",
            ]
        
        if trend == "上升":
            recommendations.insert(0, "注意：抑制率呈上升趋势，建议提前准备")
        
        return {
            "data_source": "realtime_postgresql",
            "record_time": str(latest.get("record_time", "")),
            "current_values": {
                "inlet_inhibition_ratio": round(inlet_inhibition, 2),
                "outlet_inhibition_ratio": round(outlet_inhibition, 2),
                "outlet_ammonia_nitrogen": round(outlet_ammonia, 3),
                "inlet_ph": round(inlet_ph, 2),
                "outlet_ph": round(outlet_ph, 2),
            },
            "trend": trend,
            "risk_level": risk_level,
            "risk_factors": risk_factors if risk_factors else ["各项参数正常"],
            "recommendations": recommendations,
            "thresholds": ALERT_THRESHOLDS,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
    except Exception as e:
        return {"error": f"获取实时数据失败: {e}"}


@tool
def check_toxicity_alert() -> Dict[str, Any]:
    """
    检查当前毒性/抑制率是否触发告警。
    
    基于预设阈值检查进水/出水抑制率、氨氮、pH 等参数。
    
    Returns:
        告警检查结果，包含告警状态和详细信息
    """
    try:
        import psycopg2
        from psycopg2.extras import RealDictCursor
    except ImportError:
        return {"error": "psycopg2 未安装"}
    
    try:
        from aquamind.tools.realtime_data import PG_CONFIG
    except ImportError:
        PG_CONFIG = {
            "host": "pgm-bp1ksg5v1lo5z2r8eo.rwlb.rds.aliyuncs.com",
            "port": 5432,
            "dbname": "zhikong_data",
            "user": "nju_zhikong",
            "password": "Njucongfu!",
        }
    
    try:
        conn = psycopg2.connect(**PG_CONFIG)
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute('SELECT * FROM plc_data ORDER BY id DESC LIMIT 1')
        latest = cursor.fetchone()
        conn.close()
        
        if not latest:
            return {"alert_status": "unknown", "message": "无数据"}
        
        alerts = []
        alert_level = "normal"  # normal, warning, critical
        
        inlet_inhibition = latest.get("inlet_inhibition_ratio", 0) or 0
        outlet_inhibition = latest.get("outlet_inhibition_ratio", 0) or 0
        outlet_ammonia = latest.get("outlet_ammonia_nitrogen", 0) or 0
        outlet_ph = latest.get("outlet_ph", 7.0) or 7.0
        
        # 检查进水抑制率
        if inlet_inhibition >= ALERT_THRESHOLDS["inlet_inhibition_high"]:
            alerts.append({
                "type": "critical",
                "param": "inlet_inhibition_ratio",
                "value": inlet_inhibition,
                "threshold": ALERT_THRESHOLDS["inlet_inhibition_high"],
                "message": f"进水抑制率超过严重阈值 ({inlet_inhibition:.1f}% >= {ALERT_THRESHOLDS['inlet_inhibition_high']}%)"
            })
            alert_level = "critical"
        elif inlet_inhibition >= ALERT_THRESHOLDS["inlet_inhibition_warning"]:
            alerts.append({
                "type": "warning",
                "param": "inlet_inhibition_ratio",
                "value": inlet_inhibition,
                "threshold": ALERT_THRESHOLDS["inlet_inhibition_warning"],
                "message": f"进水抑制率超过警告阈值 ({inlet_inhibition:.1f}% >= {ALERT_THRESHOLDS['inlet_inhibition_warning']}%)"
            })
            if alert_level != "critical":
                alert_level = "warning"
        
        # 检查出水抑制率
        if outlet_inhibition >= ALERT_THRESHOLDS["outlet_inhibition_high"]:
            alerts.append({
                "type": "critical",
                "param": "outlet_inhibition_ratio",
                "value": outlet_inhibition,
                "threshold": ALERT_THRESHOLDS["outlet_inhibition_high"],
                "message": f"出水抑制率超过严重阈值 ({outlet_inhibition:.1f}% >= {ALERT_THRESHOLDS['outlet_inhibition_high']}%)"
            })
            alert_level = "critical"
        elif outlet_inhibition >= ALERT_THRESHOLDS["outlet_inhibition_warning"]:
            alerts.append({
                "type": "warning",
                "param": "outlet_inhibition_ratio",
                "value": outlet_inhibition,
                "threshold": ALERT_THRESHOLDS["outlet_inhibition_warning"],
                "message": f"出水抑制率超过警告阈值 ({outlet_inhibition:.1f}% >= {ALERT_THRESHOLDS['outlet_inhibition_warning']}%)"
            })
            if alert_level != "critical":
                alert_level = "warning"
        
        # 检查氨氮
        if outlet_ammonia >= ALERT_THRESHOLDS["ammonia_high"]:
            alerts.append({
                "type": "warning",
                "param": "outlet_ammonia_nitrogen",
                "value": outlet_ammonia,
                "threshold": ALERT_THRESHOLDS["ammonia_high"],
                "message": f"出水氨氮超过阈值 ({outlet_ammonia:.2f} mg/L >= {ALERT_THRESHOLDS['ammonia_high']} mg/L)"
            })
            if alert_level == "normal":
                alert_level = "warning"
        
        # 检查 pH
        if outlet_ph < ALERT_THRESHOLDS["ph_low"]:
            alerts.append({
                "type": "warning",
                "param": "outlet_ph",
                "value": outlet_ph,
                "threshold": ALERT_THRESHOLDS["ph_low"],
                "message": f"出水 pH 过低 ({outlet_ph:.2f} < {ALERT_THRESHOLDS['ph_low']})"
            })
            if alert_level == "normal":
                alert_level = "warning"
        elif outlet_ph > ALERT_THRESHOLDS["ph_high"]:
            alerts.append({
                "type": "warning",
                "param": "outlet_ph",
                "value": outlet_ph,
                "threshold": ALERT_THRESHOLDS["ph_high"],
                "message": f"出水 pH 过高 ({outlet_ph:.2f} > {ALERT_THRESHOLDS['ph_high']})"
            })
            if alert_level == "normal":
                alert_level = "warning"
        
        return {
            "alert_status": alert_level,
            "alert_count": len(alerts),
            "alerts": alerts,
            "record_time": str(latest.get("record_time", "")),
            "current_values": {
                "inlet_inhibition_ratio": round(inlet_inhibition, 2),
                "outlet_inhibition_ratio": round(outlet_inhibition, 2),
                "outlet_ammonia_nitrogen": round(outlet_ammonia, 3),
                "outlet_ph": round(outlet_ph, 2),
            },
            "check_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        
    except Exception as e:
        return {"error": f"告警检查失败: {e}"}


@tool
def predict_toxicity(
    ammonia_n: float = 15.0,
    temperature: float = 25.0,
    ph: float = 7.0,
    current_toxicity: Optional[float] = None
) -> Dict[str, Any]:
    """
    预测未来 24 小时的水质毒性等级。
    
    根据当前水质参数和历史数据，预测未来毒性水平并提供风险评估。
    
    Args:
        ammonia_n: 氨氮浓度 (mg/L)，正常范围 5-30
        temperature: 水温 (°C)，正常范围 10-35
        ph: pH 值，正常范围 6.5-8.5
        current_toxicity: 当前毒性值（可选），用于趋势分析
    
    Returns:
        包含毒性预测结果的字典，包括:
        - predicted_toxicity: 预测毒性值
        - toxicity_level: 毒性等级 (低/中/高)
        - trend: 变化趋势 (上升/稳定/下降)
        - risk_level: 风险等级
        - confidence: 置信度
        - factors: 影响因素列表
        - recommendations: 建议措施
    """
    # 加载历史数据
    historical_data = _load_historical_data()
    
    # 基础预测
    base_toxicity = historical_data["toxicity"].mean() if len(historical_data) > 0 else 2.0
    
    # 参数影响调整
    adjustment = 1.0
    factors = []
    
    # 氨氮影响
    if ammonia_n > 25:
        adjustment += 0.2
        factors.append(f"氨氮浓度偏高 ({ammonia_n:.1f} mg/L)")
    elif ammonia_n > 20:
        adjustment += 0.1
        factors.append(f"氨氮浓度略高 ({ammonia_n:.1f} mg/L)")
    elif ammonia_n < 5:
        adjustment -= 0.05
    
    # pH 影响
    if ph < 6.5 or ph > 8.5:
        adjustment += 0.1
        factors.append(f"pH 值偏离正常范围 ({ph:.1f})")
    
    # 温度影响
    if temperature > 32:
        adjustment += 0.1
        factors.append(f"高温环境 ({temperature:.1f}°C)")
    elif temperature < 10:
        adjustment += 0.05
        factors.append(f"低温环境 ({temperature:.1f}°C)")
    
    # 计算预测值
    predicted_toxicity = round(base_toxicity * adjustment, 2)
    predicted_toxicity = max(0.1, min(10.0, predicted_toxicity))
    
    # 计算趋势
    if len(historical_data) >= 7:
        recent_toxicity = historical_data.tail(24)["toxicity"].values
        trend = _calculate_toxicity_trend(recent_toxicity)
    else:
        trend = "稳定"
    
    # 确定等级
    toxicity_level = settings.agent.get_toxicity_level(predicted_toxicity)
    
    # 确定风险等级
    if predicted_toxicity > 3.5 or (predicted_toxicity > 2.5 and trend == "上升"):
        risk_level = "高风险"
    elif predicted_toxicity > 2.0 or (predicted_toxicity > 1.5 and trend == "上升"):
        risk_level = "中风险"
    else:
        risk_level = "低风险"
    
    # 生成建议
    recommendations = []
    if toxicity_level == "高":
        recommendations.extend([
            "建议启用备用转盘反应器",
            "提高转盘频率至 35-50 Hz",
            "加强 MBR 曝气量",
            "检查活性炭是否需要再生"
        ])
    elif toxicity_level == "中":
        recommendations.extend([
            "维持转盘频率在 15-35 Hz",
            "持续监测毒性变化趋势",
            "确保 MBR 系统正常运行"
        ])
    else:
        recommendations.extend([
            "可考虑节能运行模式",
            "转盘频率可降至 5-15 Hz",
            "定期检查设备状态"
        ])
    
    if trend == "上升":
        recommendations.insert(0, "毒性呈上升趋势，建议提前准备应对措施")
    
    # 计算置信度
    confidence = 0.85
    if len(factors) > 2:
        confidence -= 0.05
    if trend == "上升":
        confidence -= 0.05
    
    return {
        "predicted_toxicity": predicted_toxicity,
        "toxicity_level": toxicity_level,
        "trend": trend,
        "risk_level": risk_level,
        "confidence": round(confidence, 2),
        "factors": factors if factors else ["各项参数正常"],
        "recommendations": recommendations,
        "input_params": {
            "ammonia_n": ammonia_n,
            "temperature": temperature,
            "ph": ph
        },
        "prediction_time": (datetime.now() + timedelta(hours=24)).strftime("%Y-%m-%d %H:%M"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }


@tool
def get_historical_stats() -> Dict[str, Any]:
    """
    获取历史毒性数据统计信息。
    
    返回过去 30 天的毒性数据统计，包括均值、标准差、最大最小值等。
    用于辅助毒性预测和趋势分析。
    
    Returns:
        包含统计信息的字典:
        - mean_toxicity: 平均毒性
        - std_toxicity: 标准差
        - max_toxicity: 最大值
        - min_toxicity: 最小值
        - data_points: 数据点数量
        - recent_trend: 近期趋势
    """
    historical_data = _load_historical_data()
    
    if len(historical_data) == 0:
        return {
            "mean_toxicity": 2.0,
            "std_toxicity": 0.5,
            "max_toxicity": 3.5,
            "min_toxicity": 0.5,
            "data_points": 0,
            "recent_trend": "未知"
        }
    
    toxicity_values = historical_data["toxicity"].dropna()
    
    # 计算趋势
    if len(toxicity_values) >= 24:
        recent = toxicity_values.tail(24).values
        trend = _calculate_toxicity_trend(recent)
    else:
        trend = "未知"
    
    return {
        "mean_toxicity": round(float(toxicity_values.mean()), 2),
        "std_toxicity": round(float(toxicity_values.std()), 2),
        "max_toxicity": round(float(toxicity_values.max()), 2),
        "min_toxicity": round(float(toxicity_values.min()), 2),
        "data_points": len(toxicity_values),
        "recent_trend": trend,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
