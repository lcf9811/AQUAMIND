---
name: water-treatment-orchestrator

description: 水处理 OpenClaw 唯一编排入口：约定 Hook 触发条件、message 内嵌与 three_process_telemetry 同形 JSON、步骤 0～5 流水线、标准报告 Markdown 模板；Markdown 定稿后必须调用本 Skill 随附脚本 `scripts/markdown_report_to_docx.py` 生成 Word 至 workspace 根下 `水处理/水处理遥测研判报告_<时间戳>.docx`；子 Skill 为 water-plant-gate、进水/规则库/吸附/出水及换线门禁。

# 水处理 Hook 遥测编排（Orchestrator）
---
## 1. 定位与边界


| 项目       | 说明                                                                                                      |
| -------- | ------------------------------------------------------------------------------------------------------- |
| **职责**   | 把 **单次** SCADA 经 OpenClaw 上报的遥测，解析为结构化对象，按固定顺序做 **门控 → 进水 → 规则 → 工段优化（AAO） → 出水** 研判，并输出 **统一版式** 的 Markdown 报告；定稿后 **必须** 调用本 Skill 随附 **`scripts/markdown_report_to_docx.py`** 将同一份 Markdown **生成 Word（.docx）**，保存到 **workspace 根目录下 `水处理/`**（见 §5.6），**不得**仅口头说明而不执行脚本。 |
| **唯一入口** | 三工序工艺智能体在 **Hook 周期遥测** 场景下 **只加载本 Skill** 作为编排说明；解析与初筛在 **§4 步骤 0**，不另设独立 anomaly Skill。               |
| **不做的事** | 不替代 PLC 联锁；**默认不自动** `POST` 控制接口；均质池等仅能通过 Flask API，无独立 Skill。                                          |
| **不做的事2** | 所有回复必须用简体中文，不准用其他语言，可以出现英文单词。                                          |
| **依据文档** | `water-treatment-rules-kb/references/规则及约束条件_抽取.md`、`water-treatment-rules-kb/references/三工序系统架构说明.md`。 |


---

## 2. 触发条件（何时必须跑本编排）

需 **同时满足** 下列 **A + B**；否则本周期 **不按全流水线出报告**，仅给出 §7「降级输出」。

### 2.1 传输层（A：必须）


| #   | 条件                                                    | 说明                   |
| --- | ----------------------------------------------------- | -------------------- |
| A1  | 请求为 `**POST`** 至 OpenClaw `**/hooks/agent`**（或网关等价路径） | 一次 HTTP 请求 = 一轮推理周期。 |
| A2  | 外层 Body 为 JSON，且含 `**message`（字符串）**                  | 与网关字段定义一致。           |


### 2.2 载荷门控（B：必须）

对 `**message`** 做 `**json.loads(message)`**（见 §3）得到根对象后：


| #   | 条件                                                                        | 说明                                                                                                               |
| --- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------- |
| B1  | 根对象为 **JSON 对象**                                                          | 与 `**POST {SCADA_BASE_URL}/api/v1/scada/three_process_telemetry`** 的 **JSON 正文同形**（模拟器将同一份 dict 序列化进 `message`）。 |
| B2  | 根对象含 `**inlet`、`outlet`、`line_switch_state`** 三键（`adsorption` 为可选兼容键，`process_stage` 为新增工段数据键）             | 结构与水厂遥测 API 一致；缺键则在步骤 0 打标。                                                                                    |
| B3  | `**line_switch_state`** 含 `**running**`（长度为 2 的数组）与 `**standby**`（单条线路编号） | 与「二备一」一致；不满足则在步骤 0 打标并仍可按策略继续或短路。                                                                                |


### 2.3 辅助识别（非必须，仅便于路由/日志）


| 字段                                            | 作用                    |
| --------------------------------------------- | --------------------- |
| `**name**` 如 `SCADA-Water`                    | 网关/Agent 将请求路由到水处理代理。 |
| `**wakeMode**` 如 `now`                        | 立即处理，不等队列。            |
| `**name**` 如 `SCADA-Water`、`wakeMode` 如 `now` | 网关行为；**不能**替代 B1～B3。  |


### 2.4 不触发「完整 v1 流水线」的常见情况


| 情况                                          | 本 Skill 要求                                        |
| ------------------------------------------- | ------------------------------------------------- |
| `message` 非合法 JSON 字符串                      | **不**执行 §4 步骤 1～5；输出 §7.2 解析失败说明。                 |
| 人类可读告警（如仅 `[SCADA告警]` + `metrics_snapshot`） | 可人工研判或补发 **JSON 形态** `message`；本编排以 **B1/B2** 为准。 |
| 聊天里口头问工艺                                    | **不**自动等价于 Hook；除非用户显式附上同结构遥测根对象。                 |


