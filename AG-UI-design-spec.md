# AG-UI MVP 集成实现 Spec

> 当前文档记录本仓库与 Hermes `expertagent` profile 中已经跑通的 AG-UI MVP 实现，用于后续迭代。本文只写已由代码或 session 记录验证的实现，不把早期设计假设当成事实。
>
> 版本：MVP-0.1 | 日期：2026-06-11 | 范围：Open WebUI + Hermes Expert Agent

---

## 一、背景与目标

### 1.1 已验证目标

当前 MVP 证明了以下链路可行：

```text
Hermes Agent 直接调用 emit_agui_artifact
→ Open WebUI streaming middleware 截获 tool-call arguments
→ backend/open_webui/utils/agui.py 提取 artifact payload
→ 通过现有 Socket.IO event_emitter 发出 agui:* 事件
→ Chat.svelte 分发事件到 aguiStore
→ ChatSidePanel 自动切到 AG-UI 面板
→ StateRenderer 按 artifact_type 渲染右侧预览
```

最近一次连通性验证记录：

| 项 | 值 |
|---|---|
| Hermes profile | `expertagent` |
| session id | `3293fd3b-9341-48b9-8c55-3a7df54c6bef` |
| session title | `AGUI generic preview test` |
| tool_call_count | `1` |
| 唯一工具 | `emit_agui_artifact` |
| artifact_type | `generic-preview` |
| final reply | `AGUI generic preview sent.` |

### 1.2 当前设计目标

1. 用 `emit_agui_artifact(artifact_type, payload)` 作为 Hermes 到 Open WebUI 的轻量结构化事件桥。
2. Open WebUI 负责 AG-UI 翻译、状态事件发射和前端渲染。
3. MVP 阶段不依赖 MinIO、iframe、临时预览文件或上传脚本。
4. 保留 `write_file` payload 提取作为 fallback 兼容路径，但首选路径是直接工具调用。
5. 支持通用 JSON 预览与气缸选型专用 renderer，后续再扩展更多 artifact 类型。

### 1.3 非目标

- 当前实现不是完整 AG-UI SDK 接入；它是基于现有 Open WebUI Socket.IO 的 `agui:*` 事件子集。
- 当前 `emit_agui_artifact` 不负责渲染、不写文件、不上传文件。
- 当前 MVP 不处理用户交互回传、approval/interrupt、sub-agent 可视化等后续能力。

---

## 二、总体架构

```text
┌────────────────────────────────────────────────────────────┐
│ Hermes Agent / profile: expertagent                         │
│                                                            │
│ tools/agui_tool.py                                          │
│ - emit_agui_artifact schema + handler                       │
│ - validates artifact_type and payload                       │
│ - returns {"ok": true, ...}                                 │
│                                                            │
│ toolsets.py / tools_config.py                               │
│ - registers agui toolset and emit_agui_artifact             │
└──────────────────────────────┬─────────────────────────────┘
                               │ OpenAI-compatible tool call
                               │ {artifact_type, payload}
                               ▼
┌────────────────────────────────────────────────────────────┐
│ Open WebUI backend                                          │
│                                                            │
│ backend/open_webui/utils/middleware.py                      │
│ - streaming_chat_response_handler                           │
│ - hooks Hermes native events, streaming tool_calls,          │
│   and final function-call execution path                    │
│                                                            │
│ backend/open_webui/utils/agui.py                            │
│ - AguiEventEmitter                                          │
│ - extract_artifact_payload                                  │
│ - tool_to_step_name                                         │
│ - de-dupe and single-artifact guard                         │
└──────────────────────────────┬─────────────────────────────┘
                               │ Socket.IO event_emitter
                               │ agui:step_* / agui:tool_call_* /
                               │ agui:state_snapshot
                               ▼
┌────────────────────────────────────────────────────────────┐
│ Open WebUI frontend                                         │
│                                                            │
│ Chat.svelte                                                 │
│ - activates aguiStore for each submit                       │
│ - routes agui:* events                                      │
│                                                            │
│ ChatSidePanel.svelte                                        │
│ - adds agui panel mode                                      │
│ - switches to AG-UI when artifact or steps appear           │
│                                                            │
│ src/lib/agui                                                │
│ - agui.ts store                                             │
│ - AguiPanel.svelte                                          │
│ - StateRenderer.svelte                                      │
│ - renderers/*                                               │
└────────────────────────────────────────────────────────────┘
```

