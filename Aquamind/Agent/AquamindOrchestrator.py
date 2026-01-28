"""
Aquamind 系统协调器 (AquamindOrchestrator)
顶层架构，协调所有智能体的工作

功能:
1. 协调 ToxicityAgent 进行毒性预测
2. 协调 ControlAgent 生成控制建议
3. 可选调用进阶智能体(转盘/MBR/再生/诊断/反馈)
4. 生成综合报告

注意: 此类继承自旧版设计，与MainOrchestrator兼容
"""

import sys
import os
import re
from datetime import datetime
from typing import Dict, Any, Optional

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from Agent.ToxicityAgent import ToxicityAgent
from Agent.ControlAgent import ControlAgent
from LLM.llm_interface import LLMInterface

# 尝试导入进阶智能体
try:
    from Agent.TurntableAgent import TurntableAgent
    from Agent.MBRAgent import MBRAgent
    from Agent.RegenerationAgent import RegenerationAgent
    from Agent.DiagnosticAgent import DiagnosticAgent
    from Agent.FeedbackAgent import FeedbackAgent
    from Knowledge.knowledge_base import get_knowledge_base
    HAS_ADVANCED_AGENTS = True
except ImportError:
    HAS_ADVANCED_AGENTS = False
    get_knowledge_base = None


