"""
EquipmentMapper — Agent 概念参数 → SUMO 变量 / 设备地址 / PLC 寄存器
桥接"工艺概念"和"具体装备"，让 Agent 知道"动哪个设备"。
"""
from typing import Dict, Any, List, Optional


class EquipmentMapper:
    """翻译层：Agent 参数 ↔ SUMO 变量 ↔ Modbus 寄存器 ↔ 设备名称"""

    MAPPING: Dict[str, Dict[str, Any]] = {
        # ─── 好氧段 ───
        "aerobic.do_target_mg_l": {
            "sumo_var": "Sumo__Plant__CSTR3__param__DOSP",
            "modbus_addr": 96,
            "modbus_count": 2,
            "modbus_format": "float32",
            "equipment": "好氧池 DO 传感器 + 曝气风机 (CSTR3)",
            "unit": "mg/L",
            "range": [1.5, 3.0],
        },
        "aerobic.fan_hz": {
            "sumo_var": None,  # 风机频率间接影响 kLa
            "modbus_addr": None,
            "equipment": "曝气鼓风机变频器",
            "unit": "Hz",
            "range": [20, 50],
            "note": "风机频率通过氧转移效率间接影响 SUMO kLaGO2",
        },
        "aerobic.pac_dose_mg_l": {
            "sumo_var": None,  # PAC 非 SUMO 原生变量
            "modbus_addr": None,
            "equipment": "化学除磷加药泵",
            "unit": "mg/L",
            "range": [0, 50],
        },
        "aerobic.recirculation_ratio": {
            "sumo_var": None,
            "modbus_addr": None,
            "equipment": "混合液回流泵",
            "unit": "ratio (xQin)",
            "range": [2.0, 4.0],
        },

        # ─── 缺氧段 ───
        "anoxic.carbon_dose_mg_l": {
            "sumo_var": "Sumo__Plant__Carbon1__param__Q",
            "modbus_addr": 696,
            "modbus_count": 2,
            "modbus_format": "float32",
            "equipment": "碳源投加泵 (Carbon1)",
            "unit": "m3/d (SUMO) / mg/L (Agent)",
            "note": "Agent 的 mg/L 需转换为 SUMO 的 Q (m3/d): Q = dose_mgL * flow_m3h * 24 / (conc_mgL * 1e6)",
        },
        "anoxic.mixing_power_w_m3": {
            "sumo_var": None,
            "modbus_addr": None,
            "equipment": "缺氧池搅拌器",
            "unit": "W/m3",
            "range": [5, 10],
        },
        "anoxic.recirculation_ratio": {
            "sumo_var": "Sumo__Plant__Sideflowdivider__param__Qpumped_target",
            "modbus_addr": None,
            "equipment": "硝化液内回流泵 (Sideflowdivider)",
            "unit": "m3/d",
            "note": "Agent 回流比 → SUMO Qpumped: Qpumped = ratio * Q_influent",
        },

        # ─── 厌氧段 ───
        "anaerobic.carbon_dose_mg_l": {
            "sumo_var": None,
            "modbus_addr": None,
            "equipment": "厌氧池碳源投加泵",
            "unit": "mg/L",
        },
        "anaerobic.mixing_power_w_m3": {
            "sumo_var": None,
            "modbus_addr": None,
            "equipment": "厌氧池搅拌器",
            "unit": "W/m3",
            "range": [3, 8],
        },
        "anaerobic.return_ratio_pct": {
            "sumo_var": None,
            "modbus_addr": None,
            "equipment": "污泥回流泵",
            "unit": "%",
            "range": [50, 100],
        },

        # ─── 进水 (SUMO 直通) ───
        "influent.flow_m3_h": {
            "sumo_var": "Sumo__Plant__Influent__param__Q",
            "modbus_addr": None,
            "equipment": "进水流量计",
            "unit": "m3/d (SUMO) / m3/h (Agent)",
            "note": "SUMO Q = Agent flow_m3h * 24",
        },
        "influent.cod_mg_l": {
            "sumo_var": "Sumo__Plant__Influent__param__TCOD",
            "equipment": "进水 COD 在线分析仪",
            "unit": "mg/L",
        },
        "influent.tkn_mg_l": {
            "sumo_var": "Sumo__Plant__Influent__param__TKN",
            "equipment": "进水 TKN 在线分析仪",
            "unit": "mg/L",
        },
    }

    # ─── SUMO 命令生成 ─────────────────────────────────

    def to_sumo_commands(self, agent_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将 Agent 参数翻译为 SUMO set 命令列表

        Args:
            agent_params: 平铺的参数 dict, key 如 "aerobic.do_target_mg_l"

        Returns:
            [{"command": "set Sumo__...", "value": ...}, ...]
        """
        commands = []
        for param_path, value in self._flatten(agent_params).items():
            mapping = self.MAPPING.get(param_path)
            if mapping and mapping.get("sumo_var"):
                commands.append({
                    "command": f"set {mapping['sumo_var']} {value}",
                    "param": param_path,
                    "sumo_var": mapping["sumo_var"],
                    "value": value,
                    "equipment": mapping.get("equipment", ""),
                })
        return commands

    # ─── Modbus 写操作生成 ──────────────────────────────

    def to_modbus_writes(self, agent_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """将 Agent 参数翻译为 Modbus 写操作列表"""
        writes = []
        for param_path, value in self._flatten(agent_params).items():
            mapping = self.MAPPING.get(param_path)
            if mapping and mapping.get("modbus_addr") is not None:
                writes.append({
                    "address": mapping["modbus_addr"],
                    "count": mapping.get("modbus_count", 2),
                    "format": mapping.get("modbus_format", "float32"),
                    "value": value,
                    "param": param_path,
                    "equipment": mapping.get("equipment", ""),
                })
        return writes

    # ─── 设备描述 ──────────────────────────────────────

    def get_equipment_info(self, param_path: str) -> Optional[Dict[str, Any]]:
        """查询某个参数对应的设备信息"""
        return self.MAPPING.get(param_path)

    def list_equipment(self, stage: str = None) -> List[Dict[str, Any]]:
        """列出所有设备，可按工艺段筛选"""
        result = []
        for param_path, info in self.MAPPING.items():
            if stage and not param_path.startswith(stage):
                continue
            result.append({"param": param_path, **info})
        return result

    # ─── 帮助方法 ──────────────────────────────────────

    @staticmethod
    def _flatten(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """展平嵌套字典: {"aerobic": {"do": 2.5}} → {"aerobic.do": 2.5}"""
        flat = {}
        for k, v in d.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                flat.update(EquipmentMapper._flatten(v, key))
            else:
                flat[key] = v
        return flat
