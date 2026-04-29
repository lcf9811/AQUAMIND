"""
厌氧池机理模型 — 基于 SUMO1.xlsm Gujer 矩阵
核心反应过程 (来自 SUMO Model Sheet):
  r5/r6 : SB 发酵 (OHO 厌氧生长, 高/低 VFA)
  r9    : OHO 厌氧衰减
  r19   : PAO 储 PHA + 释磷
  r20   : GAO 储 PHA
  r25/r26: SB 发酵 (PAO 厌氧生长, 高/低 VFA)
  r28   : CASTO 厌氧衰减
  r29   : ORP 滞后开关

关键切换函数 (Monod/Logistic):
  Msat(S, K)  = S / (S + K)          — 底物饱和
  Minh(S, K)  = K / (S + K)          — 底物抑制
  Logsat/Loginh                       — 逻辑斯谛切换

环境约束:
  DO < 0.2 mg/L, ORP -250~-100 mV, HRT 1~2 h
"""

import math
from typing import Dict, Any, Optional


# ─────────── SUMO 动力学参数 (默认值来自 SUMO1.xlsm Parameters Sheet) ──────
SUMO_PARAMS_ANAEROBIC = {
    # OHO 发酵动力学
    "mu_FERM_OHO":   0.3,     # d⁻¹ 发酵生长速率
    "theta_FERM_OHO": 1.04,   # Arrhenius 温度系数
    "Y_OHO_SB_ana":  0.1,     # 厌氧条件下 OHO 基质产率
    "Y_OHO_H2_high": 0.35,   # 高 VFA 发酵 H2 产率
    "Y_OHO_H2_low":  0.1,    # 低 VFA 发酵 H2 产率
    "K_SB_ana":      5.0,     # SB 半饱和常数 (mgCOD/L)
    "K_VFA_FERM":    50.0,    # 发酵 VFA 半饱和切换阈值
    "Logrange_VFA_FERM": 0.012, # VFA 逻辑斯谛切换有效范围

    # OHO 衰减
    "b_OHO":         0.62,    # d⁻¹ OHO 衰减速率
    "theta_b_OHO":   1.03,    # 衰减 Arrhenius 系数
    "eta_b_OHO_ana": 0.33,    # 厌氧衰减折减系数

    # CASTO/PAO 储碳动力学
    "q_PAO_PHA":     7.0,     # d⁻¹ PAO PHA 储存速率
    "theta_q_PAO_PHA": 1.04,
    "q_GAO_PHA":     4.0,     # d⁻¹ GAO PHA 储存速率
    "theta_q_GAO_PHA": 1.072,
    "K_VFA_CASTO":   5.0,     # VFA 半饱和 (CASTO)

    # PAO 发酵
    "mu_FERM_PAO":   0.45,    # d⁻¹ PAO 发酵速率
    "theta_FERM_PAO": 1.04,

    # CASTO 衰减
    "b_CASTO":       0.08,    # d⁻¹
    "theta_b_CASTO": 1.03,
    "eta_b_CASTO_ana": 0.25,  # 厌氧衰减折减

    # PP 释放 (厌氧维护)
    "b_PP_ana":      0.005,   # d⁻¹ 厌氧条件下 PP 释放速率
    "theta_b_PP_ana": 1.03,

    # 公共 Monod 切换参数
    "K_O2_OHO":      0.15,    # mgO2/L  OHO O2 半饱和
    "K_O2_CASTO":    0.05,    # mgO2/L  CASTO O2 半饱和
    "K_NOx_OHO":     0.03,    # mgN/L   OHO NOx 半饱和
    "K_NOx_CASTO":   0.03,    # mgN/L   CASTO NOx 半饱和
    "K_NHx_BIO":     0.05,    # mgN/L   生物 NHx 半饱和
    "K_PO4_BIO":     0.01,    # mgP/L   生物 PO4 半饱和

    # 化学计量
    "f_E":           0.08,    # 内源产物分数
    "i_N_BIO":       0.07,    # 生物体 N 含量 (gN/gCOD)
    "i_N_XE":        0.06,    # 内源产物 N 含量
    "i_P_BIO":       0.02,    # 生物体 P 含量 (gP/gCOD)

    # ORP 切换 (PAO/GAO 活性)
    "LogsatORP_PAO_Half": -200,  # mV
    "LogsatORP_PAO_Slope": 0.1,
    "LogsatORP_GAO_Half_15": -120,
    "LogsatORP_GAO_Half_25": -170,
    "LogsatORP_GAO_Slope": 0.02,

    # Arrhenius 基准温度
    "T_base": 20.0,

    # 典型生物量浓度 (mgCOD/L, 可从 MLSS 估算)
    "X_OHO_default":   2000.0,
    "X_CASTO_default":  500.0,
    "X_PAO_default":    300.0,
    "X_GAO_default":    200.0,
}


