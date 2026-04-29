"""
StageCalculator — 纯机理计算参考基准
独立于 Agent，不参与决策。Agent 推理出的策略与 Calculator 的参考值对比，
偏差在合理范围内则采用 Agent 建议，偏差大则标记审核。
"""
import yaml
import os
from typing import Dict, Any
from .anaerobic_model import AnaerobicModel
from .anoxic_model import AnoxicModel
from .aerobic_model import AerobicModel


class StageCalculator:
    """三段机理计算统一入口—Agent 的参考基准"""

    def __init__(self, config: Dict[str, Any] = None):
        config = config or {}
        self.anaerobic = AnaerobicModel(config.get("anaerobic", {}))
        self.anoxic = AnoxicModel(config.get("anoxic", {}))
        self.aerobic = AerobicModel(config.get("aerobic", {}))

    @classmethod
    def from_yaml(cls, config_path: str = None) -> "StageCalculator":
        if config_path is None:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "config", "process_stage_params.yaml"
            )
        cfg = {}
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f)
        return cls(cfg.get("process_stage", {}))

    # ═══════════════════════════════════════════════════════════
    # 厌氧段参考值
    # ═══════════════════════════════════════════════════════════

    def calc_anaerobic_reference(self, status: Dict[str, Any]) -> Dict[str, Any]:
        """基于工况计算厌氧段理论最优参数"""
        reactor = status.get("reactor_state", {})
        wq = status.get("current_water_quality", {})

        dosing = self.anaerobic.optimize_dosing(
            cod_in=wq.get("cod_in_mg_l", 300),
            bod_in=wq.get("bod_in_mg_l", 150),
            tn_in=wq.get("tn_in_mg_l", 35),
            tp_in=wq.get("tp_in_mg_l", 5),
            vfa_in=wq.get("vfa_in_mg_l", 20),
            flow_m3_h=reactor.get("flow_m3_h", 500),
            temp_c=reactor.get("temp_c", 20),
            volume_m3=reactor.get("volume_m3", 800),
        )
        mixing = self.anaerobic.optimize_mixing(
            volume_m3=reactor.get("volume_m3", 800),
            do_actual=reactor.get("do_mg_l", 0.1),
            orp_actual=reactor.get("orp_mv", -180),
            mixer_power_kw=status.get("mixer_state", {}).get("power_kw", 3.0),
            mixer_count=status.get("mixer_state", {}).get("count", 2),
            temp_c=reactor.get("temp_c", 20),
        )
        recirc = self.anaerobic.optimize_recirculation(
            mlss=reactor.get("mlss_mg_l", 3500),
            rass=reactor.get("rass_mg_l", 8000),
            flow_m3_h=reactor.get("flow_m3_h", 500),
            tn_in=wq.get("tn_in_mg_l", 35),
            tn_target=wq.get("tn_target_mg_l", 15),
            volume_m3=reactor.get("volume_m3", 800),
            current_return_ratio_pct=reactor.get("return_ratio_pct", 75),
        )
        return {
            "stage": "anaerobic",
            "carbon_dose_mg_l": dosing.get("dose_mg_l"),
            "mixing_power_w_m3": mixing.get("recommended_power_density_w_m3"),
            "return_ratio_pct": recirc.get("return_ratio_recommended_pct"),
            "source": "mechanism_calculation",
        }

    # ═══════════════════════════════════════════════════════════
    # 缺氧段参考值
    # ═══════════════════════════════════════════════════════════

    def calc_anoxic_reference(self, status: Dict[str, Any]) -> Dict[str, Any]:
        reactor = status.get("reactor_state", {})
        wq = status.get("current_water_quality", {})

        dosing = self.anoxic.optimize_dosing(
            no3_in=wq.get("no3_in_mg_l", 15),
            no3_target=wq.get("no3_target_mg_l", 3),
            bod_in=wq.get("bod_in_mg_l", 100),
            flow_m3_h=reactor.get("flow_m3_h", 500),
            mlvss=reactor.get("mlvss_mg_l", 2600),
            volume_m3=reactor.get("volume_m3", 1500),
            temp_c=reactor.get("temp_c", 20),
        )
        mixing = self.anoxic.optimize_mixing(
            volume_m3=reactor.get("volume_m3", 1500),
            do_actual=reactor.get("do_mg_l", 0.3),
            orp_actual=reactor.get("orp_mv", -30),
            mixer_power_kw=status.get("mixer_state", {}).get("power_kw", 5.5),
            mixer_count=status.get("mixer_state", {}).get("count", 2),
        )
        recirc = self.anoxic.optimize_recirculation(
            tn_in=wq.get("tn_in_mg_l", 35),
            tn_target=wq.get("tn_target_mg_l", 15),
            no3_aerobic_out=wq.get("no3_aerobic_out_mg_l", 12),
            flow_m3_h=reactor.get("flow_m3_h", 500),
            volume_m3=reactor.get("volume_m3", 1500),
            current_recirc_ratio=reactor.get("recirculation_ratio", 3.0),
        )
        return {
            "stage": "anoxic",
            "carbon_dose_mg_l": dosing.get("dose_mg_l"),
            "mixing_power_w_m3": mixing.get("recommended_power_density_w_m3"),
            "recirculation_ratio": recirc.get("recirculation_ratio_recommended"),
            "source": "mechanism_calculation",
        }

    # ═══════════════════════════════════════════════════════════
    # 好氧段参考值
    # ═══════════════════════════════════════════════════════════

    def calc_aerobic_reference(self, status: Dict[str, Any]) -> Dict[str, Any]:
        reactor = status.get("reactor_state", {})
        wq = status.get("current_water_quality", {})
        blower = status.get("aeration_state", {})

        aeration = self.aerobic.optimize_aeration(
            do_actual=reactor.get("do_mg_l", 2.0),
            mlss=reactor.get("mlss_mg_l", 3500),
            mlvss=reactor.get("mlvss_mg_l", 2600),
            temp_c=reactor.get("temp_c", 20),
            cod_in=wq.get("cod_in_mg_l", 80),
            cod_out=wq.get("cod_out_mg_l", 30) if "cod_out_mg_l" in wq else 30,
            nh3_in=wq.get("nh3_n_in_mg_l", 20),
            nh3_out=wq.get("nh3_n_target_mg_l", 3),
            no3_out=wq.get("no3_n_in_mg_l", 0.5),
            flow_m3_h=reactor.get("flow_m3_h", 500),
            hrt_h=reactor.get("volume_m3", 3000) / max(1, reactor.get("flow_m3_h", 500)),
            current_fan_hz=blower.get("frequency_hz", 40) if blower else 40,
            volume_m3=reactor.get("volume_m3", 3000),
        )
        dosing = self.aerobic.optimize_dosing(
            tp_in=wq.get("tp_in_mg_l", 4),
            tp_target=wq.get("tp_target_mg_l", 0.5),
            tp_bio_removal_est=wq.get("tp_bio_removal_mg_l", 2.5) if "tp_bio_removal_mg_l" in wq else 2.5,
            flow_m3_h=reactor.get("flow_m3_h", 500),
            temp_c=reactor.get("temp_c", 20),
        )
        recirc = self.aerobic.optimize_recirculation(
            tn_in=wq.get("tn_in_mg_l", 35) if "tn_in_mg_l" in wq else 35,
            tn_target=wq.get("tn_target_mg_l", 15) if "tn_target_mg_l" in wq else 15,
            no3_out=wq.get("no3_n_in_mg_l", 10),
            flow_m3_h=reactor.get("flow_m3_h", 500),
            volume_m3=reactor.get("volume_m3", 3000),
            current_recirc_ratio=reactor.get("recirculation_ratio", 3.0),
        )
        return {
            "stage": "aerobic",
            "do_target_mg_l": aeration.get("target_do_mg_l"),
            "fan_hz": aeration.get("recommended_fan_hz"),
            "our_total_kgO2_d": aeration.get("our_breakdown", {}).get("our_total_kgO2_d"),
            "pac_dose_mg_l": dosing.get("dose_mg_l"),
            "recirculation_ratio": recirc.get("recirculation_ratio_recommended"),
            "source": "mechanism_calculation",
        }

    # ═══════════════════════════════════════════════════════════
    # 全段参考值 (兼容旧接口)
    # ═══════════════════════════════════════════════════════════

    def calculate_all_references(self, full_status: Dict[str, Any]) -> Dict[str, Any]:
        stages = full_status.get("stages", {})
        return {
            "anaerobic": self.calc_anaerobic_reference(stages.get("anaerobic", {})),
            "anoxic": self.calc_anoxic_reference(stages.get("anoxic", {})),
            "aerobic": self.calc_aerobic_reference(stages.get("aerobic", {})),
        }

    # ═══════════════════════════════════════════════════════════
    # 链式计算 (支持任意 flow_sequence)
    # ═══════════════════════════════════════════════════════════

    CALC_MAP = {
        "anaerobic": "calc_anaerobic_reference",
        "anoxic": "calc_anoxic_reference",
        "aerobic": "calc_aerobic_reference",
    }

    def calculate_chain_references(
        self, stages_info: list, stages_status: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        按 flow_sequence 链式计算：前段出水水质 → 后段进水水质。

        Args:
            stages_info: [{"type": "anaerobic", "id": "anaerobic", "agent": ...}, ...]
            stages_status: { "anaerobic": {...}, "anoxic_1": {...}, ... }

        Returns:
            { "anaerobic": {...}, "anoxic": {...}, "aerobic": {...}, "anoxic_2": {...} }
        """
        refs = {}
        prev_effluent = None

        for si in stages_info:
            stage_type = si["type"]
            stage_id = si["id"]
            status = stages_status.get(stage_id, {})

            # 前段出水水质 → 当前段进水
            if prev_effluent:
                status = self._merge_inlet(status, prev_effluent, stage_type)

            calc_method = getattr(self, self.CALC_MAP[stage_type])
            refs[stage_id] = calc_method(status)

            # 记录本段出水预测供下一段使用
            prev_effluent = refs[stage_id]

        return refs

    @staticmethod
    def _merge_inlet(
        status: Dict[str, Any], prev_ref: Dict[str, Any], target_type: str
    ) -> Dict[str, Any]:
        """将前段出水注入当前段进水水质"""
        status = dict(status)  # shallow copy
        wq = dict(status.get("current_water_quality", {}))
        prev_stage = prev_ref.get("stage", "")

        # 厌氧段出水特征: PO4 升高 (释磷), VFA 变化
        if "anaerobic" in prev_stage:
            wq.setdefault("vfa_in_mg_l", 20)
            wq.setdefault("tp_in_mg_l", wq.get("tp_in_mg_l", 5) * 1.1)

        # 好氧段出水特征: NH3 大幅降低, NO3 升高
        if "aerobic" in prev_stage:
            eff = prev_ref.get("effluent_prediction", {})
            # 不直接覆盖，因为每个段有独立的 water_quality 字段名体系
            # 这里做尽力而为的合并
            if "nh3_n_out_mg_l" in eff:
                wq.setdefault("nh3_n_in_mg_l", eff["nh3_n_out_mg_l"])
            if "no3_n_out_mg_l" in eff:
                wq.setdefault("no3_n_in_mg_l", eff["no3_n_out_mg_l"])

        status["current_water_quality"] = wq
        return status