class AquamindOrchestrator:
    """
    AquamindOrchestrator: 顶层架构，污水处理厂运营工程师。
    负责协调所有子智能体，生成最终报告。
    
    兼容旧版API，同时支持进阶功能。
    """
    
    def __init__(self):
        """初始化协调器"""
        self.llm_interface = LLMInterface()
        
        # 核心智能体
        self.toxicity_agent = ToxicityAgent(self.llm_interface)
        self.control_agent = ControlAgent(self.llm_interface)
        
        # 进阶智能体（如果可用）
        if HAS_ADVANCED_AGENTS:
            self.turntable_agent = TurntableAgent(self.llm_interface)
            self.mbr_agent = MBRAgent(self.llm_interface)
            self.regeneration_agent = RegenerationAgent(self.llm_interface)
            self.diagnostic_agent = DiagnosticAgent(self.llm_interface)
            self.feedback_agent = FeedbackAgent(self.llm_interface)
            self.kb = get_knowledge_base() if get_knowledge_base else None
        else:
            self.turntable_agent = None
            self.mbr_agent = None
            self.regeneration_agent = None
            self.diagnostic_agent = None
            self.feedback_agent = None
            self.kb = None
        
        # 系统状态
        self.system_state = {
            "toxicity": 2.0,
            "toxicity_level": "中",
            "turntable_frequency": 25.0,
            "mbr_tmp": 20.0,
            "carbon_efficiency": 85.0,
            "last_update": None
        }
        
        print("[AquamindOrchestrator] 系统初始化完成")
        
    def _parse_input(self, user_input: str) -> Dict[str, Any]:
        """
        输入解析器，提取关键信息。
        """
        params = {
            "treatment_process": "智能体调控",
            "time_frame": "24小时",
            "toxicity": None,
            "ammonia_n": None,
            "temperature": None,
            "ph": None
        }
        
        # 提取工艺
        treatment_match = re.search(r"工艺[是为]?\s*([a-zA-Z0-9\u4e00-\u9fa5]+)", user_input)
        if treatment_match:
            params["treatment_process"] = treatment_match.group(1)
        else:
            known_processes = ["AAO", "A2O", "SBR", "MBR", "氧化沟", "活性污泥法", "智能体调控"]
            for process in known_processes:
                if process.upper() in user_input.upper():
                    params["treatment_process"] = process
                    break
                    
        # 提取时间
        time_match = re.search(r"未来\s*(\d+\s*(小时|天|h|day))", user_input, re.IGNORECASE)
        if time_match:
            params["time_frame"] = time_match.group(1)
        
        # 提取数值参数
        patterns = {
            "toxicity": r"毒性[是为:：]?\s*([\d.]+)",
            "ammonia_n": r"氨氮[是为:：]?\s*([\d.]+)",
            "temperature": r"温度[是为:：]?\s*([\d.]+)",
            "ph": r"[pP][hH][值是为:：]?\s*([\d.]+)"
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, user_input)
            if match:
                params[key] = float(match.group(1))
            
        return params
    
    def _identify_intent(self, user_input: str) -> str:
        """识别用户意图"""
        input_lower = user_input.lower()
        
        # 关键词匹配
        if any(kw in input_lower for kw in ["反馈", "记录", "建议", "意见"]):
            return "collect_feedback"
        elif any(kw in input_lower for kw in ["再生", "饱和"]):
            return "check_regeneration"
        elif any(kw in input_lower for kw in ["诊断", "评估", "状态", "健康"]):
            return "system_diagnostic"
        elif any(kw in input_lower for kw in ["预测", "毒性"]):
            return "predict_toxicity"
        elif any(kw in input_lower for kw in ["mbr", "膜", "通量", "tmp"]):
            return "control_mbr"
        elif any(kw in input_lower for kw in ["转盘", "吸附", "频率"]):
            return "control_turntable"
        elif any(kw in input_lower for kw in ["综合", "全部", "整体", "完整"]):
            return "full_analysis"
        else:
            return "general_query"

    def run(self, user_input: str) -> str:
        """
        执行主流程
        
        Args:
            user_input: 用户输入的自然语言请求
            
        Returns:
            str: 最终生成的报告路径或内容摘要
        """
        timestamp = datetime.now().strftime('%H:%M:%S')
        print(f"[{timestamp}] AquamindOrchestrator: 收到请求，正在分析...")
        
        # 1. 分析输入
        parsed_params = self._parse_input(user_input)
        intent = self._identify_intent(user_input)
        treatment_process = parsed_params["treatment_process"]
        time_frame = parsed_params["time_frame"]
        
        print(f"[{timestamp}] 识别意图: {intent}")
        print(f"[{timestamp}] 识别关键信息: 工艺={treatment_process}, 预测时间={time_frame}")
        
        # 2. 调用 ToxicityAgent
        print(f"[{timestamp}] 正在调度 ToxicityAgent 进行毒性预测...")
        toxicity_result = self.toxicity_agent.run(user_input)
        
        if toxicity_result["status"] != "success":
            return f"流程中断：毒性预测失败 - {toxicity_result['analysis']}"
            
        toxicity_analysis = toxicity_result["analysis"]
        toxicity_level = toxicity_result.get("toxicity_level", "中")
        toxicity_value = toxicity_result.get("toxicity_value", 2.0)
        
        # 更新系统状态
        self.system_state["toxicity"] = toxicity_value
        self.system_state["toxicity_level"] = toxicity_level
        self.system_state["last_update"] = timestamp
        
        print(f"[{timestamp}] ToxicityAgent 完成预测，毒性等级: {toxicity_level}")
        
        # 3. 调用 ControlAgent
        print(f"[{timestamp}] 正在调度 ControlAgent 生成工艺建议...")
        control_result = self.control_agent.run(
            toxicity_analysis=toxicity_analysis,
            treatment_process=treatment_process,
            time_frame=time_frame
        )
        
        if control_result["status"] != "success":
            return f"流程中断：控制建议生成失败 - {control_result['suggestion']}"
            
        control_suggestion = control_result["suggestion"]
        print(f"[{timestamp}] ControlAgent 完成建议生成。")
        
        # 4. 可选：调用进阶智能体
        advanced_results = {}
        
        if HAS_ADVANCED_AGENTS:
            # 根据意图调用相应智能体
            if intent in ["control_turntable", "full_analysis"] and self.turntable_agent:
                print(f"[{timestamp}] 调度 TurntableAgent...")
                turntable_output = self.turntable_agent.generate_control_output(
                    toxicity=toxicity_value,
                    toxicity_level=toxicity_level,
                    trend="稳定"
                )
                advanced_results["turntable"] = turntable_output.to_dict()
            
            if intent in ["control_mbr", "full_analysis"] and self.mbr_agent:
                print(f"[{timestamp}] 调度 MBRAgent...")
                mbr_output = self.mbr_agent.generate_control_output(
                    current_tmp=self.system_state.get("mbr_tmp", 20.0)
                )
                advanced_results["mbr"] = mbr_output.to_dict()
            
            if intent in ["check_regeneration", "full_analysis"] and self.regeneration_agent:
                print(f"[{timestamp}] 调度 RegenerationAgent...")
                regen_output = self.regeneration_agent.generate_control_output(
                    adsorption_efficiency=self.system_state.get("carbon_efficiency", 85.0)
                )
                advanced_results["regeneration"] = regen_output.to_dict()
            
            if intent in ["system_diagnostic", "full_analysis"] and self.diagnostic_agent:
                print(f"[{timestamp}] 调度 DiagnosticAgent...")
                diag_report = self.diagnostic_agent.generate_diagnostic_report()
                advanced_results["diagnostic"] = diag_report.to_dict()
            
            if intent in ["collect_feedback"] and self.feedback_agent:
                print(f"[{timestamp}] 调度 FeedbackAgent...")
                feedback_result = self.feedback_agent.run(feedback_data=user_input)
                advanced_results["feedback"] = feedback_result
        
        # 5. 生成报告
        report = self._generate_report(
            user_input, parsed_params, toxicity_result, 
            control_suggestion, advanced_results, intent
        )
        
        return report

    def _generate_report(self, user_input: str, params: Dict[str, Any], 
                         toxicity_result: Dict, control_suggestion: str,
                         advanced_results: Dict, intent: str) -> str:
        """生成并保存报告"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        report_content = f"""# Aquamind Systems 智能预测与控制报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## 1. 用户请求摘要
