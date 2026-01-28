"""
毒性预测机器人 - LangChain Agent入口
根据用户输入的毒性数据，预测24小时后的毒性数据
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.Tool.predict_toxicity import PredictToxicityTool
from Agent.Task.task_manager import TaskManager


class ToxicityPredictionBot:
    """毒性预测机器人 - LangChain Agent入口"""

    def __init__(self):
        # 初始化任务管理器
        self.task_manager = TaskManager()

    def run_agent(self, query: str, input_params: dict = None):
        """
        运行Agent进行毒性预测

        Args:
            query: 查询字符串（描述预测需求）
            input_params: 输入参数字典

        Returns:
            预测结果
        """
        if input_params is None:
            input_params = {
                "temperature": 25.0,
                "humidity": 60.0,
                "ammonia_n": 10.0,
                "nitrate_n": 5.0,
                "ph": 7.0,
                "rainfall": 0.0
            }

        # 执行毒性预测任务
        result = self.task_manager.execute_task('toxicity_prediction', input_params)
        return result

    def predict_24h_toxicity(self, input_data: dict = None):
        """
        专门用于24小时毒性预测的方法

        Args:
            input_data: 包含水质参数的字典

        Returns:
            24小时后毒性预测结果
        """
        return self.run_agent("预测24小时后毒性", input_data)

    def analyze_historical_data(self):
        """
        分析历史数据

        Returns:
            历史数据分析结果
        """
        return self.task_manager.execute_task('historical_analysis')


def main():
    """主函数，演示毒性预测机器人功能"""
    print("=== 毒性预测机器人 (LangChain Agent) ===\n")

    # 创建机器人实例
    print("初始化毒性预测机器人...")
    bot = ToxicityPredictionBot()
    print("✓ 机器人初始化成功\n")

    # 示例1: 默认参数预测
    print("1. 示例1: 使用默认参数预测24小时后毒性")
    default_result = bot.predict_24h_toxicity()
    print(f"   预测结果: {default_result}\n")

    # 示例2: 自定义参数预测
    print("2. 示例2: 使用自定义参数预测")
    custom_params = {
        "temperature": 28.5,
        "humidity": 75.0,
        "ammonia_n": 18.2,
        "nitrate_n": 6.8,
        "ph": 8.2,
        "rainfall": 5.0
    }
    custom_result = bot.predict_24h_toxicity(custom_params)
    print(f"   输入参数: {custom_params}")
    print(f"   预测结果: {custom_result}\n")

    # 示例3: 高风险参数预测
    print("3. 示例3: 高风险参数预测")
    high_risk_params = {
        "temperature": 32.0,
        "humidity": 80.0,
        "ammonia_n": 25.0,
        "nitrate_n": 8.0,
        "ph": 9.0,
        "rainfall": 15.0
    }
    high_risk_result = bot.predict_24h_toxicity(high_risk_params)
    print(f"   输入参数: {high_risk_params}")
    print(f"   预测结果: {high_risk_result}\n")

    # 示例4: 历史数据分析
    print("4. 示例4: 历史数据分析")
    historical_analysis = bot.analyze_historical_data()
    print(f"   历史数据分析: {historical_analysis}\n")

    print("="*60)
    print("✓ 毒性预测机器人功能演示完成")


if __name__ == "__main__":
    main()