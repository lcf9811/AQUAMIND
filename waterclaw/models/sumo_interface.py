"""
SUMO 文件交互接口
实现与 Dynamita SUMO 污水处理模拟器的文件级交互:
  - export_input_file(): 导出三段参数为 SUMO 可读的 XML 文件
  - parse_output_file(): 解析 SUMO 模拟输出 CSV
  - compare_and_feedback(): 对比预测 vs SUMO, 生成偏差报告
  - generate_iteration_params(): 根据偏差自动调参, 用于自迭代
"""

import os
import csv
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Dict, Any, List, Optional


class SumoInterface:
    """SUMO 污水处理模拟器文件交互接口"""

    def __init__(self, sumo_cfg: Dict[str, Any]):
        """
        Args:
            sumo_cfg: process_stage_params.yaml -> process_stage.sumo 节点
        """
        self.output_dir = sumo_cfg.get("output_dir", "sumo_results")
        self.max_iterations = sumo_cfg.get("max_iterations", 5)
        self.convergence_pct = sumo_cfg.get("convergence_threshold_pct", 5.0)
        self.input_template = sumo_cfg.get("input_template", "sumo_input_template.xml")

    # ─── 导出输入文件 ──────────────────────────────────

    def export_input_file(
        self,
        influent: Dict[str, Any],
        anaerobic_params: Dict[str, Any],
        anoxic_params: Dict[str, Any],
        aerobic_params: Dict[str, Any],
        filepath: Optional[str] = None,
    ) -> str:
        """
        将三段调整参数导出为 SUMO 可读的 XML 输入文件

        Args:
            influent: 进水水质 {cod, bod, tn, nh3, tp, ss, flow_m3_h, temp_c}
            anaerobic_params: AnaerobicModel.export_parameters() 输出
            anoxic_params:    AnoxicModel.export_parameters() 输出
            aerobic_params:   AerobicModel.export_parameters() 输出
            filepath: 输出路径 (默认自动生成)

        Returns:
            生成的文件路径
        """
        if filepath is None:
            os.makedirs(self.output_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            filepath = os.path.join(self.output_dir, f"sumo_input_{ts}.xml")

        root = ET.Element("SumoInput")
        root.set("version", "1.0")
        root.set("generated_at", datetime.now().isoformat())
        root.set("generator", "AQUAMIND_ProcessStage")

        # -- 进水特征 --
        inf_el = ET.SubElement(root, "Influent")
        for key, val in influent.items():
            el = ET.SubElement(inf_el, key)
            el.text = str(val)

        # -- 三段工艺参数 --
        for stage_name, stage_params in [
            ("Anaerobic", anaerobic_params),
            ("Anoxic", anoxic_params),
            ("Aerobic", aerobic_params),
        ]:
            stage_el = ET.SubElement(root, stage_name)
            self._dict_to_xml(stage_el, stage_params)

        # -- 写入文件 --
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(filepath, encoding="utf-8", xml_declaration=True)

        return filepath

    # ─── 解析输出文件 ──────────────────────────────────

    def parse_output_file(self, filepath: str) -> Dict[str, Any]:
        """
        解析 SUMO 模拟输出结果

        支持两种格式:
        1. CSV 格式 (SUMO 默认导出)
        2. XML 格式

        Returns:
            解析后的结构化结果字典
        """
        if not os.path.exists(filepath):
            return {"error": f"文件不存在: {filepath}"}

        ext = os.path.splitext(filepath)[1].lower()

        if ext == ".csv":
            return self._parse_csv_output(filepath)
        elif ext in (".xml", ".sumo"):
            return self._parse_xml_output(filepath)
        elif ext == ".json":
            return self._parse_json_output(filepath)
        else:
            return {"error": f"不支持的文件格式: {ext}"}

    # ─── 偏差对比 ──────────────────────────────────────

    def compare_and_feedback(
        self,
        predicted: Dict[str, Any],
        sumo_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        对比智能体预测结果与 SUMO 模拟结果, 生成偏差报告

        Args:
            predicted: 三段智能体的汇总预测 (各段出水水质 + OUR + 泥量)
            sumo_result: parse_output_file() 返回的 SUMO 结果

        Returns:
            偏差报告 {deviations, verdict, explanations, corrections}
        """
        if "error" in sumo_result:
            return {"error": sumo_result["error"]}

        deviations = {}
        explanations = []

        # 对比关键指标
        compare_keys = [
            ("effluent_cod_mg_l", "出水COD"),
            ("effluent_nh3_mg_l", "出水NH3-N"),
            ("effluent_no3_mg_l", "出水NO3-N"),
            ("effluent_tn_mg_l", "出水TN"),
            ("effluent_tp_mg_l", "出水TP"),
            ("our_total_kgO2_d", "总需氧量"),
            ("sludge_production_kgTSS_d", "污泥产量"),
        ]

        significant_count = 0
        for key, label in compare_keys:
            pred_val = predicted.get(key)
            sumo_val = sumo_result.get(key)

            if pred_val is not None and sumo_val is not None and sumo_val != 0:
                dev_pct = abs(pred_val - sumo_val) / abs(sumo_val) * 100
                deviations[key] = {
                    "predicted": pred_val,
                    "sumo": sumo_val,
                    "deviation_pct": round(dev_pct, 1),
                    "label": label,
                }

                if dev_pct > 30:
                    significant_count += 1
                    explanations.append(
                        f"{label}: 预测{pred_val:.1f} vs SUMO{sumo_val:.1f}, "
                        f"偏差{dev_pct:.1f}% (显著偏离)"
                    )
                elif dev_pct > 15:
                    explanations.append(
                        f"{label}: 预测{pred_val:.1f} vs SUMO{sumo_val:.1f}, "
                        f"偏差{dev_pct:.1f}% (边际偏差)"
                    )

        # 整体判定
        if significant_count == 0:
            verdict = "converged"
        elif significant_count <= 2:
            verdict = "marginal"
        else:
            verdict = "divergent"

        # 生成修正建议
        corrections = self._generate_corrections(deviations)

        return {
            "verdict": verdict,
            "deviations": deviations,
            "significant_deviation_count": significant_count,
            "explanations": explanations,
            "corrections": corrections,
            "converged": verdict == "converged",
        }

    # ─── 自迭代参数生成 ────────────────────────────────

    def generate_iteration_params(
        self,
        current_params: Dict[str, Any],
        deviation_report: Dict[str, Any],
        iteration: int,
    ) -> Dict[str, Any]:
        """
        根据偏差报告自动调整参数, 用于下一轮迭代

        采用简单的比例修正策略:
        - 预测偏高 → 降低对应参数
        - 预测偏低 → 提升对应参数
        - 学习率随迭代次数递减 (避免振荡)
        """
        if deviation_report.get("converged", False):
            return {
                "converged": True,
                "iteration": iteration,
                "params": current_params,
                "message": "已收敛, 无需进一步调整",
            }

        corrections = deviation_report.get("corrections", {})
        learning_rate = 1.0 / (1.0 + iteration * 0.3)  # 递减学习率

        adjusted = json.loads(json.dumps(current_params))  # deep copy

        adjustment_log = []

        for key, correction in corrections.items():
            direction = correction.get("direction", 0)
            magnitude = correction.get("magnitude_pct", 0)
            target_param = correction.get("target_param")

            if target_param and magnitude > 0:
                adj_pct = direction * magnitude * learning_rate / 100.0

                # 在嵌套字典中找到并修改参数
                parts = target_param.split(".")
                obj = adjusted
                for part in parts[:-1]:
                    if isinstance(obj, dict) and part in obj:
                        obj = obj[part]
                    else:
                        break
                else:
                    if isinstance(obj, dict) and parts[-1] in obj:
                        old_val = obj[parts[-1]]
                        if isinstance(old_val, (int, float)):
                            new_val = old_val * (1.0 + adj_pct)
                            obj[parts[-1]] = round(new_val, 4)
                            adjustment_log.append(
                                f"{target_param}: {old_val} → {new_val:.4f} "
                                f"(adj {adj_pct*100:+.1f}%)"
                            )

        return {
            "converged": False,
            "iteration": iteration + 1,
            "learning_rate": round(learning_rate, 3),
            "params": adjusted,
            "adjustment_log": adjustment_log,
            "max_iterations": self.max_iterations,
            "should_continue": (iteration + 1) < self.max_iterations,
        }

    # ─── 私有方法 ───────────────────────────────────────

    def _dict_to_xml(self, parent: ET.Element, d: Dict) -> None:
        """递归将字典转为 XML 子元素"""
        for key, val in d.items():
            if isinstance(val, dict):
                child = ET.SubElement(parent, key)
                self._dict_to_xml(child, val)
            elif isinstance(val, (list, tuple)):
                child = ET.SubElement(parent, key)
                child.text = ",".join(str(v) for v in val)
            else:
                child = ET.SubElement(parent, key)
                child.text = str(val)

    def _parse_csv_output(self, filepath: str) -> Dict[str, Any]:
        """解析 SUMO CSV 输出"""
        result = {}
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                if rows:
                    # 取最后一行 (稳态结果)
                    last = rows[-1]
                    # 标准化字段名映射
                    field_map = {
                        "COD_eff": "effluent_cod_mg_l",
                        "NH3_eff": "effluent_nh3_mg_l",
                        "NO3_eff": "effluent_no3_mg_l",
                        "TN_eff": "effluent_tn_mg_l",
                        "TP_eff": "effluent_tp_mg_l",
                        "OUR_total": "our_total_kgO2_d",
                        "Sludge_prod": "sludge_production_kgTSS_d",
                        "MLSS": "mlss_mg_l",
                        "SRT": "srt_days",
                    }
                    for csv_key, std_key in field_map.items():
                        if csv_key in last:
                            try:
                                result[std_key] = float(last[csv_key])
                            except (ValueError, TypeError):
                                pass
                    result["raw_data"] = last
                    result["total_rows"] = len(rows)
        except Exception as e:
            result["error"] = str(e)
        return result

    def _parse_xml_output(self, filepath: str) -> Dict[str, Any]:
        """解析 SUMO XML 输出"""
        result = {}
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()

            # 提取出水水质
            effluent = root.find(".//Effluent")
            if effluent is not None:
                for child in effluent:
                    try:
                        result[f"effluent_{child.tag.lower()}_mg_l"] = float(child.text)
                    except (ValueError, TypeError):
                        pass

            # 提取 OUR
            our_el = root.find(".//OUR")
            if our_el is not None and our_el.text:
                result["our_total_kgO2_d"] = float(our_el.text)

            # 提取污泥产量
            sludge_el = root.find(".//SludgeProduction")
            if sludge_el is not None and sludge_el.text:
                result["sludge_production_kgTSS_d"] = float(sludge_el.text)

        except Exception as e:
            result["error"] = str(e)
        return result

    def _parse_json_output(self, filepath: str) -> Dict[str, Any]:
        """解析 JSON 格式输出 (用于测试 mock)"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"error": str(e)}

    def _generate_corrections(self, deviations: Dict) -> Dict[str, Any]:
        """根据偏差生成参数修正建议"""
        corrections = {}

        for key, dev in deviations.items():
            dev_pct = dev.get("deviation_pct", 0)
            predicted = dev.get("predicted", 0)
            sumo = dev.get("sumo", 0)

            if dev_pct <= 5:
                continue  # 偏差可接受

            direction = -1 if predicted > sumo else 1  # 预测偏高则降低

            # 映射到可调参数
            param_map = {
                "effluent_cod_mg_l": "aerobic.aeration.do_setpoint_mg_l",
                "effluent_nh3_mg_l": "aerobic.aeration.do_setpoint_mg_l",
                "effluent_no3_mg_l": "anoxic.recirculation.ratio",
                "effluent_tn_mg_l": "anoxic.recirculation.ratio",
                "effluent_tp_mg_l": "aerobic.dosing.dose_mg_l",
                "our_total_kgO2_d": "aerobic.aeration.fan_hz",
            }

            target_param = param_map.get(key)
            if target_param:
                corrections[key] = {
                    "target_param": target_param,
                    "direction": direction,
                    "magnitude_pct": min(dev_pct * 0.3, 15),  # 最大修正幅度 15%
                    "reason": f"{dev['label']}偏差{dev_pct:.1f}%",
                }

        return corrections
