"""
厌氧工艺智能体 (Anaerobic Process Agent)
只负责获取工况数据供 LLM 推理，不做机理计算。
机理计算交给 StageCalculator，本 Agent 不导入任何 Model。
"""
import json
import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime


class AnaerobicProcessAgent:
    """AAO 工艺厌氧段智能体 — 纯工况感知"""

    def __init__(self, scada_base_url: str, agent_id: str = "anaerobic_process"):
        self.scada_base_url = scada_base_url.rstrip('/')
        self.agent_id = agent_id
        self.last_snapshot = None
        self.last_verification = None

    def get_stage_status(self) -> Dict[str, Any]:
        """
        返回厌氧段当前工况的结构化数据，供 OpenCLAW LLM 推理调控建议。
        LLM 根据这些数据自主推理出碳源投加量、搅拌功率、回流比等建议。
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
                'stage': 'anaerobic',
                'current_water_quality': {
                    'cod_in_mg_l': wq.get('cod_in_mg_l', 300),
                    'bod_in_mg_l': wq.get('bod_in_mg_l', 150),
                    'tn_in_mg_l': wq.get('tn_in_mg_l', 35),
                    'tp_in_mg_l': wq.get('tp_in_mg_l', 5),
                    'nh3_n_in_mg_l': wq.get('nh3_n_in_mg_l', 25),
                    'vfa_in_mg_l': wq.get('vfa_in_mg_l', 20),
                },
                'reactor_state': {
                    'volume_m3': reactor.get('volume_m3', 800),
                    'flow_m3_h': reactor.get('flow_m3_h', 500),
                    'temp_c': reactor.get('temp_c', 20),
                    'do_mg_l': reactor.get('do_mg_l', 0.1),
                    'orp_mv': reactor.get('orp_mv', -180),
                    'mlss_mg_l': reactor.get('mlss_mg_l', 3500),
                    'rass_mg_l': reactor.get('rass_mg_l', 8000),
                    'return_ratio_pct': reactor.get('return_ratio_pct', 75),
                },
                'mixer_state': snapshot.get('mixer', {}),
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
            'name': 'Anaerobic Process Agent',
            'description': '厌氧段感知智能体，获取工况数据供 LLM 推理碳源投加/搅拌/回流建议',
            'skills': [
                {'name': 'get_stage_status', 'description': '获取厌氧段当前工况(供LLM推理)',
                 'parameters': [], 'returns': 'stage_status'},
            ],
        }

    def _get_snapshot(self) -> Dict[str, Any]:
        try:
            url = f"{self.scada_base_url}/api/v1/process_stage/anaerobic/snapshot"
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
            'domain': 'anaerobic',
            'water_quality': {
                'cod_in_mg_l': 300, 'bod_in_mg_l': 150, 'tn_in_mg_l': 35,
                'tp_in_mg_l': 5, 'vfa_in_mg_l': 20, 'tn_target_mg_l': 15,
            },
            'reactor': {
                'volume_m3': 800, 'flow_m3_h': 500, 'temp_c': 20,
                'do_mg_l': 0.1, 'orp_mv': -180, 'mlss_mg_l': 3500,
                'rass_mg_l': 8000, 'return_ratio_pct': 75,
            },
            'mixer': {'power_kw': 3.0, 'count': 2},
        }
