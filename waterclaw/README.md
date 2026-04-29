# WaterClaw — Configurable Multi-Agent Water Quality Assistant

基于机理模型的污水处理多智能体系统，**配置驱动**，支持任意工艺段自由组合（A²O / AAOA / AOA / AO / ...）。
可在 Claude Code 中以 Skill 形式直接调用。

## 架构

```
进水数据 (SCADA / Mock / Excel)
       │
       ▼
ProcessStageAgent (编排层 — 配置驱动)
    ├── AnaerobicProcessAgent  →  厌氧段: 碳源/搅拌/回流工况感知
    ├── AnoxicProcessAgent     →  缺氧段: 碳源/搅拌/内回流工况感知
    ├── AerobicProcessAgent    →  好氧段: DO/曝气/除磷工况感知
    └── AnoxicProcessAgent     →  后缺氧段 (AAOA, 按需)
       │
       ▼
  OpenCLAW / Claude LLM 推理调控建议 (方向 + 幅度 + 置信度)
       │
       ▼
StageCalculator (独立机理参考) → DeviationAnalyzer (偏差分析) → EquipmentMapper (设备映射)
       │
       ▼
  SUMO 仿真验证 / 实际设备执行
```

**核心原则**: Agent 只推理，不计算。机理模型作为独立参考基准。

## 工艺流程自由组合

修改 `config/process_stage_params.yaml` 中的 `flow_sequence` 即可：

```yaml
# A²O (默认)
flow_sequence: [anaerobic, anoxic, aerobic]

# AAOA (4段，后置缺氧)
flow_sequence: [anaerobic, anoxic, aerobic, anoxic]

# AOA
flow_sequence: [anaerobic, aerobic, anoxic]

# 简单 AO
flow_sequence: [anaerobic, aerobic]
```

同名工艺段自动编号区分（`anoxic` / `anoxic_2`），Calculator 自动链式传递前段出水至后段进水。

## 快速部署

```bash
git clone https://github.com/Axl1Huang/waterclaw.git
cd waterclaw
pip install -r requirements.txt
```

```python
from agents.process_stage_agent import ProcessStageAgent

psa = ProcessStageAgent('http://localhost:5000')
status = psa.get_process_status()
print(status['flow_sequence'])  # ['anaerobic', 'anoxic', 'aerobic', 'anoxic']
print(list(status['stages'].keys()))  # ['anaerobic', 'anoxic', 'aerobic', 'anoxic_2']
```

## 项目结构

```
waterclaw/
├── README.md
├── requirements.txt
├── agents/                    # 工艺段感知智能体
│   ├── process_stage_agent.py # 编排层 (配置驱动)
│   ├── anaerobic_agent.py     # 厌氧段
│   ├── anoxic_agent.py        # 缺氧段
│   └── aerobic_agent.py       # 好氧段
├── models/                    # 机理模型 (独立于 Agent)
│   ├── calculator.py          # 统一机理计算 (含链式计算)
│   ├── deviation_analyzer.py  # 偏差分析
│   ├── equipment_mapper.py    # 参数 → SUMO/设备映射
│   ├── sumo_integration.py    # SUMO 文件 I/O
│   ├── sumo_validator.py      # SUMO Gujer 矩阵验证
│   ├── anaerobic_model.py     # 厌氧池机理
│   ├── anoxic_model.py        # 缺氧池机理
│   └── aerobic_model.py       # 好氧池 SUMO Gujer 矩阵 (10反应)
├── config/
│   └── process_stage_params.yaml  # 工艺流程 + 参数配置
├── mockdata/                  # 离线测试数据
└── docs/
    └── ARCHITECTURE.md        # 架构文档
```

## Skills

| Agent | Skill | 描述 |
|-------|-------|------|
| ProcessStage | `get_process_status` | 全工段工况 (按 flow_sequence) |
| ProcessStage | `compare_with_calculator` | LLM 建议 vs 机理参考偏差分析 |
| ProcessStage | `validate_suggestions` | SUMO Gujer 矩阵验证 |
| ProcessStage | `export_to_sumo` | 导出 SUMO 输入文件 |
| Anaerobic / Anoxic / Aerobic | `get_stage_status` | 各段工况 |

## 扩展新工艺段

1. 创建 Agent 类（实现 `get_stage_status()`）
2. 在 `process_stage_agent.py` 的 `STAGE_CLASS_MAP` 注册
3. 在 `calculator.py` 的 `CALC_MAP` 注册计算方法
4. 在 `deviation_analyzer.py` 的 `COMPARABLE_PARAMS` 添加对比参数
