"""
Aquamind 毒性预测机器人
用于快速调用毒性预测功能

使用方式:
    python bot.py                    # 交互模式
    python bot.py --predict          # 使用默认参数预测
    python bot.py --ammonia 20       # 指定参数预测
    python bot.py --history          # 查看历史数据统计
"""

import sys
import os
import argparse

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.abspath(__file__))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from Tool.predict_toxicity import PredictToxicityTool
from Task.task_manager import TaskManager
from logger import get_logger

# 初始化日志
logger = get_logger(__name__)


class ToxicityPredictionBot:
    """
    毒性预测机器人
    
    提供便捷的毒性预测接口，支持：
    - 默认参数预测
    - 自定义参数预测
    - 历史数据分析
    """

    def __init__(self):
        """初始化机器人"""
        logger.info("初始化毒性预测机器人")
        self.task_manager = TaskManager()
        logger.info("毒性预测机器人初始化完成")

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

        logger.info(f"执行毒性预测: {query}")
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
        logger.info("分析历史数据")
        return self.task_manager.execute_task('historical_analysis')


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Aquamind 毒性预测机器人",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python bot.py                                    # 交互模式
  python bot.py --predict                          # 默认参数预测
  python bot.py --ammonia 20 --temp 22            # 自定义参数预测
  python bot.py --history                          # 历史数据分析
        """
    )
    
    parser.add_argument("--predict", action="store_true", 
                       help="执行毒性预测")
    parser.add_argument("--history", action="store_true", 
                       help="分析历史数据")
    parser.add_argument("--interactive", action="store_true", 
                       help="交互模式")
    
    # 水质参数
    parser.add_argument("--ammonia", "--ammonia_n", type=float, 
                       help="氨氮浓度 (mg/L)")
    parser.add_argument("--temp", "--temperature", type=float, 
                       help="温度 (°C)")
    parser.add_argument("--ph", type=float, 
                       help="pH值")
    parser.add_argument("--nitrate", "--nitrate_n", type=float, 
                       help="硝氮浓度 (mg/L)")
    parser.add_argument("--humidity", type=float, 
                       help="湿度 (%)")
    parser.add_argument("--rainfall", type=float, 
                       help="降雨量 (mm)")
    
    return parser.parse_args()


def run_interactive(bot: ToxicityPredictionBot):
    """交互模式"""
    print("\n" + "=" * 60)
    print("Aquamind 毒性预测机器人 - 交互模式")
    print("=" * 60)
    print("\n可用命令:")
    print("  predict - 使用默认参数预测")
    print("  history - 查看历史数据")
    print("  exit    - 退出程序")
    print()
    
    while True:
        try:
            cmd = input(">>> ").strip().lower()
            
            if cmd in ["exit", "quit", "q"]:
                print("再见！")
                break
            elif cmd == "predict":
                result = bot.predict_24h_toxicity()
                print(f"\n预测结果: {result}\n")
            elif cmd == "history":
                result = bot.analyze_historical_data()
                print(f"\n历史数据: {result}\n")
            elif cmd == "help":
                print("\n可用命令: predict, history, exit")
            else:
                print("未知命令，输入 'help' 查看帮助")
                
        except KeyboardInterrupt:
            print("\n\n再见！")
            break
        except Exception as e:
            logger.error(f"执行命令出错: {e}")
            print(f"错误: {e}")


def main():
    """主函数"""
    args = parse_arguments()
    
    print("=" * 60)
    print("Aquamind 毒性预测机器人")
    print("=" * 60)
    
    # 创建机器人实例
    bot = ToxicityPredictionBot()
    
    # 历史数据分析
    if args.history:
        print("\n[历史数据分析]")
        result = bot.analyze_historical_data()
        
        if "error" not in result:
            print(f"  总记录数: {result.get('total_records', 0)}")
            print(f"  日期范围: {result.get('date_range', {}).get('start', '')} 至 {result.get('date_range', {}).get('end', '')}")
            
            if "toxicity_stats" in result:
                stats = result["toxicity_stats"]
                print(f"\n  毒性统计:")
                print(f"    平均值: {stats.get('mean', 0):.2f}")
                print(f"    标准差: {stats.get('std', 0):.2f}")
                print(f"    最小值: {stats.get('min', 0):.2f}")
                print(f"    最大值: {stats.get('max', 0):.2f}")
            
            if "recent_trend" in result:
                trend = result["recent_trend"]
                print(f"\n  最近趋势:")
                print(f"    近7天平均: {trend.get('recent_avg', 0):.2f}")
                print(f"    与总体差异: {trend.get('change_from_overall', 0):+.2f}")
        else:
            print(f"  错误: {result['error']}")
        
        return
    
    # 毒性预测
    if args.predict or any([args.ammonia, args.temp, args.ph, args.nitrate, args.humidity, args.rainfall]):
        # 构建参数
        params = {}
        if args.ammonia is not None:
            params["ammonia_n"] = args.ammonia
        if args.temp is not None:
            params["temperature"] = args.temp
        if args.ph is not None:
            params["ph"] = args.ph
        if args.nitrate is not None:
            params["nitrate_n"] = args.nitrate
        if args.humidity is not None:
            params["humidity"] = args.humidity
        if args.rainfall is not None:
            params["rainfall"] = args.rainfall
        
        print("\n[毒性预测]")
        if params:
            print(f"  输入参数: {params}")
        else:
            print("  使用默认参数")
        
        result = bot.predict_24h_toxicity(params if params else None)
        
        if "error" not in result:
            print(f"\n  预测结果:")
            print(f"    预测毒性: {result.get('predicted_toxicity', 'N/A')}")
            print(f"    毒性等级: {result.get('toxicity_level', 'N/A')}")
            print(f"    置信度: {result.get('confidence', 0):.2%}")
            
            if "explanation" in result:
                print(f"\n  分析说明:\n    {result['explanation']}")
            
            if "recommendations" in result and result["recommendations"]:
                print(f"\n  建议措施:")
                for i, rec in enumerate(result["recommendations"], 1):
                    print(f"    {i}. {rec}")
        else:
            print(f"  错误: {result.get('error', '未知错误')}")
        
        return
    
    # 交互模式（默认）
    run_interactive(bot)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n程序已终止")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        print(f"\n程序出错: {e}")