class AnaerobicModel:
    """AAO 工艺厌氧段机理计算器 — SUMO Gujer 矩阵驱动"""

    def __init__(self, params: Dict[str, Any]):
        self.cfg = params
        self.dosing_cfg = params.get("dosing", {})
        self.hrt_range = params.get("hrt_h", [1.0, 2.0])
        self.do_max = params.get("do_max_mg_l", 0.2)
        self.orp_range = params.get("orp_range_mv", [-250, -100])
        self.mix_power_range = params.get("mixing_power_w_m3", [3, 8])

        # 合并 SUMO 参数 (允许 yaml 覆盖默认值)
        self.sp = dict(SUMO_PARAMS_ANAEROBIC)
        sumo_override = params.get("sumo_kinetics", {})
        self.sp.update(sumo_override)

    # ═══════════════════════════════════════════════════════════
    #  SUMO Monod 切换函数
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _msat(S: float, K: float) -> float:
        """Monod 饱和切换: S/(S+K)"""
        return S / (S + K) if (S + K) > 0 else 0.0

    @staticmethod
    def _minh(S: float, K: float) -> float:
        """Monod 抑制切换: K/(S+K)"""
        return K / (S + K) if (S + K) > 0 else 1.0

    @staticmethod
    def _logsat(S: float, K_half: float, slope: float) -> float:
        """逻辑斯谛饱和切换"""
        x = slope * (S - K_half)
        x = max(-50, min(50, x))
        return 1.0 / (1.0 + math.exp(-x))

    @staticmethod
    def _loginh(S: float, K_half: float, slope: float) -> float:
        """逻辑斯谛抑制切换"""
        x = slope * (S - K_half)
        x = max(-50, min(50, x))
        return 1.0 / (1.0 + math.exp(x))

    def _arrhenius(self, rate_20: float, theta: float, temp_c: float) -> float:
        """Arrhenius 温度校正: rate_T = rate_20 * theta^(T - T_base)"""
        return rate_20 * theta ** (temp_c - self.sp["T_base"])

    # ═══════════════════════════════════════════════════════════
    #  核心: SUMO 厌氧生化模拟
    # ═══════════════════════════════════════════════════════════

    def simulate_biochemistry(
        self,
        S_VFA: float,       # 挥发性脂肪酸 (mgCOD/L)
        S_B: float,         # 易降解基质 (mgCOD/L)
        S_NHx: float,       # 氨氮 NH3-N (mg/L)
        S_NOx: float,       # 硝氮 NO3-N (mg/L)
        S_PO4: float,       # 正磷酸盐 (mgP/L)
        S_O2: float,        # 溶解氧 (mg/L)
        ORP: float,         # 氧化还原电位 (mV)
        temp_c: float,      # 温度 (°C)
        X_OHO: Optional[float] = None,   # OHO 生物量 (mgCOD/L)
        X_CASTO: Optional[float] = None, # CASTO 生物量
        X_PAO: Optional[float] = None,   # PAO 生物量
        X_GAO: Optional[float] = None,   # GAO 生物量
        hrt_h: float = 1.5,              # 水力停留时间 (h)
        volume_m3: float = 1000.0,       # 池容
    ) -> Dict[str, Any]:
        """
        基于 SUMO Gujer 矩阵计算厌氧段生化反应速率和浓度变化

        返回: 各反应速率、浓度变化量、出水预测浓度
        """
        sp = self.sp
        dt_total = hrt_h / 24.0  # 总时间步长 (天)
        n_steps = 20  # 子步迭代避免 Euler 过冲
        dt_d = dt_total / n_steps

        # 默认生物量
        X_OHO = X_OHO or sp["X_OHO_default"]
        X_CASTO = X_CASTO or sp["X_CASTO_default"]
        X_PAO = X_PAO or sp["X_PAO_default"]
        X_GAO = X_GAO or sp["X_GAO_default"]

        # ─── 温度校正后的速率 ───
        mu_ferm_T = self._arrhenius(sp["mu_FERM_OHO"], sp["theta_FERM_OHO"], temp_c)
        b_OHO_T = self._arrhenius(sp["b_OHO"], sp["theta_b_OHO"], temp_c)
        q_PAO_PHA_T = self._arrhenius(sp["q_PAO_PHA"], sp["theta_q_PAO_PHA"], temp_c)
        q_GAO_PHA_T = self._arrhenius(sp["q_GAO_PHA"], sp["theta_q_GAO_PHA"], temp_c)
        mu_ferm_PAO_T = self._arrhenius(sp["mu_FERM_PAO"], sp["theta_FERM_PAO"], temp_c)
        b_CASTO_T = self._arrhenius(sp["b_CASTO"], sp["theta_b_CASTO"], temp_c)
        b_PP_ana_T = self._arrhenius(sp["b_PP_ana"], sp["theta_b_PP_ana"], temp_c)

        # ─── 公共 Monod 切换 ───
        sw_inh_O2_OHO = self._minh(S_O2, sp["K_O2_OHO"])     # DO 抑制 (厌氧需 DO 低)
        sw_inh_O2_CASTO = self._minh(S_O2, sp["K_O2_CASTO"])
        sw_inh_NOx_OHO = self._minh(S_NOx, sp["K_NOx_OHO"])   # NOx 抑制 (厌氧需无 NOx)
        sw_inh_NOx_CASTO = self._minh(S_NOx, sp["K_NOx_CASTO"])
        sw_sat_SB = self._msat(S_B, sp["K_SB_ana"])           # SB 底物饱和
        sw_sat_NHx = self._msat(S_NHx, sp["K_NHx_BIO"])
        sw_sat_PO4 = self._msat(S_PO4, sp["K_PO4_BIO"])
        sw_sat_VFA_CASTO = self._msat(S_VFA, sp["K_VFA_CASTO"])

        # ORP 活性切换 (PAO/GAO)
        act_PAO_ORP = self._logsat(ORP, sp["LogsatORP_PAO_Half"], sp["LogsatORP_PAO_Slope"])
        # GAO ORP 切换 (温度插值)
        orp_half_GAO = sp["LogsatORP_GAO_Half_15"] + (
            sp["LogsatORP_GAO_Half_25"] - sp["LogsatORP_GAO_Half_15"]
        ) * (temp_c - 15.0) / 10.0
        act_GAO_ORP = self._logsat(ORP, orp_half_GAO, sp["LogsatORP_GAO_Slope"])

        # VFA 高/低切换 (发酵)
        sw_logsat_VFA = self._logsat(S_VFA, sp["K_VFA_FERM"], sp["Logrange_VFA_FERM"])
        sw_loginh_VFA = 1.0 - sw_logsat_VFA

        # ─── 反应速率计算 (mgCOD/L/d) ───

        # r5: SB 发酵 高 VFA (OHO, 厌氧)
        rho_5 = (mu_ferm_T * X_OHO * sw_logsat_VFA * sw_sat_SB
                 * sw_inh_O2_OHO * sw_inh_NOx_OHO * sw_sat_NHx * sw_sat_PO4)

        # r6: SB 发酵 低 VFA (OHO, 厌氧)
        rho_6 = (mu_ferm_T * X_OHO * sw_loginh_VFA * sw_sat_SB
                 * sw_inh_O2_OHO * sw_inh_NOx_OHO * sw_sat_NHx * sw_sat_PO4)

        # r9: OHO 厌氧衰减
        rho_9 = b_OHO_T * sp["eta_b_OHO_ana"] * X_OHO * sw_inh_O2_OHO * sw_inh_NOx_OHO

        # r19: PAO PHA 储存 + 释磷
        rho_19 = q_PAO_PHA_T * X_PAO * act_PAO_ORP * sw_sat_VFA_CASTO * sw_inh_O2_CASTO * sw_inh_NOx_CASTO

        # r20: GAO PHA 储存
        rho_20 = q_GAO_PHA_T * X_GAO * act_GAO_ORP * sw_sat_VFA_CASTO * sw_inh_O2_CASTO * sw_inh_NOx_CASTO

        # r25: PAO 发酵 高 VFA
        rho_25 = (mu_ferm_PAO_T * X_PAO * act_PAO_ORP * sw_logsat_VFA
                  * sw_sat_SB * sw_sat_NHx * sw_sat_PO4
                  * sw_inh_O2_CASTO * sw_inh_NOx_CASTO)

        # r26: PAO 发酵 低 VFA
        rho_26 = (mu_ferm_PAO_T * X_PAO * act_PAO_ORP * sw_loginh_VFA
                  * sw_sat_SB * sw_sat_NHx * sw_sat_PO4
                  * sw_inh_O2_CASTO * sw_inh_NOx_CASTO)

        # r28: CASTO 厌氧衰减
        rho_28 = b_CASTO_T * sp["eta_b_CASTO_ana"] * X_CASTO * sw_inh_O2_CASTO * sw_inh_NOx_CASTO

        # r24: PP 厌氧释放 (维护)
        rho_24 = b_PP_ana_T * X_PAO * sw_inh_O2_CASTO * sw_inh_NOx_CASTO

        # ─── 化学计量: 浓度变化量 (mg/L/d) ───
        Y = sp["Y_OHO_SB_ana"]
        fE = sp["f_E"]
        iN_BIO = sp["i_N_BIO"]
        iN_XE = sp["i_N_XE"]
        iP_BIO = sp["i_P_BIO"]

        # S_VFA 变化: r5产生 + r6产生 - r19消耗 - r20消耗 + r25产生 + r26产生
        Y_h2_high = sp["Y_OHO_H2_high"]
        Y_h2_low = sp["Y_OHO_H2_low"]
        dVFA_r5 = (1.0 - Y - Y_h2_high) / Y * rho_5    # 发酵产 VFA
        dVFA_r6 = (1.0 - Y - Y_h2_low) / Y * rho_6
        dVFA_r19 = -1.0 * rho_19   # PAO 消耗 VFA
        dVFA_r20 = -1.0 * rho_20   # GAO 消耗 VFA
        dVFA_r25 = (1.0 - Y - Y_h2_high) / Y * rho_25
        dVFA_r26 = (1.0 - Y - Y_h2_low) / Y * rho_26
        dS_VFA = dVFA_r5 + dVFA_r6 + dVFA_r19 + dVFA_r20 + dVFA_r25 + dVFA_r26

        # S_B 变化: 被发酵消耗
        dS_B = -(1.0 / Y) * (rho_5 + rho_6 + rho_25 + rho_26)

        # S_NHx 变化: 生物量合成消耗 + 衰减释放
        dNHx_growth = -iN_BIO * (rho_5 + rho_6 + rho_25 + rho_26)
        dNHx_decay = -fE * (iN_XE - iN_BIO) * (rho_9 + rho_28)
        dS_NHx = dNHx_growth + dNHx_decay

        # S_NOx: 厌氧段基本无变化 (无硝化, 无反硝化)
        dS_NOx = 0.0

        # S_PO4 变化: PAO 释磷 (r19 PP释放 + r24 维护释放)
        # SUMO 中 r19 每消耗 1 gCOD VFA 释放约 0.4 gP (经验值)
        po4_release_per_pha = 0.4  # gP/gCOD_VFA
        dS_PO4 = abs(dVFA_r19) * po4_release_per_pha + rho_24 * 0.1

        # ─── 子步迭代积分 ───
        S_VFA_cur, S_B_cur, S_NHx_cur = S_VFA, S_B, S_NHx
        S_NOx_cur, S_PO4_cur = S_NOx, S_PO4
        for _ in range(n_steps):
            # 重新计算 Monod 切换 (使用当前浓度)
            sw_sb_i = self._msat(S_B_cur, sp["K_SB_ana"])
            sw_vfa_i = self._msat(S_VFA_cur, sp["K_VFA_CASTO"])
            sw_nhx_i = self._msat(S_NHx_cur, sp["K_NHx_BIO"])
            sw_logsat_i = self._logsat(S_VFA_cur, sp["K_VFA_FERM"], sp["Logrange_VFA_FERM"])
            sw_loginh_i = 1.0 - sw_logsat_i

            rr5 = mu_ferm_T * X_OHO * sw_logsat_i * sw_sb_i * sw_inh_O2_OHO * sw_inh_NOx_OHO * sw_nhx_i
            rr6 = mu_ferm_T * X_OHO * sw_loginh_i * sw_sb_i * sw_inh_O2_OHO * sw_inh_NOx_OHO * sw_nhx_i
            rr19 = q_PAO_PHA_T * X_PAO * act_PAO_ORP * sw_vfa_i * sw_inh_O2_CASTO * sw_inh_NOx_CASTO
            rr20 = q_GAO_PHA_T * X_GAO * act_GAO_ORP * sw_vfa_i * sw_inh_O2_CASTO * sw_inh_NOx_CASTO
            rr25 = mu_ferm_PAO_T * X_PAO * act_PAO_ORP * sw_logsat_i * sw_sb_i * sw_nhx_i * sw_inh_O2_CASTO * sw_inh_NOx_CASTO
            rr26 = mu_ferm_PAO_T * X_PAO * act_PAO_ORP * sw_loginh_i * sw_sb_i * sw_nhx_i * sw_inh_O2_CASTO * sw_inh_NOx_CASTO

            dVFA_i = ((1-Y-Y_h2_high)/Y*rr5 + (1-Y-Y_h2_low)/Y*rr6 - rr19 - rr20
                      + (1-Y-Y_h2_high)/Y*rr25 + (1-Y-Y_h2_low)/Y*rr26)
            dSB_i = -(1.0/Y) * (rr5 + rr6 + rr25 + rr26)
            dNHx_i = -iN_BIO * (rr5 + rr6 + rr25 + rr26)
            dPO4_i = abs(rr19) * po4_release_per_pha + rho_24 * 0.1

            S_VFA_cur = max(0, S_VFA_cur + dVFA_i * dt_d)
            S_B_cur = max(0, S_B_cur + dSB_i * dt_d)
            S_NHx_cur = max(0, S_NHx_cur + dNHx_i * dt_d)
            S_PO4_cur = max(0, S_PO4_cur + dPO4_i * dt_d)

        S_VFA_out = S_VFA_cur
        S_B_out = S_B_cur
        S_NHx_out = S_NHx_cur
        S_NOx_out = max(0, S_NOx)  # 厌氧段 NOx 基本不变
        S_PO4_out = S_PO4_cur

        return {
            "stage": "anaerobic",
            "temp_c": temp_c,
            "hrt_h": hrt_h,
            "reaction_rates": {
                "rho_5_ferm_highVFA": round(rho_5, 4),
                "rho_6_ferm_lowVFA": round(rho_6, 4),
                "rho_9_OHO_decay": round(rho_9, 4),
                "rho_19_PAO_PHA_store": round(rho_19, 4),
                "rho_20_GAO_PHA_store": round(rho_20, 4),
                "rho_25_PAO_ferm_high": round(rho_25, 4),
                "rho_26_PAO_ferm_low": round(rho_26, 4),
                "rho_28_CASTO_decay": round(rho_28, 4),
                "rho_24_PP_release": round(rho_24, 4),
            },
            "switching_functions": {
                "sw_inh_O2_OHO": round(sw_inh_O2_OHO, 4),
                "sw_inh_O2_CASTO": round(sw_inh_O2_CASTO, 4),
                "sw_inh_NOx_OHO": round(sw_inh_NOx_OHO, 4),
                "sw_inh_NOx_CASTO": round(sw_inh_NOx_CASTO, 4),
                "act_PAO_ORP": round(act_PAO_ORP, 4),
                "act_GAO_ORP": round(act_GAO_ORP, 4),
                "sw_sat_SB": round(sw_sat_SB, 4),
            },
            "concentration_changes_per_day": {
                "dS_VFA_mgCOD_L_d": round(dS_VFA, 3),
                "dS_B_mgCOD_L_d": round(dS_B, 3),
                "dS_NHx_mgN_L_d": round(dS_NHx, 4),
                "dS_NOx_mgN_L_d": round(dS_NOx, 4),
                "dS_PO4_mgP_L_d": round(dS_PO4, 4),
            },
            "effluent_prediction": {
                "S_VFA_out_mgCOD_L": round(S_VFA_out, 2),
                "S_B_out_mgCOD_L": round(S_B_out, 2),
                "nh3_n_out_mg_l": round(S_NHx_out, 2),
                "no3_n_out_mg_l": round(S_NOx_out, 2),
                "S_PO4_out_mgP_L": round(S_PO4_out, 2),
            },
            "sumo_params_used": {
                "mu_FERM_OHO_T": round(mu_ferm_T, 4),
                "b_OHO_T": round(b_OHO_T, 4),
                "q_PAO_PHA_T": round(q_PAO_PHA_T, 4),
                "q_GAO_PHA_T": round(q_GAO_PHA_T, 4),
                "Y_OHO_SB_ana": Y,
            },
        }

    # ═══════════════════════════════════════════════════════════
    #  操作控制方法 (保留原有能力, 与 SUMO 模拟互补)
    # ═══════════════════════════════════════════════════════════

    def optimize_dosing(
        self, cod_in: float, bod_in: float, tn_in: float, tp_in: float,
        vfa_in: float, flow_m3_h: float, temp_c: float, volume_m3: float,
    ) -> Dict[str, Any]:
        """碳源投加量优化 — BOD5/TN 比 + VFA/TP 比判断"""
        cn_ratio = bod_in / tn_in if tn_in > 0 else float("inf")
        cn_target = self.dosing_cfg.get("cn_ratio_target", 4.0)
        vfa_tp_ratio = vfa_in / tp_in if tp_in > 0 else float("inf")
        vfa_tp_min = self.cfg.get("vfa_tp_ratio_min", 4.0)
        carbon_source = self.dosing_cfg.get("carbon_source", "sodium_acetate")
        cod_equivalents = {"sodium_acetate": 0.78, "methanol": 1.5, "glucose": 1.07, "acetic_acid": 1.07}
        cod_equiv = cod_equivalents.get(carbon_source, 0.78)

        dose_mg_l = 0.0
        dose_reason = "碳源充足, 无需投加"
        if cn_ratio < cn_target:
            bod_deficit = (cn_target - cn_ratio) * tn_in
            dose_mg_l = bod_deficit / cod_equiv
            dose_reason = f"C/N={cn_ratio:.1f}<{cn_target}, 需补充碳源"
        vfa_sufficient = vfa_tp_ratio >= vfa_tp_min
        if not vfa_sufficient and dose_mg_l == 0:
            vfa_deficit = vfa_tp_min * tp_in - vfa_in
            dose_mg_l = max(dose_mg_l, vfa_deficit / cod_equiv)
            dose_reason = f"VFA/TP={vfa_tp_ratio:.1f}<{vfa_tp_min}, 需补充碳源促释磷"

        temp_factor = self.sp["theta_FERM_OHO"] ** (20.0 - temp_c)
        dose_mg_l *= temp_factor
        max_dose = self.dosing_cfg.get("max_dose_mg_l", 100.0)
        min_dose = self.dosing_cfg.get("min_dose_mg_l", 0.0)
        dose_mg_l = max(min_dose, min(max_dose, dose_mg_l))
        dose_kg_d = dose_mg_l * flow_m3_h * 24.0 / 1e6

        return {
            "carbon_source": carbon_source, "dose_mg_l": round(dose_mg_l, 2),
            "dose_kg_d": round(dose_kg_d, 3), "cn_ratio_actual": round(cn_ratio, 2),
            "cn_ratio_target": cn_target, "vfa_tp_ratio": round(vfa_tp_ratio, 2),
            "vfa_sufficient": vfa_sufficient, "temp_correction_factor": round(temp_factor, 3),
            "reason": dose_reason,
        }

    def optimize_mixing(
        self, volume_m3: float, do_actual: float, orp_actual: float,
        mixer_power_kw: float, mixer_count: int = 1, temp_c: float = 20.0,
    ) -> Dict[str, Any]:
        """搅拌强度优化 — 功率密度 3~8 W/m³"""
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
            recommendations.append(f"DO={do_actual}mg/L超过厌氧上限{self.do_max}mg/L")
        if not orp_ok:
            recommendations.append(f"ORP={orp_actual}mV不在{self.orp_range}范围")
        recommended_power_kw = recommended_density * volume_m3 / 1000.0 / mixer_count
        return {
            "current_power_density_w_m3": round(current_density, 1),
            "recommended_power_density_w_m3": round(recommended_density, 1),
            "recommended_mixer_power_kw": round(recommended_power_kw, 2),
            "environment_check": {"do_ok": do_ok, "orp_ok": orp_ok},
            "recommendations": recommendations,
        }

    def optimize_recirculation(
        self, mlss: float, rass: float, flow_m3_h: float,
        tn_in: float, tn_target: float, volume_m3: float,
        current_return_ratio_pct: float = 75,
    ) -> Dict[str, Any]:
        """污泥回流比优化 — 浓度法: R = MLSS / (RASS - MLSS)"""
        if rass > mlss:
            r_theoretical_pct = mlss / (rass - mlss) * 100
        else:
            r_theoretical_pct = 75
        r_min, r_max = 50, 100
        recommended_pct = max(r_min, min(r_max, r_theoretical_pct))
        hrt = volume_m3 / flow_m3_h if flow_m3_h > 0 else 0
        hrt_ok = self.hrt_range[0] <= hrt <= self.hrt_range[1] if hrt > 0 else True
        return {
            "return_ratio_theoretical_pct": round(r_theoretical_pct, 1),
            "return_ratio_recommended_pct": round(recommended_pct, 1),
            "current_pct": current_return_ratio_pct,
            "reason": f"浓度法 MLSS={mlss}/RASS={rass}",
            "hrt_h": round(hrt, 2),
            "hrt_ok": hrt_ok,
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
            "stage": "anaerobic", "compliant": len(violations) == 0,
            "violations": violations,
            "parameters": {"do_mg_l": do_actual, "orp_mv": orp_actual, "temp_c": temp_c, "hrt_h": hrt_actual_h},
        }

    def export_parameters(
        self, dosing_result: Dict, mixing_result: Dict,
        recirculation_result: Dict, volume_m3: float, temp_c: float,
    ) -> Dict[str, Any]:
        """导出厌氧段所有调整参数 (用于 SUMO 输入)"""
        return {
            "stage": "anaerobic", "volume_m3": volume_m3, "temp_c": temp_c,
            "hrt_design_h": self.hrt_range, "do_setpoint_mg_l": 0.0,
            "dosing": {
                "carbon_source": dosing_result.get("carbon_source"),
                "dose_mg_l": dosing_result.get("dose_mg_l", 0),
            },
            "mixing": {"power_density_w_m3": mixing_result.get("recommended_power_density_w_m3", 5)},
            "recirculation": {
                "return_ratio_pct": recirculation_result.get("return_ratio_recommended_pct", 75),
            },
        }