---

## 三、Hermes 侧实现

### 3.1 工具定义

文件：`/Users/anthony/.hermes/hermes-agent/tools/agui_tool.py`

当前工具：

```text
emit_agui_artifact
```

参数 schema：

```json
{
  "artifact_type": "string",
  "payload": "object"
}
```

handler 行为：

1. 校验 `artifact_type` 是非空字符串。
2. 校验 `payload` 是 object。
3. 返回：

```json
{
  "ok": true,
  "artifact_type": "<artifact_type>",
  "message": "Artifact payload emitted for AG-UI rendering."
}
```

关键边界：

- 工具本身是 no-op event bridge。
- 不写文件。
- 不上传 MinIO。
- 不生成 iframe。
- UI 更新依赖 Open WebUI 在流式 tool call 中截获 arguments。

### 3.2 工具注册

已验证代码路径：

| 文件 | 当前职责 |
|---|---|
| `/Users/anthony/.hermes/hermes-agent/tools/agui_tool.py` | 注册 `emit_agui_artifact`，toolset 为 `agui` |
| `/Users/anthony/.hermes/hermes-agent/toolsets.py` | `_HERMES_CORE_TOOLS` 包含 `emit_agui_artifact`，并定义 `agui` toolset |
| `/Users/anthony/.hermes/hermes-agent/hermes_cli/tools_config.py` | `CONFIGURABLE_TOOLSETS` 包含 `agui` |

注意：profile 配置文件中的 toolset 可见性可能按平台区分。API Server 是否实际暴露 `emit_agui_artifact`，不要只凭配置片段判断，优先用 `/v1/toolsets` 或 session trace 验证。

### 3.3 技能行为约束

已验证相关技能文件：

| 文件 | 约束 |
|---|---|
| `/Users/anthony/.hermes/profiles/expertagent/skills/productivity/artifact-delivery/SKILL.md` | 默认直接调用 `emit_agui_artifact`，禁止 terminal/execute_code/write_file 包装，`write_file` 仅 fallback |
| `/Users/anthony/.hermes/profiles/expertagent/skills/experts/cylinder-selection-for-expo/SKILL.md` | 气缸选型使用 `artifact_type="cylinder-selection-public"`，最终回复只输出文本 |

通用连通性测试首选：

```json
{
  "artifact_type": "generic-preview",
  "payload": {
    "title": "AGUI Generic Preview Test",
    "summary": "ASCII only payload to verify panel activation.",
    "metrics": {
      "status": "ok",
      "transport": "emit_agui_artifact",
      "renderer": "generic-preview"
    }
  }
}
```

---

## 四、Open WebUI 后端实现

### 4.1 核心文件

| 文件 | 职责 |
|---|---|
| `backend/open_webui/utils/agui.py` | AG-UI 事件发射、artifact payload 提取、工具到步骤名映射、去重 |
| `backend/open_webui/utils/middleware.py` | 在 streaming chat 流程中注入 AG-UI 检测和事件发射 |

### 4.2 artifact writer 工具白名单

`backend/open_webui/utils/agui.py` 当前识别以下工具名为 artifact writer：

```python
ARTIFACT_WRITER_TOOLS = {
    "write_file",
    "agui_artifact",
    "emit_agui_artifact",
    "render_agui_artifact",
}
```

含义：

- `emit_agui_artifact` 是当前首选路径。
- `write_file` 是兼容路径。
- `agui_artifact`、`render_agui_artifact` 是预留或兼容命名。

### 4.3 artifact type

`backend/open_webui/utils/agui.py` 当前知道的 artifact type：

