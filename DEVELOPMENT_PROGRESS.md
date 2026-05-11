# Development Progress

Last updated: 2026-05-09

This is the compact handoff log for Hermes-specific Open WebUI development. Keep it evidence-based: preserve current outcomes, active contracts, validation rules, and durable caveats. Do not append debugging chronology.

## Current Status

Conclusion: verified for the core chat, tool rendering, Expert Agent, R2 attachment, and file preview paths listed below. Full repo-wide production build is intentionally not part of the default validation flow.

The project is now a Hermes-focused Open WebUI fork: it keeps Open WebUI's useful chat/admin/file infrastructure, removes or disables broad platform features that are not needed for Hermes Agent, and adapts streaming/tool/attachment behavior to the Hermes gateway contract.

## Active Structure

- Chat forwarding, Hermes SSE adaptation, file context injection: `backend/open_webui/utils/middleware.py`
- Expert Agent API: `backend/open_webui/routers/expert_agents.py`
- Chat orchestration: `src/lib/components/chat/Chat.svelte`
- Assistant message rendering: `src/lib/components/chat/Messages/ResponseMessage.svelte`
- Native reasoning/tool details: `src/lib/components/chat/Messages/Markdown/MarkdownTokens.svelte` and `src/lib/components/common/ToolCallDisplay.svelte`
- File preview modal: `src/lib/components/common/FileItemModal.svelte`
- Startup helpers: `scripts/start-oui.sh`, `backend/dev.sh`, `backend/start.sh`
- Full production build helper: `npm run build:bigmem`

## Validation Rules

- Do not run `npm run check` automatically; it is noisy in this trimmed Open WebUI fork.
- Do not run `npm run build:bigmem` unless the user explicitly asks for a full build.
- Prefer focused validation:
  - `python3 -m py_compile` for touched backend Python files.
  - Prettier check/write only on touched frontend files.
  - Single-file Svelte compiler smoke compile for touched Svelte components.
  - `git diff --check -- <touched-files>` for final whitespace checks.
- If a runtime behavior matters, verify with a new Hermes/Open WebUI session. Old saved chats may not contain enough structured metadata to prove the current bridge.

## Core Outcomes

### Hermes Reasoning And Tool Rendering

Status: patched and verified

- Hermes reasoning and tool calls stay on Open WebUI's native Markdown `<details>` / `ToolCallDisplay` path; no active parallel Hermes trace renderer is required.
- `middleware.py` recognizes Hermes tool SSE events and converts useful ones into Open WebUI-compatible `function_call` / `function_call_output` items.
- `event: hermes.tool.progress` is display-only metadata. It is kept out of local Open WebUI tool execution while its official Hermes preview remains visible in chat.
- Open WebUI preserves the official Hermes progress lifecycle:
  - `toolCallId` correlates `running` and `completed` updates.
  - `label` and `emoji` remain the official preview fields.
  - `args` / `arguments` are preserved so Todo lists, file paths, skill file paths, and search parameters can render.
  - Duplicate Open WebUI pending rows are suppressed only when the same `call_id` already has a Hermes display row.
- `ToolCallDisplay.svelte` renders a compact icon + tool/action + preview row, with richer previews for Todo, file, search, and skill calls.
- Known limitation: old saved messages that only persisted `label` / `emoji` or empty `arguments="{}"` cannot be retroactively enriched.

### Hermes Gateway Patch Boundary

Status: patched and verified after `hermes update`

- The Hermes checkout at `~/.hermes/hermes-agent` was reset to official upstream by `hermes update`; old local gateway routes should not be assumed active.
- Official Hermes gateway source no longer exposes the custom `/skills` route. Open WebUI should read local Hermes skill storage directly for Expert Agent listing.
- The preferred minimal Hermes gateway patches are:
  - Chat Completions SSE reasoning passthrough via `choices[0].delta.reasoning_content`.
  - Raw `args` passthrough on `hermes.tool.progress` events so Open WebUI can preserve structured tool preview details.
- Preserve Hermes official fields (`event`, `toolCallId`, `status`, `label`, `emoji`) and adapt Open WebUI around them.
- A live 8642 stream returned normal `delta.content`; absence of `reasoning_content` in a specific response proves only that the provider did not emit public reasoning for that request.

### Expert Agent

Status: patched and verified

- `GET /api/v1/expert-agents` and detail reads are implemented in Open WebUI and read local Hermes skills directly, defaulting to `~/.hermes/profiles/expertagent/skills` when present.
- Bundled Hermes skills in `.bundled_manifest` are filtered out so the panel focuses on user-added/non-bundled skills.
- `HERMES_EXPERT_AGENT_HIDDEN_SKILLS` hides individual skills; `HERMES_EXPERT_AGENT_VISIBLE_SKILLS` can act as a whitelist.
- Expert Agent UI lives in the chat right-side pane beside Controls / Files / Overview, not as a global overlay.
- Normal-user "Start Chat" routes through `/?expert-agent=<skill>&expert-agent-start=<nonce>` and uses the repo's `uuidv4()` helper instead of `crypto.randomUUID()` for browser compatibility.
- Active expert skill state is stored in chat `meta.expert_skill_name`; the chat top area shows the active expert mode badge.
- Expert skill management is intentionally not implemented as destructive UI controls in Open WebUI. Skill lifecycle work should happen through the agent/Hermes side.

