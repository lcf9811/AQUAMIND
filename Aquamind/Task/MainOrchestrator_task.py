"""
主智能体测试任务脚本
测试 MainOrchestrator 及所有子智能体

功能:
1. 交互模式 - 与智能体实时对话
2. 演示模式 - 运行预设场景
3. 批量测试 - 批量场景测试
4. 性能监控 - 记录响应时间
5. 历史记录 - 保存交互历史
6. 结果导出 - 导出测试结果
"""

import sys
import os
import argparse
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Agent.MainOrchestrator import MainOrchestrator


# 配置日志
def setup_logging(log_file: str = None):
    """配置日志系统"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    if log_file:
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    else:
        logging.basicConfig(level=logging.INFO, format=log_format)
    
    return logging.getLogger(__name__)


class SessionManager:
    """会话管理器 - 记录交互历史"""
    
    def __init__(self, session_dir: str = "./sessions"):
        self.session_dir = session_dir
        os.makedirs(session_dir, exist_ok=True)
        self.session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.history: List[Dict[str, Any]] = []
        self.session_file = os.path.join(session_dir, f"session_{self.session_id}.json")
    
    def add_interaction(self, user_input: str, system_output: str, 
                       response_time: float, intent: str = "unknown"):
        """添加交互记录"""
        interaction = {
            "timestamp": datetime.now().isoformat(),
            "user_input": user_input,
            "system_output": system_output[:500],  # 只保存前500字符
            "response_time": response_time,
            "intent": intent
        }
        self.history.append(interaction)
    
    def save_session(self):
        """保存会话到文件"""
        session_data = {
            "session_id": self.session_id,
            "total_interactions": len(self.history),
            "avg_response_time": sum(h["response_time"] for h in self.history) / len(self.history) if self.history else 0,
            "history": self.history
        }
        
        with open(self.session_file, 'w', encoding='utf-8') as f:
            json.dump(session_data, f, ensure_ascii=False, indent=2)
        
        return self.session_file
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取会话统计"""
        if not self.history:
            return {"message": "无交互记录"}
        
        response_times = [h["response_time"] for h in self.history]
        return {
            "total_interactions": len(self.history),
            "avg_response_time": sum(response_times) / len(response_times),
            "min_response_time": min(response_times),
            "max_response_time": max(response_times),
            "session_duration": (datetime.fromisoformat(self.history[-1]["timestamp"]) - 
                               datetime.fromisoformat(self.history[0]["timestamp"])).total_seconds()
        }


def main():
    print("=" * 60)
    print("Aquamind 水处理智能体系统 v2.0")
    print("=" * 60)
    
    parser = argparse.ArgumentParser(description="Aquamind 智能体系统")
    parser.add_argument("--input", type=str, help="用户输入", default=None)
    parser.add_argument("--demo", action="store_true", help="运行演示")
    parser.add_argument("--batch", type=str, help="批量测试文件路径")
    parser.add_argument("--log", type=str, help="日志文件路径", default=None)
    parser.add_argument("--no-session", action="store_true", help="禁用会话记录")
    args = parser.parse_args()
    
    # 配置日志
    logger = setup_logging(args.log)
    
    # 初始化会话管理
    session = None if args.no_session else SessionManager()
    
    # 初始化主智能体
    print("\n[初始化] 正在启动智能体系统...")
    start_time = time.time()
    orchestrator = MainOrchestrator()
    init_time = time.time() - start_time
    print(f"[初始化] 智能体系统启动完成 (耗时: {init_time:.2f}秒)")
    logger.info(f"系统初始化完成，耗时: {init_time:.2f}秒")
    
    try:
        if args.batch:
            # 批量测试模式
            run_batch_test(orchestrator, args.batch, session, logger)
        elif args.demo:
            # 演示模式
            run_demo(orchestrator, session, logger)
        elif args.input:
            # 单次执行
            start_time = time.time()
            result = orchestrator.run(args.input)
            response_time = time.time() - start_time
            
            print(f"\n[响应时间: {response_time:.2f}秒]")
            print("\n" + result)
            
            if session:
                session.add_interaction(args.input, result, response_time)
        else:
            # 交互模式
            run_interactive(orchestrator, session, logger)
    finally:
        # 保存会话
        if session and session.history:
            session_file = session.save_session()
            print(f"\n[会话已保存] {session_file}")
            
            # 显示统计
            stats = session.get_statistics()
            print(f"\n会话统计:")
            print(f"  - 总交互次数: {stats['total_interactions']}")
            print(f"  - 平均响应时间: {stats['avg_response_time']:.2f}秒")
            print(f"  - 会话时长: {stats.get('session_duration', 0):.0f}秒")


def run_demo(orchestrator: MainOrchestrator, session: SessionManager = None, logger = None):
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
        
        start_time = time.time()
        result = orchestrator.run(demo_input)
        response_time = time.time() - start_time
        
        # 只显示前800字符
        print(result[:800] + "\n..." if len(result) > 800 else result)
        print(f"\n[响应时间: {response_time:.2f}秒]")
        
        if session:
            intent = orchestrator._identify_intent(demo_input)
            session.add_interaction(demo_input, result, response_time, intent)
        
        if logger:
            logger.info(f"演示 {i} 完成，响应时间: {response_time:.2f}秒")


