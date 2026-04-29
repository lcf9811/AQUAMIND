"""
好氧池机理模型 — 基于 SUMO1.xlsm Gujer 矩阵
核心反应过程 (来自 SUMO Model Sheet):
  r1  : OHO 好氧生长 (VFA + O2)
  r3  : OHO 好氧生长 (SB + O2)
  r7  : OHO 好氧生长 (甲醇 + O2)
  r8  : OHO 衰减 (好氧)
  r13 : CASTO 好氧生长 (PHA + O2)
  r15 : PAO 聚磷储存 (好氧)
  r21 : CASTO 好氧维护
  r27 : CASTO 衰减
  r30 : NITO 硝化生长 (NH3 → NO3) ★核心
  r31 : NITO 衰减 (好氧+缺氧)
  r47 : XB 水解 (好氧)
  r49 : 氨化 (有机氮→NH4)

关键化学计量 (来自 SUMO Gujer 矩阵):
  r30: SNHx = -1/Y_NITO - i_N_BIO        (硝化消耗 NHx)
       SNOx = +1/Y_NITO                  (硝化产生 NOx)
       SO2  = -(EEQ_NO3 - Y_NITO)/Y_NITO (硝化耗氧)
  r1:  SO2  = -(1-Y_OHO_VFA_ox)/Y_OHO_VFA_ox (碳氧化耗氧)
  r3:  SO2  = -(1-Y_OHO_SB_ox)/Y_OHO_SB_ox

SUMO 参数来源: SUMO1.xlsm Parameters Sheet
  Y_NITO = 0.24, µ_NITO = 0.9 d⁻¹, θ = 1.072
  K_NHx_NITO = 0.7, K_O2_NITO = 0.5
  EEQ_NO3 = 4.57

环境约束:
  DO 1.5~3.0 mg/L, ORP +50~+300 mV, HRT 4~8 h, SRT 10~25 d
"""

import math
from typing import Dict, Any, Optional


# ─────────── SUMO 动力学参数 (默认值来自 SUMO1.xlsm Parameters Sheet) ──────
SUMO_PARAMS_AEROBIC = {
    # ─── NITO 硝化动力学 (★核心) ───
    "mu_NITO":        0.9,     # d⁻¹ NITO 最大比生长速率
    "theta_mu_NITO":  1.072,   # Arrhenius 温度系数 (敏感!)
    "b_NITO":         0.17,    # d⁻¹ NITO 衰减速率
    "theta_b_NITO":   1.03,
    "Y_NITO":         0.24,    # gCOD biomass / gN oxidized
    "K_NHx_NITO":     0.7,     # mgN/L  NHx 半饱和 (NITO)
    "K_O2_NITO":      0.5,     # mgO2/L O2 半饱和 (NITO)
    "K_NOx_NITO":     0.03,    # mgN/L  NOx 半饱和 (NITO 衰减)
    "EEQ_NO3":        4.57,    # 电子当量 (gCOD/gN), NH4→NO3 需氧
    "eta_b_anox":     0.5,     # 缺氧衰减折减

    # ─── OHO 好氧生长动力学 ───
    "mu_OHO":         4.0,     # d⁻¹
    "theta_mu_OHO":   1.04,
    "Y_OHO_VFA_ox":   0.6,     # 好氧 VFA 产率
    "Y_OHO_SB_ox":    0.67,    # 好氧 SB 产率
    "Y_OHO_MEOL_ox":  0.4,     # 好氧甲醇产率
    "K_VFA":          0.5,     # mgCOD/L
    "K_SB":           5.0,     # mgCOD/L
    "K_MEOL_OHO":     0.1,     # mgCOD/L
    "K_O2_OHO":       0.15,    # mgO2/L
    "K_NOx_OHO":      0.03,    # mgN/L

    # OHO 衰减
    "b_OHO":          0.62,
    "theta_b_OHO":    1.03,

    # ─── CASTO 好氧 ───
    "mu_CASTO":       1.0,
    "theta_mu_CASTO": 1.04,
    "K_PHA":          0.01,
    "K_O2_CASTO":     0.05,
    "b_STC":          0.07,    # 好氧维护
    "theta_b_STC":    1.064,

    # ─── PAO 聚磷储存 (好氧) ───
    "q_PAO_PP":       0.1,     # d⁻¹ 聚磷摄取速率
    "theta_q_PAO_PP": 1.04,
    "K_PO4_PAO":      0.15,    # mgP/L

    # ─── 水解 & 氨化 ───
    "q_HYD_XB":       3.0,
    "theta_q_HYD":    1.03,
    "K_HYD":          0.03,
    "q_AMMON":        40.0,
    "theta_q_AMMON":  1.03,

    # ─── 公共化学计量 ───
    "EEQ_N2_NO3":     2.86,    # 反硝化电子当量
    "f_E":            0.08,
    "i_N_BIO":        0.07,
    "i_N_XE":         0.06,
    "i_P_BIO":        0.02,
    "K_NHx_BIO":      0.05,
    "K_PO4_BIO":      0.01,

    # Arrhenius 基准温度
    "T_base": 20.0,

    # 典型生物量浓度 (mgCOD/L)
    "X_OHO_default":   2000.0,
    "X_NITO_default":   200.0,
    "X_CASTO_default":  500.0,
    "X_PAO_default":    300.0,
    "X_HET_default":   2500.0,
}