---

## 3. Hook 与 message 协议（摘要）

**外层：**

```json
{
  "message": "<JSON 字符串，见下>",
  "name": "SCADA-Water",
  "agentId": "main",
  "wakeMode": "now"
}
```

**内层（`json.loads(message)` 的结果，与 SCADA 遥测 POST 正文一致）：**

```json
{
  "inlet": { "pipe1": {}, "pipe2": {}, "pipe3": {} },
  "adsorption": { "disk1": {}, "disk2": {}, "disk3": {} },
  "process_stage": {
    "anaerobic": { "COD_in": 0, "TN_in": 0, "TP_in": 0, "temperature": 20 },
    "anoxic": { "NO3_in": 0, "COD_available": 0 },
    "aerobic": { "DO": 2.0, "MLSS": 3500, "NH3_in": 0 }
  },
  "outlet": { "outlet1": {}, "outlet2": {}, "outlet3": {} },
  "line_switch_state": { "running": [1, 3], "standby": 2 }
}
```

- `**message` 禁止使用 Python 单引号字典字面量**；请用 `**json.dumps(telemetry_dict, ensure_ascii=False)`**（模拟器：`format_three_process_hook_message_as_json_string(payload)`，其中 `payload` 即发往 `…/three_process_telemetry` 的对象）。

---

## 4. 处理步骤（流水线）

**顺序固定**；任一步可因策略 **短路**（例如已判定必须停线则后续可摘要化）。


| 步骤    | 名称      | 加载的子 Skill / 动作               | 输入要点                                        | 输出要点                                                                                        |
| ----- | ------- | ----------------------------- | ------------------------------------------- | ------------------------------------------------------------------------------------------- |
| **0** | 解析与初筛   | 本 Skill 内置逻辑                  | `message` 字符串                               | `parse_ok`、遥测根对象（可作 `telemetry` 变量）、`anomaly_flags[]`                                       |
| **1** | 厂站门控    | `water-plant-gate`            | `plant_ready`、`line_switch_state`、各域 status | `gate`、`topology_compliant`                                                                 |
| **2** | 进水毒性+流量 | `water-inlet-toxicity-flow`   | 各 pipe 毒性、流量；≥60% 停进水                       | `inlet_ok`、`suggested_close_line`；策略允许时 **本 Skill 内调用** `coordinated-line-switch-eval` 执行换线 |
| **3** | 规则与架构检索 | `water-treatment-rules-kb`    | 与 1～2、4～5 的条款对齐                             | 引用条款摘要（不篡改数值）                                                                               |
| **4** | 工段优化（AAO） | `water-process-stage-optimization` | 进水水质、反应器参数、工艺设定值          | 三段（厌氧/缺氧/好氧）优化参数、SUMO验证状态、迭代收敛结论                      |
| **5** | 出水毒性    | `water-outlet-toxicity`       | 各 outlet 毒性 %                               | `tier`：达标 / 再监测 / 不达标；`trip` 且策略允许时 **本 Skill 内调用** `coordinated-line-switch-eval`          |


**联动换线执行：** `**coordinated-line-switch-eval`** 为门禁与 `coordinated_line_switch` 的**统一实现**；当 `**water-inlet-toxicity-flow` / `water-process-stage-optimization` / `water-outlet-toxicity`** 在各自 §「联动换线执行」条件满足时，**由该域 Skill 直接调用**（非仅编排代调）。

---

## 5. 报告样式（Markdown 模板）

每轮 Hook 推理的 **默认输出** 应贴近下述结构（中文优先，便于人读与归档）。

### 5.1 固定抬头

```markdown
## 水处理遥测研判报告

| 项 | 值 |
|----|-----|
| **载荷形态** | 与 `POST …/three_process_telemetry` 同形（根对象四键） |
| **解析** | 成功 / 失败 |
| **本轮时间** | （来自请求或系统时间，注明时区） |
| **线路拓扑** | running: [_, _]；standby: _ |
```

### 5.2 步骤 0 摘要（仅当解析成功）

```markdown
### 1. 数据与初筛

- **初筛标记**：（无 / topology_warning / spike_suspected / …）
- **说明**：（一句话）
```

### 5.3 分线汇总表（解析成功时必填）

```markdown
### 2. 分线状态摘要

| 线 | 进水毒性(抑制率) | 进水流量 | 工段状态(AAO) | 出水毒性% | 备注 |
|----|------------------|----------|---------------|-----------|------|
| L1 | | | | | |
| L2 | | | | | |
| L3 | | | | | |
```

