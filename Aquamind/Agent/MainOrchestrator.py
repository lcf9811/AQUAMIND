"""
总智能体 (MainOrchestrator)
水处理智能体系统的核心协调器

功能:
1. 协调所有子智能体的工作
2. 解析用户自然语言请求
3. 编排智能体执行流程
4. 生成综合报告
"""

import sys
import os
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from LLM.llm_interface import LLMInterface
from Knowledge.knowledge_base import get_knowledge_base

# 导入所有子智能体
from Agent.ToxicityAgent import ToxicityAgent
from Agent.TurntableAgent import TurntableAgent
from Agent.RegenerationAgent import RegenerationAgent
from Agent.MBRAgent import MBRAgent
from Agent.DiagnosticAgent import DiagnosticAgent
from Agent.FeedbackAgent import FeedbackAgent


class MainOrchestrator:
    """
    总智能体 (MainOrchestrator)
    
    作为水处理智能体系统的核心协调器，负责：
    - 理解用户意图
    - 协调各子智能体
    - 生成综合报告
    - 管理系统状态
    """
    
    # 系统提示词
    SYSTEM_PROMPT = """你是Aquamind水处理智能体系统的总协调器 (MainOrchestrator)。

你是一位经验丰富的污水处理厂运营总工程师，负责协调以下子智能体完成各项任务：

## 子智能体列表
1. **毒性预测智能体 (ToxicityAgent)**: 预测进水毒性水平
2. **转盘智能体 (TurntableAgent)**: 控制活性炭转盘吸附系统
3. **再生智能体 (RegenerationAgent)**: 管理活性炭再生
4. **MBR智能体 (MBRAgent)**: 控制MBR膜生物反应器
5. **诊断智能体 (DiagnosticAgent)**: 系统诊断评估
6. **反馈智能体 (FeedbackAgent)**: 收集反馈优化

## 工作流程
1. 分析用户请求，识别意图
2. 调度相关子智能体
3. 整合各智能体结果
4. 生成综合建议报告

## 交互原则
- 准确理解用户意图
- 合理安排子智能体执行顺序
- 综合各方面信息给出建议
- 使用专业术语但保持通俗易懂

请根据用户的请求，协调各子智能体完成任务。"""

    def __init__(self):
        """初始化总智能体"""
        self.llm_interface = LLMInterface()
        self.kb = get_knowledge_base()
        
        # 初始化所有子智能体
        self.toxicity_agent = ToxicityAgent(self.llm_interface)
        self.turntable_agent = TurntableAgent(self.llm_interface)
        self.regeneration_agent = RegenerationAgent(self.llm_interface)
        self.mbr_agent = MBRAgent(self.llm_interface)
        self.diagnostic_agent = DiagnosticAgent(self.llm_interface)
        self.feedback_agent = FeedbackAgent(self.llm_interface)
        
        # 系统状态
        self.system_state = {
            "toxicity": 2.0,
            "toxicity_level": "中",
            "turntable_frequency": 25.0,
            "mbr_tmp": 20.0,
            "carbon_efficiency": 85.0,
            "last_update": None
        }
        
        # 创建意图识别链
        self.intent_chain = self._create_intent_chain()
        
        print("[MainOrchestrator] 智能体系统初始化完成")
    
    def _create_intent_chain(self):
        """创建意图识别链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """分析用户输入，识别意图和关键参数。

可能的意图类型：
- predict_toxicity: 毒性预测
- control_turntable: 转盘控制
- control_mbr: MBR控制
- check_regeneration: 检查再生需求
- system_diagnostic: 系统诊断
- general_query: 一般咨询

