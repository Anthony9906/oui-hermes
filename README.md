# OUI Hermes

OUI Hermes 是基于 Open WebUI 裁剪的 Hermes Agent 对话 UI。当前项目目标不是保留完整 Open WebUI 平台能力，而是将其收敛为一个面向 Hermes Agent 的轻量对话前端、管理后台和扩展入口。

上游项目：<https://github.com/open-webui/open-webui>

当前远程仓库：<https://github.com/Anthony9906/oui-hermes>

## 当前定位

- 作为 Hermes Agent 的 Web 对话界面。
- 使用 OpenAI-compatible API 层连接 Hermes。
- 保留用户、会话、聊天记录、模型列表、管理员基础设置、Automations、Evaluations、Analytics、Pipelines、文件上传预览等核心能力。
- 移除或禁用通用 Open WebUI 中暂不需要的模块，降低项目复杂度和运行依赖。
- Hermes reasoning、tool call、Expert Agent、附件上传等路径优先适配 Hermes Agent 的运行契约，而不是恢复完整 Open WebUI 平台能力。

## 保留模块

- Chat UI：主页、会话页、消息渲染、聊天历史。
- Auth/User/Admin：登录、用户管理、权限基础设施。
- OpenAI-compatible API：默认指向 Hermes API。
- Hermes Expert Agents：`/api/v1/expert-agents` 及对应前端组件，技能列表通过 Hermes gateway `GET /skills` 发现。
- Files / Tools API：保留 `/api/v1/files` 支持聊天图片、PDF、Markdown、HTML、文本等附件上传与预览；保留 `/api/v1/tools` 满足聊天启动路径依赖。
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
- 后端不再挂载 `retrieval`、`images`、`knowledge`、`prompts`、`skills`、`memories`、`notes`、`channels`、`calendar` 等 router。
- 前端 `dev` / `build` / `build:watch` 不再自动执行 `pyodide:fetch`，仓库不再保存预下载的 Pyodide 分发文件。

## Hermes 适配状态

### Reasoning 与 Tool Rendering

- Hermes reasoning 和 tool call 走 Open WebUI 原生 Markdown `<details>` / `ToolCallDisplay` 渲染路径，不再维护并行的 Hermes trace UI。
- `backend/open_webui/utils/middleware.py` 会把 Hermes tool SSE events 转成 Open WebUI-compatible `function_call` / `function_call_output` item。
- `event: hermes.tool.progress` 只作为展示进度处理，不执行为本地 Open WebUI tool。
- 前端优先显示 Hermes payload 中的 `emoji`、`tool`、`label` 字段，并递归提取常见嵌套字段用于工具摘要。

### Expert Agent

- Open WebUI 通过 `HERMES_API_BASE_URL` 访问 Hermes gateway 8642；不要把它指向 Hermes Web UI 8787。
- Expert Agent 面板位于聊天右侧 pane 中，和 Controls / Files / Overview 共用交互模型。
- 普通用户启动 Expert Agent 通过 URL 参数 `expert-agent` 和 `expert-agent-start` 进入新会话，启动 nonce 使用项目内 `uuidv4()`，避免 `crypto.randomUUID()` 浏览器兼容问题。
- 当前会话会在聊天内容 `meta.expert_skill_name` 中保存启用的专家技能，并在聊天顶部显示专家模式 badge。

### 附件上传与预览

- 图片附件直接以 `process=false` 上传；Open WebUI 用 `/api/v1/files/{id}/content` 预览，Hermes 收到模型可访问的图片 URL。
- PDF、HTML、Markdown、TXT、JSON、CSV、YAML 等文档类附件直接上传，不走 Open WebUI RAG/vector processing。
- 文档类附件会被注入到最新用户消息的 `<attached_files>` block，包含 URL、content type 和文件名；Hermes gateway 负责轻量下载、缓存和文本提取。
- PDF 预览使用现有 `PDFViewer`；Markdown 渲染为 Markdown；HTML 使用 sandboxed `iframe srcdoc` 预览；其他代码类文本仍使用代码预览。
- Audio / video 仍保留现有 Open WebUI 媒体处理路径需要的 server processing。

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

