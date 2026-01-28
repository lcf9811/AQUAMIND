"""
诊断评估智能体 (DiagnosticAgent)
负责整体系统运行状态的诊断和评估

功能:
1. 综合评估各子系统运行状态
2. 识别潜在问题和风险
3. 生成系统健康报告
4. 提供维护建议
"""

import sys
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

# 添加项目根目录到Python路径
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if root_dir not in sys.path:
    sys.path.append(root_dir)

from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import ChatOpenAI

from LLM.llm_interface import LLMInterface
from Knowledge.knowledge_base import get_knowledge_base


class HealthLevel(Enum):
    """系统健康等级"""
    EXCELLENT = "优秀"
    GOOD = "良好"
    ATTENTION = "需关注"
    WARNING = "警告"
    CRITICAL = "严重"


@dataclass
class SubsystemStatus:
    """子系统状态"""
    name: str
    health_level: HealthLevel
    score: float  # 0-100
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class DiagnosticReport:
    """诊断报告"""
    overall_health: HealthLevel
    overall_score: float
    subsystem_status: Dict[str, SubsystemStatus]
    critical_issues: List[str]
    warnings: List[str]
    recommendations: List[str]
    timestamp: str
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "overall_health": self.overall_health.value,
            "overall_score": self.overall_score,
            "subsystem_status": {
                name: {
                    "name": status.name,
                    "health_level": status.health_level.value,
                    "score": status.score,
                    "issues": status.issues,
                    "recommendations": status.recommendations
                }
                for name, status in self.subsystem_status.items()
            },
            "critical_issues": self.critical_issues,
            "warnings": self.warnings,
            "recommendations": self.recommendations,
            "timestamp": self.timestamp
        }
    
    def to_markdown(self) -> str:
        """生成Markdown格式报告"""
        md = f"""# 系统诊断评估报告
生成时间: {self.timestamp}

## 1. 整体评估
- **健康等级**: {self.overall_health.value}
- **综合评分**: {self.overall_score:.1f}/100

## 2. 子系统状态
"""
        for name, status in self.subsystem_status.items():
            md += f"""
### {status.name}
- 健康等级: {status.health_level.value}
- 评分: {status.score:.1f}/100
"""
            if status.issues:
                md += "- 问题:\n"
                for issue in status.issues:
                    md += f"  - {issue}\n"
            if status.recommendations:
                md += "- 建议:\n"
                for rec in status.recommendations:
                    md += f"  - {rec}\n"
        
        if self.critical_issues:
            md += "\n## 3. 严重问题\n"
            for issue in self.critical_issues:
                md += f"- ⚠️ {issue}\n"
        
        if self.warnings:
            md += "\n## 4. 警告\n"
            for warning in self.warnings:
                md += f"- ⚡ {warning}\n"
        
        md += "\n## 5. 综合建议\n"
        for rec in self.recommendations:
            md += f"- {rec}\n"
        
        return md