```python
ARTIFACT_TYPES = {
    "agui-generic",
    "cylinder-selection-public",
    "generic-json",
    "generic-preview",
    "motor-selection-public",
}
```

注意：后端知道某个 type 不代表前端已有专用 renderer。当前前端 renderer 注册以 `StateRenderer.svelte` 为准。

### 4.4 payload 提取规则

入口函数：

```python
extract_artifact_payload(tool_args)
```

支持的参数形态：

1. 直接 AG-UI transport：

```json
{
  "artifact_type": "generic-preview",
  "payload": {}
}
```

2. StateSnapshot-like：

```json
{
  "snapshot": {
    "artifact": {
      "artifact_type": "generic-preview",
      "payload": {}
    }
  }
}
```

3. 气缸选型兼容格式：

```json
{
  "mechanism": "...",
  "recommendations": []
}
```

4. 完整 payload 顶层 recommendations：

```json
{
  "type": "cylinder-selection-public",
  "recommendations": []
}
```

5. 完整 payload 嵌套 data：

```json
{
  "type": "cylinder-selection-public",
  "data": {
    "recommendations": []
  }
}
```

`extract_artifact_payload` 会检查这些候选 key：

```text
payload, artifact, state, snapshot, content, arguments, args,
parameters, params, input, tool_input, args itself
```

### 4.5 发出的事件

Open WebUI 后端通过现有 `event_emitter` 发 Socket.IO 事件，事件 type 带 `agui:` 前缀。

| 事件 | data 关键字段 |
|---|---|
| `agui:step_started` | `step_name`, `run_id`, `timestamp` |
| `agui:step_finished` | `step_name`, `run_id`, `timestamp` |
| `agui:tool_call_start` | `tool_call_id`, `tool_name`, `run_id`, `timestamp` |
| `agui:tool_call_end` | `tool_call_id`, `tool_name`, `run_id`, `timestamp` |
| `agui:state_snapshot` | `artifact_type`, `payload`, `run_id`, `timestamp` |

`AguiEventEmitter` 内部行为：

- `run_id` 由后端初始化时生成：`run_<timestamp_ms>`。
- `_seen_tool_calls` 防止同一 tool call 重复发 start。
- `_artifact_emitted` 限制单次 run 只发一个 artifact snapshot。
- `on_artifact_detected` 会先结束当前 step，再发 `state_snapshot`。
- `flush` 会在正常完成或取消时结束未完成 step。

### 4.6 middleware 注入点

当前后端有三个 AG-UI 检测路径：

| 路径 | 代码位置 | 作用 |
|---|---|---|
| Hermes 原生工具事件 | `middleware.py` `_is_hermes_tool_event(...)` 分支 | 处理 Hermes-native tool event |
| streaming OpenAI tool_calls | `response_tool_calls` 累积处理块 | 处理 `choices[].delta.tool_calls[]` |
| final tool-call execution | final function-call output item 执行前后 | 处理 provider 不走前两个路径但最终执行工具的情况 |

这三个路径都重要。后续改动不要只维护其中一个路径，否则可能出现聊天正文有 tool call、右侧 AG-UI 面板无状态的分叉。

当前还有若干 `log.info("AG-UI: ...")` 调试日志，后续产品化可降级为 debug 或增加开关。

---

## 五、Open WebUI 前端实现

### 5.1 文件清单

| 文件 | 职责 |
|---|---|
| `src/lib/agui/stores/agui.ts` | AG-UI store、steps/artifact/tool_calls 状态、derived stores |
| `src/lib/agui/components/AguiPanel.svelte` | 右侧 AG-UI 面板容器，显示执行进度或 artifact |
| `src/lib/agui/components/StateRenderer.svelte` | renderer 注册表，按 `artifact_type` 路由 |
| `src/lib/agui/components/renderers/GenericPreviewRenderer.svelte` | 通用 JSON 预览 renderer |
| `src/lib/agui/components/renderers/CylinderSelectionRenderer.svelte` | 气缸选型 artifact renderer |
| `src/lib/components/chat/Chat.svelte` | 激活 store，接收并分发 `agui:*` 事件 |
| `src/lib/components/chat/ChatSidePanel.svelte` | 新增 `agui` panel mode，并处理展示优先级和关闭逻辑 |