请返回JSON格式：
{
    "intent": "意图类型",
    "parameters": {提取的参数},
    "sub_intents": ["次要意图列表"]
}"""),
            ("human", "{user_input}")
        ])
        
        api_key = self.llm_interface.qwen_api_key or self.llm_interface.openai_api_key
        base_url = self.llm_interface.qwen_api_base or self.llm_interface.openai_api_base
        model_name = self.llm_interface.qwen_model_name or "qwen-plus"
        
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=0.2
        )
        
        return prompt | llm | StrOutputParser()
    
    def _parse_input(self, user_input: str) -> Dict[str, Any]:
        """解析用户输入，提取关键信息"""
        params = {
            "treatment_process": "智能体调控",
            "time_frame": "24小时",
            "toxicity": None,
            "ammonia_n": None,
            "temperature": None,
            "ph": None
        }
        
        # 提取工艺类型
        process_patterns = [
            (r"工艺[是为]?\s*([A-Za-z0-9\u4e00-\u9fa5]+)", 1),
            (r"(AAO|A2O|SBR|MBR|氧化沟)", 0)
        ]
        for pattern, group in process_patterns:
            match = re.search(pattern, user_input, re.IGNORECASE)
            if match:
                params["treatment_process"] = match.group(group + 1) if group else match.group(0)
                break
        
        # 提取时间范围
        time_match = re.search(r"(\d+)\s*(小时|天|h|hour|day)", user_input, re.IGNORECASE)
        if time_match:
            params["time_frame"] = f"{time_match.group(1)}{time_match.group(2)}"
        
        # 提取数值参数
        patterns = {
            "toxicity": r"毒性[是为]?\s*([\d.]+)",
            "ammonia_n": r"氨氮[是为]?\s*([\d.]+)",
            "temperature": r"温度[是为]?\s*([\d.]+)",
            "ph": r"[pP][hH][值是为]?\s*([\d.]+)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, user_input)
            if match:
                params[key] = float(match.group(1))
        
        return params
    
    def _identify_intent(self, user_input: str) -> str:
        """识别用户意图"""
        input_lower = user_input.lower()
        
        # 关键词匹配（按优先级排序）
        # 1. 反馈收集（优先级最高，因为是用户主动反馈）
        if any(kw in input_lower for kw in ["反馈", "记录", "feedback", "建议", "意见", "改进"]):
            return "collect_feedback"
        # 2. 再生控制（优先于转盘，因为再生也涉及活性炭）
        elif any(kw in input_lower for kw in ["再生", "饱和", "regenerat", "再生温度", "加热"]):
            return "check_regeneration"
        # 3. 系统诊断
        elif any(kw in input_lower for kw in ["诊断", "评估", "状态", "健康", "检测系统"]):
            return "system_diagnostic"
        # 4. 毒性预测
        elif any(kw in input_lower for kw in ["预测", "毒性", "forecast", "predict"]):
            return "predict_toxicity"
        # 5. MBR控制
        elif any(kw in input_lower for kw in ["mbr", "膜", "通量", "tmp", "跨膜压"]):
            return "control_mbr"
        # 6. 转盘控制
        elif any(kw in input_lower for kw in ["转盘", "吸附", "频率", "转速"]):
            return "control_turntable"
        # 7. 综合分析
        elif any(kw in input_lower for kw in ["综合", "全部", "整体", "完整"]):
            return "full_analysis"
        else:
            return "general_query"
    
    def run(self, user_input: str) -> str:
        """
        运行主流程
        
        Args:
            user_input: 用户输入的自然语言请求
            
        Returns:
            str: 最终报告
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] MainOrchestrator: 收到请求，正在分析...")
        
        # 1. 解析输入
        params = self._parse_input(user_input)
        intent = self._identify_intent(user_input)
        
        print(f"[{timestamp}] 识别意图: {intent}")
        print(f"[{timestamp}] 提取参数: {params}")
        
        # 2. 根据意图调度子智能体
        results = {}
        
        if intent == "predict_toxicity" or intent == "full_analysis":
            print(f"[{timestamp}] 调度 ToxicityAgent...")
            results["toxicity"] = self.toxicity_agent.run(user_input)
            
            # 更新系统状态
            if results["toxicity"]["status"] == "success":
                # 从分析中提取毒性值（简化处理）
                self.system_state["last_update"] = timestamp
        
        if intent in ["control_turntable", "full_analysis"]:
            print(f"[{timestamp}] 调度 TurntableAgent...")
            toxicity = params.get("toxicity") or self.system_state.get("toxicity", 2.0)
            turntable_output = self.turntable_agent.generate_control_output(
                toxicity=toxicity,
                toxicity_level=self._get_toxicity_level(toxicity),
                trend="稳定"
            )
            results["turntable"] = turntable_output.to_dict()
        
        if intent in ["control_mbr", "full_analysis"]:
            print(f"[{timestamp}] 调度 MBRAgent...")
            mbr_output = self.mbr_agent.generate_control_output(
                current_tmp=self.system_state.get("mbr_tmp", 20.0)
            )
            results["mbr"] = mbr_output.to_dict()
        
        if intent in ["check_regeneration", "full_analysis"]:
            print(f"[{timestamp}] 调度 RegenerationAgent...")
            regen_output = self.regeneration_agent.generate_control_output(
                adsorption_efficiency=self.system_state.get("carbon_efficiency", 85.0)
            )
            results["regeneration"] = regen_output.to_dict()
        
        if intent in ["system_diagnostic", "full_analysis"]:
            print(f"[{timestamp}] 调度 DiagnosticAgent...")
            diagnostic_report = self.diagnostic_agent.generate_diagnostic_report()
            results["diagnostic"] = diagnostic_report.to_dict()
        
        if intent in ["collect_feedback", "full_analysis"]:
            print(f"[{timestamp}] 调度 FeedbackAgent...")
            # 将用户反馈记录到系统
            feedback_result = self.feedback_agent.run(feedback_data=user_input)
            # 添加原始输入和反馈类型信息
            feedback_result["original_input"] = user_input
            feedback_result["feedback_type"] = "操作员反馈"
            feedback_result["parameter_adjustment"] = "已记录，将用于后续优化"
            results["feedback"] = feedback_result
        
        # 3. 生成综合报告
        report = self._generate_report(user_input, params, intent, results)
        
        # 4. 保存报告
        report_path = self._save_report(report)
        print(f"[{timestamp}] 报告已生成: {report_path}")
        
        return report
    
    def _get_toxicity_level(self, toxicity: float) -> str:
        """获取毒性等级"""
        if toxicity < 1.5:
            return "低"
        elif toxicity < 3.0:
            return "中"
        else:
            return "高"
    
    def _generate_report(self, user_input: str, params: Dict, 
                         intent: str, results: Dict) -> str:
        """生成综合报告"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        report = f"""# Aquamind 水处理智能体系统报告
