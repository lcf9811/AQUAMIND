"""
反馈智能体 (FeedbackAgent)
负责收集运行反馈、评估控制效果并进行自适应调整

功能:
1. 收集各子系统运行反馈
2. 评估控制策略效果
3. 学习和优化控制参数
4. 生成改进建议
"""

import sys
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque
import json

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from LLM.llm_interface import LLMInterface
from Knowledge.knowledge_base import get_knowledge_base


@dataclass
class ControlFeedback:
    """控制反馈记录"""
    agent_name: str              # 智能体名称
    action_taken: str            # 采取的操作
    expected_result: str         # 预期结果
    actual_result: str           # 实际结果
    effectiveness: float         # 有效性评分 (0-1)
    parameters: Dict[str, Any]   # 控制参数
    timestamp: str               # 时间戳
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_name": self.agent_name,
            "action_taken": self.action_taken,
            "expected_result": self.expected_result,
            "actual_result": self.actual_result,
            "effectiveness": self.effectiveness,
            "parameters": self.parameters,
            "timestamp": self.timestamp
        }


@dataclass
class LearningRecord:
    """学习记录"""
    scenario: str                # 场景描述
    optimal_parameters: Dict[str, Any]  # 最优参数
    success_rate: float          # 成功率
    sample_count: int            # 样本数量
    last_updated: str            # 最后更新时间


@dataclass
class FeedbackAnalysisOutput:
    """反馈分析输出"""
    effectiveness_score: float   # 整体有效性评分
    successful_actions: List[str]  # 成功的操作
    failed_actions: List[str]    # 失败的操作
    parameter_adjustments: Dict[str, Any]  # 参数调整建议
    learning_insights: List[str]  # 学习洞察
    improvement_suggestions: List[str]  # 改进建议
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "effectiveness_score": self.effectiveness_score,
            "successful_actions": self.successful_actions,
            "failed_actions": self.failed_actions,
            "parameter_adjustments": self.parameter_adjustments,
            "learning_insights": self.learning_insights,
            "improvement_suggestions": self.improvement_suggestions,
            "timestamp": self.timestamp
        }


class FeedbackAgent:
    """
    反馈智能体
    
    负责系统运行反馈的收集和分析，包括：
    - 控制效果评估
    - 参数优化建议
    - 自适应学习
    - 持续改进
    """
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一位水处理系统反馈分析专家 (FeedbackAgent)。

你的核心职责是分析各控制智能体的执行效果，评估控制策略的有效性，并提供优化建议。

## 分析维度
1. **效果评估**: 对比预期结果与实际结果
2. **参数优化**: 根据历史数据推荐最优参数
3. **趋势分析**: 识别长期运行趋势
4. **问题诊断**: 分析失败原因

## 反馈原则
1. 基于数据做客观评估
2. 关注可量化的改进指标
3. 提供具体可执行的建议
4. 支持持续学习和优化

## 评估标准
- 有效性 > 80%: 控制策略成功
- 有效性 60-80%: 需要微调
- 有效性 < 60%: 需要重新评估策略

请基于提供的反馈数据，生成详细的分析报告和改进建议。"""

    def __init__(self, llm_interface: LLMInterface = None, history_size: int = 100):
        """初始化反馈智能体"""
        self.llm_interface = llm_interface or LLMInterface()
        self.kb = get_knowledge_base()
        self.chain = self._create_chain()
        
        # 反馈历史记录
        self.feedback_history: deque = deque(maxlen=history_size)
        
        # 学习记录
        self.learning_records: Dict[str, LearningRecord] = {}
        
        # 参数基准值
        self.parameter_baselines: Dict[str, Dict[str, float]] = {
            "turntable": {"frequency": 25.0, "reactors": 2},
            "mbr": {"aeration": 50.0, "flux": 18.0},
            "regeneration": {"temperature": 800.0, "feed_rate": 30.0}
        }
    
    def _create_chain(self):
        """创建LangChain处理链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", """
## 最近的控制反馈数据
{feedback_data}

## 历史统计
- 平均有效性：{avg_effectiveness}%
- 总反馈数量：{total_feedbacks}

