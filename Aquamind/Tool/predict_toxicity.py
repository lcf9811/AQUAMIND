"""
基于LangChain的毒性预测工具
根据用户输入的毒性数据，预测24小时后的毒性数据
"""

from langchain.tools import BaseTool
from typing import Optional, Type, Dict, Any
from pydantic import BaseModel, Field, PrivateAttr
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from LLM.llm_interface import LLMInterface


class PredictToxicityInput(BaseModel):
    """毒性预测工具的输入参数"""
    temperature: Optional[float] = Field(default=25.0, description="温度 (°C)")
    humidity: Optional[float] = Field(default=60.0, description="湿度 (%)")
    ammonia_n: Optional[float] = Field(default=10.0, description="氨氮 (mg/L)")
    nitrate_n: Optional[float] = Field(default=5.0, description="硝氮 (mg/L)")
    ph: Optional[float] = Field(default=7.0, description="pH值")
    rainfall: Optional[float] = Field(default=0.0, description="降雨量 (mm)")


class PredictToxicityTool(BaseTool):
    """毒性预测工具类"""
    name: str = "predict_toxicity"
    description: str = "根据输入的环境和水质参数预测24小时后的毒性水平"

    args_schema: Type[BaseModel] = PredictToxicityInput
    
    # 使用 PrivateAttr 来定义私有属性，避免 Pydantic 验证错误
    _historical_data_cache: Optional[pd.DataFrame] = PrivateAttr(default=None)
    _llm_interface: Optional[Any] = PrivateAttr(default=None)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # 初始化大模型接口
        try:
            # 必须使用 object.__setattr__ 绕过 pydantic 的 __setattr__ 检查
            # 或者直接赋值，因为 PrivateAttr 应该允许赋值，但似乎 v1/v2 兼容性有问题
            # 在 LangChain 0.1 中 BaseTool 可能是 Pydantic V1 模型
            object.__setattr__(self, "_llm_interface", LLMInterface())
        except Exception as e:
            print(f"警告：初始化大模型接口失败: {e}，将使用本地预测方法")
            object.__setattr__(self, "_llm_interface", None)

    @property
    def historical_data(self):
        """获取历史数据，延迟加载"""
        if self._historical_data_cache is None:
            try:
                self._historical_data_cache = self._load_csv_data()
                print(f"成功加载历史数据，共 {len(self._historical_data_cache)} 条记录")
            except FileNotFoundError:
                print("警告：未找到'Toxicity.csv'文件，将使用模拟数据")
                self._historical_data_cache = self._generate_mock_data()
        return self._historical_data_cache

    def _get_historical_data(self):
        """获取历史数据的辅助方法"""
        try:
            return self._load_csv_data()
        except FileNotFoundError:
            print("警告：未找到'Toxicity.csv'文件，将使用模拟数据")
            return self._generate_mock_data()

    def _load_csv_data(self):
        """从CSV文件加载数据"""
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "Data", "Toxicity.csv")
        df = pd.read_csv(csv_path, encoding='utf-8')

        # 数据预处理，确保列名正确
        # 根据实际数据结构，建立正确的列名映射
        column_mapping = {}

        # 日期列
        if 'Date' in df.columns:
            column_mapping['Date'] = 'date'

        # 毒性列 - 优先使用Inhibition（抑制率），如果不存在则找其他毒性相关列
        if 'Inhibition' in df.columns:
            column_mapping['Inhibition'] = 'toxicity'
        elif 'inflow_inhibition_rate（进水抑制率）' in df.columns:
            column_mapping['inflow_inhibition_rate（进水抑制率）'] = 'toxicity'
        elif 'box1_toxicity（1箱毒性）' in df.columns:
            column_mapping['box1_toxicity（1箱毒性）'] = 'toxicity'
        elif 'box2_toxicity（2箱毒性）' in df.columns:
            column_mapping['box2_toxicity（2箱毒性）'] = 'toxicity'
        elif 'box3_toxicity（3箱毒性）' in df.columns:
            column_mapping['box3_toxicity（3箱毒性）'] = 'toxicity'

        # 温度列
        if '日最高温' in df.columns:
            column_mapping['日最高温'] = 'temperature'
        elif '总进水温度' in df.columns:
            column_mapping['总进水温度'] = 'temperature'
        elif '逐小时气温 (°C)' in df.columns:
            column_mapping['逐小时气温 (°C)'] = 'temperature'

        # 湿度列
        if '相对湿度' in df.columns:
            column_mapping['相对湿度'] = 'humidity'

        # 氨氮列
        if 'total_inflow_ammonia（总进水氨氮）' in df.columns:
            column_mapping['total_inflow_ammonia（总进水氨氮）'] = 'ammonia_n'

        # 硝氮列
        if 'total_inflow_nitrate（总进水硝氮）' in df.columns:
            column_mapping['total_inflow_nitrate（总进水硝氮）'] = 'nitrate_n'

        # pH列
        if 'total_inflow_ph（总进水pH）' in df.columns:
            column_mapping['total_inflow_ph（总进水pH）'] = 'ph'

        # 应用列名映射
        df = df.rename(columns=column_mapping)

        # 处理日期列
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
        else:
            # 如果没有日期列，使用索引作为日期
            df['date'] = pd.date_range(start='2025-01-01', periods=len(df), freq='H')

        # 选择相关列并处理缺失值
        relevant_cols = ['date', 'toxicity', 'temperature', 'humidity', 'ammonia_n', 'nitrate_n', 'ph']
        available_cols = [col for col in relevant_cols if col in df.columns]
        df = df[available_cols].ffill().bfill()

        return df

    def _generate_mock_data(self):
        """生成模拟历史数据用于测试"""
        dates = pd.date_range(start=datetime.now() - timedelta(days=30), periods=30, freq='D')
        data = {
            'date': dates,
            'temperature': np.random.normal(25, 5, 30),
            'humidity': np.random.normal(60, 10, 30),
            'ammonia_n': np.random.normal(10, 3, 30),
            'nitrate_n': np.random.normal(5, 2, 30),
            'ph': np.random.normal(7, 0.5, 30),
            'toxicity': np.random.normal(2.0, 0.5, 30)
        }
        return pd.DataFrame(data)

    def _prepare_input_data(self, **kwargs) -> dict:
        """准备输入数据"""
        input_data = {
            'date': datetime.now() + timedelta(hours=24),  # 预测24小时后
            'temperature': kwargs.get('temperature', 25.0),
            'humidity': kwargs.get('humidity', 60.0),
            'ammonia_n': kwargs.get('ammonia_n', 10.0),
            'nitrate_n': kwargs.get('nitrate_n', 5.0),
            'ph': kwargs.get('ph', 7.0),
            'rainfall': kwargs.get('rainfall', 0.0)
        }
        return input_data

    def _time_series_prediction(self, input_data: dict) -> float:
        """基于时间序列的趋势预测24小时后的毒性"""
        # 获取最近的数据趋势
        if len(self.historical_data) >= 7:
            recent_data = self.historical_data.tail(7).copy()

            # 计算毒性趋势
            recent_toxicity = recent_data['toxicity'].values
            time_points = np.arange(len(recent_toxicity))

            # 使用线性回归预测趋势
            if len(time_points) > 1:
                coeffs = np.polyfit(time_points, recent_toxicity, 1)
                # 预测下一个时间点（即24小时后）
                next_toxicity = coeffs[0] * len(time_points) + coeffs[1]

                # 根据输入参数调整预测值
                # 氨氮影响
                if input_data['ammonia_n'] > 15:
                    next_toxicity *= 1.1
                elif input_data['ammonia_n'] > 25:
                    next_toxicity *= 1.2

                # pH影响
                if input_data['ph'] < 6.5 or input_data['ph'] > 8.5:
                    next_toxicity *= 1.05

                # 温度影响
                if input_data['temperature'] > 30:
                    next_toxicity *= 1.05
                elif input_data['temperature'] < 10:
                    next_toxicity *= 1.03

                return max(0.1, next_toxicity)  # 确保毒性值为正

        # 如果历史数据不足，使用简单方法
        avg_toxicity = self.historical_data['toxicity'].mean() if len(self.historical_data) > 0 else 2.0

        # 根据输入参数调整基础毒性
        adjustment = 1.0
        if input_data['ammonia_n'] > 15:
            adjustment += 0.1
        if input_data['ph'] < 6.5 or input_data['ph'] > 8.5:
            adjustment += 0.05
        if input_data['temperature'] > 30 or input_data['temperature'] < 10:
            adjustment += 0.03

        return avg_toxicity * adjustment

    def _run(self, **kwargs) -> str:
        """执行预测的主要方法"""
        try:
            # 准备输入数据
            input_data = self._prepare_input_data(**kwargs)

            # 尝试使用大模型进行预测
            if self._llm_interface is not None:
                try:
                    # 准备历史数据统计
                    hist_data = self._get_historical_stats()
                    llm_result = self._llm_interface.predict_toxicity_with_llm(input_data, hist_data)

                    # 合并结果
                    result = {
                        "prediction_type": "24小时毒性预测",
                        "current_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        "prediction_time": (datetime.now() + timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S'),
                        "input_parameters": input_data,
                        "predicted_toxicity": llm_result.get("predicted_toxicity", 2.0),
                        "toxicity_level": llm_result.get("toxicity_level", "中"),
                        "confidence": llm_result.get("confidence", 0.7),
                        "llm_explanation": llm_result.get("explanation", ""),
                        "factors": llm_result.get("factors", []),
                        "recommendations": llm_result.get("recommendations", [])
                    }

                    # 为兼容性添加风险评估
                    risk_assessment = self._assess_risk(
                        result["predicted_toxicity"],
                        result["input_parameters"]
                    )
                    result["risk_assessment"] = risk_assessment

                    return str(result)
                except Exception as llm_e:
                    print(f"大模型预测失败: {llm_e}，回退到本地预测方法")
                    # 如果大模型预测失败，回退到本地方法

            # 使用本地时间序列方法预测
            predicted_toxicity = self._time_series_prediction(input_data)

            # 获取当前时间及预测时间
            current_time = datetime.now()
            prediction_time = current_time + timedelta(hours=24)

            # 生成预测报告
            result = {
                "prediction_type": "24小时毒性预测",
                "current_time": current_time.strftime('%Y-%m-%d %H:%M:%S'),
                "prediction_time": prediction_time.strftime('%Y-%m-%d %H:%M:%S'),
                "input_parameters": {
                    "temperature": input_data['temperature'],
                    "humidity": input_data['humidity'],
                    "ammonia_n": input_data['ammonia_n'],
                    "nitrate_n": input_data['nitrate_n'],
                    "ph": input_data['ph'],
                    "rainfall": input_data['rainfall']
                },
                "predicted_toxicity": round(predicted_toxicity, 2),
                "toxicity_level": self._get_toxicity_level(predicted_toxicity),
                "confidence": 0.85  # 默认置信度
            }

            # 添加风险提示
            risk_assessment = self._assess_risk(predicted_toxicity, input_data)
            result["risk_assessment"] = risk_assessment

            return str(result)

        except Exception as e:
            return f"预测过程中发生错误: {str(e)}"

    async def _arun(self, **kwargs) -> str:
        """异步运行方法"""
        raise NotImplementedError("predict_toxicity工具不支持异步运行")

    def _get_historical_stats(self) -> Dict[str, float]:
        """获取历史数据统计信息"""
        try:
            historical_df = self.historical_data
            if len(historical_df) > 0 and 'toxicity' in historical_df.columns:
                toxicity_values = historical_df['toxicity'].dropna()
                if len(toxicity_values) > 0:
                    return {
                        "mean_toxicity": float(toxicity_values.mean()),
                        "std_toxicity": float(toxicity_values.std()),
                        "max_toxicity": float(toxicity_values.max()),
                        "min_toxicity": float(toxicity_values.min())
                    }
        except Exception:
            pass

        # 如果无法获取历史数据统计，返回默认值
        return {
            "mean_toxicity": 2.0,
            "std_toxicity": 0.5,
            "max_toxicity": 5.0,
            "min_toxicity": 0.0
        }

    def _get_toxicity_level(self, toxicity_value: float) -> str:
        """根据毒性值确定毒性等级"""
        if toxicity_value < 1.5:
            return "低"
        elif toxicity_value < 3.0:
            return "中"
        else:
            return "高"

    def _assess_risk(self, predicted_toxicity: float, input_data: dict) -> dict:
        """评估风险"""
        risk_factors = []

        if input_data['ammonia_n'] > 20:
            risk_factors.append("氨氮浓度过高，可能影响毒性水平")
        if input_data['ph'] < 6.5 or input_data['ph'] > 8.5:
            risk_factors.append("pH值偏离正常范围，可能增加毒性风险")
        if input_data['temperature'] > 35:
            risk_factors.append("高温可能加剧毒性效应")
        if input_data['rainfall'] > 10:
            risk_factors.append("降雨可能导致污染物冲刷，影响水质")

        if predicted_toxicity > 3.0:
            risk_level = "高风险"
            recommendations = [
                "加强水质监测频率",
                "准备应急处理措施",
                "考虑调整处理工艺参数"
            ]
        elif predicted_toxicity > 2.0:
            risk_level = "中等风险"
            recommendations = [
                "保持常规监测",
                "关注水质变化趋势"
            ]
        else:
            risk_level = "低风险"
            recommendations = [
                "维持当前运行状态",
                "继续常规监测"
            ]

        return {
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "recommendations": recommendations
        }


# 测试函数
def test_predict_tool():
    """测试预测工具"""
    print("初始化毒性预测工具...")
    tool = PredictToxicityTool()

    print("\n测试1: 使用默认参数预测")
    result1 = tool.run({})
    print(f"预测结果: {result1}")

    print("\n测试2: 使用自定义参数预测")
    test_params = {
        "temperature": 28.5,
        "humidity": 75.0,
        "ammonia_n": 18.2,
        "nitrate_n": 6.8,
        "ph": 8.2,
        "rainfall": 5.0
    }
    result2 = tool.run(test_params)
    print(f"预测结果: {result2}")


if __name__ == "__main__":
    test_predict_tool()