### Attachments, R2, And Preview

Status: patched and runtime verified

- Open WebUI owns attachment upload, storage, preview, model URL generation, and `<attached_files>` injection.
- R2/S3-compatible storage is supported through the existing Open WebUI storage provider plus Hermes-style `R2_*` variables.
- `R2_PUBLIC_BASE_URL` / `S3_PUBLIC_BASE_URL` is used to generate model-accessible public URLs.
- Images upload with `process=false`, preview through `/api/v1/files/{id}/content`, and are sent to Hermes as model-accessible image URLs.
- PDF, HTML, Markdown, TXT, JSON, CSV, and YAML attachments upload directly without Open WebUI RAG/vector processing.
- Document attachments are injected into the latest user message as `<attached_files>` with URL, content type, file name, and lightweight extracted text when supported.
- Text extraction now runs in Open WebUI's chat forwarding path:
  - PDF extraction uses `pypdf`.
  - Text/HTML extraction is capped by `ATTACHED_FILE_CONTENT_MAX_CHARS` and `ATTACHED_FILES_TOTAL_MAX_CHARS`.
  - Unsupported/binary files fall back to URL-only `<file .../>` tags.
- File IDs are resolved from either direct IDs or Open WebUI file-content URLs.
- File preview remains UI-owned: PDF uses `PDFViewer`, Markdown renders as Markdown, HTML uses sandboxed `iframe srcdoc`, and other text/code files use source previews.
- Runtime tests confirmed PDF, HTML, Markdown, and image attachments store in R2, inject attachment URLs into the Hermes request, and are parsed by the agent.

### Trimmed Open WebUI Surface

Status: patched

- The project keeps Chat, Auth/User/Admin basics, model/admin settings needed for Hermes, files/tools APIs needed by chat startup, Automations, Evaluations, Analytics, Pipelines, and file upload preview.
- Ollama is disabled by default.
- Workspace routes for Models, Knowledge, Prompts, Tools, and Skills are removed from the frontend.
- Notes, Channels, Calendar, Playground, and Admin Functions routes are removed or disabled.
- RAG, Retrieval, Vector DB, Web Search, Image Generation, and Code Execution are disabled by default.
- The chat input menu no longer shows screenshot capture, existing-file attachment, or attached knowledge entries. Direct file upload, webpage attachment, notes, chat references, and cloud-drive integrations remain.
- PDF/document workflow cleanup removed old RAG-facing preview/content controls from the user path.

### Local Runtime

Status: verified with caveats

- `backend/dev.sh` and `backend/start.sh` auto-load repo-root `.env` for local non-Docker runs.
- `scripts/start-oui.sh` is the preferred local start/restart helper; it manages frontend `5173` and backend `8080` and writes logs under `logs/`.
- Verified runtime ports in the latest handoff: Hermes gateway `8642`, Open WebUI backend `8080`, frontend `5173`, local artifact service `8787`.
- Running backend processes do not automatically reload new `.env`, storage, dependency, or middleware changes; restart before runtime validation.
- In the Codex sandbox, `uvicorn --reload` or binding `0.0.0.0:8080` may fail with `Operation not permitted`; use an approved/user-session launch path when runtime proof is needed.

## Recent Focused Validation

- Hermes gateway: `py_compile` on `gateway/platforms/api_server.py`; targeted tests for reasoning SSE, tool progress display event, `toolCallId/status`, and `reasoning_config` forwarding.
- Open WebUI backend: `python3 -m py_compile backend/open_webui/utils/middleware.py`
- Open WebUI backend in venv: `.venv/bin/python -m py_compile backend/open_webui/utils/middleware.py`
- Attachment helper smoke tests: HTML extraction, truncation, and CDATA wrapping.
- Frontend: Prettier and single-file Svelte compiler smoke checks on touched components such as `ToolCallDisplay.svelte`, `Chat.svelte`, `ChatControls.svelte`, `Navbar.svelte`, `FileItemModal.svelte`, and message input components.
- Runtime/user checks: PDF, HTML, Markdown, and image attachments through R2 into Hermes Agent.

## Known Limits And Next Work

- Full `npm run check` and `npm run build:bigmem` remain manual only.
- Old saved chats cannot be backfilled with structured tool arguments that were not stored at the time.
- HTML preview is scoped to single-file HTML reports; relative sibling assets may need a later resource-resolution path.
- Optional runtime imports can make local shell import probes fail when the full environment is not installed; prefer syntax checks and focused runtime tests.
- Future cleanup candidates: Pyodide worker remnants, unused Workspace/Notes/Channels components, and any remaining RAG/vector-facing UI surfaces not needed by Hermes.

## Future Entry Rule

Append only durable outcomes in this shape:

```md
### Short outcome title

Status: patched | verified | blocked

- What changed.
- Validation performed.
- Remaining caveat, if any.
```
