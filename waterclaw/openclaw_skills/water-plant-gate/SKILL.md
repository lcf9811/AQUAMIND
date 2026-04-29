---
name: water-plant-gate
description: 判断 Hook 遥测是否对应厂站「开/关」工况；开态时校验 plant_ready、二备一（line_switch_state）、以及一条线路（pipe N / disk N / outlet N）与架构说明一致。
---

# 厂站门控（开 / 关）

## 目标

从单次遥测中判断当前是否处于可简化为 **关**（未总启动或等价停机）、**开**（总启动且工艺可评估），或 **未明确**（需进入进水毒性/流量等深度步骤）。

## 与《三工序系统架构说明》对齐

- **二备一**：同一时刻 **2 条线路运行、1 条备用**（架构文档与 `water-treatment-rules-kb/references/三工序系统架构说明.md`）。
- **一条线路**：**进水管道 N → 吸附转盘 N → 出水管道 N** 同编号，三处运行/备用状态应一致；切换为 **三工序联动**，非仅进水单端操作。**本 Skill 不判定 `close_line`、不发起换线**；若门控 **open** 且后续 **water-inlet-toxicity-flow / water-adsorption-saturation / water-outlet-toxicity** 的逻辑要求换线，由 **上述域 Skill 在本轮内调用** **`coordinated-line-switch-eval`** 执行（或走审批任务）；本 Skill 仅提供 `gate` 与 `line_switch_state` 供其使用。
- **状态字段**：`inlet_perception.tags.line_switch_state`：`running`（长度为 2）、`standby`（长度为 1）。

## 输入字段（从 telemetry / 各域 perception 读取）

- `plant_ready`（bool）：厂站是否总启动。
- 一键启动相关标志位（若存在）：如规则稿中的 `v18.5` 等，与项目点位表一致。
- `line_switch_state`：**running** / **standby**；须符合二备一。
- 可选：各域 `pipe*` / `disk*` / `outlet*` 或等价结构中，**同编号** 的 `status` 是否一致（与架构 JSON 模型一致）。
- 可选：`master_start`、全停模式。

## 判定逻辑

1. **关**：`plant_ready == false`（或未总启动且无明确运行线路）→ `gate: closed`，**不建议**执行吸附/出水达标推演；可提示「待总启动后再评估」。**此状态下不得执行**联动换线（`coordinated_line_switch` 服务端亦会拒绝）。
2. **开**：`plant_ready == true` 且 `line_switch_state` 符合二备一、同线编号状态一致、进水流量在规则允许范围内（单线最大 1.5 m³/h 等）→ `gate: open`，`line_topology_ok: true/false`。
3. **未明确**：遥测缺失关键字段、或运行/备用与二备一冲突、或同编号三工序状态不一致 → `gate: ambiguous`，**必须**进入 `water-inlet-toxicity-flow` 做毒性与流量联合判断。

## 输出（供 Orchestrator 合并）

```json
{
  "gate": "closed|open|ambiguous",
  "plant_ready": true,
  "line_switch_state": {},
  "topology_compliant": true,
  "notes": []
}
```

## 知识库与其它 Skill

- **`water-treatment-rules-kb`**：`references/三工序系统架构说明.md`（拓扑与 API）、`references/规则及约束条件_抽取.md`（一键启动与流量细则）。
- **`water-inlet-toxicity-flow` / `water-adsorption-saturation` / `water-outlet-toxicity`**：在各自业务逻辑与策略允许时 **直接调用** **`coordinated-line-switch-eval`** 执行换线；**本 Skill 不调用**（无切线业务输入）。
- **`coordinated-line-switch-eval`**：换线执行实现；**不由本 Skill 调用**。当 `gate: closed` 时，域 Skill **不得**调用该执行（与服务端「未总启动拒绝换线」一致）。