生成时间: {timestamp}

## 1. 用户请求
- **原始输入**: {user_input}
- **识别意图**: {intent}
- **提取参数**: {params}

"""
        
        # 毒性预测结果
        if "toxicity" in results:
            toxicity_result = results["toxicity"]
            report += f"""## 2. 毒性预测分析 (ToxicityAgent)
**状态**: {toxicity_result.get('status', 'unknown')}

{toxicity_result.get('analysis', '无分析结果')}

"""
        
        # 转盘控制结果
        if "turntable" in results:
            tt = results["turntable"]
            report += f"""## 3. 转盘控制建议 (TurntableAgent)
- **推荐频率**: {tt.get('frequency_1', 0):.1f} Hz
- **转速**: {tt.get('rpm_1', 0):.0f} rpm
- **活跃反应器**: {tt.get('active_reactors', 2)} 台
- **备用触发**: {'是' if tt.get('standby_triggered') else '否'}
- **预期去除率**: {tt.get('expected_removal_rate', 0):.1f}%
- **决策原因**: {tt.get('decision_reason', '')}

"""
        
        # MBR控制结果
        if "mbr" in results:
            mbr = results["mbr"]
            report += f"""## 4. MBR控制建议 (MBRAgent)
- **曝气量**: {mbr.get('aeration_rate', 50):.1f} m³/h
- **通量设定**: {mbr.get('flux_setpoint', 18):.1f} LMH
- **污染状态**: {mbr.get('fouling_status', 'normal')}
- **需要反洗**: {'是' if mbr.get('backwash_needed') else '否'}
- **需要化学清洗**: {'是' if mbr.get('chemical_cleaning_needed') else '否'}