（字段名与单位以根对象下 `inlet`/`adsorption`/`outlet` 实际键为准，表中可合并列。）

### 5.4 结论与建议

```markdown
### 3. 结论

- **门控**：（open / closed / ambiguous + 简述）
- **进水**：**正常 / 需关注 / 建议切线** —— 依据：（条款或阈值）
- **工段优化**：**正常 / 需调整 / 异常** —— 厌氧(VFA/TP、ORP)、缺氧(反硝化率、内回流)、好氧(DO、SRT)综合评价
- **出水**：**达标 / 再监测 / 不达标** —— 分线说明

### 4. 控制建议（默认不自动执行）

| 类型 | 内容 | 需审批 |
|------|------|--------|
| 联动换线 | close_line = _ | 是/否 |
| 其它 | | |

触发时间：
触发skill：
**免责声明**：以下为建议；实际写操作须经 HMI 或策略门控。
```

### 5.5 可选机器可读块

在报告末尾可追加 **一个** JSON 代码块，便于 SCADA/工单系统采集：

```json
{
  "parse_ok": true,
  "line_switch_state": { "running": [1, 3], "standby": 2 },
  "summary": {
    "gate": "open",
    "inlet_risk": "low",
    "adsorption_max_saturation_pct": 62.4,
    "outlet_worst_tier": "pass"
  },
  "recommended_close_line": null,
  "needs_approval": false
}
```

---

## 5.6 Word 文档归档（SCADA 请求处理完成后）

在 **§4 流水线已执行完毕** 且 **§5（或 §7）Markdown 报告已作为本轮终稿确定** 之后，**必须** 追加一步：将 **同一份** Markdown 正文通过 **仓库脚本** 转为 **独立** 的 Word 文档，**不得**仅依赖聊天窗口中的 Markdown，也 **不得** 将归档路径放在 Skill 目录下。

### 5.6.1 归档目录、文件名与时间戳

| 项 | 约定 |
|----|------|
| **Workspace 根** | 含 **`scripts/markdown_report_to_docx.py`**（与本 `SKILL.md` 同 Skill 包内的脚本）及 **`水处理/`** 的仓库根（即本项目的 `water_project` 根）。 |
| **归档目录** | **`{workspace}/水处理/`**（若不存在则脚本会创建）。 |
| **文件名** | **`水处理遥测研判报告_<YYYYMMDD_HHMMSS>.docx`** —— **时间戳在文件名中**，与 §5.1「本轮时间」**同一时区**（默认本地时间）。 |
| **每轮一份** | 每完成一轮 Hook 报告，**生成一个新的** `.docx` 文件；**不覆盖** 历史文件。 |

**相对路径示例：**

```text
水处理/水处理遥测研判报告_20260328143052.docx
```

- **内容范围**：与本轮 Markdown 终稿一致（含 §5.1～5.5；若为 **§7 降级**，亦将实际 Markdown 全文写入 Word，便于审计）。

### 5.6.2 必须调用的实现（仓库脚本）

**禁止**仅描述「可用 pandoc」等思路而不执行；**必须**在 **workspace 根目录** 运行下列方式之一（依赖见仓库根 `requirements.txt` 中的 `python-docx`；脚本路径相对于仓库根）：

**方式 A — 从 Markdown 文件生成（推荐）**

先将本轮终稿写入 **UTF-8** 的临时或固定路径的 `.md` 文件，再执行：

```bash
# 方式1：在 workspace 根目录运行（脚本会自动推断路径）
python <skill安装路径>/water-treatment-orchestrator/scripts/markdown_report_to_docx.py --markdown-file "<绝对或相对路径>.md"

# 方式2：显式指定 workspace 路径（适用于 skill 安装在其他位置时）
python <skill安装路径>/water-treatment-orchestrator/scripts/markdown_report_to_docx.py --workspace "<workspace根目录>" --markdown-file "<绝对或相对路径>.md"
```

**方式 B — 标准输入**

```bash
python <skill安装路径>/water-treatment-orchestrator/scripts/markdown_report_to_docx.py < report.md
```

（PowerShell 可用：`Get-Content report.md -Encoding utf8 | python <skill安装路径>/water-treatment-orchestrator/scripts/markdown_report_to_docx.py`）

**说明**：`<skill安装路径>` 取决于实际安装位置：
- 项目开发时：`./openclaw_skills`（项目仓库内）
- OpenClaw 安装目录：`C:\Users\%USERNAME%\.openclaw\skills`
- OpenClaw Workspace：`C:\Users\%USERNAME%\.openclaw\workspace\skills`

