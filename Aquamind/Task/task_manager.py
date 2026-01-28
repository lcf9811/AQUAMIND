"""
任务管理模块
处理不同类型的任务请求
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.Tool.predict_toxicity import PredictToxicityTool


class BaseTask(ABC):
    """任务基类"""

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """执行任务"""
        pass


class ToxicityPredictionTask(BaseTask):
    """毒性预测任务"""

    def __init__(self):
        self.predictor = PredictToxicityTool()

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行毒性预测任务

        Args:
            params: 预测参数

        Returns:
            预测结果
        """
        # 设置默认参数
        default_params = {
            "temperature": 25.0,
            "humidity": 60.0,
            "ammonia_n": 10.0,
            "nitrate_n": 5.0,
            "ph": 7.0,
            "rainfall": 0.0
        }

        # 合并参数
        default_params.update(params)

        # 执行预测
        result_str = self.predictor.run(default_params)

        # 解析结果字符串为字典
        try:
            # 移除numpy类型标记和datetime对象，使其成为有效的Python字典字符串
            import re
            result_str_clean = re.sub(r"np\.float64\(([^)]+)\)", r"\1", result_str)
            # 移除datetime对象的表示
            result_str_clean = re.sub(r"datetime\.datetime\([^)]+\)", r"'datetime_object'", result_str_clean)
            import ast
            result = ast.literal_eval(result_str_clean)
            return result
        except Exception as e:
            # 如果解析失败，返回原始字符串
            print(f"解析结果时出错: {e}")
            return {"raw_result": result_str}


class HistoricalAnalysisTask(BaseTask):
    """历史数据分析任务"""

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行历史数据分析任务

        Args:
            params: 分析参数

        Returns:
            分析结果
        """
        try:
            # 使用与预测工具相同的CSV数据加载方法
            from Agent.Tool.predict_toxicity import PredictToxicityTool
            predictor = PredictToxicityTool()
            historical_data = predictor.historical_data
        except Exception as e:
            print(f"警告：加载历史数据时出错: {e}，将使用模拟数据")
            import pandas as pd
            import numpy as np
            from datetime import datetime, timedelta

            dates = pd.date_range(start=datetime.now() - timedelta(days=30), periods=30, freq='D')
            historical_data = pd.DataFrame({
                'date': dates,
                'toxicity': np.random.normal(2.0, 0.5, 30)
            })

        if len(historical_data) == 0:
            return {"error": "没有历史数据可供分析"}

        analysis = {
            "total_records": len(historical_data),
            "date_range": {
                "start": historical_data['date'].min().strftime('%Y-%m-%d'),
                "end": historical_data['date'].max().strftime('%Y-%m-%d')
            },
            "toxicity_stats": {
                "mean": float(historical_data['toxicity'].mean()),
                "std": float(historical_data['toxicity'].std()),
                "min": float(historical_data['toxicity'].min()),
                "max": float(historical_data['toxicity'].max())
            }
        }

        # 计算最近7天的趋势
        if len(historical_data) >= 7:
            recent_data = historical_data.tail(7)
            recent_avg = recent_data['toxicity'].mean()
            overall_avg = historical_data['toxicity'].mean()
            analysis["recent_trend"] = {
                "recent_avg": float(recent_avg),
                "change_from_overall": float(recent_avg - overall_avg)
            }

        return analysis


class TaskManager:
    """任务管理器"""

    def __init__(self):
        self.tasks = {
            'toxicity_prediction': ToxicityPredictionTask(),
            'historical_analysis': HistoricalAnalysisTask()
        }

    def execute_task(self, task_name: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        执行指定任务

        Args:
            task_name: 任务名称
            params: 任务参数

        Returns:
            任务执行结果
        """
        if params is None:
            params = {}

        if task_name not in self.tasks:
            return {"error": f"未知任务: {task_name}"}

        try:
            return self.tasks[task_name].execute(params)
        except Exception as e:
            return {"error": f"任务执行失败: {str(e)}"}