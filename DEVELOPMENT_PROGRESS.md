# Development Progress

Last updated: 2026-06-12

Compact handoff log for the Hermes-focused Open WebUI fork. Keep future entries short and limited to each feature's function, structure, and key logic.

## Current Direction

This fork keeps Open WebUI's chat, admin, file, and preview infrastructure while adapting the active user path to Hermes Agent. Hermes owns agent execution and session continuity; Open WebUI owns the browser client, file upload/preview, AG-UI rendering, and chat-side presentation.

## Validation Policy

- Do not run full `npm run check` or `npm run build:bigmem` by default.
- Prefer focused checks: `python3 -m py_compile`, targeted pytest, Prettier on touched frontend files, Svelte smoke checks for touched components, and `git diff --check`.
- Runtime behavior should be verified in a fresh Hermes/Open WebUI session when the behavior depends on streaming, tool calls, files, or AG-UI events.

## Feature Log

### Hermes Session Delta Bridge

Function: Open WebUI sends only the current user turn to Hermes while Hermes maintains server-side chat history.

Structure: `backend/open_webui/utils/hermes.py`, OpenAI router Hermes delta handling, and `X-Hermes-Session-Id`.

Key logic: strip Open WebUI-owned history/tools/system fields from Hermes delta payloads, preserve current user context and attachments, reject temporary chat ids, and inject the Open WebUI AG-UI interaction rule for this client path.

### Hermes Streaming And Tool Display

Function: Hermes reasoning, tool progress, and tool results render in the normal Open WebUI chat transcript.

Structure: `backend/open_webui/utils/middleware.py`, `ToolCallDisplay.svelte`, and message Markdown rendering.

Key logic: normalize Hermes SSE/tool progress into Open WebUI-compatible output items, preserve official Hermes `toolCallId`, `status`, `label`, `emoji`, and structured args, and avoid executing display-only Hermes tool rows as local Open WebUI tools.

### AG-UI Workspace And Artifact Bridge

Function: Hermes can trigger Open WebUI-native interactive previews and choice dialogs through structured tool calls.

Structure: `backend/open_webui/utils/agui.py`, `src/lib/agui/`, `Chat.svelte`, `ChatSidePanel.svelte`, and `src/routes/agui-preview/`.

Key logic: intercept `emit_agui_artifact` / compatible artifact-writer arguments from streaming tool calls, emit `agui:*` Socket.IO events, store AG-UI state client-side, render artifacts in the right-side AI workspace, and treat `artifact_type="interaction-request"` as an in-chat choice interaction.

### AG-UI Interaction Responses

Function: Open WebUI shows choice/approval cards and returns selected user input to Hermes.

Structure: `InteractionCard.svelte`, `agui.ts`, `Chat.svelte`, and `/utils/agui/approval`.

Key logic: normalize choice options from payloads, support custom choice text for normal choice prompts, submit approvals through the backend approval endpoint, and submit normal choices back as an `<agui_interaction_response>` message with a user-readable display string.

### AG-UI Renderers

Function: Right-side preview renders both generic artifacts and product-specific engineering artifacts.

Structure: `StateRenderer.svelte`, `GenericPreviewRenderer.svelte`, `CylinderSelectionRenderer.svelte`, and `static/assets/images/expert-agent/cylinder-selection/`.

Key logic: route by `artifact_type`, support `generic-preview` / generic JSON display, render `cylinder-selection-public` payloads with recommendation cards and image assets, and expose local preview links through `/agui-preview`.

### Expert Agent Surface

Function: Open WebUI exposes team Expert Agent skills as selectable chat-side cards.

Structure: `backend/open_webui/routers/expert_agents.py`, `src/lib/stores/expertAgents.ts`, Expert Agent drawer components, and chat route parameters.

Key logic: read only the profile `skills/experts/` boundary, keep skill lifecycle work on the Hermes side, start expert chats through URL parameters, and persist active expert state in chat metadata.

### Expert Agent Display Assets

Function: Project assets support Expert Agent visual presentation and public-facing previews.

Structure: `output/expert-agent-flyer.*` and static expert-agent image assets.

Key logic: keep generated display assets versioned when they are part of the product presentation, while runtime-only generated files should stay out of commits.

### Attachment And File Preview Path

Function: Open WebUI handles upload, preview, and model-accessible attachment context for Hermes.

Structure: file APIs, chat middleware file context helpers, R2/S3-compatible storage settings, and frontend file preview components.

Key logic: upload files through Open WebUI, forward image attachments as model-accessible URLs instead of base64, inject non-image attachments as `<attached_files>` metadata with bounded extracted text, and keep browser preview separate from model-facing URLs.

### Reusable Artifact Title Cards

Function: Chat transcript cards use meaningful artifact titles for iframe-style local artifacts.

Structure: `backend/open_webui/routers/utils.py` and chat artifact card rendering.

Key logic: prefer explicit iframe/title metadata, proxy only allowed local artifact viewer URLs for metadata lookup, and keep local artifact title resolution browser-safe.

### Trimmed Open WebUI Surface

Function: The fork removes broad Open WebUI product areas that are not needed for the Hermes-focused workflow.

Structure: frontend routes, chat input menus, admin settings, and disabled feature flags.

Key logic: keep chat/auth/admin/files/tools needed by Hermes, disable Ollama and unused workspace areas by default, and remove RAG/vector/image/code paths from the normal user flow unless explicitly needed later.

### Local Runtime

Function: Local development can run Hermes, Open WebUI backend, frontend, and artifact preview services together.

Structure: `scripts/start-oui.sh`, backend startup scripts, repo `.env`, and local service ports.

Key logic: load repo env for local non-Docker runs, prefer the start helper for backend/frontend lifecycle, restart services after middleware/env changes, and use focused runtime checks instead of full builds by default.

## Future Entry Rule

Add one section per durable feature:

```md
### Feature Name

Function: one sentence.

Structure: main files/modules.

Key logic: one to three short implementation notes.
```
