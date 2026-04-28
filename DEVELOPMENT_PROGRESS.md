# Development Progress

Last updated: 2026-04-28

This file is the compact handoff log for Hermes-specific Open WebUI development. Keep it evidence-based and concise: preserve current outcomes, key structure, validation rules, and hard-won lessons; avoid step-by-step process history.

## Project Structure Summary

- Backend entry points are under `backend/open_webui/`.
- Hermes/OpenAI-compatible streaming and SSE bridge logic currently relevant to chat rendering lives in `backend/open_webui/utils/middleware.py`.
- Main chat orchestration lives in `src/lib/components/chat/Chat.svelte`.
- Assistant message rendering lives in `src/lib/components/chat/Messages/ResponseMessage.svelte`.
- Markdown `<details>` rendering lives under `src/lib/components/chat/Messages/Markdown/`.
- Native tool/reasoning detail UI support is shared through `src/lib/components/common/Collapsible.svelte` and `src/lib/components/common/ToolCallDisplay.svelte`.
- Global UI styling overrides live in `src/app.css`.
- App/admin/automation shell width is controlled by route-level containers such as:
  - `src/routes/(app)/home/+layout.svelte`
  - `src/routes/(app)/automations/+page.svelte`
  - `src/routes/(app)/admin/+layout.svelte`
- `package.json` includes `build:bigmem`, intended for manual full production build verification only.

## Validation Rules

- Do not run `npm run check` unless explicitly requested.
- Do not run `npm run build:bigmem` automatically. Ask the user before any full build.
- Preferred lightweight validation:
  - Prettier check/write only on touched frontend files.
  - Single-file Svelte compiler smoke compile for touched Svelte components.
  - `python3 -m py_compile` for touched backend Python files.
- If `npm run build:bigmem` fails on the user's machine, inspect only the real final error section. Existing Svelte warning noise is not useful.

## Current Outcomes

### Hermes Reasoning And Tool Rendering

Goal: keep Hermes reasoning and tool calls on Open WebUI's native Markdown `<details>` rendering path instead of maintaining a parallel Hermes trace renderer.

Current state:

- `MarkdownTokens.svelte` renders Hermes reasoning/tool call `<details>` blocks directly.
- Reasoning details default open and use muted text styling.
- Tool call details default collapsed.
- `ToolCallDisplay.svelte` shows a compact icon + tool/action name + preview row.
- Expanded tool output shows only returned tool information and is capped for readability.
- Hermes-provided `emoji`, `tool`, and `label` fields are preferred when present.
- Generic tool wrappers are recursively inspected for useful nested fields such as `tool_name`, `function_name`, `command`, `query`, `path`, `url`, and result text.

Backend bridge:

- `middleware.py` recognizes Hermes tool SSE events and converts them into Open WebUI-compatible `function_call` / `function_call_output` items.
- `event: hermes.tool.progress` is treated as Hermes display-only progress: render it in native tool details, but do not execute it as a local Open WebUI tool.
- The normal `serialize_output(...)` path emits `<details type="tool_calls">`, so the frontend remains on native rendering.

Known limitation:

- Old saved messages that already contain only `name="tool"` and `arguments="{}"` cannot be retroactively enriched.

### Chat Input Menu Simplification

Status: patched

Changed areas:

- `src/lib/components/chat/MessageInput/InputMenu.svelte`
  - Removed the chat input menu entries for screenshot capture, attached files from existing files, and attached knowledge.
  - Kept direct file upload, webpage attachment, notes, chat references, and cloud-drive integrations unchanged.
- `src/lib/components/chat/MessageInput.svelte`
  - Removed the now-unused screen-capture handler and stopped passing screenshot/file-picker-only props into `InputMenu`.

Validation:

- `./node_modules/.bin/prettier --write src/lib/components/chat/MessageInput.svelte src/lib/components/chat/MessageInput/InputMenu.svelte`
- `git diff --check -- src/lib/components/chat/MessageInput.svelte src/lib/components/chat/MessageInput/InputMenu.svelte`
- Single-file Svelte compiler smoke compile for `MessageInput.svelte` and `MessageInput/InputMenu.svelte`.

### 2026-04-28: Expert Agent Skills Panel

Status: patched

Changed areas:

- `backend/open_webui/routers/expert_agents.py`
  - Proxies `GET /api/v1/expert-agents` to Hermes `GET /skills`.
  - Sends `Authorization: Bearer HERMES_API_KEY` when configured.
- Hermes gateway `gateway/platforms/api_server.py`
  - Adds `GET /skills` on port 8642 for Open WebUI Expert Agent discovery.
  - Returns Open WebUI-compatible `items[]` with `skill_name` and `description`.
  - Filters out Hermes bundled skills recorded in `~/.hermes/skills/.bundled_manifest`, so the Expert Agent panel shows non-bundled/user-added skills only.