S3-compatible / R2 附件存储：

```bash
# Cloudflare R2
STORAGE_PROVIDER=r2
# 或使用 Hermes 风格变量：
# ARTIFACT_STORAGE_PROVIDER=r2
R2_ENDPOINT=https://<account-id>.r2.cloudflarestorage.com
R2_BUCKET=hermes-artifacts
R2_ACCESS_KEY_ID=...
R2_SECRET_ACCESS_KEY=...
R2_PUBLIC_BASE_URL=https://assets.example.com
AWS_DEFAULT_REGION=auto
S3_KEY_PREFIX=open-webui

# MinIO / S3-compatible
# STORAGE_PROVIDER=s3
# S3_ENDPOINT_URL=http://127.0.0.1:9000
# S3_BUCKET_NAME=hermes
# S3_ACCESS_KEY_ID=...
# S3_SECRET_ACCESS_KEY=...
# S3_REGION_NAME=us-east-1
# S3_ADDRESSING_STYLE=path
# S3_PUBLIC_BASE_URL=https://files.example.com
# S3_KEY_PREFIX=open-webui
```

说明：

- `R2_PUBLIC_BASE_URL` / `S3_PUBLIC_BASE_URL` 存在时，Open WebUI 会为 Hermes 生成模型可访问的公开附件 URL。
- 不要提交真实 R2、S3、MinIO 密钥；本地密钥应放在未跟踪的 `.env` 或用户环境配置中。

## 本地开发启动

仓库根目录存在 `.env` 时，`backend/dev.sh` 和 `backend/start.sh` 会自动加载它；Docker Compose 不参与本地非 Docker 启动。

一键启动或重启前后端：

```bash
scripts/start-oui.sh
```

脚本会检查前端 `5173` 和后端 `8080` 端口；如果已有服务在运行会先停止再重启，没有运行则直接启动。日志写入 `logs/open-webui-frontend.log` 和 `logs/open-webui-backend.log`。

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
npm run build:bigmem
```

说明：`build:bigmem` 会以较高 Node heap 运行 `vite build`，用于手动完整生产构建验证。不要在日常小改动中自动运行全量构建。

## 当前已知事项

- 不要自动运行 `npm run check`；它会触发上游遗留的全量 Svelte 类型检查问题，其中包含部分已不再路由引用的组件。
- 不要自动运行 `npm run build:bigmem`；完整生产构建应由用户明确要求后再执行。
- 后端为了支持无 RAG/vector 环境启动，已将部分 RAG/Web/Image/Memory 入口改为 disabled stub 或 lazy import。
- 运行中的后端进程不会自动读取新的 `.env`、storage 配置或 middleware 修改；相关变更后需要重启。
- 在 Codex 沙箱中用 `uvicorn --reload` 或绑定 `0.0.0.0:8080` 可能遇到 `Operation not permitted`，运行时验证应使用已批准或用户会话后台启动方式。
- 旧聊天记录如果只保存了 `name="tool"` 和 `arguments="{}"`，无法被当前 Hermes tool detail 逻辑 retroactively enrich。
- HTML 附件预览当前面向单文件 HTML 报告；依赖同级相对资源的 HTML 可能需要后续资源解析路径。
- 下一阶段可以继续清理前端残留组件和依赖，例如 Pyodide worker、PDF/Office 预览、Workspace 组件目录、Notes/Channels 组件目录等。

## 轻量验证建议

```bash
python3 -m py_compile backend/open_webui/main.py backend/open_webui/config.py backend/open_webui/utils/middleware.py
./node_modules/.bin/prettier --check <touched-frontend-files>
git diff --check -- <touched-files>
curl http://localhost:8080/health
```

针对 Svelte 组件，优先做 touched file 的 Prettier 和单文件 Svelte compiler smoke compile；只有用户明确要求时再运行全量 `npm run check` 或 `npm run build:bigmem`。

## License

本项目基于 Open WebUI 修改，保留上游许可证与版权声明。详情见 `LICENSE` 和 `LICENSE_HISTORY`。
