---
name: waterclaw
description: WaterClaw — 基于机理模型的污水处理多智能体系统。用于分析/诊断/优化 AAO 工艺。支持任意工艺段自由组合（A²O/AAOA/AOA/AO）。
---

# WaterClaw — 污水处理多智能体工艺助手

基于 SUMO Gujer 矩阵机理模型的 AAO 多智能体系统。
Agent 只做 LLM 推理，Calculator 独立提供机理参考，
DeviationAnalyzer 对比两者偏差，EquipmentMapper 桥接到设备层。

## 项目位置

`/home/axlhuang/waterclaw` 或 `git clone https://github.com/Axl1Huang/waterclaw.git`

## 工作流程

### 1. 检查/修改工艺流程

编辑 `config/process_stage_params.yaml` 中的 `flow_sequence`：

```yaml
flow_sequence:
  - anaerobic
  - anoxic
  - aerobic
  - anoxic    # 后缺氧段，不需要可删除
```

支持组合: A²O / AAOA / AOA / AO

### 2. 获取全工段工况

```python
from agents.process_stage_agent import ProcessStageAgent
psa = ProcessStageAgent('http://localhost:5000')
status = psa.get_process_status()
```

返回当前 flow_sequence 下所有工艺段的工况数据，供 LLM 推理调控建议。

### 3. LLM 推理调控建议 → 对比机理参考

```python
suggestions = {"anaerobic": {"carbon_dose_mg_l": 25, ...}, ...}
result = psa.compare_with_calculator(suggestions)
```

返回偏差分析报告：`within_range` / `marginal` / `significant` / `divergent`。

### 4. 导出到 SUMO 仿真

```python
psa.export_to_sumo(suggestions, influent={...})
```

### 5. 运行验证

```bash
python3 -c "
from agents.process_stage_agent import ProcessStageAgent
psa = ProcessStageAgent('http://localhost:5000')
status = psa.get_process_status()
print('Flow:', ' → '.join(status['flow_sequence']))
print('Stages:', list(status['stages'].keys()))
"
```

## 架构

```
进水数据 → ProcessStageAgent(编排) → 各段工况
    → LLM 推理建议 → StageCalculator(机理参考) → DeviationAnalyzer(偏差)
    → EquipmentMapper(设备映射) → SUMO/PLC执行
```

## 文件索引

| 路径 | 职责 |
|------|------|
| `agents/process_stage_agent.py` | 编排层，配置驱动 |
| `agents/anaerobic_agent.py` | 厌氧段感知 |
| `agents/anoxic_agent.py` | 缺氧段感知 |
| `agents/aerobic_agent.py` | 好氧段感知 |
| `models/calculator.py` | 链式机理计算 |
| `models/deviation_analyzer.py` | 偏差分析 |
| `models/equipment_mapper.py` | 参数→设备映射 |
| `models/aerobic_model.py` | SUMO Gujer矩阵 (10反应) |
| `config/process_stage_params.yaml` | 工艺流程+参数 |
