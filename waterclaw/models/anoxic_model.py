"""
缺氧池机理模型 — 基于 SUMO1.xlsm Gujer 矩阵
核心反应过程 (来自 SUMO Model Sheet):
  r2  : OHO 缺氧生长 (VFA 为碳源, NOx 为电子受体)
  r4  : OHO 缺氧生长 (SB 为碳源, NOx 为电子受体)
  r8  : OHO 衰减 (好氧+缺氧)  — 缺氧部分
  r10 : MEOLO 缺氧生长 (甲醇利用菌, NOx)
  r14 : CASTO 缺氧生长 (PHA 为碳源, NOx)
  r22 : CASTO 缺氧维护 (消耗 NOx)
  r47 : XB 水解 (缺氧条件折减)
  r49 : SN,B 氨化 (有机氮→NH4)

关键化学计量 (来自 SUMO Gujer 矩阵):
  SNOx for r2: -(1-Y_OHO_VFA_anox) / (EEQ_N2_NO3 * Y_OHO_VFA_anox)
  SNOx for r4: -(1-Y_OHO_SB_anox) / (EEQ_N2_NO3 * Y_OHO_SB_anox)
  EEQ_N2_NO3 = 2.86  (电子当量: 1 gNO3-N → 2.86 gCOD 氧当量)

环境约束:
  DO < 0.5 mg/L, ORP -100~+50 mV, HRT 2~4 h
"""

import math
from typing import Dict, Any, Optional


# ─────────── SUMO 动力学参数 (默认值来自 SUMO1.xlsm Parameters Sheet) ──────
SUMO_PARAMS_ANOXIC = {
    # OHO 缺氧生长动力学
    "mu_OHO":         4.0,     # d⁻¹ OHO 最大比生长速率
    "theta_mu_OHO":   1.04,    # Arrhenius 温度系数
    "eta_OHO_anox":   0.6,     # 缺氧生长折减系数
    "Y_OHO_VFA_anox": 0.45,    # 缺氧条件 VFA 基质产率 (gCOD/gCOD)
    "Y_OHO_SB_anox":  0.54,    # 缺氧条件 SB 基质产率
    "K_VFA":          0.5,     # VFA 半饱和 (mgCOD/L)
    "K_SB":           5.0,     # SB 半饱和 (mgCOD/L)
    "K_NOx_OHO":      0.03,    # NOx 半饱和 (mgN/L) — OHO
    "K_O2_OHO":       0.15,    # O2 半饱和 (mg/L) — OHO

    # OHO 衰减
    "b_OHO":          0.62,    # d⁻¹
    "theta_b_OHO":    1.03,
    "eta_b_anox":     0.5,     # 缺氧衰减折减

    # MEOLO (甲醇利用菌) 缺氧生长
    "mu_MEOLO":       1.3,     # d⁻¹
    "theta_mu_MEOLO": 1.06,
    "Y_MEOLO":        0.4,     # 产率 (假设与好氧甲醇利用相似)
    "K_MEOL":         0.5,     # 甲醇半饱和 (mgCOD/L)
    "K_NOx_MEOLO":    0.03,
    "K_iO2_MEOLO":    0.05,    # O2 半抑制

    # CASTO 缺氧生长 + 维护
    "mu_CASTO":       1.0,     # d⁻¹
    "theta_mu_CASTO": 1.04,
    "eta_CASTO_anox": 0.66,    # 缺氧折减
    "K_PHA":          0.01,    # PHA 半饱和 (gCOD/gCOD)
    "K_O2_CASTO":     0.05,
    "K_NOx_CASTO":    0.03,
    "b_STC":          0.07,    # d⁻¹ 储碳维护速率
    "theta_b_STC":    1.064,
    "eta_b_STC_anox": 0.66,

    # 水解
    "q_HYD_XB":       3.0,     # d⁻¹ 水解速率
    "theta_q_HYD":    1.03,
    "eta_HYD_anox":   0.6,     # 缺氧水解折减
    "K_HYD":          0.03,    # XB/XHET 半饱和比

    # 氨化
    "q_AMMON":        40.0,    # L/(gCOD·d)
    "theta_q_AMMON":  1.03,

    # 公共化学计量
    "EEQ_N2_NO3":     2.86,    # 电子当量 (gCOD/gN)
    "f_E":            0.08,
    "i_N_BIO":        0.07,
    "i_N_XE":         0.06,
    "i_P_BIO":        0.02,
    "K_NHx_BIO":      0.05,
    "K_PO4_BIO":      0.01,

    # Arrhenius 基准温度
    "T_base": 20.0,

    # 典型生物量浓度 (mgCOD/L)
    "X_OHO_default":    2000.0,
    "X_CASTO_default":   500.0,
    "X_MEOLO_default":    50.0,
    "X_HET_default":    2500.0,   # 全部异养菌
}


