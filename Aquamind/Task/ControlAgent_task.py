
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.ControlAgent import ControlAgent

def main():
    print("=== 测试 ControlAgent ===")
    
    agent = ControlAgent()
    
    # 模拟输入
    toxicity_analysis = """
    基于当前水质参数，预测24小时后的毒性水平为 2.8 (中等偏高)。
    主要风险因素是氨氮浓度较高 (25mg/L)，可能导致硝化反应受抑制。
    """
    treatment_process = "智能体调控"
    time_frame = "24小时"
    
    print(f"输入工艺: {treatment_process}")
    print(f"毒性分析: {toxicity_analysis}")
    print("-" * 50)
    
    result = agent.run(toxicity_analysis, treatment_process, time_frame)
    
    if result["status"] == "success":
        print("Agent 建议:")
        print(result["suggestion"])
    else:
        print("错误:")
        print(result["suggestion"])

if __name__ == "__main__":
    main()
