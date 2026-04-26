# OUI Hermes

OUI Hermes 是基于 Open WebUI 裁剪的 Hermes Agent 对话 UI。当前项目目标不是保留完整 Open WebUI 平台能力，而是将其收敛为一个面向 Hermes Agent 的轻量对话前端、管理后台和扩展入口。

上游项目：<https://github.com/open-webui/open-webui>

当前远程仓库：<https://github.com/Anthony9906/oui-hermes>

## 当前定位

- 作为 Hermes Agent 的 Web 对话界面。
- 使用 OpenAI-compatible API 层连接 Hermes。
- 保留用户、会话、聊天记录、模型列表、管理员基础设置、Automations、Evaluations、Analytics、Pipelines 等核心能力。
- 移除或禁用通用 Open WebUI 中暂不需要的模块，降低项目复杂度和运行依赖。

## 保留模块

- Chat UI：主页、会话页、消息渲染、聊天历史。
- Auth/User/Admin：登录、用户管理、权限基础设施。
- OpenAI-compatible API：默认指向 Hermes API。
- Hermes Expert Agents：`/api/v1/expert-agents` 及对应前端组件。
- Automations：保留前端路由和后端 API。
- Admin Evaluations：保留。
- Admin Analytics：保留。
- Admin Settings：保留核心设置、Connections、Models、Evaluations、Integrations、Interface、Pipelines、Database。
- Audio 后端依赖：保留基础音频处理依赖。

## 已移除或禁用模块

- Ollama 接口默认关闭，后端不再挂载 `/ollama`。
- Workspace 前端路由已删除：Models、Knowledge、Prompts、Tools、Skills。
- Notes 前端路由已删除。
- Channels 前端路由和后端 router 已移除。
- Calendar 前端路由和后端 router 已移除。
- Playground 前端路由已删除。
- Admin Functions 前端路由已删除。
- RAG、Retrieval、Vector DB、Web Search、Image Generation、Code Execution 默认禁用。
- 后端不再挂载 `retrieval`、`images`、`knowledge`、`prompts`、`tools`、`skills`、`memories`、`files`、`notes`、`channels`、`calendar` 等 router。
- 前端 `dev` / `build` 不再自动执行 `pyodide:fetch`。

## 环境变量

关键默认值见 `.env.example`。

常用配置：

```bash
HERMES_API_BASE_URL=http://127.0.0.1:8642
OPENAI_API_BASE_URL=http://127.0.0.1:8642
OPENAI_API_KEY=

ENABLE_OLLAMA_API=false
ENABLE_CHANNELS=false
ENABLE_NOTES=false
ENABLE_CALENDAR=false
ENABLE_WEB_SEARCH=false
ENABLE_CODE_EXECUTION=false
ENABLE_CODE_INTERPRETER=false
ENABLE_IMAGE_GENERATION=false
VECTOR_DB=none
```

## 本地开发启动

### 前端

```bash
npm install
npm run dev -- --host 0.0.0.0
```

默认地址：<http://localhost:5173>

### 后端

当前建议使用 `uv` 根据精简后的 `backend/requirements.txt` 启动，避免依赖系统 Python 环境：

```bash
uv run --no-project --python 3.12 --with-requirements backend/requirements.txt \
  uvicorn open_webui.main:app \
  --app-dir backend \
  --host 0.0.0.0 \
  --port 8080 \
  --forwarded-allow-ips "*" \
  --reload
```

默认地址：<http://localhost:8080>

健康检查：

```bash
curl http://localhost:8080/health
```

## 后台启动示例

```bash
nohup npm run dev -- --host 0.0.0.0 > frontend-dev.log 2>&1 &

nohup uv run --no-project --python 3.12 --with-requirements backend/requirements.txt \
  uvicorn open_webui.main:app \
  --app-dir backend \
  --host 0.0.0.0 \
  --port 8080 \
  --forwarded-allow-ips "*" \
  --reload > backend-dev.log 2>&1 &
```

日志文件：

- `frontend-dev.log`
- `backend-dev.log`

## 构建

```bash
NODE_OPTIONS=--max-old-space-size=8192 npm run build
```

说明：当前前端仍保留部分较重的聊天渲染、文件预览、Markdown、PDF/Office 预览、Pyodide worker 残留依赖。默认 Node heap 可能不足，构建时建议显式提高内存上限。

## 当前已知事项

- `npm run check` 会触发上游遗留的全量 Svelte 类型检查问题，其中包含部分已不再路由引用的组件；当前以 `npm run build` 作为更贴近运行路径的验证方式。
- 后端为了支持无 RAG/vector 环境启动，已将部分 RAG/Web/Image/Memory 入口改为 disabled stub 或 lazy import。
- 下一阶段可以继续清理前端残留组件和依赖，例如 Pyodide worker、PDF/Office 预览、Workspace 组件目录、Notes/Channels 组件目录等。

## 验证过的命令

```bash
python3 -m py_compile backend/open_webui/main.py backend/open_webui/config.py
NODE_OPTIONS=--max-old-space-size=8192 npm run build
curl http://localhost:8080/health
```

## License

本项目基于 Open WebUI 修改，保留上游许可证与版权声明。详情见 `LICENSE` 和 `LICENSE_HISTORY`。
