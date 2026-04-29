---
name: water-inlet-toxicity-flow
description: 进水毒性抑制率与流量联合检测；对齐架构「≥60%停止进水」与流量 band；若逻辑要求整条线路联动切线且策略允许即时联动，本 Skill 内调用 coordinated-line-switch-eval 执行换线（不手填 activate_line）。
---

# 进水毒性 + 流量检测

## 适用条件

- `water-plant-gate` 为 `open` 或 `ambiguous`，或业务要求每次 Hook 都做进水安全扫描。

## 与《三工序系统架构说明》对齐

- **监测参数**（每条进水管道）：毒性、温度、进水流量（m³/h）。
- **硬动作**：**毒性抑制率 ≥60% → 停止进水**（见 `water-treatment-rules-kb/references/三工序系统架构说明.md` — 进水工序）。
- **流量推荐 band**（与架构一致，用于校核当前流量设定是否合理）：
  - ≥60%：停止进水
  - 50–60%：10–30% 流量
  - 30–50%：30–50% 流量
  - 20–30%：50–70% 流量
  - 10–20%：70–90% 流量
  - &lt;10%：90–100% 流量
- **规则抽取稿**（`references/规则及约束条件_抽取.md`）中另有分档与加药等描述；若与架构冲突，**停机/停进水以架构 ≥60% 为硬约束**，其余由运营策略或 `water-treatment-rules-kb` 说明的「就高安全」处理。
- **整条线路退出**：须走 **三工序联动**；**不要**在智能体侧指定 `activate_line`（由后端根据唯一 standby 计算）。见架构说明 §「一条线路与三工序联动切换」。**执行方式**：在满足 §「联动换线执行」条件时，由 **本 Skill 直接调用** **`coordinated-line-switch-eval`**（其内完成门禁并调用 WebAPI/脚本），**不是**仅输出建议交给编排代执行。

## 输入

- 各线 **进水毒性抑制率**（%）及趋势（若多周期缓存）。
- **瞬时流量**（m³/h）：单线 ≤ **1.5**（规则约束，见规则抽取稿）。
- `line_switch_state`：当前 **running**（2 条）、**standby**（1 条）。

## 判定

1. **流量异常**：任一线流量超限、或为 0 但标记为 running → `flow_anomaly: true`。
2. **毒性异常**：抑制率 **≥60%** 仍进水 → 高风险；或相对历史突升、或与架构 band 不匹配（对照 `water-treatment-rules-kb`）。
3. **联合异常**：毒性高且流量未按 band 下调 → 高风险。

## 动作建议

- 若需 **切备用线**：先确定 **`close_line`**（须为当前 **running** 之一）与 **`reason`**；**不输出** `activate_line`（由服务端在换线响应中返回）。
- **反向控制消息**（示例字段，以项目 Hook/控制 API 为准）：
  - `recommended_action`: `request_coordinated_line_switch` | `adjust_inlet_flow_band` | `stop_inlet` | `hold`
  - `close_line` / `suggested_close_line`: 1–3（仅当动作为联动切换时）
  - `reason`: 简短说明（毒性/流量/架构或规则章节引用）

## 联动换线执行（本 Skill 内）

| 条件 | 行为 |
|------|------|
| 逻辑判定需 **`request_coordinated_line_switch`**，且 **策略允许即时联动**（无需人工审批） | **本 Skill 必须调用** **`coordinated-line-switch-eval`**：传入当前 `line_switch_state` 与 `close_line`，由其执行 `coordinated_line_switch`（实现见该 Skill §Execution，不在本文重复 HTTP）。 |


## 与知识库与其它 Skill

- **`water-treatment-rules-kb`**：`references/三工序系统架构说明.md`（band、联动）、`references/规则及约束条件_抽取.md`（细则）。
- **`coordinated-line-switch-eval`**：即时联动换线时的 **执行载体**（门禁 + WebAPI）；由 **本 Skill 在上一表条件满足时直接调用**，而非仅由编排代调。

## 输出

```json
{
  "inlet_ok": false,
  "flow_anomaly": true,
  "toxicity_anomaly": false,
  "inhibit_ge_60_stop_required": false,
  "suggested_close_line": 1,
  "line_switch_executed": false,
  "line_switch_execution_ref": "coordinated-line-switch-eval",
  "control_suggestion": {},
  "escalate_to_adsorption": false
}
```

- `line_switch_executed`：当本 Skill **已调用** `coordinated-line-switch-eval` 并成功执行时为 `true`。
- 若 `inlet_ok == false` 且策略为「先切线再评吸附」，可将 `escalate_to_adsorption` 设为 false；若仅轻微偏离，可继续评吸附。