## 请分析并给出建议
1. 评估各智能体控制效果
2. 识别需要改进的方面
3. 提供参数优化建议
4. 给出持续改进方案
""")
        ])
        
        api_key = self.llm_interface.qwen_api_key or self.llm_interface.openai_api_key
        base_url = self.llm_interface.qwen_api_base or self.llm_interface.openai_api_base
        model_name = self.llm_interface.qwen_model_name or "qwen-plus"
        
        llm = ChatOpenAI(
            api_key=api_key,
            base_url=base_url,
            model=model_name,
            temperature=0.3
        )
        
        return prompt | llm | StrOutputParser()
    
    def record_feedback(self, feedback: ControlFeedback):
        """记录控制反馈"""
        self.feedback_history.append(feedback)
        
        # 更新学习记录
        self._update_learning_record(feedback)
    
    def _update_learning_record(self, feedback: ControlFeedback):
        """更新学习记录"""
        scenario_key = f"{feedback.agent_name}_{feedback.action_taken}"
        
        if scenario_key not in self.learning_records:
            self.learning_records[scenario_key] = LearningRecord(
                scenario=scenario_key,
                optimal_parameters=feedback.parameters.copy(),
                success_rate=feedback.effectiveness,
                sample_count=1,
                last_updated=feedback.timestamp
            )
        else:
            record = self.learning_records[scenario_key]
            n = record.sample_count
            
            # 更新成功率（移动平均）
            record.success_rate = (record.success_rate * n + feedback.effectiveness) / (n + 1)
            record.sample_count += 1
            record.last_updated = feedback.timestamp
            
            # 如果这次效果更好，更新最优参数
            if feedback.effectiveness > 0.8:
                record.optimal_parameters = feedback.parameters.copy()
    
    def get_recommended_parameters(self, agent_name: str, 
                                    action: str) -> Dict[str, Any]:
        """获取推荐参数"""
        scenario_key = f"{agent_name}_{action}"
        
        if scenario_key in self.learning_records:
            record = self.learning_records[scenario_key]
            if record.success_rate > 0.7:
                return record.optimal_parameters
        
        # 返回基准参数
        return self.parameter_baselines.get(agent_name, {})
    
    def calculate_effectiveness(self, expected: float, actual: float,
                                 tolerance: float = 0.2) -> float:
        """计算控制有效性"""
        if expected == 0:
            return 1.0 if actual == 0 else 0.0
        
        error = abs(expected - actual) / expected
        effectiveness = max(0, 1 - error / tolerance)
        return round(effectiveness, 2)
    
    def run(self, feedback_data: str = None) -> Dict[str, Any]:
        """
        运行反馈分析
        
        Args:
            feedback_data: 反馈数据描述（可选，默认使用历史记录）
            
        Returns:
            Dict: 包含分析结果和LLM建议
        """
        try:
            # 准备反馈数据
            if feedback_data is None:
                recent_feedbacks = list(self.feedback_history)[-10:]
                feedback_data = json.dumps(
                    [f.to_dict() for f in recent_feedbacks],
                    ensure_ascii=False,
                    indent=2
                ) if recent_feedbacks else "无历史反馈数据"
            
            # 计算统计数据
            if self.feedback_history:
                avg_effectiveness = sum(f.effectiveness for f in self.feedback_history) / len(self.feedback_history) * 100
            else:
                avg_effectiveness = 0
            
            llm_response = self.chain.invoke({
                "feedback_data": feedback_data,
                "avg_effectiveness": f"{avg_effectiveness:.1f}",
                "total_feedbacks": len(self.feedback_history)
            })
            
            return {
                "status": "success",
                "analysis": llm_response,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {
                "status": "error",
                "analysis": f"反馈分析失败: {str(e)}",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def generate_feedback_analysis(self) -> FeedbackAnalysisOutput:
        """生成反馈分析报告"""
        if not self.feedback_history:
            return FeedbackAnalysisOutput(
                effectiveness_score=0.0,
                successful_actions=[],
                failed_actions=[],
                parameter_adjustments={},
                learning_insights=["无历史反馈数据"],
                improvement_suggestions=["开始收集运行反馈"],
                timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        
        # 统计成功和失败的操作
        successful_actions = []
        failed_actions = []
        effectiveness_sum = 0
        
        for feedback in self.feedback_history:
            effectiveness_sum += feedback.effectiveness
            if feedback.effectiveness >= 0.7:
                successful_actions.append(
                    f"{feedback.agent_name}: {feedback.action_taken}"
                )
            else:
                failed_actions.append(
                    f"{feedback.agent_name}: {feedback.action_taken} "
                    f"(效果: {feedback.effectiveness:.0%})"
                )
        
        avg_effectiveness = effectiveness_sum / len(self.feedback_history)
        
        # 生成参数调整建议
        parameter_adjustments = {}
        for agent_name, baseline in self.parameter_baselines.items():
            agent_feedbacks = [f for f in self.feedback_history 
                             if f.agent_name == agent_name and f.effectiveness >= 0.8]
            if agent_feedbacks:
                # 使用最成功的参数
                best_feedback = max(agent_feedbacks, key=lambda x: x.effectiveness)
                parameter_adjustments[agent_name] = best_feedback.parameters
        
        # 生成学习洞察
        learning_insights = []
        for scenario, record in self.learning_records.items():
            if record.sample_count >= 3:
                insight = f"{scenario}: 成功率 {record.success_rate:.0%} (样本数: {record.sample_count})"
                learning_insights.append(insight)
        
        # 生成改进建议
        improvement_suggestions = []
        if avg_effectiveness < 0.6:
            improvement_suggestions.append("整体控制效果较差，建议重新评估控制策略")
        elif avg_effectiveness < 0.8:
            improvement_suggestions.append("控制效果有待提高，建议优化关键参数")
        
        if failed_actions:
            improvement_suggestions.append(f"重点改进失败操作（共{len(failed_actions)}项）")
        
        for agent_name in ["turntable", "mbr", "regeneration"]:
            agent_feedbacks = [f for f in self.feedback_history if f.agent_name == agent_name]
            if agent_feedbacks:
                agent_avg = sum(f.effectiveness for f in agent_feedbacks) / len(agent_feedbacks)
                if agent_avg < 0.7:
                    improvement_suggestions.append(
                        f"{agent_name}智能体效果较差({agent_avg:.0%})，建议检查"
                    )
        
        return FeedbackAnalysisOutput(
            effectiveness_score=avg_effectiveness,
            successful_actions=successful_actions[:10],
            failed_actions=failed_actions[:10],
            parameter_adjustments=parameter_adjustments,
            learning_insights=learning_insights[:10],
            improvement_suggestions=improvement_suggestions[:5],
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def create_turntable_feedback(self, toxicity_before: float, toxicity_after: float,
                                   frequency: float, expected_removal: float) -> ControlFeedback:
        """创建转盘控制反馈"""
        actual_removal = (toxicity_before - toxicity_after) / toxicity_before * 100 if toxicity_before > 0 else 0
        effectiveness = self.calculate_effectiveness(expected_removal, actual_removal)
        
        return ControlFeedback(
            agent_name="turntable",
            action_taken="frequency_control",
            expected_result=f"预期去除率 {expected_removal:.1f}%",
            actual_result=f"实际去除率 {actual_removal:.1f}%",
            effectiveness=effectiveness,
            parameters={
                "frequency": frequency,
                "toxicity_before": toxicity_before,
                "toxicity_after": toxicity_after
            },
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )
    
    def create_mbr_feedback(self, tmp_before: float, tmp_after: float,
                            aeration_rate: float, flux: float) -> ControlFeedback:
        """创建MBR控制反馈"""
        # TMP降低或稳定视为成功
        effectiveness = 1.0 if tmp_after <= tmp_before else max(0, 1 - (tmp_after - tmp_before) / 10)
        
        return ControlFeedback(
            agent_name="mbr",
            action_taken="tmp_control",
            expected_result="TMP稳定或降低",
            actual_result=f"TMP从 {tmp_before:.1f} 变为 {tmp_after:.1f} kPa",
            effectiveness=effectiveness,
            parameters={
                "aeration_rate": aeration_rate,
                "flux": flux,
                "tmp_change": tmp_after - tmp_before
            },
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )


if __name__ == "__main__":
    # 测试反馈智能体
    print("=== 反馈智能体测试 ===")
    
    agent = FeedbackAgent()
    
    # 模拟添加反馈
    print("\n添加模拟反馈...")
    
    # 成功的转盘控制
    feedback1 = agent.create_turntable_feedback(
        toxicity_before=3.0,
        toxicity_after=1.2,
        frequency=30.0,
        expected_removal=50.0
    )
    agent.record_feedback(feedback1)
    print(f"  转盘反馈: 效果 {feedback1.effectiveness:.0%}")
    
    # MBR控制
    feedback2 = agent.create_mbr_feedback(
        tmp_before=28.0,
        tmp_after=25.0,
        aeration_rate=55.0,
        flux=16.0
    )
    agent.record_feedback(feedback2)
    print(f"  MBR反馈: 效果 {feedback2.effectiveness:.0%}")
    
    # 生成分析报告
    print("\n生成分析报告...")
    analysis = agent.generate_feedback_analysis()
    print(f"  整体有效性: {analysis.effectiveness_score:.0%}")
    print(f"  成功操作: {len(analysis.successful_actions)} 项")
    print(f"  改进建议: {analysis.improvement_suggestions}")
    
    # 获取推荐参数
    print("\n推荐参数:")
    params = agent.get_recommended_parameters("turntable", "frequency_control")
    print(f"  转盘参数: {params}")