- `src/lib/components/chat/ChatControls.svelte`
  - Expert Agent now opens inside the chat right-side pane as a tab beside Controls/Files/Overview, matching the chat controls/artifact interaction model.
- `src/lib/components/expert-agents/ExpertAgentDrawer.svelte`
  - Converted from a fixed overlay drawer into embeddable right-pane content.
- `src/routes/(app)/+layout.svelte`
  - Removed global Expert Agent drawer mounting.
- `src/lib/components/layout/Sidebar.svelte`
  - Sidebar Expert Agent button opens the chat controls pane and switches to the Expert Agent tab.

Validation:

- Hermes gateway: `PYTHONPYCACHEPREFIX=/tmp/hermes-pycache venv/bin/python -m py_compile gateway/platforms/api_server.py tests/gateway/test_api_server.py`
- Hermes gateway: `PYTHONPYCACHEPREFIX=/tmp/hermes-pycache venv/bin/python -m pytest tests/gateway/test_api_server.py::TestSkillsEndpoint -q`
- Open WebUI backend: `python3 -m py_compile backend/open_webui/routers/expert_agents.py`
- Frontend: `./node_modules/.bin/prettier --write 'src/routes/(app)/+layout.svelte' src/lib/components/layout/Sidebar.svelte src/lib/components/chat/ChatControls.svelte src/lib/components/expert-agents/ExpertAgentDrawer.svelte src/lib/components/expert-agents/ExpertSkillCard.svelte`
- Frontend: `git diff --check -- 'src/routes/(app)/+layout.svelte' src/lib/components/layout/Sidebar.svelte src/lib/components/chat/ChatControls.svelte src/lib/components/expert-agents/ExpertAgentDrawer.svelte src/lib/components/expert-agents/ExpertSkillCard.svelte`
- Frontend: single-file Svelte compiler smoke compile for `ChatControls.svelte`, `ExpertAgentDrawer.svelte`, `ExpertSkillCard.svelte`, `(app)/+layout.svelte`, and `Sidebar.svelte`.

Notes:

- The running Hermes gateway must be restarted after gateway changes for `/skills` filtering to take effect.
- Do not point `HERMES_API_BASE_URL` at Hermes Web UI port 8787; Open WebUI chat should continue using the OpenAI-compatible gateway on 8642.
- Full `npm run check` and `npm run build:bigmem` were intentionally not run automatically.

### 2026-04-28: Expert Agent Normal User Start Fix

Status: verified

Changed areas:

- `src/lib/components/chat/ChatControls.svelte`
  - Expert Agent start now routes through `/?expert-agent=<skill>&expert-agent-start=<nonce>` so the new chat page consumes the start request directly.
  - Replaced `crypto.randomUUID()` with the repo-used `uuidv4()` helper; `crypto.randomUUID()` was not available in at least one normal user's browser context and caused the click handler to throw before navigation.
- `src/lib/stores/expertAgents.ts`
  - Replaced the remaining store-based `crypto.randomUUID()` nonce generation with `uuidv4()` for compatibility.

Validation:

- User browser console showed `TypeError: crypto.randomUUID is not a function` from `ChatControls.svelte` on normal-user click.
- Normal-user retest confirmed Expert Agent "Start Chat" now works.
- Frontend: `./node_modules/.bin/prettier --write src/lib/components/chat/Chat.svelte src/lib/components/chat/ChatControls.svelte src/lib/stores/expertAgents.ts`
- Frontend: `rg -n "crypto\\.randomUUID\\(" src/lib/components/chat/Chat.svelte src/lib/components/chat/ChatControls.svelte src/lib/stores/expertAgents.ts src/lib/components/expert-agents`
- Frontend: `git diff --check -- src/lib/components/chat/Chat.svelte src/lib/components/chat/ChatControls.svelte src/lib/stores/expertAgents.ts`
- Frontend: single-file Svelte compiler smoke compile for `Chat.svelte` and `ChatControls.svelte`.

Notes:

- The root cause was browser API compatibility, not model access or the disabled normal-user `permissions.chat.controls` tab.
- Full `npm run check` and `npm run build:bigmem` were intentionally not run automatically.

### 2026-04-28: Expert Agent Chat Skill Badge And Prompt Template

Status: patched

Changed areas:

- `src/lib/stores/expertAgents.ts`
  - Expert Agent startup prompt now uses the selected expert skill markdown template:
    - `当前对话启用专家技能： 技能名称`
    - `优先按照该专家技能的知识、流程和约束完成用户的后续任务，`
    - `只读取SKILL.md，然后用简洁的语言指导用户下一步做什么`
