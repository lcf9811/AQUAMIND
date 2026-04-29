"""
工段编排智能体 (Process Stage Agent)
纯编排层 — 按配置文件 flow_sequence 自由排列工艺段。
支持任意组合: A2O, AAOA, AOA, AO 等。
"""
import os
import yaml
from typing import Dict, Any, Optional, List
from datetime import datetime

from models.calculator import StageCalculator
from models.deviation_analyzer import DeviationAnalyzer
from models.equipment_mapper import EquipmentMapper
from models.sumo_integration import SumoIntegration

from agents.anaerobic_agent import AnaerobicProcessAgent
from agents.anoxic_agent import AnoxicProcessAgent
from agents.aerobic_agent import AerobicProcessAgent


STAGE_CLASS_MAP = {
    "anaerobic": AnaerobicProcessAgent,
    "anoxic": AnoxicProcessAgent,
    "aerobic": AerobicProcessAgent,
}


class ProcessStageAgent:
    """工段编排智能体 — 配置驱动，自由组合工艺段"""

    def __init__(self, scada_base_url: str, agent_id: str = "process_stage",
                 config_path: str = None):
        self.scada_base_url = scada_base_url.rstrip('/')
        self.agent_id = agent_id
        self.last_verification = None

        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "config", "process_stage_params.yaml"
            )
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        ps_cfg = cfg.get("process_stage", {})

        # ─── 读取 flow_sequence，动态创建工段 Agent ───
        sequence = ps_cfg.get("flow_sequence", ["anaerobic", "anoxic", "aerobic"])
        counter: Dict[str, int] = {}
        self.stages: List[Dict[str, Any]] = []
        self.flow_sequence = sequence

        for stage_type in sequence:
            if stage_type not in STAGE_CLASS_MAP:
                raise ValueError(
                    f"未知工艺段类型: {stage_type}，支持: {list(STAGE_CLASS_MAP.keys())}"
                )
            counter[stage_type] = counter.get(stage_type, 0) + 1
            if counter[stage_type] > 1:
                stage_id = f"{stage_type}_{counter[stage_type]}"
            else:
                stage_id = stage_type

            cls = STAGE_CLASS_MAP[stage_type]
            self.stages.append({
                "type": stage_type,
                "id": stage_id,
                "agent": cls(scada_base_url, f"{stage_id}_process"),
            })

        self.calculator = StageCalculator(ps_cfg)
        self.analyzer = DeviationAnalyzer()
        self.mapper = EquipmentMapper()
        self.sumo = SumoIntegration()

    # ═══════════════════════════════════════════════════════════
    #  Skill 1: 获取全工段工况
    # ═══════════════════════════════════════════════════════════

    def get_process_status(self) -> Dict[str, Any]:
        """按 flow_sequence 顺序返回所有工艺段工况"""
        ts = datetime.utcnow().isoformat()
        try:
            stages_status = {}
            for s in self.stages:
                stages_status[s["id"]] = s["agent"].get_stage_status()

            return {
                "agent_id": self.agent_id,
                "skill": "get_process_status",
                "timestamp": ts,
                "flow_sequence": [s["type"] for s in self.stages],
                "stages": stages_status,
                "note": "此数据供 LLM 推理调控建议，Agent 不做计算。",
            }
        except Exception as e:
            return {"agent_id": self.agent_id, "skill": "get_process_status",
                    "timestamp": ts, "error": str(e)}

    # ═══════════════════════════════════════════════════════════
    #  Skill 2: 对比 Agent 建议与 Calculator 参考
    # ═══════════════════════════════════════════════════════════

    def compare_with_calculator(
        self, agent_suggestions: Dict[str, Any]
    ) -> Dict[str, Any]:
        """将 LLM 推理建议与机理 Calculator 链式参考值对比"""
        ts = datetime.utcnow().isoformat()
        try:
            status = self.get_process_status()
            references = self.calculator.calculate_chain_references(
                self.stages, status["stages"]
            )
            analysis = self.analyzer.analyze(
                agent_suggestions, references, self.stages
            )

            equipment_commands = None
            if analysis["verdict"] != "divergent":
                equipment_commands = {
                    "sumo_commands": self.mapper.to_sumo_commands(agent_suggestions),
                    "modbus_writes": self.mapper.to_modbus_writes(agent_suggestions),
                }

            return {
                "agent_id": self.agent_id,
                "skill": "compare_with_calculator",
                "timestamp": ts,
                "flow_sequence": [s["type"] for s in self.stages],
                "agent_suggestions": agent_suggestions,
                "calculator_references": references,
                "deviation_analysis": analysis,
                "equipment_commands": equipment_commands,
                "can_proceed": analysis["verdict"] != "divergent",
            }
        except Exception as e:
            return {"agent_id": self.agent_id, "skill": "compare_with_calculator",
                    "timestamp": ts, "error": str(e)}

    # ═══════════════════════════════════════════════════════════
    #  Skill 3: SUMO 验证
    # ═══════════════════════════════════════════════════════════

    def validate_suggestions(
        self, suggestions: Dict[str, Any],
        inlet_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self.sumo.validate_suggestions(suggestions, inlet_state)

    # ═══════════════════════════════════════════════════════════
    #  Skill 4: 导出 SUMO
    # ═══════════════════════════════════════════════════════════

    def export_to_sumo(
        self, agent_suggestions: Dict[str, Any],
        influent: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        ts = datetime.utcnow().isoformat()
        try:
            comparison = self.compare_with_calculator(agent_suggestions)
            if influent is None:
                influent = {
                    "cod_mg_l": 300, "bod_mg_l": 150,
                    "tn_mg_l": 35, "nh3_mg_l": 25,
                    "tp_mg_l": 5, "ss_mg_l": 200,
                    "flow_m3_h": 500, "temp_c": 20,
                }
            keys = list(agent_suggestions.keys())[:3]
            ap = agent_suggestions.get(keys[0], {}) if len(keys) > 0 else {}
            anp = agent_suggestions.get(keys[1], {}) if len(keys) > 1 else {}
            aep = agent_suggestions.get(keys[2], {}) if len(keys) > 2 else {}
            filepath = self.sumo.export_input(influent, ap, anp, aep)
            return {
                "agent_id": self.agent_id, "skill": "export_to_sumo",
                "timestamp": ts, "sumo_input_file": filepath,
                "influent": influent,
                "deviation_check": comparison.get("deviation_analysis", {}),
                "warning": (
                    "偏差超出正常范围，建议人工审核后再执行 SUMO 仿真"
                    if not comparison.get("can_proceed", True) else None
                ),
            }
        except Exception as e:
            return {"agent_id": self.agent_id, "skill": "export_to_sumo",
                    "timestamp": ts, "error": str(e)}

    # ═══════════════════════════════════════════════════════════
    #  Public
    # ═══════════════════════════════════════════════════════════

    def get_sub_agents(self) -> Dict[str, Any]:
        return {s["id"]: s["agent"].get_tools() for s in self.stages}

    def get_verification_summary(self) -> Optional[Dict[str, Any]]:
        summaries = {s["id"]: s["agent"].get_verification_summary() for s in self.stages}
        if self.last_verification:
            summaries["orchestrator"] = {
                "agent_id": self.agent_id,
                "last_skill": self.last_verification["skill"],
                "last_timestamp": self.last_verification["timestamp"],
                "result": self.last_verification["result"],
            }
        return summaries

    def get_tools(self) -> Dict[str, Any]:
        seq_str = " → ".join(s["type"] for s in self.stages)
        return {
            "agent_id": self.agent_id,
            "name": "Process Stage Agent (Configurable Orchestrator)",
            "description": f"工艺编排智能体，当前流程: {seq_str}",
            "skills": [
                {"name": "get_process_status",
                 "description": f"获取 {len(self.stages)} 段工况({seq_str})",
                 "parameters": [], "returns": "process_status"},
                {"name": "compare_with_calculator",
                 "description": "LLM 建议 vs 机理 Calculator 偏差分析",
                 "parameters": [{"name": "agent_suggestions", "type": "dict"}],
                 "returns": "comparison_report"},
                {"name": "validate_suggestions",
                 "description": "SUMO Gujer 矩阵验证",
                 "parameters": [
                     {"name": "suggestions", "type": "dict"},
                     {"name": "inlet_state", "type": "dict", "default": None},
                 ], "returns": "validation_result"},
                {"name": "export_to_sumo",
                 "description": "导出 SUMO 输入文件",
                 "parameters": [
                     {"name": "agent_suggestions", "type": "dict"},
                     {"name": "influent", "type": "dict", "default": None},
                 ], "returns": "sumo_export_result"},
            ],
            "sub_agents": self.get_sub_agents(),
        }