class DiagnosticAgent:
    """
    诊断评估智能体
    
    负责整体系统运行状态的诊断，包括：
    - 各子系统健康评估
    - 问题识别和风险预警
    - 维护建议生成
    - 系统优化建议
    """
    
    # 系统提示词
    SYSTEM_PROMPT = """你是一位资深的水处理系统诊断专家 (DiagnosticAgent)。

你的核心职责是综合分析整个水处理系统的运行状态，识别潜在问题，并提供专业的诊断报告。

## 诊断范围
1. **毒性预测系统**: 预测准确性、数据质量
2. **转盘吸附系统**: 运行效率、设备状态
3. **MBR膜系统**: 膜污染、通量稳定性
4. **再生系统**: 再生效果、能耗水平
5. **整体协调**: 各系统配合、参数匹配

## 评估标准
- **优秀** (90-100分): 所有指标正常，效率最优
- **良好** (75-89分): 大部分指标正常，无明显问题
- **需关注** (60-74分): 存在需要关注的问题
- **警告** (40-59分): 存在明显问题，需要处理
- **严重** (<40分): 存在严重问题，需要立即处理

## 诊断原则
1. 综合考虑各系统的关联性
2. 优先识别影响出水质量的问题
3. 关注能耗和运行成本
4. 预防性维护建议

请基于提供的系统数据，生成专业的诊断评估报告。"""

    def __init__(self, llm_interface: LLMInterface = None):
        """初始化诊断评估智能体"""
        self.llm_interface = llm_interface or LLMInterface()
        self.kb = get_knowledge_base()
        self.chain = self._create_chain()
    
    def _create_chain(self):
        """创建LangChain处理链"""
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            ("human", """
## 系统运行数据

### 毒性预测
{toxicity_data}

### 转盘吸附系统
{turntable_data}

### MBR膜系统
{mbr_data}

### 再生系统
{regeneration_data}

## 请生成诊断报告
请从以下方面进行评估：
1. 各子系统健康状态评分
2. 发现的问题和风险
3. 优化建议
4. 维护计划建议
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
    
    def _score_to_health_level(self, score: float) -> HealthLevel:
        """评分转换为健康等级"""
        if score >= 90:
            return HealthLevel.EXCELLENT
        elif score >= 75:
            return HealthLevel.GOOD
        elif score >= 60:
            return HealthLevel.ATTENTION
        elif score >= 40:
            return HealthLevel.WARNING
        else:
            return HealthLevel.CRITICAL
    
    def _evaluate_toxicity_subsystem(self, toxicity: float, confidence: float,
                                      prediction_accuracy: float) -> SubsystemStatus:
        """评估毒性预测子系统"""
        issues = []
        recommendations = []
        score = 100.0
        
        # 评估预测置信度
        if confidence < 0.6:
            score -= 20
            issues.append("预测置信度较低")
            recommendations.append("增加历史数据量，提高模型准确性")
        elif confidence < 0.8:
            score -= 10
            issues.append("预测置信度中等")
        
        # 评估预测准确性
        if prediction_accuracy < 70:
            score -= 25
            issues.append("预测准确性不足")
            recommendations.append("重新训练预测模型")
        elif prediction_accuracy < 85:
            score -= 10
        
        # 评估毒性水平
        if toxicity > 5.0:
            score -= 15
            issues.append("进水毒性偏高")
            recommendations.append("关注进水来源，加强预处理")
        
        return SubsystemStatus(
            name="毒性预测系统",
            health_level=self._score_to_health_level(score),
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_turntable_subsystem(self, frequency: float, removal_rate: float,
                                       standby_triggered: bool) -> SubsystemStatus:
        """评估转盘吸附子系统"""
        issues = []
        recommendations = []
        score = 100.0
        
        # 评估去除率
        if removal_rate < 50:
            score -= 30
            issues.append("毒性去除率偏低")
            recommendations.append("检查活性炭吸附能力")
            recommendations.append("考虑增加运行频率")
        elif removal_rate < 70:
            score -= 15
            issues.append("去除率有待提高")
        
        # 评估运行频率
        if frequency > 45:
            score -= 10
            issues.append("运行频率偏高")
            recommendations.append("关注设备能耗")
        
        # 备用线路状态
        if standby_triggered:
            score -= 15
            issues.append("备用线路已启用")
            recommendations.append("检查主线路是否存在问题")
        
        return SubsystemStatus(
            name="转盘吸附系统",
            health_level=self._score_to_health_level(score),
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_mbr_subsystem(self, tmp: float, flux: float,
                                 fouling_status: str) -> SubsystemStatus:
        """评估MBR子系统"""
        issues = []
        recommendations = []
        score = 100.0
        
        # 评估TMP
        if tmp > 40:
            score -= 35
            issues.append("TMP严重超标")
            recommendations.append("立即进行化学清洗")
        elif tmp > 30:
            score -= 20
            issues.append("TMP偏高")
            recommendations.append("增强反洗，准备清洗")
        elif tmp > 25:
            score -= 10
            issues.append("TMP接近预警值")
        
        # 评估通量
        if flux < 10:
            score -= 25
            issues.append("产水通量严重不足")
        elif flux < 15:
            score -= 15
            issues.append("产水通量偏低")
        
        # 污染状态
        if fouling_status == "critical":
            score -= 30
            issues.append("膜污染严重")
        elif fouling_status == "warning":
            score -= 15
            issues.append("存在膜污染")
        
        return SubsystemStatus(
            name="MBR膜系统",
            health_level=self._score_to_health_level(score),
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )
    
    def _evaluate_regeneration_subsystem(self, adsorption_efficiency: float,
                                          need_regeneration: bool) -> SubsystemStatus:
        """评估再生子系统"""
        issues = []
        recommendations = []
        score = 100.0
        
        # 评估吸附效率
        if adsorption_efficiency < 60:
            score -= 30
            issues.append("活性炭吸附效率严重下降")
            recommendations.append("立即安排再生")
        elif adsorption_efficiency < 80:
            score -= 15
            issues.append("吸附效率下降")
        
        # 再生需求
        if need_regeneration:
            score -= 10
            issues.append("需要进行再生")
            recommendations.append("安排再生计划")
        
        return SubsystemStatus(
            name="再生系统",
            health_level=self._score_to_health_level(score),
            score=max(0, score),
            issues=issues,
            recommendations=recommendations
        )
    
    def run(self, toxicity_data: str, turntable_data: str,
            mbr_data: str, regeneration_data: str) -> Dict[str, Any]:
        """
        运行诊断评估智能体
        
        Args:
            toxicity_data: 毒性预测数据描述
            turntable_data: 转盘系统数据描述
            mbr_data: MBR系统数据描述
            regeneration_data: 再生系统数据描述
            
        Returns:
            Dict: 包含诊断结果和LLM分析
        """
        try:
            llm_response = self.chain.invoke({
                "toxicity_data": toxicity_data,
                "turntable_data": turntable_data,
                "mbr_data": mbr_data,
                "regeneration_data": regeneration_data
            })
            
            return {
                "status": "success",
                "diagnosis": llm_response,
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            return {
                "status": "error",
                "diagnosis": f"诊断评估失败: {str(e)}",
                "timestamp": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
    
    def generate_diagnostic_report(self,
                                    toxicity: float = 2.0,
                                    confidence: float = 0.85,
                                    prediction_accuracy: float = 80.0,
                                    turntable_frequency: float = 25.0,
                                    turntable_removal_rate: float = 70.0,
                                    turntable_standby: bool = False,
                                    mbr_tmp: float = 20.0,
                                    mbr_flux: float = 18.0,
                                    mbr_fouling: str = "normal",
                                    carbon_efficiency: float = 85.0,
                                    need_regeneration: bool = False) -> DiagnosticReport:
        """
        生成结构化诊断报告
        
        Returns:
            DiagnosticReport: 诊断报告
        """
        # 评估各子系统
        toxicity_status = self._evaluate_toxicity_subsystem(
            toxicity, confidence, prediction_accuracy
        )
        turntable_status = self._evaluate_turntable_subsystem(
            turntable_frequency, turntable_removal_rate, turntable_standby
        )
        mbr_status = self._evaluate_mbr_subsystem(
            mbr_tmp, mbr_flux, mbr_fouling
        )
        regeneration_status = self._evaluate_regeneration_subsystem(
            carbon_efficiency, need_regeneration
        )
        
        # 汇总子系统状态
        subsystem_status = {
            "toxicity": toxicity_status,
            "turntable": turntable_status,
            "mbr": mbr_status,
            "regeneration": regeneration_status
        }
        
        # 计算整体评分
        overall_score = sum(s.score for s in subsystem_status.values()) / len(subsystem_status)
        
        # 收集严重问题和警告
        critical_issues = []
        warnings = []
        for status in subsystem_status.values():
            if status.health_level in [HealthLevel.CRITICAL, HealthLevel.WARNING]:
                critical_issues.extend(status.issues)
            elif status.health_level == HealthLevel.ATTENTION:
                warnings.extend(status.issues)
        
        # 生成综合建议
        recommendations = []
        for status in subsystem_status.values():
            recommendations.extend(status.recommendations)
        
        # 去重
        recommendations = list(set(recommendations))
        
        return DiagnosticReport(
            overall_health=self._score_to_health_level(overall_score),
            overall_score=overall_score,
            subsystem_status=subsystem_status,
            critical_issues=critical_issues,
            warnings=warnings,
            recommendations=recommendations[:10],  # 限制建议数量
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        )


if __name__ == "__main__":
    # 测试诊断评估智能体
    print("=== 诊断评估智能体测试 ===")
    
    agent = DiagnosticAgent()
    
    # 测试场景1：系统正常
    print("\n场景1：系统正常运行")
    report1 = agent.generate_diagnostic_report(
        toxicity=1.5,
        confidence=0.88,
        prediction_accuracy=85.0,
        turntable_frequency=25.0,
        turntable_removal_rate=75.0,
        mbr_tmp=18.0,
        mbr_flux=19.0,
        carbon_efficiency=88.0
    )
    print(f"  整体健康: {report1.overall_health.value}")
    print(f"  综合评分: {report1.overall_score:.1f}")
    
    # 测试场景2：存在问题
    print("\n场景2：MBR膜污染")
    report2 = agent.generate_diagnostic_report(
        toxicity=2.5,
        mbr_tmp=35.0,
        mbr_flux=12.0,
        mbr_fouling="warning"
    )
    print(f"  整体健康: {report2.overall_health.value}")
    print(f"  严重问题: {report2.critical_issues}")
    
    # 输出Markdown报告
    print("\n=== Markdown报告示例 ===")
    print(report2.to_markdown()[:500] + "...")
