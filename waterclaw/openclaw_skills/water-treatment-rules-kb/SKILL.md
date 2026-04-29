---
name: water-treatment-rules-kb
description: 水处理规则综合知识库（唯一入口）：references/ 含规则抽取稿与三工序系统架构说明；供进水/吸附/出水业务 Skill 统一检索；扩展材料见 assets/。
---

# 水处理规则综合知识库

## 目录结构（本 Skill 标准布局）

```text
water-treatment-rules-kb/
├── SKILL.md
├── references/                                    # 权威文档（勿手改正文；更新见各文件头注释）
│   ├── 规则及约束条件_抽取.md                     # 业务规则、阶段表、流量 band（与 requirement/ 同源）
│   └── 三工序系统架构说明.md                      # 二备一、一条线路、API、line_switch_state、联动切换
└── assets/                                        # 可选：文献摘录、图表等（不替代 references/）
```

- **`references/规则及约束条件_抽取.md`**：docx → `scripts/extract_docx_text.py` → `requirement/` → **复制到本路径**。
- **`references/三工序系统架构说明.md`**：与 `requirement/三工序系统架构说明.md` **同步复制**（架构与 API 以本文件为准做 Skill 对齐）。

## 与《三工序系统架构说明》对齐的硬约束（摘要）

智能体研判时应同时检索 **两文件**；若与 `规则及约束条件_抽取.md` 表述有差异，**停机/切线/人身安全相关以更高安全侧或项目配置为准**。

| 主题 | 架构说明要求 |
|------|----------------|
| 冗余 | **二备一**：同一时刻 **2 条运行、1 条备用**（与规则稿「两运一备」同义）。 |
| 一条线路 | **进水管道 N → 转盘 N → 出水管道 N** 同编号联动，状态一致。 |
| 联动切换 | 仅提交 **`close_line`**（当前运行线之一）；**`activate_line` 由系统根据唯一 standby 自动计算**，非双下拉选人。 |
| 状态权威 | `inlet_perception.tags.line_switch_state`：`running` 长度 2、`standby` 长度 1；成功后三域可写 `last_coordinated_switch`。 |
| 进水毒性 | **抑制率 ≥60% → 停止进水**；其余 band 见架构文档「进水工序」表格。 |
| 吸附 | 饱和 **≥80% → 再生**；转盘频率与去除率正相关；温度 **14–16℃** 为最佳范围（与抽取稿 0–50Hz、≤20℃ 上限一并遵守）。 |
| 出水 | **&lt;10% 达标**；**10–20% 再监测**；**&gt;20% 不达标**。 |
| 推荐 API | 感知：`GET .../inlet|adsorption|outlet/snapshot`；联动：`POST /api/v1/control/coordinated_line_switch`；事件：`GET /api/v1/sse/events`。 |

## 何时加载本 Skill

- 任一子流程需对照 **规则条款、架构拓扑、API、band** 时 **只加载本 Skill**。
- 与业务 Skill 组合：`water-inlet-toxicity-flow` / `water-adsorption-saturation` / `water-outlet-toxicity` 等 **引用本 Skill 的 `references/`**，勿再使用已废弃的独立 `*-kb` 目录。

## 一、进水单元（检索锚点）

对应 **`references/规则及约束条件_抽取.md`** — 「一、进水单元」；**band 与 ≥60% 停机**与 **`references/三工序系统架构说明.md`** — 「进水工序」**交叉核对**。

- **拓扑**：两运一备；全停后重启延续先前两条运行线。
- **一键启动**：规则稿中的标志位与阀位示例。
- **流量与毒性**：抑制率越高流量设定越低；单线流量上限 **1.5 m³/h**（规则稿）。

## 二、吸附单元（检索锚点 + 材料与运行参数）

对应 **`references/规则及约束条件_抽取.md`** — 「二、吸附单元」；**转盘/线路编号与架构**见 **`references/三工序系统架构说明.md`** — 「吸附工序」「管路连接」。

- **硬约束**：频率 **0–50 Hz**；温度 **≤20℃**（勿顶格）；饱和 **≥80%** → 再生/换线（与架构一致）。
- **调节优先级**：**频率优先于温度**。
- **扩展**：活性炭与文献锚点可放 **`assets/`**。

## 三、出水单元（检索锚点）

对应 **`references/规则及约束条件_抽取.md`** — 「三、出水单元」；分级与 **`references/三工序系统架构说明.md`** — 「出水工序」「水质标准」一致。

## 与其他 Skill 的分工

| 业务 Skill | 本 KB 的用法 |
|------------|----------------|
| `water-plant-gate` | `line_switch_state`、二备一、一条线路拓扑 |
| `water-inlet-toxicity-flow` | 第一节 + 架构进水 band；**≥60% 停止进水**；切线仅 `close_line` |
| `water-adsorption-saturation` | 第二节；**disk N 与 pipe N 同线**；≥80% 再生；`coordinated_line_switch` / 审批任务 |
| `water-outlet-toxicity` | 第三节；出水 toxicity + flow；超标走联动切换 |
| `water-treatment-orchestrator` | 编排时 **一次引用** 本 Skill |

## 使用方式

- 回答中标注 **文档名 + 章节**（如「三工序系统架构说明 § 一条线路与三工序联动切换」），**不篡改** `references/` 内数值与原文。
- 更新流程：**规则抽取**改 docx → 抽取 → 复制 `规则及约束条件_抽取.md`；**架构**改 `requirement/三工序系统架构说明.md` → 复制覆盖 `references/三工序系统架构说明.md`。
