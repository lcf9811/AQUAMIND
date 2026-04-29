---
name: water-adsorption-saturation
description: 吸附饱和率评估；对齐「disk N 与 pipe N 同线」、饱和≥80% 再生；若须即时联动换线且策略允许，本 Skill 内调用 coordinated-line-switch-eval 执行；否则可走审批任务。
---

# 吸附饱和度策略

## 与《三工序系统架构说明》对齐

- **一条线路**：**进水管道 N → 转盘 N → 出水管道 N**；评估饱和时 **disk 编号与线路编号 N 一致**。
- **阶段**：材料饱和率分 **10 个阶段（约 10%–85%）**；**饱和率 ≥80% → 启动再生/换线**（与架构「吸附工序」一致）。
- **监测**（每转盘）：温度、转盘频率、输入流量、吸附饱和率（%）。
- **控制叙述**：频率与毒性去除率正相关；温度 **14–16℃** 为最佳范围（同时遵守规则稿 **0–50 Hz、≤20℃** 上限）。
- **换线**：与进水/出水一致，业务上只关心 **`close_line`**（不填 `activate_line`）。**即时联动**时由 **本 Skill 调用** **`coordinated-line-switch-eval`** 执行（不在本文重复 HTTP）；架构与字段语义见 `water-treatment-rules-kb/references/三工序系统架构说明.md`。

## 饱和率（业务约定）

与规则抽取稿一致，饱和率与下列因素相关（现场以 SCADA 可采集量为准）：

- **流量**（可采集，m³/h）
- **工作时间**（可采集，h 或累计运行时间）
- **工作时间内的毒性**（进水/过程毒性表征，与项目点位一致）

工程上可表示为：**饱和率 ∝ f(流量, 运行时间, 时段内毒性负荷)**；具体标定系数由标定或数据拟合确定，本 Skill 只要求 **与 80% 阈值比较** 及 **趋势预测** 的叙述一致。

## 阈值与动作

| 条件 | 动作 |
|------|------|
| 饱和率 **≥ 80%** | **再生程序**；换线走 **`close_line`** + 三工序联动或 **审批任务**（见下） |
| 饱和率 **&lt; 80%** | **建议报告**：当前饱和率、预计触及 80% 的窗口（若可算）；优先调节 **转盘频率** 再考虑温度 |

## 换线（审批或即时）

- **本 Skill 职责**：根据饱和率与线号确定 **`action`**（`create_line_switch_task` | `advisory_only` | 即时联动换线等）；**不**在本 Skill 内重复粘贴换线 HTTP/Python（统一经 **`coordinated-line-switch-eval`**）。

### 审批路径（推荐）

`POST {SCADA_BASE_URL}/api/v1/tasks/line_switch`（body：`close_line`, `title`, `reason`, `requested_by`；**无需** `activate_line`）→ 审批通过后 `POST .../line_switch/<task_id>/execute`。由任务服务在服务端执行与 `coordinated_line_switch` 等价的逻辑。**此路径下本 Skill 不调用** `coordinated-line-switch-eval` 做即时 POST。

### 即时联动（无审批，慎用）

| 条件 | 行为 |
|------|------|
| 饱和率与策略判定须 **立即联动换线**，且 **无审批要求** | **本 Skill 必须调用** **`coordinated-line-switch-eval`**，传入 `line_switch_state` 与 `close_line`，由其执行 `coordinated_line_switch`（见该 Skill §Execution）。 |

> 基址与 `SCADA_BASE_URL` 一致；感知可拉取 **`GET /api/v1/adsorption/snapshot`**。

## 输出

```json
{
  "saturation_pct": 82.5,
  "line_id": 1,
  "action": "create_line_switch_task|advisory_only|coordinated_line_switch",
  "task_created_id": null,
  "line_switch_executed": false,
  "report_summary": ""
}
```

- `line_switch_executed`：走即时联动且 **已调用** `coordinated-line-switch-eval` 并成功时为 `true`。

## 关联

- **`water-treatment-rules-kb`**：`references/三工序系统架构说明.md`、`references/规则及约束条件_抽取.md`；材料与 HRT 扩展见 **`assets/`**（可选）。
- **`coordinated-line-switch-eval`**：即时联动换线时的执行实现；由 **本 Skill** 在「即时联动」分支 **直接调用**（与审批任务路径二选一）。
