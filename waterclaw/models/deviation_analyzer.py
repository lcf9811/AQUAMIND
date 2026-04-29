"""
DeviationAnalyzer — Agent 建议 vs Calculator 参考值偏差分析
偏差小 → Agent 可信，偏差大 → 标记人工审核。
不参与决策，仅提供分析报告供 Agent 参考。
"""
from typing import Dict, Any, List


class DeviationAnalyzer:
    """对比 Agent 推理建议 vs Calculator 机理参考值"""

    # 偏差阈值 (%)
    WITHIN_RANGE = 15.0     # <15%: 一致
    MARGINAL = 30.0         # 15-30%: 边际偏差
                            # >30%: 显著偏离

    # 各段可对比的参数列表 (Agent字段 → Calculator字段)
    COMPARABLE_PARAMS = {
        "anaerobic": [
            ("carbon_dose_mg_l", "carbon_dose_mg_l"),
            ("mixing_power_w_m3", "mixing_power_w_m3"),
            ("return_ratio_pct", "return_ratio_pct"),
        ],
        "anoxic": [
            ("carbon_dose_mg_l", "carbon_dose_mg_l"),
            ("mixing_power_w_m3", "mixing_power_w_m3"),
            ("recirculation_ratio", "recirculation_ratio"),
        ],
        "aerobic": [
            ("do_target_mg_l", "do_target_mg_l"),
            ("fan_hz", "fan_hz"),
            ("pac_dose_mg_l", "pac_dose_mg_l"),
            ("recirculation_ratio", "recirculation_ratio"),
        ],
    }

    def analyze(
        self,
        agent_suggestions: Dict[str, Any],
        calculator_references: Dict[str, Any],
        flow_stages: list = None,
    ) -> Dict[str, Any]:
        """
        Args:
            agent_suggestions: LLM 推理参数 (key=stage_id)
            calculator_references: Calculator 参考值 (key=stage_id)
            flow_stages: [{"type": "anaerobic", "id": "anaerobic"}, ...]
                        如果为 None，回退到 COMPARABLE_PARAMS 的 key 遍历

        Returns:
            偏差分析报告
        """
        deviations = {}
        explanations: List[str] = []
        significant_count = 0
        marginal_count = 0

        # 确定迭代的 stage 列表
        if flow_stages:
            stages_iter = [(s["type"], s["id"]) for s in flow_stages]
        else:
            stages_iter = [(k, k) for k in self.COMPARABLE_PARAMS.keys()]

        for stage_type, stage_id in stages_iter:
            param_pairs = self.COMPARABLE_PARAMS.get(stage_type, [])
            agent_params = agent_suggestions.get(stage_id, {})
            calc_refs = calculator_references.get(stage_id, {})
            stage_deviations = {}

            for agent_key, calc_key in param_pairs:
                agent_val = agent_params.get(agent_key)
                calc_val = calc_refs.get(calc_key)

                if agent_val is None or calc_val is None:
                    continue
                if calc_val == 0:
                    continue

                dev_pct = abs(agent_val - calc_val) / abs(calc_val) * 100
                stage_deviations[agent_key] = {
                    "agent": round(agent_val, 2),
                    "calculator": round(calc_val, 2),
                    "deviation_pct": round(dev_pct, 1),
                }

                label = f"[{stage_id}]"
                if dev_pct > self.MARGINAL:
                    significant_count += 1
                    explanations.append(
                        f"{label} {agent_key}: Agent={agent_val:.2f} vs "
                        f"Calculator={calc_val:.2f} ({dev_pct:.1f}% — 显著偏离)"
                    )
                elif dev_pct > self.WITHIN_RANGE:
                    marginal_count += 1
                    explanations.append(
                        f"{label} {agent_key}: Agent={agent_val:.2f} vs "
                        f"Calculator={calc_val:.2f} ({dev_pct:.1f}% — 边际偏差)"
                    )

            if stage_deviations:
                deviations[stage_id] = stage_deviations

        # 整体判定
        if significant_count == 0 and marginal_count == 0:
            verdict = "within_range"
            confidence_adjustment = "+1 (Agent 与机理一致)"
        elif significant_count == 0:
            verdict = "marginal"
            confidence_adjustment = "0 (边际偏差，可接受)"
        elif significant_count <= 2:
            verdict = "significant"
            confidence_adjustment = "-1 (建议 SUMO 验证)"
        else:
            verdict = "divergent"
            confidence_adjustment = "-2 (需人工审核)"

        return {
            "verdict": verdict,
            "deviations": deviations,
            "significant_count": significant_count,
            "marginal_count": marginal_count,
            "confidence_adjustment": confidence_adjustment,
            "explanations": explanations,
            "recommendation": self._recommend(verdict),
        }

    def _recommend(self, verdict: str) -> str:
        if verdict == "within_range":
            return "Agent 推理与机理计算一致，可直接采用"
        elif verdict == "marginal":
            return "存在边际偏差，建议记录偏差原因供后续迭代参考"
        elif verdict == "significant":
            return "存在显著偏差，建议 SUMO 离线验证后再执行"
        else:
            return "严重偏离机理，必须人工审核，不可自动执行"
