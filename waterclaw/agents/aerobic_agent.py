"""
好氧工艺智能体 (Aerobic Process Agent)
只负责获取工况数据供 LLM 推理，不做机理计算。
机理计算交给 StageCalculator，本 Agent 不导入任何 Model。
"""
import json
import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime


class AerobicProcessAgent:
    """AAO 工艺好氧段智能体 — 纯工况感知"""

    def __init__(self, scada_base_url: str, agent_id: str = "aerobic_process"):
        self.scada_base_url = scada_base_url.rstrip('/')
        self.agent_id = agent_id
        self.last_snapshot = None
        self.last_verification = None

    def get_stage_status(self) -> Dict[str, Any]:
        """
        返回好氧段当前工况的结构化数据，供 OpenCLAW LLM 推理调控建议。
        包含：水质、DO、曝气状态、回流比等。
        LLM 根据这些数据自主推理出 DO 设定值、风机频率、化学除磷投加等建议。
        """
        ts = datetime.utcnow().isoformat()
        try:
            snapshot = self._get_snapshot()
            self.last_snapshot = snapshot
            wq = snapshot.get('water_quality', {})
            reactor = snapshot.get('reactor', {})

            return {
                'agent_id': self.agent_id,
                'skill': 'get_stage_status',
                'timestamp': ts,
                'stage': 'aerobic',
                'current_water_quality': {
                    'nh3_n_in_mg_l': wq.get('nh3_n_in_mg_l', 20),
                    'nh3_n_target_mg_l': wq.get('nh3_n_target_mg_l', 3),
                    'no3_n_in_mg_l': wq.get('no3_n_in_mg_l', 0.5),
                    'tp_in_mg_l': wq.get('tp_in_mg_l', 4),
                    'tp_target_mg_l': wq.get('tp_target_mg_l', 0.5),
                    'cod_in_mg_l': wq.get('cod_in_mg_l', 80),
                    'cod_out_mg_l': wq.get('cod_out_mg_l', 30),
                },
                'reactor_state': {
                    'volume_m3': reactor.get('volume_m3', 3000),
                    'flow_m3_h': reactor.get('flow_m3_h', 500),
                    'temp_c': reactor.get('temp_c', 20),
                    'do_mg_l': reactor.get('do_mg_l', 2.0),
                    'orp_mv': reactor.get('orp_mv', 150),
                    'mlss_mg_l': reactor.get('mlss_mg_l', 3500),
                    'svi_ml_g': reactor.get('svi_ml_g', 100),
                    'recirculation_ratio': reactor.get('recirculation_ratio', 3.0),
                    'srt_d': reactor.get('srt_d', 15),
                },
                'aeration_state': snapshot.get('aeration', {}),
                'data_source': snapshot.get('source', 'unknown'),
            }
        except Exception as e:
            return {'agent_id': self.agent_id, 'skill': 'get_stage_status',
                    'timestamp': ts, 'error': str(e)}

    def get_verification_summary(self) -> Optional[Dict[str, Any]]:
        if self.last_verification:
            return {
                'agent_id': self.agent_id,
                'last_skill': self.last_verification['skill'],
                'last_timestamp': self.last_verification['timestamp'],
                'result': self.last_verification['result'],
            }
        return None

    def get_tools(self) -> Dict[str, Any]:
        return {
            'agent_id': self.agent_id,
            'name': 'Aerobic Process Agent',
            'description': '好氧段感知智能体，获取工况数据供 LLM 推理 DO控制/化学除磷/回流建议',
            'skills': [
                {'name': 'get_stage_status', 'description': '获取好氧段当前工况(供LLM推理)',
                 'parameters': [], 'returns': 'stage_status'},
            ],
        }

    def _get_snapshot(self) -> Dict[str, Any]:
        try:
            url = f"{self.scada_base_url}/api/v1/process_stage/aerobic/snapshot"
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get('ok'):
                return data.get('data', {})
            raise Exception(f"API error: {data.get('error')}")
        except requests.exceptions.RequestException:
            return self._load_mock_snapshot()

    def _load_mock_snapshot(self) -> Dict[str, Any]:
        return {
            'source': 'mock',
            'domain': 'aerobic',
            'water_quality': {
                'cod_in_mg_l': 80, 'cod_out_mg_l': 30,
                'nh3_n_in_mg_l': 20, 'nh3_n_target_mg_l': 3,
                'no3_n_in_mg_l': 0.5, 'tp_in_mg_l': 4,
                'tp_target_mg_l': 0.5, 'tn_in_mg_l': 35, 'tn_target_mg_l': 15,
            },
            'reactor': {
                'volume_m3': 3000, 'flow_m3_h': 500, 'temp_c': 20,
                'do_mg_l': 2.0, 'orp_mv': 150, 'mlss_mg_l': 3500,
                'mlvss_mg_l': 2600, 'hrt_h': 6, 'recirculation_ratio': 3.0,
                'svi_ml_g': 100, 'srt_d': 15,
            },
            'aeration': {
                'blower_running': True, 'frequency_hz': 40,
            },
        }