### 5.2 store 状态

`src/lib/agui/stores/agui.ts`：

```ts
interface AguiState {
  steps: AguiStep[];
  current_step: string | null;
  artifact: AguiArtifact | null;
  tool_calls: Record<string, AguiToolCall>;
  is_active: boolean;
  run_id: string | null;
}
```

关键行为：

- `activate(run_id)`：每次用户 submit 前调用，清空旧 steps/artifact/tool_calls，并设置 active。
- `onStepStarted`：如果已有 current step，会先把旧 step 标为 completed，再追加新 running step。
- `onStateSnapshot`：保存 artifact，触发面板渲染。
- `reset()`：关闭 AG-UI 面板时调用。

### 5.3 Chat.svelte 事件路由

`Chat.svelte` 当前行为：

1. 用户提交时调用：

```ts
aguiStore.activate(`run_${Date.now()}`);
```

2. Socket.IO chat event 中，如果 `event.data.type` 以 `agui:` 开头：

```ts
handleAguiEvent(type.replace('agui:', ''), data);
return;
```

3. `handleAguiEvent` 支持：

```text
step_started
step_finished
tool_call_start
tool_call_end
state_snapshot
```

注意：前端 `activate` 生成的 run id 与后端 `AguiEventEmitter` 生成的 run id 不是同一个来源。当前渲染不依赖二者一致；如果后续要做多 run 并发隔离，需要重新设计 run id 传播。

### 5.4 ChatSidePanel 面板逻辑

`ChatSidePanel.svelte` 当前 panel union：

```ts
'artifacts' | 'expertAgents' | 'agui'
```

AG-UI 可见条件：

```ts
$aguiStore.is_active && ($aguiStore.artifact !== null || $aguiStore.steps.length > 0)
```

切换优先级：

1. AG-UI 新出现时切到 `agui`。
2. Artifacts 新出现时切到 `artifacts`。
3. Expert Agent drawer 新出现时切到 `expertAgents`。

关闭行为：

- 关闭 `agui` 面板时调用 `aguiStore.reset()`。
- 不复用 `showArtifacts`。

### 5.5 renderer 注册表

`StateRenderer.svelte` 当前注册：

```ts
const renderers = {
  'cylinder-selection-public': CylinderSelectionRenderer,
  'generic-preview': GenericPreviewRenderer,
  'generic-json': GenericPreviewRenderer,
  'agui-generic': GenericPreviewRenderer
};
```

未注册的 `artifact_type` 会显示：

```text
不支持的制品类型: <artifactType>
```

---

## 六、当前数据流

### 6.1 首选路径：emit_agui_artifact

```text
1. Agent 完成计算或组织测试 payload
2. Agent 直接调用 emit_agui_artifact
   - artifact_type: string
   - payload: object
3. Hermes 工具 handler 返回 ok
4. Open WebUI middleware 在 tool-call arguments 中看到 payload
5. extract_artifact_payload 返回 {artifact_type, payload}
6. AguiEventEmitter.on_artifact_detected 发 agui:state_snapshot
7. Chat.svelte 收到 agui:state_snapshot
8. aguiStore.artifact 更新
9. ChatSidePanel 切到 agui
10. StateRenderer 选择 renderer 并渲染
```

### 6.2 fallback 路径：write_file

`write_file` 仍在 `ARTIFACT_WRITER_TOOLS` 中，所以如果 `emit_agui_artifact` 不可用，middleware 可以从 `write_file` 的 `content` 或其他候选字段中提取 artifact payload。

fallback 不是当前推荐路径，原因：

