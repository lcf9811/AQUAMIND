"""
缺氧工艺智能体 (Anoxic Process Agent)
只负责获取工况数据供 LLM 推理，不做机理计算。
机理计算交给 StageCalculator，本 Agent 不导入任何 Model。
"""
import json
import os
import requests
from typing import Dict, Any, Optional
from datetime import datetime


class AnoxicProcessAgent:
    """AAO 工艺缺氧段智能体 — 纯工况感知"""

    def __init__(self, scada_base_url: str, agent_id: str = "anoxic_process"):
        self.scada_base_url = scada_base_url.rstrip('/')
        self.agent_id = agent_id
        self.last_snapshot = None
        self.last_verification = None

    def get_stage_status(self) -> Dict[str, Any]:
        """
        返回缺氧段当前工况的结构化数据，供 OpenCLAW LLM 推理调控建议。
        LLM 根据这些数据自主推理出碳源投加、内回流比、搅拌控制等建议。
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
                'stage': 'anoxic',
                'current_water_quality': {
                    'no3_in_mg_l': wq.get('no3_in_mg_l', 15),
                    'no3_target_mg_l': wq.get('no3_target_mg_l', 3),
                    'bod_in_mg_l': wq.get('bod_in_mg_l', 100),
                    'tn_in_mg_l': wq.get('tn_in_mg_l', 35),
                    'tn_target_mg_l': wq.get('tn_target_mg_l', 15),
                    'no3_aerobic_out_mg_l': wq.get('no3_aerobic_out_mg_l', 12),
                },
                'reactor_state': {
                    'volume_m3': reactor.get('volume_m3', 1500),
                    'flow_m3_h': reactor.get('flow_m3_h', 500),
                    'temp_c': reactor.get('temp_c', 20),
                    'do_mg_l': reactor.get('do_mg_l', 0.3),
                    'orp_mv': reactor.get('orp_mv', -30),
                    'mlvss_mg_l': reactor.get('mlvss_mg_l', 2600),
                    'recirculation_ratio': reactor.get('recirculation_ratio', 3.0),
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
            'name': 'Anoxic Process Agent',
            'description': '缺氧段感知智能体，获取工况数据供 LLM 推理碳源投加/内回流/搅拌建议',
            'skills': [
                {'name': 'get_stage_status', 'description': '获取缺氧段当前工况(供LLM推理)',
                 'parameters': [], 'returns': 'stage_status'},
            ],
        }

    def _get_snapshot(self) -> Dict[str, Any]:
        try:
            url = f"{self.scada_base_url}/api/v1/process_stage/anoxic/snapshot"
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
            'domain': 'anoxic',
            'water_quality': {
                'no3_in_mg_l': 15, 'no3_target_mg_l': 3, 'bod_in_mg_l': 100,
                'tn_in_mg_l': 35, 'tn_target_mg_l': 15, 'no3_aerobic_out_mg_l': 12,
            },
            'reactor': {
                'volume_m3': 1500, 'flow_m3_h': 500, 'temp_c': 20,
                'do_mg_l': 0.3, 'orp_mv': -30, 'mlvss_mg_l': 2600,
                'recirculation_ratio': 3.0,
            },
            'mixer': {'power_kw': 5.5, 'count': 2},
        }