def run_interactive(orchestrator: MainOrchestrator, session: SessionManager = None, logger = None):
    """交互模式"""
    print("\n" + "=" * 60)
    print("交互模式 (输入 'exit' 退出, 'help' 查看帮助)")
    print("=" * 60)
    
    print_help()
    
    interaction_count = 0
    
    while True:
        try:
            user_input = input("\n>>> ").strip()
            
            if not user_input:
                continue
            
            # 特殊命令处理
            if user_input.lower() in ["exit", "quit", "退出", "q"]:
                print("感谢使用 Aquamind 系统，再见！")
                break
            
            if user_input.lower() in ["help", "帮助", "?"]:
                print_help()
                continue
            
            if user_input.lower() in ["stats", "统计"]:
                if session:
                    stats = session.get_statistics()
                    print(f"\n当前会话统计:")
                    for key, value in stats.items():
                        print(f"  - {key}: {value}")
                else:
                    print("\n会话记录已禁用")
                continue
            
            if user_input.lower() in ["clear", "清屏"]:
                os.system('clear' if os.name == 'posix' else 'cls')
                continue
            
            # 执行智能体
            start_time = time.time()
            result = orchestrator.run(user_input)
            response_time = time.time() - start_time
            
            print(f"\n[响应时间: {response_time:.2f}秒]")
            print("\n" + result)
            
            interaction_count += 1
            
            if session:
                intent = orchestrator._identify_intent(user_input)
                session.add_interaction(user_input, result, response_time, intent)
            
            if logger:
                logger.info(f"交互 {interaction_count} 完成，响应时间: {response_time:.2f}秒")
            
        except KeyboardInterrupt:
            print("\n\n感谢使用，再见！")
            break
        except Exception as e:
            print(f"\n发生错误: {e}")
            if logger:
                logger.error(f"交互异常: {e}", exc_info=True)


def run_batch_test(orchestrator: MainOrchestrator, batch_file: str, 
                   session: SessionManager = None, logger = None):
    """批量测试模式"""
    print("\n" + "=" * 60)
    print(f"批量测试模式: {batch_file}")
    print("=" * 60)
    
    try:
        with open(batch_file, 'r', encoding='utf-8') as f:
            test_cases = json.load(f)
        
        print(f"\n加载了 {len(test_cases)} 个测试用例\n")
        
        results = []
        for i, test_case in enumerate(test_cases, 1):
            user_input = test_case.get("input", "")
            expected_intent = test_case.get("intent", "unknown")
            
            print(f"\n[测试 {i}/{len(test_cases)}] {user_input[:50]}...")
            
            start_time = time.time()
            result = orchestrator.run(user_input)
            response_time = time.time() - start_time
            
            actual_intent = orchestrator._identify_intent(user_input)
            success = (actual_intent == expected_intent)
            
            test_result = {
                "test_id": i,
                "input": user_input,
                "expected_intent": expected_intent,
                "actual_intent": actual_intent,
                "success": success,
                "response_time": response_time,
                "output_length": len(result)
            }
            results.append(test_result)
            
            status = "✓" if success else "✗"
            print(f"{status} 意图: {actual_intent} (预期: {expected_intent}), 耗时: {response_time:.2f}秒")
            
            if session:
                session.add_interaction(user_input, result, response_time, actual_intent)
            
            if logger:
                logger.info(f"批量测试 {i} 完成: {status}")
        
        # 输出测试总结
        print("\n" + "=" * 60)
        print("批量测试总结")
        print("=" * 60)
        
        success_count = sum(1 for r in results if r["success"])
        avg_time = sum(r["response_time"] for r in results) / len(results)
        
        print(f"总测试数: {len(results)}")
        print(f"成功: {success_count} / {len(results)} ({success_count/len(results)*100:.1f}%)")
        print(f"平均响应时间: {avg_time:.2f}秒")
        
        # 保存测试结果
        result_file = f"batch_test_result_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"\n测试结果已保存: {result_file}")
        
    except FileNotFoundError:
        print(f"错误: 找不到文件 {batch_file}")
    except json.JSONDecodeError:
        print(f"错误: 文件格式不正确，应为JSON格式")
    except Exception as e:
        print(f"批量测试失败: {e}")
        if logger:
            logger.error(f"批量测试异常: {e}", exc_info=True)


def print_help():
    """打印帮助信息"""
    print("""
可用命令:
- help/帮助/?     : 显示此帮助信息
- stats/统计      : 显示当前会话统计
- clear/清屏      : 清除屏幕
- exit/quit/退出  : 退出程序

示例输入:
1. 请帮我预测一下毒性，氨氮25mg/L，温度20度
2. 进水毒性3.5，请给出转盘控制建议
3. 请检查MBR系统，TMP是30kPa
4. 请做系统诊断
5. 综合分析一下当前状态
""")


if __name__ == "__main__":
    main()
