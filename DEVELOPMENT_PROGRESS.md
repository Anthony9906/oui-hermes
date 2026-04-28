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

### Removed Historical Renderer

- `src/lib/components/chat/Messages/HermesTraceBlocks.svelte` was an unused historical artifact and has been removed.
- Do not reintroduce an active `message.hermesTraceParts` / `hermes:trace` rendering path unless there is a new explicit product decision to abandon native Open WebUI `<details>` rendering.

### Layout And Styling Adjustments

- `/automations` main content container now subtracts `20px` from the sidebar width formula:
  - `src/routes/(app)/automations/+page.svelte`
  - `md:max-w-[calc(100%-var(--sidebar-width)-20px)]`
- Admin pages now subtract `20px` from the main content width formula:
  - `src/routes/(app)/admin/+layout.svelte`
  - `md:max-w-[calc(100%-var(--sidebar-width)-20px)]`
  - collapsed-sidebar fallback also subtracts `20px`.
- Admin top menu and settings side menu text colors were adjusted from low-contrast gray to white/white-opacity styles for readability on the blue-purple background:
  - `src/routes/(app)/admin/+layout.svelte`
  - `src/lib/components/admin/Settings.svelte`

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