- `src/lib/components/chat/Chat.svelte`
  - URL-based Expert Agent startup uses the same prompt template.
  - Current-session Expert Agent startup sets `activeExpertSkillName`.
  - Chat content `meta.expert_skill_name` persists the active expert skill for refresh and chat switching.
  - Existing expert chats without meta can recover the badge by parsing the startup prompt.
  - Chat top area shows a floating high-contrast rounded badge: `🧩 专家模式：技能名称`.
  - Badge floats above `chat-pane` without occupying a separate layout row; messages can scroll underneath it.
- `src/lib/components/chat/Navbar.svelte`
  - Chat navbar's top gradient overlay is transparent so it no longer washes out the expert skill badge.

Validation:

- Frontend: `./node_modules/.bin/prettier --write src/lib/components/chat/Chat.svelte src/lib/components/chat/Navbar.svelte src/lib/stores/expertAgents.ts`
- Frontend: `git diff --check -- src/lib/components/chat/Chat.svelte src/lib/components/chat/Navbar.svelte src/lib/stores/expertAgents.ts`
- Frontend: single-file Svelte compiler smoke compile for `Chat.svelte` and `Navbar.svelte`.

Notes:

- This does not re-enable Open WebUI native Skills; expert skills remain routed through the Expert Agent startup flow.
- The expert skill value is stored in the existing chat payload meta, not Open WebUI's disabled native Skills feature.
- Full `npm run check` and `npm run build:bigmem` were intentionally not run automatically.

### 2026-04-28: Chat Image Paste Upload And Send Path

Status: patched

Changed areas:

- `backend/open_webui/main.py`
  - Restored `/api/v1/files` for chat image paste uploads.
  - Restored `/api/v1/tools` because chat startup still calls `getTools()` even in the Hermes-slim frontend path.
- `backend/open_webui/routers/files.py`
  - Moved retrieval/vector/audio imports from module import time to the specific file-processing/delete paths that need them.
  - This keeps image upload with `process=false` usable when Hermes-slim config has `VECTOR_DB=none`.
- `backend/open_webui/utils/middleware.py`
  - Converts uploaded chat image file references into `data:image/...;base64,...` before sending model payloads.
  - Prevents Hermes/OpenAI-compatible image validation errors when internal file ids or relative file URLs are used.

Validation:

- Backend: `python3 -m py_compile backend/open_webui/main.py backend/open_webui/routers/files.py backend/open_webui/routers/tools.py backend/open_webui/utils/middleware.py`
- Backend: `git diff --check -- backend/open_webui/main.py backend/open_webui/routers/files.py backend/open_webui/utils/middleware.py`
- Runtime: `/health` on port 8080 returned `200 OK`.
- Runtime logs showed pasted image upload returning `POST /api/v1/files/?process=false` `200`.
- Browser verification showed a cache-busted `http://localhost:5173/` loading past the splash screen after restoring the required routers.

Notes:

- Directly restoring the original `files` router was not sufficient: its previous top-level vector import crashed startup under `VECTOR_DB=none`.
- Uploading and sending are separate paths: upload success only proves `/api/v1/files`; model send also needs image references normalized to `http(s)` or `data:image/...`.
- Full `npm run check` and `npm run build:bigmem` were intentionally not run automatically.

## Trial And Error Lessons

- Extra custom Hermes trace UI caused duplication and ordering drift when native Markdown `<details>` were still present. The safer direction is to adapt Hermes events into Open WebUI's native item/detail model.
- Late `output` snapshots can reorder or duplicate live reasoning/tool/answer fragments if the UI rebuilds its own timeline. Prefer stable native message serialization rather than a second frontend timeline.
- Completed tool calls can disappear if progress and completion are modeled as separate transient UI parts. Preserve them as native tool-call details and merge useful completion data where possible.
- `hermes.tool.progress` is display-only. Treating it like a real local tool call risks unwanted execution semantics.
- Browser verification should use a new Hermes stream. Saved chats may not contain enough historical tool metadata to prove the current bridge.
- If Hermes still renders as `Tool Executed tool - {}`, inspect the raw Hermes tool payload before adding frontend heuristics; the missing field is usually in backend event mapping.
- Local shell import probes may fail because optional runtime dependencies such as `aiocache` are not installed. Prefer syntax checks and focused browser/runtime tests unless the environment is fully prepared.

## Future Entry Format

Append only durable outcomes, not every intermediate attempt:

```md
### YYYY-MM-DD: Short outcome title

Status: patched | verified | blocked

Changed areas:

- `path/to/file`
  - Durable behavior change.

Validation:

- Commands or manual checks performed.

Notes:

- Remaining risk, compatibility note, or lesson worth preserving.
```
