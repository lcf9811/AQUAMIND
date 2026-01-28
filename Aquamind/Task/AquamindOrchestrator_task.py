
import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.AquamindOrchestrator import AquamindOrchestrator

def main():
    print("=== Aquamind Systems 主程序启动 ===")
    
    parser = argparse.ArgumentParser(description="Aquamind Systems 智能预测与控制")
    parser.add_argument("--input", type=str, help="用户输入的自然语言请求", default=None)
    args = parser.parse_args()
    
    orchestrator = AquamindOrchestrator()
    
    if args.input:
        user_input = args.input
    else:
        # 默认交互模式
        print("请输入您的请求 (输入 'exit' 退出):")
        print("示例: 你好Aquamind，我目前的运行工艺是AAO，目前水质毒性数据是氨氮25mg/L，温度20度，请你帮我预测下未来24小时后的毒性数据并给出调整方案")
        
        while True:
            try:
                user_input = input("\n>>> ")
                if user_input.lower() in ["exit", "quit", "退出"]:
                    break
                
                if not user_input.strip():
                    continue
                    
                result = orchestrator.run(user_input)
                print("\n" + "="*50)
                print(result)
                print("="*50)
                
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"发生错误: {e}")

if __name__ == "__main__":
    main()