class AerobicModel:
    """AAO 工艺好氧段机理计算器 — SUMO Gujer 矩阵驱动"""

    def __init__(self, params: Dict[str, Any]):
        self.cfg = params
        self.do_target_range = params.get("do_target_mg_l", [1.5, 3.0])
        self.hrt_range = params.get("hrt_h", [4.0, 8.0])
        self.srt_range = params.get("srt_days", [10, 25])
        self.orp_range = params.get("orp_range_mv", [50, 300])

        # 合并 SUMO 参数
        self.sp = dict(SUMO_PARAMS_AEROBIC)
        sumo_override = params.get("sumo_kinetics", {})
        self.sp.update(sumo_override)

        # 氧转移参数 (保留工程控制)
        ot = params.get("oxygen_transfer", {})
        self.alpha = ot.get("alpha", 0.6)
        self.beta = ot.get("beta", 0.95)
        self.theta_OT = ot.get("theta", 1.024)

        # 风机参数
        blower = params.get("blower", {})
        self.freq_min = blower.get("freq_min_hz", 20.0)
        self.freq_max = blower.get("freq_max_hz", 50.0)
        self.freq_slope = blower.get("freq_to_flow_slope", 22.37)
        self.freq_intercept = blower.get("freq_to_flow_intercept", 0.0)

        # PID (stateless — 每次调用 optimize_aeration 时独立计算)
        pid = params.get("pid", {})
        self.kp = pid.get("kp", 5.0)
        self.ki = pid.get("ki", 0.5)
        self.kd = pid.get("kd", 0.1)

        # 加药 & 搅拌
        self.dosing_cfg = params.get("dosing", {})
        self.mix_power_range = params.get("mixing_power_w_m3", [5, 15])

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
    #  核心: SUMO 好氧生化模拟
    # ═══════════════════════════════════════════════════════════

    def simulate_biochemistry(
        self,
        S_VFA: float,        # 挥发性脂肪酸 (mgCOD/L)
        S_B: float,          # 易降解基质 (mgCOD/L)
        S_NHx: float,        # 氨氮 NH3-N (mg/L)
        S_NOx: float,        # 硝氮 NO3-N (mg/L)
        S_O2: float,         # 溶解氧 (mg/L)
        S_PO4: float = 1.0,  # 正磷酸盐 (mgP/L)
        X_B: float = 0.0,    # 慢速降解基质
        S_N_B: float = 0.0,  # 可生物降解有机氮
        temp_c: float = 18.5,
        X_OHO: Optional[float] = None,
        X_NITO: Optional[float] = None,
        X_CASTO: Optional[float] = None,
        X_PAO: Optional[float] = None,
        X_HET: Optional[float] = None,
        X_PHA_ratio: float = 0.1,
        hrt_h: float = 6.0,
        volume_m3: float = 2000.0,
    ) -> Dict[str, Any]:
        """
        基于 SUMO Gujer 矩阵计算好氧段生化反应

        ★ 核心输出:
          - NH3-N 去除 (硝化, r30)
          - NO3-N 产生 (硝化, r30)
          - O2 需求量 (碳氧化 + 硝化 + 内源呼吸)
          - COD 去除 (r1, r3)
        """
        sp = self.sp
        dt_total = hrt_h / 24.0
        n_steps = 50  # 子步迭代
        dt_d = dt_total / n_steps

        X_OHO = X_OHO or sp["X_OHO_default"]
        X_NITO = X_NITO or sp["X_NITO_default"]
        X_CASTO = X_CASTO or sp["X_CASTO_default"]
        X_PAO = X_PAO or sp["X_PAO_default"]
        X_HET = X_HET or sp["X_HET_default"]

        # ─── 温度校正 ───
        mu_OHO_T = self._arrhenius(sp["mu_OHO"], sp["theta_mu_OHO"], temp_c)
        mu_NITO_T = self._arrhenius(sp["mu_NITO"], sp["theta_mu_NITO"], temp_c)
        b_OHO_T = self._arrhenius(sp["b_OHO"], sp["theta_b_OHO"], temp_c)
        b_NITO_T = self._arrhenius(sp["b_NITO"], sp["theta_b_NITO"], temp_c)
        mu_CASTO_T = self._arrhenius(sp["mu_CASTO"], sp["theta_mu_CASTO"], temp_c)
        b_STC_T = self._arrhenius(sp["b_STC"], sp["theta_b_STC"], temp_c)
        q_PAO_PP_T = self._arrhenius(sp["q_PAO_PP"], sp["theta_q_PAO_PP"], temp_c)
        q_HYD_T = self._arrhenius(sp["q_HYD_XB"], sp["theta_q_HYD"], temp_c)
        q_AMMON_T = self._arrhenius(sp["q_AMMON"], sp["theta_q_AMMON"], temp_c)

        # ─── Monod 切换 ───
        sw_VFA = self._msat(S_VFA, sp["K_VFA"])
        sw_SB = self._msat(S_B, sp["K_SB"])
        sw_O2_OHO = self._msat(S_O2, sp["K_O2_OHO"])
        sw_O2_NITO = self._msat(S_O2, sp["K_O2_NITO"])
        sw_O2_CASTO = self._msat(S_O2, sp["K_O2_CASTO"])
        sw_NHx_NITO = self._msat(S_NHx, sp["K_NHx_NITO"])
        sw_NHx_BIO = self._msat(S_NHx, sp["K_NHx_BIO"])
        sw_PO4 = self._msat(S_PO4, sp["K_PO4_BIO"])
        sw_PO4_PAO = self._msat(S_PO4, sp["K_PO4_PAO"])
        sw_PHA = self._msat(X_PHA_ratio, sp["K_PHA"])
        sw_inh_VFA = self._minh(S_VFA, sp["K_VFA"])  # r3 中 VFA 抑制

        # 水解切换
        X_B_ratio = X_B / X_HET if X_HET > 0 else 0
        sw_HYD = self._msat(X_B_ratio, sp["K_HYD"])

        # ─── 反应速率 (mgCOD/L/d) ───

        # r1: OHO 好氧生长 (VFA + O2)
        rho_1 = mu_OHO_T * X_OHO * sw_VFA * sw_O2_OHO * sw_NHx_BIO * sw_PO4

        # r3: OHO 好氧生长 (SB + O2)
        rho_3 = mu_OHO_T * X_OHO * sw_SB * sw_inh_VFA * sw_O2_OHO * sw_NHx_BIO * sw_PO4

        # r7: OHO 好氧生长 (甲醇) — 通常可忽略
        rho_7 = 0.0

        # r8: OHO 好氧衰减
        rho_8 = b_OHO_T * X_OHO * sw_O2_OHO

        # r13: CASTO 好氧生长 (PHA + O2)
        rho_13 = mu_CASTO_T * X_CASTO * sw_PHA * sw_O2_CASTO * sw_NHx_BIO * sw_PO4

        # r15: PAO 聚磷储存 (好氧)
        rho_15 = q_PAO_PP_T * X_PAO * sw_PO4_PAO * sw_O2_CASTO

        # r21: CASTO 好氧维护
        sw_STC = self._msat(X_PHA_ratio, sp["K_PHA"])
        rho_21 = b_STC_T * X_CASTO * sw_O2_CASTO * sw_STC

        # ★ r30: NITO 硝化生长 (NH3 → NO3) — 核心反应
        # Rate = µ_NITO_T * X_NITO * Msat(NHx, K_NHx_NITO) * Msat(O2, K_O2_NITO)
        #        * Logsat(pH/CO2) * Msat(PO4) * ...
        # 简化: 忽略 pH/CO2 限制 (假设碱度充足)
        rho_30 = mu_NITO_T * X_NITO * sw_NHx_NITO * sw_O2_NITO * sw_PO4

        # r31: NITO 衰减 (好氧部分)
        rho_31 = b_NITO_T * X_NITO * sw_O2_NITO

        # r47: XB 好氧水解
        rho_47 = q_HYD_T * X_HET * sw_HYD * sw_O2_OHO

        # r49: 氨化
        rho_49 = q_AMMON_T * S_N_B * X_HET

        # ─── 化学计量: 浓度变化 (mg/L/d) ───
        Y_VFA = sp["Y_OHO_VFA_ox"]
        Y_SB = sp["Y_OHO_SB_ox"]
        Y_NITO = sp["Y_NITO"]
        EEQ_NO3 = sp["EEQ_NO3"]
        fE = sp["f_E"]
        iN_BIO = sp["i_N_BIO"]
        iN_XE = sp["i_N_XE"]
        iP_BIO = sp["i_P_BIO"]

        # S_VFA 消耗 (r1)
        dS_VFA = -(1.0 / Y_VFA) * rho_1

        # S_B 消耗 (r3) + 水解产生 (r47)
        dS_B = -(1.0 / Y_SB) * rho_3 + rho_47

        # ★ S_NHx 变化 (硝化消耗 + 生长消耗 + 衰减释放 + 氨化)
        # r30 stoich: -1/Y_NITO - i_N_BIO
        dNHx_nitrif = -(1.0 / Y_NITO + iN_BIO) * rho_30     # 硝化主消耗
        dNHx_growth = -iN_BIO * (rho_1 + rho_3 + rho_13)     # 异养生长消耗
        dNHx_decay = -fE * (iN_XE - iN_BIO) * (rho_8 + rho_31)  # 衰减释放
        dNHx_ammon = rho_49                                    # 氨化产生
        dS_NHx = dNHx_nitrif + dNHx_growth + dNHx_decay + dNHx_ammon

        # ★ S_NOx 变化 (硝化产生)
        # r30 stoich: +1/Y_NITO
        dS_NOx = (1.0 / Y_NITO) * rho_30

        # ★ S_O2 变化 (需氧量)
        # r30: -(EEQ_NO3 - Y_NITO)/Y_NITO  硝化耗氧
        dO2_nitrif = -(EEQ_NO3 - Y_NITO) / Y_NITO * rho_30
        # r1: -(1-Y_VFA)/Y_VFA  碳氧化(VFA)
        dO2_r1 = -(1.0 - Y_VFA) / Y_VFA * rho_1
        # r3: -(1-Y_SB)/Y_SB  碳氧化(SB)
        dO2_r3 = -(1.0 - Y_SB) / Y_SB * rho_3
        # r8: 衰减耗氧 (简化: ~fE * (1-fE))
        dO2_r8 = -(1.0 - fE) * rho_8
        # r21: CASTO 维护耗氧
        dO2_r21 = -1.0 * rho_21
        dS_O2 = dO2_nitrif + dO2_r1 + dO2_r3 + dO2_r8 + dO2_r21

        # S_PO4: PAO 摄磷 (r15 消耗)
        dS_PO4 = -rho_15 * 0.1 - iP_BIO * (rho_1 + rho_3 + rho_30)

        # ─── 子步迭代积分 ───
        S_VFA_cur, S_B_cur = S_VFA, S_B
        S_NHx_cur, S_NOx_cur = S_NHx, S_NOx

        for _ in range(n_steps):
            sw_VFA_i = self._msat(S_VFA_cur, sp["K_VFA"])
            sw_SB_i = self._msat(S_B_cur, sp["K_SB"])
            sw_NHx_NITO_i = self._msat(S_NHx_cur, sp["K_NHx_NITO"])
            sw_NHx_BIO_i = self._msat(S_NHx_cur, sp["K_NHx_BIO"])
            sw_inh_VFA_i = self._minh(S_VFA_cur, sp["K_VFA"])

            rr1 = mu_OHO_T * X_OHO * sw_VFA_i * sw_O2_OHO * sw_NHx_BIO_i * sw_PO4
            rr3 = mu_OHO_T * X_OHO * sw_SB_i * sw_inh_VFA_i * sw_O2_OHO * sw_NHx_BIO_i * sw_PO4
            rr30 = mu_NITO_T * X_NITO * sw_NHx_NITO_i * sw_O2_NITO * sw_PO4

            dVFA_i = -(1.0/Y_VFA) * rr1
            dSB_i = -(1.0/Y_SB) * rr3 + rho_47/n_steps
            dNHx_i = (-(1.0/Y_NITO + iN_BIO) * rr30
                      - iN_BIO * (rr1 + rr3 + rho_13/n_steps)
                      + rho_49/n_steps)
            dNOx_i = (1.0/Y_NITO) * rr30

            S_VFA_cur = max(0, S_VFA_cur + dVFA_i * dt_d)
            S_B_cur = max(0, S_B_cur + dSB_i * dt_d)
            S_NHx_cur = max(0, S_NHx_cur + dNHx_i * dt_d)
            S_NOx_cur = max(0, S_NOx_cur + dNOx_i * dt_d)

        S_VFA_out = S_VFA_cur
        S_B_out = S_B_cur
        S_NHx_out = S_NHx_cur
        S_NOx_out = S_NOx_cur

        # 统计: 总硝化量 = 出水NOx - 进水NOx
        total_nitrif = S_NOx_out - S_NOx  # mgN/L 产生量
        total_nh3_removed = S_NHx - S_NHx_out  # mgN/L 去除量

        nitrif_rate = total_nh3_removed / (hrt_h) if hrt_h > 0 else 0  # mgN/L/h

        # OUR 估算 (基于总变化量)
        our_nitrification = abs((EEQ_NO3 - Y_NITO)/Y_NITO) * total_nitrif * volume_m3 / 1e6 / dt_total if dt_total > 0 else 0
        cod_removed_vfa = max(0, S_VFA - S_VFA_out)
        cod_removed_sb = max(0, S_B - S_B_out)
        our_carbon = ((1-Y_VFA)/Y_VFA * cod_removed_vfa + (1-Y_SB)/Y_SB * cod_removed_sb) * volume_m3 / 1e6 / dt_total if dt_total > 0 else 0
        our_endogenous = (1-fE) * rho_8 * volume_m3 / 1e6
        our_maintenance = rho_21 * volume_m3 / 1e6
        our_total = our_nitrification + our_carbon + our_endogenous + our_maintenance

        return {
            "stage": "aerobic",
            "temp_c": temp_c,
            "hrt_h": hrt_h,
            "reaction_rates": {
                "rho_1_OHO_VFA_O2": round(rho_1, 4),
                "rho_3_OHO_SB_O2": round(rho_3, 4),
                "rho_8_OHO_decay": round(rho_8, 4),
                "rho_13_CASTO_PHA_O2": round(rho_13, 4),
                "rho_15_PAO_PP_store": round(rho_15, 4),
                "rho_21_CASTO_maint": round(rho_21, 4),
                "rho_30_NITO_nitrif": round(rho_30, 4),
                "rho_31_NITO_decay": round(rho_31, 4),
                "rho_47_hydrolysis": round(rho_47, 4),
                "rho_49_ammonification": round(rho_49, 4),
            },
            "switching_functions": {
                "sw_NHx_NITO": round(sw_NHx_NITO, 4),
                "sw_O2_NITO": round(sw_O2_NITO, 4),
                "sw_O2_OHO": round(sw_O2_OHO, 4),
                "sw_VFA": round(sw_VFA, 4),
                "sw_SB": round(sw_SB, 4),
            },
            "nitrification_detail": {
                "dNHx_nitrif_mgN_L_d": round(dNHx_nitrif, 3),
                "dNOx_produced_mgN_L_d": round(dS_NOx, 3),
                "nitrif_rate_mgN_L_h": round(nitrif_rate, 3),
                "stoich_NHx_per_rho30": round(-1.0/Y_NITO - iN_BIO, 3),
                "stoich_NOx_per_rho30": round(1.0/Y_NITO, 3),
                "stoich_O2_per_rho30": round(-(EEQ_NO3-Y_NITO)/Y_NITO, 3),
            },
            "our_breakdown": {
                "our_nitrification_kgO2_d": round(our_nitrification, 3),
                "our_carbon_kgO2_d": round(our_carbon, 3),
                "our_endogenous_kgO2_d": round(our_endogenous, 3),
                "our_maintenance_kgO2_d": round(our_maintenance, 3),
                "our_total_kgO2_d": round(our_total, 3),
            },
            "concentration_changes_per_day": {
                "dS_VFA_mgCOD_L_d": round(dS_VFA, 3),
                "dS_B_mgCOD_L_d": round(dS_B, 3),
                "dS_NHx_mgN_L_d": round(dS_NHx, 4),
                "dS_NOx_mgN_L_d": round(dS_NOx, 4),
                "dS_O2_mgO2_L_d": round(dS_O2, 3),
                "dS_PO4_mgP_L_d": round(dS_PO4, 4),
            },
            "effluent_prediction": {
                "nh3_n_out_mg_l": round(S_NHx_out, 2),
                "no3_n_out_mg_l": round(S_NOx_out, 2),
                "S_VFA_out_mgCOD_L": round(S_VFA_out, 2),
                "S_B_out_mgCOD_L": round(S_B_out, 2),
            },
            "sumo_params_used": {
                "mu_NITO_T": round(mu_NITO_T, 4),
                "b_NITO_T": round(b_NITO_T, 4),
                "mu_OHO_T": round(mu_OHO_T, 4),
                "Y_NITO": Y_NITO,
                "Y_OHO_VFA_ox": Y_VFA,
                "Y_OHO_SB_ox": Y_SB,
                "EEQ_NO3": EEQ_NO3,
                "K_NHx_NITO": sp["K_NHx_NITO"],
                "K_O2_NITO": sp["K_O2_NITO"],
            },
        }

    # ═══════════════════════════════════════════════════════════
    #  曝气控制 (SUMO OUR 驱动)
    # ═══════════════════════════════════════════════════════════

    def optimize_aeration(
        self,
        do_actual: float, mlss: float, mlvss: float, temp_c: float,
        cod_in: float, cod_out: float, nh3_in: float, nh3_out: float,
        no3_out: float, flow_m3_h: float, hrt_h: float,
        current_fan_hz: float, volume_m3: float,
        S_VFA: float = 5.0, S_B: float = 20.0, S_NOx: float = 5.0,
    ) -> Dict[str, Any]:
        """
        曝气 DO 控制 — 基于 SUMO 生化模拟的 OUR

        先运行 simulate_biochemistry() 获取精确 OUR, 再计算风机参数
        """
        # 运行 SUMO 模拟获取 OUR
        sim = self.simulate_biochemistry(
            S_VFA=S_VFA, S_B=S_B, S_NHx=nh3_in, S_NOx=S_NOx,
            S_O2=do_actual, temp_c=temp_c, hrt_h=hrt_h, volume_m3=volume_m3,
        )
        our_total = sim["our_breakdown"]["our_total_kgO2_d"]

        # 动态 DO 目标
        do_base = (self.do_target_range[0] + self.do_target_range[1]) / 2.0
        do_target = do_base
        nh3_thresh = self.cfg.get("high_nh3_threshold_mg_l", 30.0)
        if nh3_in > nh3_thresh:
            do_target += 0.5
        temp_thresh = self.cfg.get("low_temp_threshold_C", 15.0)
        if temp_c < temp_thresh:
            do_target += 0.3
        do_target = max(self.do_target_range[0], min(self.do_target_range[1], do_target))

        # 氧转移
        do_sat = self._do_saturation(temp_c) * self.beta
        theta_corr = self.theta_OT ** (temp_c - 20.0)
        do_deficit = max(0.1, do_sat - do_target)
        transfer_eff = self.alpha * theta_corr * (do_deficit / do_sat)
        transfer_eff = max(0.01, transfer_eff)
        air_flow_required = our_total / (0.28 * transfer_eff * 24.0)

        # 风量 → 频率
        recommended_hz = (air_flow_required - self.freq_intercept) / self.freq_slope if self.freq_slope > 0 else 40.0
        pid_adj, _, _ = self._pid_step_static(
            do_target - do_actual, 0.0, 0.0,
            self.kp, self.ki, self.kd,
            self.freq_min - 35.0, self.freq_max - 35.0,
        )
        recommended_hz += pid_adj
        recommended_hz = max(self.freq_min, min(self.freq_max, recommended_hz))

        new_air_flow = self.freq_slope * recommended_hz + self.freq_intercept
        power_ratio = (recommended_hz / current_fan_hz) ** 3 if current_fan_hz > 0 else 1.0
        energy_saving_pct = max(0, (1 - power_ratio) * 100)

        return {
            "target_do_mg_l": round(do_target, 2),
            "current_do_mg_l": do_actual,
            "recommended_fan_hz": round(recommended_hz, 1),
            "current_fan_hz": current_fan_hz,
            "air_flow_nm3h": round(new_air_flow, 1),
            "energy_saving_estimate_pct": round(energy_saving_pct, 1),
            "our_breakdown": sim["our_breakdown"],
            "sumo_simulation": sim["nitrification_detail"],
            "oxygen_transfer": {
                "do_saturation_mg_l": round(do_sat / self.beta, 2),
                "effective_do_sat_mg_l": round(do_sat, 2),
                "transfer_efficiency": round(transfer_eff, 4),
            },
            "pid_adjustment_hz": round(pid_adj, 2),
        }

    # ═══════════════════════════════════════════════════════════
    #  操作控制 (保留)
    # ═══════════════════════════════════════════════════════════

    def optimize_recirculation(
        self, tn_in: float, tn_target: float, no3_out: float,
        flow_m3_h: float, volume_m3: float, current_recirc_ratio: float = 3.0,
    ) -> Dict[str, Any]:
        """混合液回流优化"""
        if tn_target > 0:
            r_theoretical = tn_in / tn_target - 1.0
        else:
            r_theoretical = 4.0
        recirc_range = self.cfg.get("recirculation_ratio_range", [2.0, 4.0])
        r_min, r_max = recirc_range
        r_recommended = max(r_min, min(r_max, r_theoretical))
        recirc_flow = flow_m3_h * r_recommended
        no3_load_kg_d = no3_out * recirc_flow * 24.0 / 1e6
        return {
            "recirculation_ratio_recommended": round(r_recommended, 2),
            "recirculation_flow_m3_h": round(recirc_flow, 1),
            "no3_return_load_kgN_d": round(no3_load_kg_d, 2),
        }

    def optimize_dosing(
        self, tp_in: float, tp_target: float, tp_bio_removal_est: float,
        flow_m3_h: float, temp_c: float,
    ) -> Dict[str, Any]:
        """化学除磷投加量优化"""
        reagent = self.dosing_cfg.get("reagent", "PAC")
        al_p_ratio = self.dosing_cfg.get("al_p_molar_ratio", 2.0)
        safety_factor = self.dosing_cfg.get("safety_factor", 1.2)
        tp_residual = max(0, tp_in - tp_bio_removal_est)
        tp_chem_need = max(0, tp_residual - tp_target)
        if tp_chem_need <= 0:
            return {"reagent": reagent, "dose_mg_l": 0.0, "reason": "生物除磷已满足目标"}
        al_demand = tp_chem_need * (26.98 / 30.97) * al_p_ratio * safety_factor
        al_content_pct = self.dosing_cfg.get("al_content_pct", 15.8)
        dose_mg_l = al_demand / (al_content_pct / 100.0)
        max_dose = self.dosing_cfg.get("max_dose_mg_l", 50.0)
        dose_mg_l = max(0, min(max_dose, dose_mg_l))
        dose_kg_d = dose_mg_l * flow_m3_h * 24.0 / 1e6
        return {
            "reagent": reagent, "dose_mg_l": round(dose_mg_l, 2),
            "dose_kg_d": round(dose_kg_d, 3),
            "tp_chem_need_mg_l": round(tp_chem_need, 2),
            "reason": f"需化学除磷{tp_chem_need:.1f}mg/L",
        }

    def check_environment(
        self, do_actual: float, orp_actual: float, temp_c: float,
        hrt_actual_h: float, srt_actual_d: float,
    ) -> Dict[str, Any]:
        """综合环境约束校验"""
        violations = []
        if do_actual < self.do_target_range[0]:
            violations.append(f"DO={do_actual}<{self.do_target_range[0]}mg/L")
        if do_actual > self.do_target_range[1]:
            violations.append(f"DO={do_actual}>{self.do_target_range[1]}mg/L")
        if orp_actual < self.orp_range[0] or orp_actual > self.orp_range[1]:
            violations.append(f"ORP={orp_actual}mV不在{self.orp_range}范围")
        if hrt_actual_h < self.hrt_range[0] or hrt_actual_h > self.hrt_range[1]:
            violations.append(f"HRT={hrt_actual_h}h不在{self.hrt_range}范围")
        if srt_actual_d < self.srt_range[0] or srt_actual_d > self.srt_range[1]:
            violations.append(f"SRT={srt_actual_d}d不在{self.srt_range}范围")
        return {
            "stage": "aerobic", "compliant": len(violations) == 0,
            "violations": violations,
        }

    def export_parameters(
        self, aeration_result: Dict, dosing_result: Dict,
        mixing_result: Dict, recirculation_result: Dict,
        volume_m3: float, temp_c: float,
    ) -> Dict[str, Any]:
        """导出好氧段所有调整参数"""
        return {
            "stage": "aerobic", "volume_m3": volume_m3, "temp_c": temp_c,
            "aeration": {
                "do_setpoint_mg_l": aeration_result.get("target_do_mg_l", 2.0),
                "fan_hz": aeration_result.get("recommended_fan_hz", 35),
                "our_total_kgO2_d": aeration_result.get("our_breakdown", {}).get("our_total_kgO2_d", 0),
            },
            "dosing": {"dose_mg_l": dosing_result.get("dose_mg_l", 0)},
            "recirculation": {"ratio": recirculation_result.get("recirculation_ratio_recommended", 3.0)},
        }

    # ─── 私有方法 ─────────────────────────────────────────────

    @staticmethod
    def _do_saturation(temp_c: float) -> float:
        """DO 饱和浓度 (mg/L) — Benson & Krause 1984 经验公式"""
        t = temp_c
        return 14.62 - 0.3898 * t + 0.006969 * t ** 2 - 5.897e-5 * t ** 3

    @staticmethod
    def _pid_step_static(
        error: float, integral: float, last_error: float,
        kp: float, ki: float, kd: float,
        out_min: float, out_max: float,
    ) -> tuple:
        """无状态 PID 单步 — 返回 (output, new_integral, error)"""
        new_integral = max(-20, min(20, integral + error))
        derivative = error - last_error
        output = kp * error + ki * new_integral + kd * derivative
        return (max(out_min, min(out_max, output)), new_integral, error)