- 会重新引入文件 I/O。
- 容易让 Agent 走回旧的 MinIO/iframe 习惯。
- 对连通性测试来说会混淆“工具调用直连”和“文件写入兼容”的结果。

---

## 七、已验证行为

### 7.1 通用预览

已通过 `generic-preview` payload 验证：

- 右侧面板显示“制品预览”。
- `GenericPreviewRenderer` 展示 title、summary、metrics、items、sections、Raw Payload。
- session trace 证明只调用了 `emit_agui_artifact`。
- 最终回复符合用户指定文本。

### 7.2 气缸选型路径

代码和技能约束已支持：

- Hermes skill 要求直接调用 `emit_agui_artifact`。
- artifact type 为 `cylinder-selection-public`。
- 前端 `StateRenderer` 已注册 `CylinderSelectionRenderer`。
- Open WebUI 后端仍兼容含 `recommendations` 的历史 payload 格式。

是否每个真实选型场景都完全符合预期，需要继续用端到端任务验证。

---

## 八、已知限制与后续迭代点

| 限制 | 当前状态 | 后续方向 |
|---|---|---|
| 只支持单 artifact | `_artifact_emitted` 限制一次 run 只发一个 snapshot | 支持多 artifact、版本切换、历史列表 |
| run id 双源 | 前端和后端各自生成 run id | 由 request/session 传递统一 run id |
| 事件子集有限 | 只有 step/tool/state_snapshot | 扩展 activity、progress、approval、interrupt |
| 无用户交互回传 | renderer 仅展示 | 增加 frontend action → backend/agent continuation |
| renderer 注册静态 | `StateRenderer.svelte` 手写 map | 建立 renderer registry 或 schema-driven renderer |
| 后端日志偏调试 | `log.info("AG-UI: ...")` 较多 | 降级 debug 或加配置开关 |
| API Server 工具可用性需验证 | 配置和运行时 tool exposure 可能分叉 | 用 `/v1/toolsets` 和 session trace 做验收 |
| write_file fallback 仍存在 | 兼容旧路径 | 后续可按工具/skill 粒度收紧 |

---

## 九、调试与验收清单

### 9.1 Hermes 侧

1. 确认 `emit_agui_artifact` 在工具列表中可用。
2. 确认 Agent 直接调用该工具，不通过 `terminal`、`execute_code`、`write_file` 包装。
3. 查询 `expertagent` session trace：
   - `tool_call_count` 是否符合预期。
   - `tool_calls` 中是否只有 `emit_agui_artifact`。
   - 工具返回是否为 `ok: true`。
   - 最终回复是否没有粘贴完整 payload、iframe 或 MinIO URL。

### 9.2 Open WebUI 后端

1. 搜索服务器日志中的 `AG-UI:`。
2. 确认进入了至少一个 middleware 注入点。
3. 确认 artifact writer 判断为 true。
4. 确认 `extract_artifact_payload` 成功，日志或行为显示 artifact detected。
5. 确认发出了 `agui:state_snapshot`。

### 9.3 Open WebUI 前端

1. `Chat.svelte` 是否收到 `agui:*` event。
2. `aguiStore.artifact` 是否更新。
3. `ChatSidePanel` 是否切到 `agui`。
4. `StateRenderer` 是否有对应 `artifact_type`。
5. 如果面板出现但内容不对，优先检查 renderer 对 payload schema 的假设。

---

## 十、变更边界

后续修改时保持以下边界：

1. Hermes `emit_agui_artifact` 继续保持轻量 bridge，不把 Open WebUI 渲染逻辑搬进 Hermes。
2. Open WebUI middleware 继续负责从 tool-call arguments 翻译出 AG-UI state。
3. 技能文件只约束 Agent 行为和 payload contract，不承担 UI renderer 逻辑。
4. 新 artifact type 必须同时更新：
   - Hermes skill 的 payload contract。
   - Open WebUI 后端提取/兼容规则，如有必要。
   - `StateRenderer.svelte` renderer 注册。
   - 对应 renderer 组件。
   - 本 spec 的文件清单和验收清单。