"""
        
        # 再生检查结果
        if "regeneration" in results:
            regen = results["regeneration"]
            report += f"""## 5. 再生系统评估 (RegenerationAgent)
- **需要再生**: {'是' if regen.get('regeneration_needed') else '否'}
- **再生模式**: {regen.get('regeneration_mode', 'standby')}
- **炉温设定**: {regen.get('furnace_temperature', 0):.0f}°C
- **进料速度**: {regen.get('feed_rate', 0):.1f} kg/h
- **决策原因**: {regen.get('decision_reason', '')}

"""
        
        # 诊断结果
        if "diagnostic" in results:
            diag = results["diagnostic"]
            report += f"""## 6. 系统诊断 (DiagnosticAgent)
- **整体健康**: {diag.get('overall_health', '未知')}
- **综合评分**: {diag.get('overall_score', 0):.1f}/100

### 子系统状态
"""
            for name, status in diag.get('subsystem_status', {}).items():
                report += f"- **{status.get('name', name)}**: {status.get('health_level', '未知')} ({status.get('score', 0):.0f}分)\n"
            
            if diag.get('critical_issues'):
                report += "\n### 严重问题\n"
                for issue in diag['critical_issues']:
                    report += f"- ⚠️ {issue}\n"
            
            if diag.get('recommendations'):
                report += "\n### 改进建议\n"
                for rec in diag['recommendations'][:5]:
                    report += f"- {rec}\n"
        
        # 反馈收集结果
        if "feedback" in results:
            fb = results["feedback"]
            report += f"""## 7. 反馈收集 (FeedbackAgent)
- **反馈类型**: {fb.get('feedback_type', '未知')}
- **处理状态**: {fb.get('status', '已记录')}
- **反馈内容**: {fb.get('original_input', '')}
- **参数调整建议**: {fb.get('parameter_adjustment', '无')}

"""
        
        report += """
---
*Aquamind Systems - 您的智慧水务专家*
"""
        
        return report
    
    def _save_report(self, report: str) -> str:
        """保存报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        report_dir = os.path.join(root_dir, "Report")
        
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
        
        report_path = os.path.join(report_dir, f"Report_{timestamp}.md")
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        return report_path
    
    def quick_predict(self, toxicity: float = None, ammonia: float = None,
                      temperature: float = None) -> Dict[str, Any]:
        """快速预测接口"""
        # 使用转盘智能体生成控制建议
        toxicity = toxicity or 2.0
        toxicity_level = self._get_toxicity_level(toxicity)
        
        turntable_output = self.turntable_agent.generate_control_output(
            toxicity=toxicity,
            toxicity_level=toxicity_level,
            trend="稳定"
        )
        
        return {
            "toxicity": toxicity,
            "toxicity_level": toxicity_level,
            "turntable_control": turntable_output.to_dict(),
            "plc_command": turntable_output.to_plc_command()
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return self.system_state.copy()


if __name__ == "__main__":
    # 测试总智能体
    print("=== 总智能体测试 ===\n")
    
    orchestrator = MainOrchestrator()
    
    # 测试1：完整分析
    print("\n" + "="*50)
    print("测试1：完整分析请求")
    print("="*50)
    
    test_input = "你好Aquamind，我的进水毒性是3.5，氨氮25mg/L，温度22度，请帮我做一下综合分析和控制建议"
    result = orchestrator.run(test_input)
    print(result[:1500] + "...")
    
    # 测试2：快速预测
    print("\n" + "="*50)
    print("测试2：快速预测")
    print("="*50)
    
    quick_result = orchestrator.quick_predict(toxicity=4.0)
    print(f"毒性等级: {quick_result['toxicity_level']}")
    print(f"PLC命令: {quick_result['plc_command']}")