**可选参数**

- `--workspace <path>`：显式指定 workspace 根目录（默认自动推断）。**当 skill 安装在非项目目录时（如 `.openclaw/skills`），建议使用此参数或设置环境变量 `WATER_PROJECT_ROOT`**。
- `--timestamp YYYYMMDD_HHMMSS`：仅测试或与抬头时间强制对齐时使用；默认用 **生成时刻** 的本地时间戳。

**环境变量**

脚本支持以下环境变量（按优先级）：
- `WATER_PROJECT_ROOT`：指向 water_project 根目录
- `OPENCLAW_WORKSPACE`：指向 OpenClaw workspace 目录

设置示例（PowerShell）：
```powershell
$env:WATER_PROJECT_ROOT = "D:\workspace\water_project"
python .openclaw\skills\water-treatment-orchestrator\scripts\markdown_report_to_docx.py --markdown-file report.md
```

脚本成功时向 **stdout 打印一行**：生成文件的 **绝对路径**（Agent 应保留该行并在回复中引用）。

若执行 **失败**：在本轮回复末尾说明原因；Markdown 报告仍为有效输出，并在条件允许时 **重试**（根据实际 skill 安装位置调整脚本路径）。

### 5.6.3 与「最终回复」的顺序

1. 先完成 §4 与 §5（或 §7）的 Markdown 终稿（对用户可见的主报告）。
2. **随后** 执行 §5.6.2 中的 **`python scripts/markdown_report_to_docx.py`**（根据实际 skill 安装位置调整路径），得到 `水处理/水处理遥测研判报告_<时间戳>.docx`。
3. 在最终回复中 **写明** 脚本打印的归档路径（或相对 `水处理/` 的文件名）。

---

## 6. 短路规则（何时省略或压缩后续段落）


| 条件                  | 报告处理                                                                          |
| ------------------- | ----------------------------------------------------------------------------- |
| `parse_ok == false` | 仅输出 §5.1 抬头中 **解析失败** + 错误原因 + 修复建议（改用合法 JSON `message`）；**不**填 §5.3～5.5 业务表。 |
| `gate == closed`    | §5.3 可简写为「厂站未总启动，不展开工艺推演」；§5.4 控制建议可为「无」。                                     |
| 已明确需 **立即联动切线**     | §5.4 突出 `**close_line`** 与 `**coordinated-line-switch-eval`** 结果；其它段落可摘要。     |


---

## 7. 降级输出

### 7.1 解析成功但某子 Skill 缺数据

在 §5.4 中注明 **「某域数据缺失，结论不完整」**，并列出缺失键名。

### 7.2 解析失败（`message` 非 JSON）

```markdown
## 水处理遥测研判报告

| 项 | 值 |
|----|-----|
| **解析** | **失败** |
| **原因** | 无法对 `message` 执行 json.loads（示例：单引号非标准 JSON） |

### 修复建议

1. 使用 `format_three_process_hook_message_as_json_string` 生成 `message`。
2. 确保内层含 `version` 与 `telemetry`。
```

---

## 8. 环境与 API

- `**SCADA_BASE_URL**`：拉快照或控制时默认 `http://127.0.0.1:8080`。
- **联动切换**：`POST {SCADA_BASE_URL}/monitor/apiForward/api/writeplc`。


---

## 9. 实施提示

- Agent 在 **每次** 收到符合 §2 的 Hook 时，按 §4 顺序加载子 Skill；**最终回复** 应采用 **§5** 版式（或 §7 降级）。
- **Markdown 定稿后** 必须在 **workspace 根** 执行 **`scripts/markdown_report_to_docx.py`**（见 §5.6.2），在 **`水处理/`** 下生成 **`水处理遥测研判报告_<YYYYMMDD_HHMMSS>.docx`**，与 Markdown 内容一致。
- **脚本路径说明**：`scripts/markdown_report_to_docx.py` 位于本 Skill 包内。根据 skill 安装位置不同，完整路径可能是：
  - 项目开发时：`{project_root}/openclaw_skills/water-treatment-orchestrator/scripts/markdown_report_to_docx.py`
  - OpenClaw skills 目录：`C:/Users/%USERNAME%/.openclaw/skills/water-treatment-orchestrator/scripts/markdown_report_to_docx.py`
  - OpenClaw workspace：`C:/Users/%USERNAME%/.openclaw/workspace/skills/water-treatment-orchestrator/scripts/markdown_report_to_docx.py`
- 子 Skill 细节以各自 `SKILL.md` 为准；本文件不重复阈值公式，只约束 **触发、顺序、报告形态与 Word 归档**。

