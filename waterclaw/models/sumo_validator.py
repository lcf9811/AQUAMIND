"""
SUMO Gujer 矩阵验证器 —— 纯机理计算，不参与 Agent 推理

职责定位：
  - 接收 Agent（OpenCLAW LLM）给出的调控建议参数
  - 运行 SUMO Gujer 矩阵生化模拟
  - 返回预测出水水质 + 与目标值的偏差报告
  - 供 OpenCLAW Master 判断是否达标、是否需要反馈给 Agent 修正

架构位置：
  Agent(LLM推理) → 调控建议 → SumoValidator(本模块) → 预测+偏差 → OpenCLAW反馈

本模块复用现有三个 model 的 simulate_biochemistry() 方法，
不重复实现 Gujer 矩阵，而是作为统一调用入口和偏差分析层。

工艺流程：AAOA（厌氧A1 → 缺氧A2 → 好氧O → 后缺氧A3），四段串联验证。
后缺氧段(A3)复用缺氧模型，利用好氧出水中残余碳源和内源碳进行二次反硝化。
"""

from typing import Dict, Any, Optional
from .anaerobic_model import AnaerobicModel
from .anoxic_model import AnoxicModel
from .aerobic_model import AerobicModel


# ─── 出水水质目标 (GB 18918-2002 一级A标准) ───
DEFAULT_EFFLUENT_TARGETS = {
    "nh3_n_mg_l": 3.0,       # NH3-N ≤ 5 (一级A), 部分地区 ≤ 3
    "no3_n_mg_l": 10.0,      # TN ≤ 15, NO3-N 作为 TN 主要组分
    "tn_mg_l": 15.0,         # TN ≤ 15
    "tp_mg_l": 0.5,          # TP ≤ 0.5
    "cod_mg_l": 50.0,        # COD ≤ 50
}


