"""
主智能体测试任务脚本
测试 MainOrchestrator 及所有子智能体
"""

import sys
import os
import argparse

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.MainOrchestrator import MainOrchestrator


def main():
    print("=" * 60)
    print("Aquamind 水处理智能体系统")
    print("=" * 60)
    
    parser = argparse.ArgumentParser(description="Aquamind 智能体系统")
    parser.add_argument("--input", type=str, help="用户输入", default=None)
    parser.add_argument("--demo", action="store_true", help="运行演示")
    args = parser.parse_args()
    
    # 初始化主智能体
    print("\n[初始化] 正在启动智能体系统...")
    orchestrator = MainOrchestrator()
    print("[初始化] 智能体系统启动完成")
    
    if args.demo:
        # 演示模式
        run_demo(orchestrator)
    elif args.input:
        # 单次执行
        result = orchestrator.run(args.input)
        print("\n" + result)
    else:
        # 交互模式
        run_interactive(orchestrator)


def run_demo(orchestrator: MainOrchestrator):
    """运行演示"""
    print("\n" + "=" * 60)
    print("演示模式")
    print("=" * 60)
    
    demo_inputs = [
        "请帮我预测一下毒性情况，当前氨氮是20mg/L，温度22度",
        "进水毒性是3.5，请给出转盘控制建议",
        "请检查一下MBR系统状态，当前TMP是28kPa",
        "请做一下系统综合诊断"
    ]
    
    for i, demo_input in enumerate(demo_inputs, 1):
        print(f"\n{'=' * 40}")
        print(f"演示 {i}: {demo_input}")
        print("=" * 40)
        
        result = orchestrator.run(demo_input)
        # 只显示前500字符
        print(result[:800] + "\n..." if len(result) > 800 else result)


def run_interactive(orchestrator: MainOrchestrator):
    """交互模式"""
    print("\n" + "=" * 60)
    print("交互模式 (输入 'exit' 退出)")
    print("=" * 60)
    
    print("""
示例输入:
1. 请帮我预测一下毒性，氨氮25mg/L，温度20度
2. 进水毒性3.5，请给出转盘控制建议
3. 请检查MBR系统，TMP是30kPa
4. 请做系统诊断
5. 综合分析一下当前状态
""")
    
    while True:
        try:
            user_input = input("\n>>> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ["exit", "quit", "退出", "q"]:
                print("感谢使用 Aquamind 系统，再见！")
                break
            
            result = orchestrator.run(user_input)
            print("\n" + result)
            
        except KeyboardInterrupt:
            print("\n\n感谢使用，再见！")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")


if __name__ == "__main__":
    main()