class AnoxicModel:
    """AAO 工艺缺氧段机理计算器 — SUMO Gujer 矩阵驱动"""

    def __init__(self, params: Dict[str, Any]):
        self.cfg = params
        self.dosing_cfg = params.get("dosing", {})
        self.denitrif_cfg = params.get("denitrification", {})
        self.hrt_range = params.get("hrt_h", [2.0, 4.0])
        self.do_max = params.get("do_max_mg_l", 0.5)
        self.orp_range = params.get("orp_range_mv", [-100, 50])
        self.mix_power_range = params.get("mixing_power_w_m3", [5, 10])

        # 合并 SUMO 参数
        self.sp = dict(SUMO_PARAMS_ANOXIC)
        sumo_override = params.get("sumo_kinetics", {})
        self.sp.update(sumo_override)

    # ═══════════════════════════════════════════════════════════
    #  Monod 切换函数
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _msat(S: float, K: float) -> float:
        return S / (S + K) if (S + K) > 0 else 0.0

    @staticmethod
    def _minh(S: float, K: float) -> float:
        return K / (S + K) if (S + K) > 0 else 1.0

    def _arrhenius(self, rate_20: float, theta: float, temp_c: float) -> float:
        return rate_20 * theta ** (temp_c - self.sp["T_base"])

    # ═══════════════════════════════════════════════════════════
    #  核心: SUMO 缺氧生化模拟
    # ═══════════════════════════════════════════════════════════

    def simulate_biochemistry(
        self,
        S_VFA: float,        # 挥发性脂肪酸 (mgCOD/L)
        S_B: float,          # 易降解基质 (mgCOD/L)
        S_NHx: float,        # 氨氮 NH3-N (mg/L)
        S_NOx: float,        # 硝氮 NO3-N (mg/L)
        S_O2: float,         # 溶解氧 (mg/L)
        S_MEOL: float = 0.0, # 甲醇 (mgCOD/L), 外加碳源时 >0
        X_B: float = 0.0,    # 慢速降解基质 (mgCOD/L, 用于水解)
        S_N_B: float = 0.0,  # 可生物降解有机氮 (mgN/L, 用于氨化)
        temp_c: float = 18.5,
        X_OHO: Optional[float] = None,
        X_CASTO: Optional[float] = None,
        X_MEOLO: Optional[float] = None,
        X_HET: Optional[float] = None,
        X_PHA_ratio: float = 0.1,  # PHA/CASTO 比 (gCOD/gCOD)
        hrt_h: float = 2.5,
        volume_m3: float = 1000.0,
    ) -> Dict[str, Any]:
        """
        基于 SUMO Gujer 矩阵计算缺氧段生化反应

        关键输出:
          - NO3-N 去除量 (反硝化)
          - 碳源消耗量 (VFA + SB + 甲醇)
          - 出水 NH3-N / NO3-N 预测
        """
        sp = self.sp
        dt_total = hrt_h / 24.0
        n_steps = 50  # 细化子步 (反硝化速率高, 需更细步长)
        dt_d = dt_total / n_steps

        X_OHO = X_OHO or sp["X_OHO_default"]
        X_CASTO = X_CASTO or sp["X_CASTO_default"]
        X_MEOLO = X_MEOLO or sp["X_MEOLO_default"]
        X_HET = X_HET or sp["X_HET_default"]

        # ─── 温度校正 ───
        mu_OHO_T = self._arrhenius(sp["mu_OHO"], sp["theta_mu_OHO"], temp_c)
        b_OHO_T = self._arrhenius(sp["b_OHO"], sp["theta_b_OHO"], temp_c)
        mu_MEOLO_T = self._arrhenius(sp["mu_MEOLO"], sp["theta_mu_MEOLO"], temp_c)
        mu_CASTO_T = self._arrhenius(sp["mu_CASTO"], sp["theta_mu_CASTO"], temp_c)
        b_STC_T = self._arrhenius(sp["b_STC"], sp["theta_b_STC"], temp_c)
        q_HYD_T = self._arrhenius(sp["q_HYD_XB"], sp["theta_q_HYD"], temp_c)
        q_AMMON_T = self._arrhenius(sp["q_AMMON"], sp["theta_q_AMMON"], temp_c)

        # ─── Monod 切换 ───
        sw_VFA = self._msat(S_VFA, sp["K_VFA"])
        sw_SB = self._msat(S_B, sp["K_SB"])
        sw_NOx_OHO = self._msat(S_NOx, sp["K_NOx_OHO"])
        sw_inh_O2_OHO = self._minh(S_O2, sp["K_O2_OHO"])
        sw_NOx_CASTO = self._msat(S_NOx, sp["K_NOx_CASTO"])
        sw_inh_O2_CASTO = self._minh(S_O2, sp["K_O2_CASTO"])
        sw_MEOL = self._msat(S_MEOL, sp["K_MEOL"])
        sw_NOx_MEOLO = self._msat(S_NOx, sp["K_NOx_MEOLO"])
        sw_inh_O2_MEOLO = self._minh(S_O2, sp["K_iO2_MEOLO"])
        sw_NHx = self._msat(S_NHx, sp["K_NHx_BIO"])
        sw_PO4 = 1.0  # 简化: 假设 PO4 充足
        sw_PHA = self._msat(X_PHA_ratio, sp["K_PHA"])

        # 水解切换
        X_B_ratio = X_B / X_HET if X_HET > 0 else 0
        sw_HYD = self._msat(X_B_ratio, sp["K_HYD"])

        # ─── 反应速率 (mgCOD/L/d) ───

        # r2: OHO 缺氧生长 (VFA + NOx)
        rho_2 = (mu_OHO_T * sp["eta_OHO_anox"] * X_OHO
                 * sw_VFA * sw_NOx_OHO * sw_inh_O2_OHO * sw_NHx * sw_PO4)

        # r4: OHO 缺氧生长 (SB + NOx)
        # SUMO: 包含 VFA 抑制项 (SB 优先消耗)
        sw_inh_VFA = self._minh(S_VFA, sp["K_VFA"])
        rho_4 = (mu_OHO_T * sp["eta_OHO_anox"] * X_OHO
                 * sw_SB * sw_inh_VFA * sw_NOx_OHO * sw_inh_O2_OHO * sw_NHx * sw_PO4)

        # r8 (缺氧部分): OHO 衰减
        rho_8_anox = (b_OHO_T * sp["eta_b_anox"] * X_OHO
                      * sw_NOx_OHO * sw_inh_O2_OHO)

        # r10: MEOLO 缺氧生长 (甲醇 + NOx)
        rho_10 = (mu_MEOLO_T * X_MEOLO
                  * sw_MEOL * sw_NOx_MEOLO * sw_inh_O2_MEOLO * sw_NHx)

        # r14: CASTO 缺氧生长 (PHA + NOx)
        rho_14 = (mu_CASTO_T * sp["eta_CASTO_anox"] * X_CASTO
                  * sw_PHA * sw_NOx_CASTO * sw_inh_O2_CASTO * sw_NHx * sw_PO4)

        # r22: CASTO 缺氧维护 (消耗 NOx + 储碳)
        sw_STC = self._msat(X_PHA_ratio, sp["K_PHA"])  # 储碳可用性
        rho_22 = (b_STC_T * sp["eta_b_STC_anox"] * X_CASTO
                  * sw_inh_O2_CASTO * sw_NOx_CASTO * sw_STC)

        # r47: XB 水解 (缺氧折减)
        rho_47_anox = q_HYD_T * X_HET * sp["eta_HYD_anox"] * sw_HYD * sw_NOx_OHO * sw_inh_O2_OHO

        # r49: 氨化 (有机氮 → NH4)
        rho_49 = q_AMMON_T * S_N_B * X_HET

        # ─── 化学计量: 浓度变化 (mg/L/d) ───
        Y_VFA = sp["Y_OHO_VFA_anox"]
        Y_SB = sp["Y_OHO_SB_anox"]
        Y_MEOLO = sp["Y_MEOLO"]
        EEQ = sp["EEQ_N2_NO3"]
        fE = sp["f_E"]
        iN_BIO = sp["i_N_BIO"]
        iN_XE = sp["i_N_XE"]

        # S_VFA 消耗 (r2)
        dS_VFA = -(1.0 / Y_VFA) * rho_2

        # S_B 消耗 (r4) + 水解产生 (r47)
        dS_B = -(1.0 / Y_SB) * rho_4 + rho_47_anox

        # S_MEOL 消耗 (r10)
        dS_MEOL = -(1.0 / Y_MEOLO) * rho_10 if Y_MEOLO > 0 else 0.0

        # S_NOx 变化 (反硝化 = 消耗)
        # SUMO stoich: dNOx_r2 = -(1-Y_VFA) / (EEQ * Y_VFA) * rho_2
        dNOx_r2 = -(1.0 - Y_VFA) / (EEQ * Y_VFA) * rho_2
        dNOx_r4 = -(1.0 - Y_SB) / (EEQ * Y_SB) * rho_4
        dNOx_r10 = -(1.0 - Y_MEOLO) / (EEQ * Y_MEOLO) * rho_10 if Y_MEOLO > 0 else 0.0
        dNOx_r14 = -(1.0 - 0.6) / (EEQ * 0.6) * rho_14  # CASTO Y~0.6 简化
        dNOx_r22 = -(1.0 / EEQ) * rho_22  # 维护消耗
        dS_NOx = dNOx_r2 + dNOx_r4 + dNOx_r10 + dNOx_r14 + dNOx_r22

        # S_NHx 变化: 生物合成消耗 + 衰减释放 + 氨化产生
        dNHx_growth = -iN_BIO * (rho_2 + rho_4 + rho_10 + rho_14)
        dNHx_decay = -fE * (iN_XE - iN_BIO) * rho_8_anox
        dNHx_ammon = rho_49  # 氨化释放 NHx
        dS_NHx = dNHx_growth + dNHx_decay + dNHx_ammon

        # ─── 子步迭代积分 ───
        S_VFA_cur, S_B_cur = S_VFA, S_B
        S_NHx_cur, S_NOx_cur = S_NHx, S_NOx
        S_MEOL_cur = S_MEOL
        X_B_cur = X_B  # 跟踪慢速降解基质（内源反硝化的关键）

        # 保存总速率用于报告
        total_dNOx_acc = 0.0

        for _ in range(n_steps):
            sw_VFA_i = self._msat(S_VFA_cur, sp["K_VFA"])
            sw_SB_i = self._msat(S_B_cur, sp["K_SB"])
            sw_NOx_i = self._msat(S_NOx_cur, sp["K_NOx_OHO"])
            sw_inh_O2_i = self._minh(S_O2, sp["K_O2_OHO"])
            sw_inh_VFA_i = self._minh(S_VFA_cur, sp["K_VFA"])
            sw_MEOL_i = self._msat(S_MEOL_cur, sp["K_MEOL"])
            sw_NHx_i = self._msat(S_NHx_cur, sp["K_NHx_BIO"])
            sw_NOx_C = self._msat(S_NOx_cur, sp["K_NOx_CASTO"])
            sw_inh_O2_C = self._minh(S_O2, sp["K_O2_CASTO"])

            # ─── 衰减反应（内源反硝化碳源来源）───
            # r8: OHO 缺氧衰减 → 释放 X_B（慢速降解基质）
            rr8_anox = (b_OHO_T * sp["eta_b_anox"] * X_OHO
                        * sw_NOx_i * sw_inh_O2_i)
            # 衰减产物: (1-f_E) 比例转为 X_B
            dX_B_from_decay = (1.0 - fE) * rr8_anox

            # r47: X_B 水解（动态计算，基于当前 X_B）
            X_B_ratio_i = X_B_cur / X_HET if X_HET > 0 else 0
            sw_HYD_i = self._msat(X_B_ratio_i, sp["K_HYD"])
            rr47_i = q_HYD_T * X_HET * sp["eta_HYD_anox"] * sw_HYD_i * sw_NOx_i * sw_inh_O2_i

            rr2 = mu_OHO_T * sp["eta_OHO_anox"] * X_OHO * sw_VFA_i * sw_NOx_i * sw_inh_O2_i * sw_NHx_i
            rr4 = mu_OHO_T * sp["eta_OHO_anox"] * X_OHO * sw_SB_i * sw_inh_VFA_i * sw_NOx_i * sw_inh_O2_i * sw_NHx_i
            rr10 = mu_MEOLO_T * X_MEOLO * sw_MEOL_i * self._msat(S_NOx_cur, sp["K_NOx_MEOLO"]) * self._minh(S_O2, sp["K_iO2_MEOLO"]) * sw_NHx_i
            rr14 = mu_CASTO_T * sp["eta_CASTO_anox"] * X_CASTO * sw_PHA * sw_NOx_C * sw_inh_O2_C * sw_NHx_i
            rr22 = b_STC_T * sp["eta_b_STC_anox"] * X_CASTO * sw_inh_O2_C * sw_NOx_C * sw_STC

            dVFA_i = -(1.0/Y_VFA) * rr2
            dSB_i = -(1.0/Y_SB) * rr4 + rr47_i  # 水解动态产 SB
            dMEOL_i = -(1.0/Y_MEOLO) * rr10 if Y_MEOLO > 0 else 0
            dNOx_i = (-(1-Y_VFA)/(EEQ*Y_VFA)*rr2 - (1-Y_SB)/(EEQ*Y_SB)*rr4
                      - (1-Y_MEOLO)/(EEQ*Y_MEOLO)*rr10 if Y_MEOLO > 0 else 0)
            dNOx_i += -(1-0.6)/(EEQ*0.6)*rr14 - (1.0/EEQ)*rr22
            dNHx_i = -iN_BIO * (rr2 + rr4 + rr10 + rr14) + rho_49/n_steps
            # 衰减释放 NHx：生物质中氮含量 i_N_BIO 减去残留在惰性部分的 f_E*i_N_XE
            # SUMO Gujer 矩阵 r8 化学计量：dNHx = +(i_N_BIO - f_E * i_N_XE) * rho_8
            dNHx_i += (iN_BIO - fE * iN_XE) * rr8_anox

            # X_B 动态更新: 衰减产生 - 水解消耗
            dX_B_i = dX_B_from_decay - rr47_i

            S_VFA_cur = max(0, S_VFA_cur + dVFA_i * dt_d)
            S_B_cur = max(0, S_B_cur + dSB_i * dt_d)
            S_MEOL_cur = max(0, S_MEOL_cur + dMEOL_i * dt_d)
            S_NOx_cur = max(0, S_NOx_cur + dNOx_i * dt_d)
            S_NHx_cur = max(0, S_NHx_cur + dNHx_i * dt_d)
            X_B_cur = max(0, X_B_cur + dX_B_i * dt_d)
            total_dNOx_acc += dNOx_i * dt_d

        S_VFA_out = S_VFA_cur
        S_B_out = S_B_cur
        S_NHx_out = S_NHx_cur
        S_NOx_out = S_NOx_cur
        S_MEOL_out = S_MEOL_cur

        # 总反硝化量
        total_denitrif = S_NOx - S_NOx_out  # mg/L 去除量
        total_denitrif_rate = total_denitrif / dt_total if dt_total > 0 else 0  # mgN/L/d
        mlvss_est = (X_OHO + X_CASTO + X_MEOLO) / 1.42 / 1000.0  # gVSS/L (COD→VSS≈1.42)
        sdnr_equiv = total_denitrif_rate / mlvss_est / 24.0 if mlvss_est > 0 else 0

        return {
            "stage": "anoxic",
            "temp_c": temp_c,
            "hrt_h": hrt_h,
            "reaction_rates": {
                "rho_2_OHO_VFA_NOx": round(rho_2, 4),
                "rho_4_OHO_SB_NOx": round(rho_4, 4),
                "rho_8_OHO_decay_anox": round(rho_8_anox, 4),
                "rho_10_MEOLO_NOx": round(rho_10, 4),
                "rho_14_CASTO_PHA_NOx": round(rho_14, 4),
                "rho_22_CASTO_maint": round(rho_22, 4),
                "rho_47_hydrolysis_anox": round(rho_47_anox, 4),
                "rho_49_ammonification": round(rho_49, 4),
            },
            "switching_functions": {
                "sw_VFA": round(sw_VFA, 4),
                "sw_SB": round(sw_SB, 4),
                "sw_NOx_OHO": round(sw_NOx_OHO, 4),
                "sw_inh_O2_OHO": round(sw_inh_O2_OHO, 4),
                "sw_PHA": round(sw_PHA, 4),
            },
            "denitrification_detail": {
                "no3_removed_mg_l": round(total_denitrif, 2),
                "total_dNOx_mgN_L_d": round(total_denitrif_rate, 3),
                "sdnr_equiv_mgN_gVSS_h": round(sdnr_equiv, 3),
            },
            "concentration_changes_per_day": {
                "dS_VFA_mgCOD_L_d": round(dS_VFA, 3),
                "dS_B_mgCOD_L_d": round(dS_B, 3),
                "dS_NHx_mgN_L_d": round(dS_NHx, 4),
                "dS_NOx_mgN_L_d": round(dS_NOx, 4),
                "dS_MEOL_mgCOD_L_d": round(dS_MEOL, 3),
            },
            "effluent_prediction": {
                "nh3_n_out_mg_l": round(S_NHx_out, 2),
                "no3_n_out_mg_l": round(S_NOx_out, 2),
                "S_VFA_out_mgCOD_L": round(S_VFA_out, 2),
                "S_B_out_mgCOD_L": round(S_B_out, 2),
            },
            "sumo_params_used": {
                "mu_OHO_T": round(mu_OHO_T, 4),
                "eta_OHO_anox": sp["eta_OHO_anox"],
                "Y_OHO_VFA_anox": Y_VFA,
                "Y_OHO_SB_anox": Y_SB,
                "EEQ_N2_NO3": EEQ,
            },
        }

    # ═══════════════════════════════════════════════════════════
    #  操作控制方法 (保留)
    # ═══════════════════════════════════════════════════════════

    def optimize_dosing(
        self, no3_in: float, no3_target: float, bod_in: float,
        flow_m3_h: float, mlvss: float, volume_m3: float, temp_c: float,
    ) -> Dict[str, Any]:
        """外加碳源优化 — 基于 SUMO 反硝化碳需量"""
        sp = self.sp
        delta_no3 = max(0, no3_in - no3_target)
        cod_demand = delta_no3 * sp["EEQ_N2_NO3"]
        bod_available_ratio = self.dosing_cfg.get("bod_available_ratio", 0.65)
        bod_available = bod_in * bod_available_ratio
        carbon_deficit = max(0, cod_demand - bod_available)

        carbon_source = self.dosing_cfg.get("carbon_source", "sodium_acetate")
        cod_equivalents = {"sodium_acetate": 0.78, "methanol": 1.5, "glucose": 1.07, "acetic_acid": 1.07}
        cod_equiv = cod_equivalents.get(carbon_source, 0.78)
        dose_mg_l = carbon_deficit / cod_equiv if cod_equiv > 0 else 0

        temp_factor = sp["theta_mu_OHO"] ** (20.0 - temp_c)
        dose_mg_l *= temp_factor
        max_dose = self.dosing_cfg.get("max_dose_mg_l", 80.0)
        dose_mg_l = max(0, min(max_dose, dose_mg_l))
        dose_kg_d = dose_mg_l * flow_m3_h * 24.0 / 1e6

        # SUMO 等效 SDNR
        sdnr = self._arrhenius(2.0, 1.026, temp_c)  # 经验基准
        denitrif_capacity = sdnr * mlvss * volume_m3 / 1e6 * 24.0
        denitrif_demand = delta_no3 * flow_m3_h * 24.0 / 1e6
        capacity_ratio = (denitrif_capacity / denitrif_demand * 100.0
                          if denitrif_demand > 0 else float("inf"))

        return {
            "carbon_source": carbon_source, "dose_mg_l": round(dose_mg_l, 2),
            "dose_kg_d": round(dose_kg_d, 3),
            "no3_removal_target_mg_l": round(delta_no3, 1),
            "cod_demand_mg_l": round(cod_demand, 1),
            "bod_available_mg_l": round(bod_available, 1),
            "carbon_deficit_mg_l": round(carbon_deficit, 1),
            "sdnr_equiv_mgN_gVSS_h": round(sdnr, 3),
            "capacity_ratio_pct": round(capacity_ratio, 1),
            "temp_correction_factor": round(temp_factor, 3),
            "reason": "内碳源充足" if carbon_deficit <= 0 else f"碳源缺口{carbon_deficit:.1f}mgCOD/L",
        }

    def optimize_mixing(
        self, volume_m3: float, do_actual: float, orp_actual: float,
        mixer_power_kw: float, mixer_count: int = 1,
    ) -> Dict[str, Any]:
        """搅拌控制优化 — 功率密度 5~10 W/m³"""
        total_power_kw = mixer_power_kw * mixer_count
        current_density = (total_power_kw * 1000) / volume_m3 if volume_m3 > 0 else 0
        target_min, target_max = self.mix_power_range
        do_ok = do_actual <= self.do_max
        orp_ok = self.orp_range[0] <= orp_actual <= self.orp_range[1]
        recommendations = []
        recommended_density = current_density
        if current_density < target_min:
            recommended_density = target_min
            recommendations.append(f"搅拌功率密度{current_density:.1f}W/m³低于下限{target_min}W/m³")
        elif current_density > target_max:
            recommended_density = target_max
            recommendations.append(f"搅拌功率密度{current_density:.1f}W/m³超过上限{target_max}W/m³")
        if not do_ok:
            recommendations.append(f"DO={do_actual}mg/L超过缺氧上限{self.do_max}mg/L")
        if not orp_ok:
            recommendations.append(f"ORP={orp_actual}mV不在{self.orp_range}范围")
        return {
            "current_power_density_w_m3": round(current_density, 1),
            "recommended_power_density_w_m3": round(recommended_density, 1),
            "environment_check": {"do_ok": do_ok, "orp_ok": orp_ok},
            "recommendations": recommendations,
        }

    def optimize_recirculation(
        self, tn_in: float, tn_target: float, no3_aerobic_out: float,
        flow_m3_h: float, volume_m3: float,
        current_recirc_ratio: float = 3.0,
    ) -> Dict[str, Any]:
        """硝化液内回流比优化 — SUMO: TN_eff ≈ TN_in/(1+r)"""
        if tn_target > 0:
            r_theoretical = tn_in / tn_target - 1.0
        else:
            r_theoretical = 4.0
        if no3_aerobic_out > 0:
            tn_removal_needed = max(0, tn_in - tn_target)
            r_from_no3 = tn_removal_needed / no3_aerobic_out
            r_theoretical = min(r_theoretical, r_from_no3)
        recirc_range = self.denitrif_cfg.get("recirculation_ratio_range", [2.0, 4.0])
        r_min, r_max = recirc_range
        r_recommended = max(r_min, min(r_max, r_theoretical))
        recirc_flow = flow_m3_h * r_recommended
        predicted_tn_out = tn_in / (1.0 + r_recommended) if r_recommended > 0 else tn_in
        return {
            "recirculation_ratio_recommended": round(r_recommended, 2),
            "current_recirculation_ratio": round(current_recirc_ratio, 2),
            "recirculation_flow_m3_h": round(recirc_flow, 1),
            "predicted_tn_out_mg_l": round(predicted_tn_out, 1),
            "tn_target_mg_l": tn_target,
        }

    def check_environment(
        self, do_actual: float, orp_actual: float, temp_c: float, hrt_actual_h: float,
    ) -> Dict[str, Any]:
        """综合环境约束校验"""
        violations = []
        if do_actual > self.do_max:
            violations.append(f"DO={do_actual}>{self.do_max}mg/L")
        if orp_actual < self.orp_range[0] or orp_actual > self.orp_range[1]:
            violations.append(f"ORP={orp_actual}mV不在{self.orp_range}范围")
        if hrt_actual_h < self.hrt_range[0] or hrt_actual_h > self.hrt_range[1]:
            violations.append(f"HRT={hrt_actual_h}h不在{self.hrt_range}范围")
        return {
            "stage": "anoxic", "compliant": len(violations) == 0,
            "violations": violations,
            "parameters": {"do_mg_l": do_actual, "orp_mv": orp_actual, "temp_c": temp_c, "hrt_h": hrt_actual_h},
        }

    def export_parameters(
        self, dosing_result: Dict, mixing_result: Dict,
        recirculation_result: Dict, volume_m3: float, temp_c: float,
    ) -> Dict[str, Any]:
        """导出缺氧段所有调整参数"""
        return {
            "stage": "anoxic", "volume_m3": volume_m3, "temp_c": temp_c,
            "hrt_design_h": self.hrt_range, "do_setpoint_mg_l": 0.0,
            "dosing": {
                "carbon_source": dosing_result.get("carbon_source"),
                "dose_mg_l": dosing_result.get("dose_mg_l", 0),
            },
            "mixing": {"power_density_w_m3": mixing_result.get("recommended_power_density_w_m3", 7)},
            "recirculation": {
                "ratio": recirculation_result.get("recirculation_ratio_recommended", 3.0),
            },
        }
