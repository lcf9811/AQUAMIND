---
name: coordinated-line-switch-eval
description: 评估并执行联动换线；校验 close_line 与 line_switch_state 一致后，调用 coordinated_line_switch WebAPI（支持 Python 脚本直接执行）。
metadata:
  openclaw:
    requires:
      env:
        - SCADA_BASE_URL
    primaryEnv: SCADA_BASE_URL
---

# 联动换线评估与执行（coordinated_line_switch）

## 1. 能力定义

- 输入：当前 `line_switch_state` 与候选 `close_line`。
- 动作：完成门禁校验后，执行 `POST /monitor/apiForward/api/writeplc`。
- 输出：标准 JSON，包含 `allowed`、`api`、`body`、`execution`。

## 2. References

- `../water-treatment-rules-kb/references/三工序系统架构说明.md`
- `../water-treatment-rules-kb/references/规则及约束条件_抽取.md`
- `../water-treatment-orchestrator/SKILL.md`

## 3. Parameters

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `close_line` | `int` | 是 | 待关闭线路，不能在 `running` 中。可选值：1、2、3。 |
| `running` | `int[]` | 是 | 除去关闭线路，当前运行线路列表（如：1 2）。长度应为 2。 |
| `requested_by` | `string` | 否 | 审计字段，调用人或调用代理。 |
| `base_url` | `string` | 否 | SCADA API 地址，优先级：参数 > 环境变量 `SCADA_BASE_URL` > 默认 `http://127.0.0.1:8080`。 |

## 4. Constraints（门禁规则）

1. `close_line` 仅允许 `1|2|3`。
2. `running` 长度应为 2（符合「二备一」架构）。
3. 不填写 `activate_line`，由服务端依据当前 `standby` 自动计算。

## 5. Execution（默认执行路径）

### 5.1 Python 脚本（推荐）

脚本位置：`./coordinated_line_switch_exec.py`

```bash
# 方式1：直接指定 base-url
python ./coordinated_line_switch_exec.py \
  --close-line 1 \
  --running 3 2 \
  --base-url http://127.0.0.1:8080 \
  --requested-by openclaw_agent

# 方式2：使用环境变量配置 base-url
export SCADA_BASE_URL=http://127.0.0.1:8080
python ./coordinated_line_switch_exec.py \
  --close-line 1 \
  --running 3 2 \
  --requested-by openclaw_agent
```

### 5.2 直接 HTTP（备用）

```http
POST http://127.0.0.1:8080/monitor/apiForward/api/writeplc
Content-Type: application/json

{
  "line_switch_state": {
    "running": [3, 2],
    "close_line": [1]
  },
  "requested_by": "openclaw_agent"
}
```

## 6. Return Schema（标准返回）

```json
{
  "allowed": true,
  "close_line": 1,
  "running": [1, 2],
  "expected_activate_from_standby": 2,
  "api": "POST /monitor/apiForward/api/writeplc",
  "body": {
    "line_switch_state": {
      "running": [3, 2],
      "close_line": [1]
    },
    "requested_by": "openclaw_agent"
  },
  "execution": {
    "mode": "python_script",
    "script": "coordinated_line_switch_exec.py"
  }
}
```

## 7. 环境变量配置

| 环境变量 | 说明 | 示例 |
|----------|------|------|
| `SCADA_BASE_URL` | SCADA API 基础地址 | `http://127.0.0.1:8080` |

在 OpenClaw 中配置：可在启动 OpenClaw 前设置环境变量，或在 OpenClaw 的环境配置中添加。

## 8. 调用时机

- 当进水/吸附/出水任一子 Skill 判定需整条线路退出，并已通过策略确认后调用本 Skill。
- 由本 Skill 先门禁，再执行 WebAPI；审批模式下仅输出建议，不直接执行。
