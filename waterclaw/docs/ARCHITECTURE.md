# WaterClaw AAO 多智能体架构

## Agent 只推理，Calculator 只做参考

### 设计原则

1. **Agent 只推理**: 基于工况数据 + 领域知识推理调控策略，不嵌入机理计算
2. **Calculator 独立**: 纯机理模型计算理论最优值，作为参考基准
3. **偏差分析**: Agent 建议 vs Calculator 参考，偏差大时降置信度或标记人工审核
4. **设备映射**: 概念参数 → SUMO 变量/Modbus 地址的翻译层

### 数据流

```
SCADA/Excel 进水数据
       │
       ▼
ProcessStageAgent.get_process_status() → 三段工况
       │
       ▼
OpenCLAW LLM → 推理调控建议 (方向 + 幅度 + 置信度)
       │
       ├──→ StageCalculator → 机理理论最优值
       │         │
       │         ▼
       └──→ DeviationAnalyzer.analyze(Agent建议, Calculator参考)
                 │
                 ▼
            偏差报告 (供 Agent 迭代参考)
                 │
       ┌─────────┴──────────┐
       ▼                    ▼
  偏差 acceptable       偏差 divergent
       │                    │
       ▼                    ▼
  EquipmentMapper      标记人工审核
   → SUMO命令          或 SUMO 离线验证
   → 设备指令
```

### 为什么要这样设计

原来的 SUMO/DQN 项目中的 RL 部分存在以下问题:
- RL 训练数据来自 SUMO 仿真，与实际设备数据不匹配
- DQN 输出是黑盒离散动作，无可解释性
- RL 从未真正写入 PLC 控制设备

WaterClaw 用可解释的机理驱动多 Agent 架构替代黑盒 DQN:
- 每个决策可追溯到具体的机理公式或 LLM 推理链
- Calculator 提供独立验证，防止 Agent 幻觉
- EquipmentMapper 确保参数能落地到具体设备
