---
name: water-outlet-toxicity
description: 出水毒性分级：<10% 达标；10–20% 再监测；>20% 不达标；对齐 outlet/source 同线；若需整条线路联动切线且策略允许即时联动，本 Skill 内调用 coordinated-line-switch-eval 执行换线。
---

# 出水毒性检测与分级

## 与《三工序系统架构说明》对齐

- **监测**（每条出水管道）：毒性（%）、出水流量（m³/h）；界面以二者为主（无单独「深度处理强度」控件作为首选）。
- **水质标准**（与架构「出水工序」一致）：
  - **达标**：毒性 **&lt;10%**
  - **再监测**：毒性 **10–20%**
  - **不达标**：毒性 **&gt;20%**
- **一条线路**：`outlet` 与 **`source: pipeN`** 对应同编号线路；停线/启备用须 **三工序联动**（仅 `close_line`，不手填 `activate_line`）。**换线动作**：在满足 §「联动换线执行」时，由 **本 Skill 调用** **`coordinated-line-switch-eval`** 完成门禁与 API 执行（见该 Skill §Execution）。
- 感知：**`GET /api/v1/outlet/snapshot`**；事件可订阅 SSE `control_executed`（`action: coordinated_line_switch`）。

## 输入

- 各出水线路 **毒性**（相对指标，%，与 SCADA 一致）。
- 各线 **出水流量**（m³/h）。
- 当前 `line_switch_state`、与进水/吸附侧告警是否一致；**同编号** pipe/disk/outlet 状态是否一致。

## 分级与动作

| 出水毒性（%） | 解释 | 动作 |
|---------------|------|------|
| **&lt; 10** | 达标 | 记录达标；可与进水抑制率、吸附阶段做一致性检查 |
| **10 – 20** | 再监测 | **待复检**：下一周期遥测再判定；本周期 `pending_recheck` |
| **&gt; 20** | 不达标 | **停该条线路**并由联动切换 **启用备用**；根因分析（炭未饱和却超标 vs 前段问题） |

## 与换线

- **本 Skill 职责**：按上表给出分线与 `tier`；若需整条线路退出，确定 **`suggested_close_line`**（须为当前 **running** 之一）及原因摘要。

## 联动换线执行（本 Skill 内）

| 条件 | 行为 |
|------|------|
| 某线 **`tier == trip`**（或策略规定的其它须联动停线情形），且 **策略允许即时联动** | **本 Skill 必须调用** **`coordinated-line-switch-eval`**，传入 `line_switch_state` 与 `close_line`（即该线编号），执行 `coordinated_line_switch`。 |
| **策略要求人工审批** | **不**调用 `coordinated-line-switch-eval` 即时执行；走 **`POST {SCADA_BASE_URL}/api/v1/tasks/line_switch`** → 审批通过后 **`.../line_switch/<task_id>/execute`**。 |

## 输出

```json
{
  "lines": [
    {
      "line_id": 1,
      "outlet_toxicity_pct": 8.5,
      "tier": "pass|recheck|trip",
      "actions": ["log_ok"]
    }
  ],
  "any_trip": false,
  "suggested_close_line": null,
  "line_switch_executed": false,
  "root_cause_hints": []
}
```

- `suggested_close_line`：当某线 `tier == trip` 且须联动切线时填写（须 ∈ `line_switch_state.running`）。
- `line_switch_executed`：本 Skill **已调用** `coordinated-line-switch-eval` 并成功执行时为 `true`。

## 知识库与其它 Skill

- **`water-treatment-rules-kb`**：`references/三工序系统架构说明.md`（出水标准、联动）、`references/规则及约束条件_抽取.md`（第三节阶段表）。
- **`coordinated-line-switch-eval`**：即时联动换线时的执行实现（门禁 + WebAPI）；由 **本 Skill** 在上一节条件满足时 **直接调用**。
