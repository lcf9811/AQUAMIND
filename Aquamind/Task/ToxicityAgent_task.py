
import sys
import os

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.ToxicityAgent import ToxicityAgent

def main():
    print("=== 测试 ToxicityAgent ===")
    
    agent = ToxicityAgent()
    
    # 模拟输入
    input_text = "目前水质参数：温度25度，氨氮15mg/L，硝氮5mg/L，pH 7.2。请预测未来毒性。"
    
    print(f"输入: {input_text}")
    print("-" * 50)
    
    result = agent.run(input_text)
    
    if result["status"] == "success":
        print("Agent 分析结果:")
        print(result["analysis"])
    else:
        print("错误:")
        print(result["analysis"])

if __name__ == "__main__":
    main()