- **原始输入**: {user_input}
- **识别意图**: {intent}
- **识别工艺**: {params['treatment_process']}
- **预测时效**: {params['time_frame']}

## 2. 水质毒性预测分析 (ToxicityAgent)
- **毒性等级**: {toxicity_result.get('toxicity_level', '未知')}
- **风险等级**: {toxicity_result.get('risk_level', '未知')}

{toxicity_result.get('analysis', '')}

## 3. 工艺调整建议 (ControlAgent)
{control_suggestion}

"""
        
        # 添加进阶智能体结果
        if "turntable" in advanced_results:
            tt = advanced_results["turntable"]
            report_content += f"""## 4. 转盘控制建议 (TurntableAgent)
- **推荐频率**: {tt.get('frequency_1', 0):.1f} Hz
- **转速**: {tt.get('rpm_1', 0):.0f} rpm
- **活跃反应器**: {tt.get('active_reactors', 2)} 台
- **预期去除率**: {tt.get('expected_removal_rate', 0):.1f}%
- **决策原因**: {tt.get('decision_reason', '')}

"""
        
        if "mbr" in advanced_results:
            mbr = advanced_results["mbr"]
            report_content += f"""## 5. MBR控制建议 (MBRAgent)
- **曝气量**: {mbr.get('aeration_rate', 50):.1f} m³/h
- **通量设定**: {mbr.get('flux_setpoint', 18):.1f} LMH
- **污染状态**: {mbr.get('fouling_status', 'normal')}
- **需要反洗**: {'是' if mbr.get('backwash_needed') else '否'}

"""
        
        if "regeneration" in advanced_results:
            regen = advanced_results["regeneration"]
            report_content += f"""## 6. 再生系统评估 (RegenerationAgent)
- **需要再生**: {'是' if regen.get('regeneration_needed') else '否'}
- **再生模式**: {regen.get('regeneration_mode', 'standby')}
- **炉温设定**: {regen.get('furnace_temperature', 0):.0f}°C

"""
        
        if "diagnostic" in advanced_results:
            diag = advanced_results["diagnostic"]
            report_content += f"""## 7. 系统诊断 (DiagnosticAgent)
- **整体健康**: {diag.get('overall_health', '未知')}
- **综合评分**: {diag.get('overall_score', 0):.1f}/100

"""
        
        report_content += """---
*Aquamind Systems - 您的智慧水务专家*
"""
        
        # 保存报告
        report_dir = os.path.join(root_dir, "Report")
        if not os.path.exists(report_dir):
            os.makedirs(report_dir)
            
        report_path = os.path.join(report_dir, f"Report_{timestamp}.md")
        
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report_content)
            
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 报告已生成: {report_path}")
        return f"执行完成。报告已保存至: {report_path}\n\n报告内容:\n{report_content}"
    
    def quick_predict(self, toxicity: float = None, ammonia: float = None,
                      temperature: float = None) -> Dict[str, Any]:
        """
        快速预测接口
        
        Args:
            toxicity: 当前毒性值
            ammonia: 氨氮浓度
            temperature: 温度
            
        Returns:
            Dict: 包含预测结果和控制建议
        """
        # 构建输入
        parts = []
        if toxicity is not None:
            parts.append(f"毒性{toxicity}")
        if ammonia is not None:
            parts.append(f"氨氮{ammonia}mg/L")
        if temperature is not None:
            parts.append(f"温度{temperature}度")
        
        if not parts:
            return {"status": "error", "message": "请提供至少一个参数"}
        
        input_text = f"当前水质: {', '.join(parts)}，请预测并给出控制建议"
        
        # 调用毒性预测
        toxicity_result = self.toxicity_agent.run(input_text)
        
        # 如果有转盘智能体，直接生成控制参数
        turntable_params = {}
        if self.turntable_agent and toxicity is not None:
            output = self.turntable_agent.generate_control_output(
                toxicity=toxicity,
                toxicity_level=toxicity_result.get("toxicity_level", "中"),
                trend="稳定"
            )
            turntable_params = output.to_dict()
        
        return {
            "status": "success",
            "toxicity_prediction": toxicity_result,
            "turntable_control": turntable_params,
            "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
    
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        status = self.system_state.copy()
        
        if self.diagnostic_agent:
            diag = self.diagnostic_agent.generate_diagnostic_report()
            status["diagnostic"] = diag.to_dict()
        
        return status


if __name__ == "__main__":
    # 测试
    orchestrator = AquamindOrchestrator()
    sample_input = "你好Aquamind，我目前的运行工艺是AAO，目前水质毒性数据是氨氮25mg/L，温度20度，毒性是10，请你帮我预测下未杈24小时后的毒性数据并给出调整方案"
    print(orchestrator.run(sample_input))