class SumoValidator:
    """
    SUMO Gujer 矩阵验证器

    对外暴露三个层级的验证方法：
      1. validate_anaerobic / validate_anoxic / validate_aerobic — 单段验证
      2. validate_full_process — 全流程串联验证
      3. generate_deviation_report — 偏差分析报告（供 OpenCLAW 反馈）

    所有方法接受 Agent 建议参数 + 当前工况，返回 SUMO 预测 + 偏差。
    """

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}

        # 构建四段模型实例（使用 YAML 配置或默认参数）
        # AAOA: 厌氧(A1) → 缺氧(A2) → 好氧(O) → 后缺氧(A3)
        self.anaerobic_model = AnaerobicModel(config.get("anaerobic", {}))
        self.anoxic_model = AnoxicModel(config.get("anoxic", {}))
        self.aerobic_model = AerobicModel(config.get("aerobic", {}))
        self.post_anoxic_model = AnoxicModel(config.get("post_anoxic", config.get("anoxic", {})))

        # 出水目标
        self.targets = config.get("effluent_targets", DEFAULT_EFFLUENT_TARGETS)

    # ═══════════════════════════════════════════════════════════
    #  单段验证
    # ═══════════════════════════════════════════════════════════

    def validate_anaerobic(
        self,
        suggestion: Dict[str, Any],
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        用 Agent 的厌氧段建议跑 SUMO，返回预测出水 + 偏差

        Args:
            suggestion: Agent 建议的参数，如 {"carbon_dose_mg_l": 30, "mixing_w_m3": 5, ...}
            current_state: 当前工况，如 {"S_VFA": 60, "S_B": 120, "S_NHx": 25, "S_NOx": 1.5, ...}
        """
        # 从 current_state 提取模拟输入（Agent 建议的操作参数影响环境条件）
        sim_input = {
            "S_VFA": current_state.get("S_VFA", 60.0),
            "S_B": current_state.get("S_B", 120.0),
            "S_NHx": current_state.get("nh3_n_in", current_state.get("S_NHx", 25.0)),
            "S_NOx": current_state.get("no3_n_in", current_state.get("S_NOx", 1.5)),
            "S_PO4": current_state.get("S_PO4", 5.0),
            "S_O2": suggestion.get("do_setpoint", current_state.get("do_mg_l", 0.1)),
            "ORP": current_state.get("orp_mv", -180),
            "temp_c": current_state.get("temp_c", 20.0),
            "hrt_h": current_state.get("hrt_h", 1.5),
            "volume_m3": current_state.get("volume_m3", 2000.0),
        }

        result = self.anaerobic_model.simulate_biochemistry(**sim_input)
        eff = result.get("effluent_prediction", {})

        return {
            "stage": "anaerobic",
            "sumo_prediction": eff,
            "agent_suggestion": suggestion,
            "reaction_rates": result.get("reaction_rates", {}),
        }

    def validate_anoxic(
        self,
        suggestion: Dict[str, Any],
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """用 Agent 的缺氧段建议跑 SUMO"""
        sim_input = {
            "S_VFA": current_state.get("S_VFA", 30.0),
            "S_B": current_state.get("S_B", 80.0),
            "S_NHx": current_state.get("nh3_n", current_state.get("S_NHx", 24.0)),
            "S_NOx": current_state.get("no3_n", current_state.get("S_NOx", 16.5)),
            "S_O2": suggestion.get("do_setpoint", current_state.get("do_mg_l", 0.2)),
            "temp_c": current_state.get("temp_c", 20.0),
            "hrt_h": current_state.get("hrt_h", 3.0),
            "volume_m3": current_state.get("volume_m3", 4000.0),
        }

        # 外加碳源转换为甲醇当量
        external_carbon = suggestion.get("carbon_dose_mg_l", 0)
        if external_carbon > 0:
            sim_input["S_MEOL"] = external_carbon * 0.78  # 醋酸钠→COD

        result = self.anoxic_model.simulate_biochemistry(**sim_input)
        eff = result.get("effluent_prediction", {})
        denitrif = result.get("denitrification_detail", {})

        return {
            "stage": "anoxic",
            "sumo_prediction": eff,
            "denitrification_detail": denitrif,
            "agent_suggestion": suggestion,
        }

    def validate_aerobic(
        self,
        suggestion: Dict[str, Any],
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """用 Agent 的好氧段建议跑 SUMO"""
        do_setpoint = suggestion.get("do_setpoint", 2.0)
        sim_input = {
            "S_VFA": current_state.get("S_VFA", 10.0),
            "S_B": current_state.get("S_B", 30.0),
            "S_NHx": current_state.get("nh3_n", current_state.get("S_NHx", 21.0)),
            "S_NOx": current_state.get("no3_n", current_state.get("S_NOx", 0.0)),
            "S_O2": do_setpoint,
            "temp_c": current_state.get("temp_c", 20.0),
            "hrt_h": current_state.get("hrt_h", 6.0),
            "volume_m3": current_state.get("volume_m3", 8000.0),
        }

        result = self.aerobic_model.simulate_biochemistry(**sim_input)
        eff = result.get("effluent_prediction", {})
        nitrif = result.get("nitrification_detail", {})
        our = result.get("our_breakdown", {})

        return {
            "stage": "aerobic",
            "sumo_prediction": eff,
            "nitrification_detail": nitrif,
            "our_breakdown": our,
            "agent_suggestion": suggestion,
        }

    def validate_post_anoxic(
        self,
        suggestion: Dict[str, Any],
        current_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        后缺氧段(A3)验证 —— 复用缺氧模型，利用内源碳进行二次反硝化

        与前缺氧段的主要区别：
          - 进水NO3来自好氧出水（浓度高，是主要去除对象）
          - 可生化碳源极少（好氧段已基本耗尽），主要依赖内源反硝化
          - HRT较短（1~2h），DO需严格控制（<0.3 mg/L）
        """
        sim_input = {
            "S_VFA": current_state.get("S_VFA", 2.0),       # 好氧出水VFA极低
            "S_B": current_state.get("S_B", 5.0),           # 好氧出水BOD极低
            "S_NHx": current_state.get("nh3_n", current_state.get("S_NHx", 0.5)),
            "S_NOx": current_state.get("no3_n", current_state.get("S_NOx", 15.0)),
            "S_O2": suggestion.get("do_setpoint", current_state.get("do_mg_l", 0.15)),
            "X_B": current_state.get("X_B", 250.0),        # 混合液中慢速降解基质（内源反硝化碳源）
            "temp_c": current_state.get("temp_c", 20.0),
            "hrt_h": current_state.get("hrt_h", 1.5),
            "volume_m3": current_state.get("volume_m3", 2000.0),
        }

        # 后缺氧段外加碳源（可选，通常不投加或少量投加）
        external_carbon = suggestion.get("carbon_dose_mg_l", 0)
        if external_carbon > 0:
            sim_input["S_MEOL"] = external_carbon * 0.78

        result = self.post_anoxic_model.simulate_biochemistry(**sim_input)
        eff = result.get("effluent_prediction", {})
        denitrif = result.get("denitrification_detail", {})

        return {
            "stage": "post_anoxic",
            "sumo_prediction": eff,
            "denitrification_detail": denitrif,
            "agent_suggestion": suggestion,
        }

    # ═══════════════════════════════════════════════════════════
    #  全流程串联验证（AAOA 四段）
    # ═══════════════════════════════════════════════════════════

    def validate_full_process(
        self,
        suggestions: Dict[str, Dict[str, Any]],
        inlet_state: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        全流程 AAOA（厌氧→缺氧→好氧→后缺氧）四段串联验证

        Args:
            suggestions: {
                "anaerobic": {"carbon_dose_mg_l": 30, ...},
                "anoxic": {"carbon_dose_mg_l": 0, "recirculation_ratio": 3.0, ...},
                "aerobic": {"do_setpoint": 2.0, "fan_hz": 35, ...},
                "post_anoxic": {"do_setpoint": 0.15, "carbon_dose_mg_l": 0, ...},  # 可选
            }
            inlet_state: 进水工况 {"nh3_n_in": 25, "no3_n_in": 1.5, "S_VFA": 60, ...}

        Returns:
            各段预测 + 最终出水 + 达标判定 + 偏差报告
        """
        ana_sug = suggestions.get("anaerobic", {})
        anox_sug = suggestions.get("anoxic", {})
        aer_sug = suggestions.get("aerobic", {})
        post_anox_sug = suggestions.get("post_anoxic", {})

        # ─── 1) 厌氧段 ───
        ana_state = dict(inlet_state)
        ana_result = self.validate_anaerobic(ana_sug, ana_state)
        ana_eff = ana_result["sumo_prediction"]

        # ─── 2) 缺氧段（接收厌氧出水 + 内回流 NO3）───
        recirc_ratio = anox_sug.get("recirculation_ratio", 3.0)
        # 内回流带入的 NO3 需要后续好氧段出水值，先估算
        # 简化：内回流 NO3 ≈ 进水 TN 的一部分
        estimated_aerobic_no3 = inlet_state.get("nh3_n_in", 25.0) * 0.7
        no3_with_recirc = ana_eff.get("no3_n_out_mg_l", 1.5) + estimated_aerobic_no3 * recirc_ratio / (1 + recirc_ratio)

        anox_state = {
            "S_VFA": ana_eff.get("S_VFA_out_mgCOD_L", 30.0),
            "S_B": ana_eff.get("S_B_out_mgCOD_L", 80.0),
            "nh3_n": ana_eff.get("nh3_n_out_mg_l", 24.0),
            "no3_n": no3_with_recirc,
            "do_mg_l": 0.2,
            "temp_c": inlet_state.get("temp_c", 20.0),
            "hrt_h": inlet_state.get("anoxic_hrt_h", 3.0),
            "volume_m3": inlet_state.get("anoxic_volume_m3", 4000.0),
        }
        anox_result = self.validate_anoxic(anox_sug, anox_state)
        anox_eff = anox_result["sumo_prediction"]

        # ─── 3) 好氧段 ───
        aer_state = {
            "S_VFA": anox_eff.get("S_VFA_out_mgCOD_L", 10.0),
            "S_B": anox_eff.get("S_B_out_mgCOD_L", 30.0),
            "nh3_n": anox_eff.get("nh3_n_out_mg_l", 21.0),
            "no3_n": anox_eff.get("no3_n_out_mg_l", 0.0),
            "temp_c": inlet_state.get("temp_c", 20.0),
            "hrt_h": inlet_state.get("aerobic_hrt_h", 6.0),
            "volume_m3": inlet_state.get("aerobic_volume_m3", 8000.0),
        }
        aer_result = self.validate_aerobic(aer_sug, aer_state)
        aer_eff = aer_result["sumo_prediction"]

        # ─── 4) 后缺氧段 A3（接收好氧出水，二次反硝化）───
        post_anox_state = {
            "S_VFA": aer_eff.get("S_VFA_out_mgCOD_L", 2.0),
            "S_B": aer_eff.get("S_B_out_mgCOD_L", 5.0),
            "nh3_n": aer_eff.get("nh3_n_out_mg_l", 0.5),
            "no3_n": aer_eff.get("no3_n_out_mg_l", 15.0),
            "do_mg_l": 0.15,
            "temp_c": inlet_state.get("temp_c", 20.0),
            "hrt_h": inlet_state.get("post_anoxic_hrt_h", 1.5),
            "volume_m3": inlet_state.get("post_anoxic_volume_m3", 2000.0),
            # 混合液中的慢速降解基质 X_B：
            # 活性污泥中含有大量额粒态有机物（来自细胞衰减、未水解进水颗粒），
            # 典型 MLSS 3000-5000 mg/L 时 X_B 约 200-400 mgCOD/L。
            # 这是内源反硝化的关键碳源：衰减→X_B→水解→SB→反硝化
            "X_B": inlet_state.get("post_anoxic_X_B", 250.0),
        }
        post_anox_result = self.validate_post_anoxic(post_anox_sug, post_anox_state)
        post_anox_eff = post_anox_result["sumo_prediction"]

        # ─── 5) 达标判定 + 偏差报告（以后缺氧出水为最终出水）───
        final_nh3 = post_anox_eff.get("nh3_n_out_mg_l", aer_eff.get("nh3_n_out_mg_l", 0))
        final_no3 = post_anox_eff.get("no3_n_out_mg_l", aer_eff.get("no3_n_out_mg_l", 0))

        deviation = self._calculate_deviation(post_anox_eff)

        compliant = all(d["within_target"] for d in deviation.values())

        return {
            "compliant": compliant,
            "final_effluent": {
                "nh3_n_mg_l": final_nh3,
                "no3_n_mg_l": final_no3,
            },
            "stage_predictions": {
                "anaerobic": ana_eff,
                "anoxic": anox_eff,
                "aerobic": aer_eff,
                "post_anoxic": post_anox_eff,
            },
            "deviation_report": deviation,
            "process_details": {
                "anaerobic": {
                    "reaction_rates": ana_result.get("reaction_rates", {}),
                },
                "anoxic": {
                    "denitrification": anox_result.get("denitrification_detail", {}),
                },
                "aerobic": {
                    "nitrification": aer_result.get("nitrification_detail", {}),
                    "our_breakdown": aer_result.get("our_breakdown", {}),
                },
                "post_anoxic": {
                    "denitrification": post_anox_result.get("denitrification_detail", {}),
                },
            },
            "suggestions_used": suggestions,
        }

    # ═══════════════════════════════════════════════════════════
    #  偏差分析
    # ═══════════════════════════════════════════════════════════

    def _calculate_deviation(self, effluent_prediction: Dict) -> Dict[str, Any]:
        """计算预测出水与目标值的偏差"""
        result = {}

        # NH3-N
        nh3_pred = effluent_prediction.get("nh3_n_out_mg_l", 0)
        nh3_target = self.targets.get("nh3_n_mg_l", 3.0)
        result["nh3_n"] = {
            "predicted": round(nh3_pred, 2),
            "target": nh3_target,
            "deviation": round(nh3_pred - nh3_target, 2),
            "deviation_pct": round((nh3_pred - nh3_target) / nh3_target * 100, 1) if nh3_target > 0 else 0,
            "within_target": nh3_pred <= nh3_target,
        }

        # NO3-N
        no3_pred = effluent_prediction.get("no3_n_out_mg_l", 0)
        no3_target = self.targets.get("no3_n_mg_l", 10.0)
        result["no3_n"] = {
            "predicted": round(no3_pred, 2),
            "target": no3_target,
            "deviation": round(no3_pred - no3_target, 2),
            "deviation_pct": round((no3_pred - no3_target) / no3_target * 100, 1) if no3_target > 0 else 0,
            "within_target": no3_pred <= no3_target,
        }

        return result

    def generate_feedback_prompt(self, validation_result: Dict) -> str:
        """
        将验证结果转为自然语言反馈，供 OpenCLAW LLM 二次推理

        这个反馈会被注入到 OpenCLAW 的下一轮 prompt 中，
        让 LLM 看到 SUMO 验证结果后调整建议。
        """
        dev = validation_result.get("deviation_report", {})
        eff = validation_result.get("final_effluent", {})
        compliant = validation_result.get("compliant", False)

        lines = ["[SUMO机理验证结果]"]

        if compliant:
            lines.append(f"出水达标: NH3-N={eff.get('nh3_n_mg_l', 0):.2f}mg/L, "
                         f"NO3-N={eff.get('no3_n_mg_l', 0):.2f}mg/L")
            lines.append("当前建议参数通过SUMO验证，无需调整。")
        else:
            lines.append("出水未达标，需要调整建议参数:")
            for param, d in dev.items():
                if not d["within_target"]:
                    direction = "偏高" if d["deviation"] > 0 else "偏低"
                    lines.append(
                        f"  - {param}: 预测={d['predicted']}mg/L, "
                        f"目标<={d['target']}mg/L, {direction}{abs(d['deviation']):.2f}mg/L "
                        f"({d['deviation_pct']:+.1f}%)"
                    )

            # 给出调整方向提示
            nh3_dev = dev.get("nh3_n", {})
            no3_dev = dev.get("no3_n", {})
            if not nh3_dev.get("within_target", True):
                lines.append("调整建议: 提高好氧段DO设定值或延长HRT以增强硝化")
            if not no3_dev.get("within_target", True):
                lines.append("调整建议: 提高内回流比、增加缺氧段碳源投加以增强反硝化，或在后缺氧段(A3)增加少量外加碳源")

        return "\n".join(lines)
