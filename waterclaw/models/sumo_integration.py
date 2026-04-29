"""
SumoIntegration — SUMO 文件 I/O + 自迭代闭环
从 ProcessStageAgent 中拆分出来，独立职责。
复用现有 SumoInterface 和 SumoValidator。
"""
import os
import json
import yaml
from datetime import datetime
from typing import Dict, Any, Optional
from .sumo_interface import SumoInterface
from .sumo_validator import SumoValidator


class SumoIntegration:
    """SUMO 交互层 — 文件导出、结果导入、自迭代"""

    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "config", "process_stage_params.yaml"
            )
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        ps_cfg = cfg.get("process_stage", {})
        self.interface = SumoInterface(ps_cfg.get("sumo", {}))
        self.validator = SumoValidator(ps_cfg)
        self._iteration_log: list = []

    # ═══════════════════════════════════════════════════════════
    # 导出
    # ═══════════════════════════════════════════════════════════

    def export_input(
        self,
        influent: Dict[str, Any],
        anaerobic_params: Dict[str, Any],
        anoxic_params: Dict[str, Any],
        aerobic_params: Dict[str, Any],
    ) -> str:
        """导出三段参数为 SUMO XML 输入文件"""
        return self.interface.export_input_file(
            influent=influent,
            anaerobic_params=anaerobic_params,
            anoxic_params=anoxic_params,
            aerobic_params=aerobic_params,
        )

    # ═══════════════════════════════════════════════════════════
    # 导入 + 对比
    # ═══════════════════════════════════════════════════════════

    def import_and_compare(
        self, sumo_output_path: str, predicted: Dict[str, Any]
    ) -> Dict[str, Any]:
        """解析 SUMO 输出并与预测对比"""
        sumo_result = self.interface.parse_output_file(sumo_output_path)
        if "error" in sumo_result:
            return {"error": sumo_result["error"]}
        return self.interface.compare_and_feedback(predicted, sumo_result)

    # ═══════════════════════════════════════════════════════════
    # 验证 Agent 建议
    # ═══════════════════════════════════════════════════════════

    def validate_suggestions(
        self,
        suggestions: Dict[str, Any],
        inlet_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """用 SUMO Gujer 矩阵验证 LLM 建议，返回预测 + 偏差"""
        return self.validator.validate_full_process(
            suggestions=suggestions,
            inlet_state=inlet_state,
        )

    # ═══════════════════════════════════════════════════════════
    # 自迭代
    # ═══════════════════════════════════════════════════════════

    def iterate(
        self,
        sumo_output_path: str,
        current_params: Dict[str, Any],
        predicted: Dict[str, Any],
        iteration: int = 0,
    ) -> Dict[str, Any]:
        """执行一轮自迭代：对比 → 判定 → 修正/收敛"""
        comparison = self.import_and_compare(sumo_output_path, predicted)
        if "error" in comparison:
            return {"error": comparison["error"], "iteration": iteration}

        # 收敛
        if comparison.get("converged", False):
            result = {
                "iteration": iteration,
                "status": "converged",
                "message": f"第{iteration}轮收敛",
                "comparison": comparison,
                "locked_params": current_params,
            }
            self._log(iteration, result, final=True)
            return result

        # 达上限
        if iteration >= self.interface.max_iterations:
            result = {
                "iteration": iteration,
                "status": "max_iterations",
                "comparison": comparison,
                "locked_params": current_params,
            }
            self._log(iteration, result, final=True)
            return result

        # 修正
        adjusted = self.interface.generate_iteration_params(current_params, comparison, iteration)
        result = {
            "iteration": iteration,
            "status": "iterating",
            "adjusted_params": adjusted,
            "should_continue": adjusted.get("should_continue", True),
            "comparison": comparison,
        }
        self._log(iteration, result, final=False)
        return result

    def _log(self, iteration: int, result: Dict, final: bool) -> None:
        entry = {
            "iteration": iteration,
            "timestamp": datetime.utcnow().isoformat(),
            "status": result.get("status", ""),
            "final": final,
        }
        if "comparison" in result:
            entry["max_deviation_pct"] = result["comparison"].get("max_deviation_pct")
        if final and "locked_params" in result:
            entry["locked_params"] = result["locked_params"]
        self._iteration_log.append(entry)

    def get_iteration_log(self) -> list:
        return self._iteration_log
