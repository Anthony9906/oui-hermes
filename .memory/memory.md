# OUI Hermes Shared Memory

## Current Objective

Status: active

- Analyze and maintain `oui-hermes`, a Hermes-focused fork of Open WebUI.
- Current verified baseline for local diff analysis: `8dae237a0` (`0.9.2 (#24081)`) to `HEAD` (`85255e84d`).

## Current State

Status: verified from local repository on 2026-05-13

- The project is not a full Open WebUI distribution; it is trimmed into a Hermes Agent chat UI, admin surface, and extension entry.
- Major changes after the Open WebUI 0.9.2 baseline are grouped as:
  - Open WebUI platform surface trimmed and many routes/assets removed.
  - Hermes API defaults and OpenAI-compatible forwarding set to Hermes gateway.
  - Hermes tool/reasoning stream events adapted into Open WebUI `function_call` / `function_call_output` rendering.
  - Expert Agent APIs and right-side chat pane added.
  - Direct attachment upload, preview, R2/S3 public URL generation, and `<attached_files>` injection added.
  - Runtime, Docker, dependency, Pyodide, and local startup paths simplified.

## Key Facts

Status: verified from files and Git history

- Remote: `https://github.com/Anthony9906/oui-hermes.git`.
- Diff base used for Open WebUI comparison: `8dae237a0..HEAD`.
- Diff size at analysis time: 141 files changed, 7578 insertions, 24849 deletions.
- `.env.example` disables Ollama, Channels, Notes, Calendar, Web Search, Code Execution, Code Interpreter, Image Generation, and sets `VECTOR_DB=none` by default.
- `backend/open_webui/main.py` mounts the retained API routers and adds `/api/v1/expert-agents`; it no longer mounts Ollama, retrieval, images, knowledge, prompts, skills, memories, notes, channels, or calendar routers.
- Frontend routes for Workspace, Notes, Channels, Calendar, Playground, and Admin Functions were deleted.
- `backend/open_webui/routers/expert_agents.py` reads local Hermes skill markdown from `~/.hermes/profiles/expertagent/skills` when present, filters bundled skills, and supports hidden/visible skill env controls.
- `backend/open_webui/utils/middleware.py` contains Hermes tool SSE parsing, display-only progress handling, duplicate pending tool suppression, attachment URL generation, and direct file context injection.
- `backend/open_webui/storage/provider.py` supports `r2` through the S3 provider and public URL generation via `R2_PUBLIC_BASE_URL` / `S3_PUBLIC_BASE_URL`.
- `package.json` renamed the app to `oui-hermes`, removed automatic `pyodide:fetch`, removed Cypress scripts/deps, and added `build:bigmem`.
- `Dockerfile`, `docker-compose.yaml`, `backend/dev.sh`, `backend/start.sh`, and `scripts/start-oui.sh` were simplified around local Hermes defaults.

## Next Useful Action

Status: active

- If asked for deeper proof, inspect exact diffs for:
  - `backend/open_webui/utils/middleware.py`
  - `backend/open_webui/routers/expert_agents.py`
  - `src/lib/components/chat/Chat.svelte`
  - `src/lib/components/chat/ChatControls.svelte`
  - `src/lib/components/common/ToolCallDisplay.svelte`
  - `src/lib/components/common/FileItemModal.svelte`

## Caveats

Status: verified limitation

- This memory is a recovery aid, not proof. Re-check current files/Git history before making compatibility, safety, or version claims.
- `DEVELOPMENT_PROGRESS.md` is an existing handoff document with richer historical detail, but `.memory/memory.md` is now the project memory entry point.

## Trim Verification

Status: verified from static repository inspection on 2026-05-13

- Corrected conclusion: trimmed Open WebUI features are not fully physically removed. Most user-facing routes and backend mount points were removed or disabled, but substantial backend routers/models/retrieval code and frontend API/component code still remain.
- Frontend route files for Workspace, Notes, Channels, Calendar, Playground, and Admin Functions are deleted, but related `src/lib/apis/*` and `src/lib/components/*` directories still exist for calendar, channels, notes, workspace, playground, functions, knowledge, prompts, skills, retrieval, images, memories, and ollama.
- Backend `main.py` does not mount Ollama, retrieval, images, knowledge, prompts, skills, memories, notes, channels, or calendar routers, but those router files and related models/retrieval directories still exist.
- Backend heavy RAG/vector/web dependencies are mostly removed from `backend/requirements.txt`, while code importing those packages remains under unmounted or lazy paths.
- Dependency trim risk: `backend/open_webui/storage/provider.py` still imports `boto3`, `botocore`, `google-cloud-storage`, and `azure-storage-blob` at module import time, while only `azure-identity` is present in `backend/requirements.txt`; because `files.py` imports `Storage` from this provider, a clean install may fail unless those packages are supplied elsewhere or imports are made lazy/requirements restored.
- Pyodide is not fully removed: static predownload files and `pyodide:fetch` script are gone, but `pyodide`, `@pyscript/core`, workers, stores, and UI references still remain.

## Hermes Session Continuity

Status: verified from local OUI Hermes and `/Users/yangxiaofeng/opensource/hermes-agent` source on 2026-05-13

- Hermes `gateway/platforms/api_server.py` documents and implements OpenAI Chat Completions session continuity via the `X-Hermes-Session-Id` request header. When this header is provided, Hermes uses that session id and loads history from `SessionDB`; when absent, it derives a deterministic `api-...` session id from the system prompt plus the first user message.
- Current OUI Hermes does not explicitly send `X-Hermes-Session-Id` for OpenAI-compatible requests. The frontend sends `chat_id` in the JSON body, `main.py` stores it in `metadata`, and `routers/openai.py` can forward `metadata.chat_id` as a configurable header only when `ENABLE_FORWARD_USER_INFO_HEADERS=true`.
- The default forwarded chat header name is `X-OpenWebUI-Chat-Id`, not `X-Hermes-Session-Id`, and `ENABLE_FORWARD_USER_INFO_HEADERS` defaults to false. Therefore same OpenWebUI chat to same Hermes session is not guaranteed by OUI defaults.
- Context behavior is separate from Hermes session continuity: normal OpenWebUI chat requests do send conversation context in the OpenAI-compatible `messages` payload. For persisted chats, the frontend sends the system prompt plus ids and the backend reloads the message chain from DB up to the current user message; for temporary chats, the frontend sends the current branch's message list directly. This means provider-visible context is present even without `X-Hermes-Session-Id`, but upstream Hermes-side session memory is still not explicitly bound to OpenWebUI `chat_id`.
- Correct follow-up if implementing: for Hermes base URLs, add a first-class mapping from OpenWebUI `metadata.chat_id` to the upstream header `X-Hermes-Session-Id`, without relying on user-info forwarding. Also consider returning/storing Hermes' echoed `X-Hermes-Session-Id` for new chats if the upstream generated one.

## Review Preparation

Status: verified from targeted local file inspection on 2026-05-13

- Current review object is the local fork `/Users/yangxiaofeng/cowain/oui-hermes`, not upstream Open WebUI and not the Hermes source tree.
- Review framing: most changes are implemented by keeping Open WebUI's chat/auth/admin/file shell, defaulting the OpenAI-compatible provider to Hermes, adapting Hermes stream/tool/file contracts in middleware, adding an Expert Agent side pane backed by local Hermes skill files, and disabling/removing many broad Open WebUI entry points.
- Key implementation risk to review first: OpenWebUI `chat_id` is persisted in request metadata and can be forwarded only through generic user-info headers when enabled; it is not first-class mapped to Hermes `X-Hermes-Session-Id` by default.
- Key cleanup risk to review first: feature trimming is mostly route/UI/default-config based; substantial unmounted source files and some residual dependencies/import risks remain.
- Current review conclusion: the fork's changes are usable as a pragmatic adaptation layer, but several implementation choices are architecturally weak for a Hermes-focused product. Main issues are: Hermes session continuity is not first-class (`X-Hermes-Session-Id` missing), context is carried mainly by OpenWebUI-side history assembly with token-limit risk, trimmed Open WebUI features are hidden/unmounted more than physically removed, local STT/TTS paths and dependencies remain despite a remote-only requirement, and attachment storage/direct URL handling has inconsistent R2/S3/local/fallback behavior. Treat these as review blockers before calling the implementation clean or production-ready.
- Additional verified review risks found on 2026-05-14:
  - Expert Agent skill update endpoints use `get_verified_user` and write directly to local Hermes `SKILL.md`; any authenticated user who can reach the drawer/API can modify visible local Hermes skills unless another layer blocks it.
  - `.env.example` and `scripts/start-oui.sh` use broad development defaults (`CORS_ALLOW_ORIGIN='*'`, `FORWARDED_ALLOW_IPS='*'`, `--forwarded-allow-ips "*"`, `0.0.0.0` hosts). These are not production-safe defaults.
  - `ENABLE_DIRECT_CONNECTIONS` is still exposed/configurable; when enabled, browser-side direct OpenAI-compatible calls can bypass backend middleware where Hermes-specific context/file/tool/session adaptation lives.
  - Image handling is partially disabled in `middleware.py` by local stubs that raise `Image handling is disabled`, while other code paths still call image conversion helpers. This creates inconsistent image behavior.
  - `VECTOR_DB=none` is used as a trim default, but `retrieval/vector/factory.py` has no `none` vector implementation and raises `Unsupported vector type: none` if retrieval processing is imported; file upload processing still lazily imports retrieval for processed files.
  - The startup script depends on an external local artifact preview service at `$HOME/Documents/Hermes/local-artifact-preview-service` and starts it on `0.0.0.0`, making local startup depend on a sibling repo/path outside this project.
  - Terminal/tool server integration remains mounted and is injected into chat payloads separately from normal selected tool ids, adding a large execution/proxy surface that is not clearly tied to the disabled code-execution/code-interpreter feature flags.

## Audio STT/TTS Remote-Only Requirement

Status: verified from local repository inspection on 2026-05-13

- Desired direction: future STT and TTS should use remote providers only.
- Current state does not satisfy this yet. Backend still keeps local STT through `faster-whisper` and local TTS through `transformers` / SpeechT5 code paths.
- Current dependency risk: `backend/requirements.txt` still includes `faster-whisper`, `soundfile`, `pydub`, and `av`; frontend `package.json` still includes `kokoro-js` and `@huggingface/transformers`.
- Current UI risk: admin audio settings still expose local faster-whisper STT and local Transformers TTS; chat audio settings and message playback still expose/use browser Kokoro.js.
- Follow-up cleanup should remove local audio engine options, remove local model dependencies, and constrain accepted `STT_ENGINE` / `TTS_ENGINE` values to remote providers such as OpenAI-compatible, Azure, ElevenLabs, Deepgram, or Mistral.

## Review Remediation Plan

Status: proposed on 2026-05-14; not implemented yet; corrected to Hermes-only on 2026-05-14

- Product boundary correction: OUI Hermes is a Hermes-targeted fork, so remediation should not preserve generic Open WebUI provider compatibility unless explicitly requested. Previous compatibility-preserving parts of the plan are superseded.
- Hermes session continuity: always map OUI `metadata.chat_id` to Hermes `X-Hermes-Session-Id` on model/tool upstream requests, independent of `ENABLE_FORWARD_USER_INFO_HEADERS`; remove or ignore generic `X-OpenWebUI-Chat-Id` forwarding for the Hermes path. Because Hermes loads session history from `SessionDB` when this header is present, OUI should switch the Hermes path to session-delta payloads: send only the current user turn and current-turn attachments, not the full DB-reconstructed conversation history. Do not send OUI system/developer prompts in the Hermes path; Hermes owns the agent/system prompt.
- Open WebUI trim cleanup: define the retained Hermes product surface and physically remove or quarantine generic Open WebUI surfaces. Priority slices are retrieval/vector/knowledge leftovers, Ollama/images/memories/prompts/skills/notes/channels/calendar/workspace/playground frontend APIs/components, direct connections, terminal/tool-server surface unless intentionally part of Hermes, Pyodide/code-interpreter leftovers, and unsafe dev defaults. Each slice should include import/build checks so hidden references are removed deliberately.
- Audio remote-only cleanup: remove local STT/TTS engines rather than only hiding UI. Backend should reject unsupported engines and keep only remote STT providers such as OpenAI-compatible, Deepgram, Azure, and Mistral, and remote TTS providers such as OpenAI-compatible, ElevenLabs, Azure, and Mistral. Remove `faster-whisper`, local Transformers/SpeechT5, browser Kokoro, and related UI/dependency/config paths after compatibility checks.

## Hermes-Only Remediation Implementation

Status: implemented and locally verified on 2026-05-14

- Hermes session continuity is now first-class for persisted chats: OUI marks Hermes delta requests, rejects `local:*` temporary chats in chat middleware, forwards `metadata.chat_id` as `X-Hermes-Session-Id`, and strips outgoing Hermes payloads to the current user message/current attachments instead of replaying DB history or OUI system/developer prompt.
- Temporary chat is no longer exposed as a product feature: default permissions are false, frontend creation paths and shortcut entries were removed/neutralized, and the backend returns `400 Temporary chats are disabled for Hermes sessions.` for `local:*` chat completion requests.
- Direct browser connections were removed from the reachable frontend/backend config surface: `ENABLE_DIRECT_CONNECTIONS` and `enable_direct_connections` are no longer returned, the user direct-connections settings UI was deleted, and browser-side `request:chat:completion` now returns a disabled error instead of calling provider URLs directly.
- Local STT/TTS was removed from active code and dependencies: backend accepted engines are remote-only, faster-whisper/Whisper config and local Transformers/SpeechT5 branches were removed, Kokoro/browser TTS and browser SpeechRecognition paths were removed, and `faster-whisper`, `soundfile`, `av`, `kokoro-js`, and `@huggingface/transformers` were removed from dependency manifests.
- File upload processing no longer imports generic retrieval processing for ordinary uploads; uploaded files are retained as attachments, remote STT can still transcribe supported audio, and `VECTOR_DB=none` now maps to a no-op vector client to avoid clean-import failures.
- Pyodide/browser code interpreter was removed from the frontend bundle and dependency graph: Pyodide workers/file-nav/admin code-execution UI were deleted, `pyodide` was removed from package manifests, and code paths now return explicit disabled errors/no-op behavior instead of loading browser Python.
- Verification run in this phase:
  - `python3 -m py_compile` passed for changed backend modules including Hermes helpers, middleware, OpenAI router, audio/files/config/storage/vector, builtin tools, and sanitize utility.
  - `npm run build` passed under local Node 24 after installing dependencies with `--engine-strict=false`; build output no longer contains Pyodide artifacts.
  - Static grep for `faster-whisper|set_faster_whisper_model|WHISPER_|kokoro-js|@huggingface/transformers|SpeechT5|TTS_ENGINE == 'transformers'|browser-kokoro|Kokoro|pyodide|Pyodide|directConnections|ENABLE_DIRECT_CONNECTIONS|enable_direct_connections|temporaryChatEnabled.set(true)|NEW_TEMPORARY_CHAT` returned no active hits in `backend`, `src`, and package manifests.
  - `npm run check` still fails on existing project-wide Svelte/TypeScript diagnostics, first errors including missing `process` types in `vite.config.ts`, implicit `any` in `RichTextInput` JS helpers, and existing `$i18n` store typing issues in auth/share routes. Treat this as a known baseline typecheck gap, not a successful clean typecheck.
- Remaining cleanup candidates: many unmounted generic Open WebUI source files still exist, especially Ollama, knowledge/retrieval routers, workspace/model helper components, pipelines/functions, memories, channels, calendar, image-generation remnants, and terminal/tool-server surfaces. They are not fully physically deleted in this phase; continue by deleting one feature slice at a time with import/build checks.

## Temporary Chat And Node Engine Follow-Up

Status: verified and corrected on 2026-05-14; updated for Node 24 support and clean build warnings on 2026-05-14

- Temporary chat user entry points are hidden/removed, and backend Hermes chat completion rejects `local:*` chat ids. Follow-up cleanup also removed the residual temporary chat display blocks from chat navbar/placeholders, removed stale `temporaryChatByDefault` settings state, and removed the unused temporary-chat tooltip translation key from locale files.
- Static verification command `rg -n "Temporary Chat|This chat won't appear|temporaryChatByDefault|NEW_TEMPORARY_CHAT|temporaryChatEnabled\.set\(true\)|Allow Temporary Chat|Temporary Chat by Default" src backend package.json package-lock.json` returned no matches after the cleanup.
- Hard-disable update: `src/lib/stores/index.ts` now exports a disabled temporary chat store that keeps the existing Svelte store API but coerces every `set`/`update` to `false`. This means leftover imports and defensive checks remain compatible, but accidental writes cannot make `$temporaryChatEnabled` true or surface temporary-chat UI.
- Node 24 support correction: npm registry verification showed latest `i18next-parser` is still `9.4.0` and only declares `node: ^18.0.0 || ^20.0.0 || ^22.0.0`; there was no compatible same-package upgrade path.
- Implemented replacement: removed `i18next-parser` from dev dependencies and replaced `npm run i18n:parse` with `scripts/i18n-parse.mjs`, a local scanner for simple `$i18n.t(...)` / `i18n.t(...)` string-literal keys. The script updates all locale catalogs and preserves existing translations for retained keys.
- Root engine declaration is now `node >=18.13.0 <=24.x.x` in `package.json` and `package-lock.json`.
- Build warning cleanup update: `npm run build` now completes with zero warning lines in `/tmp/oui-hermes-build-final-2.log` after fixing Svelte 5 warnings for non-void self-closing tags, stale `svelte-ignore` codes, unused exported props, a11y labels/roles/keyboard access, invalid `href="#"`, module-level reassignment warnings, third-party Svelte resolve warning config, and Rollup chunk-size warning threshold.
- Prettier 3 cleanup: removed deprecated `pluginSearchDirs` from `.prettierrc` and removed `--plugin-search-dir` from the `format` script. Static grep for `aria-label="Action"|pluginSearchDirs|plugin-search-dir` returns no matches in `.prettierrc`, `package.json`, and `src`.
- Verification after replacement and warning cleanup: `npm install --package-lock-only --engine-strict=true --ignore-scripts` passes on local Node `v24.5.0`; a lockfile engine scan has no Node 24-incompatible package hits; `npm run i18n:parse` passes; `npm run build` passes with no Svelte/Vite/Rollup warning output. Existing `npm run check` project-wide TypeScript/Svelte diagnostics remain a separate known baseline gap unless explicitly fixed later.

## Local Manual Startup

Status: verified and corrected during manual service startup on 2026-05-15

- Frontend dev server was started successfully with `npm run dev -- --host 0.0.0.0 --port 5173`; `curl -I http://localhost:5173/` returned `200 OK`.
- Correction: a separate frontend dev server is not required for normal manual testing after `npm run build` has produced `build/`. The FastAPI backend mounts `FRONTEND_BUILD_DIR` at `/`, and `FRONTEND_BUILD_DIR` defaults to repo-root `build/`, so `http://localhost:8080/` serves the built SvelteKit SPA directly.
- The temporary Vite dev server on port 5173 was stopped after confirming `http://localhost:8080/` returns `200 OK` and port 5173 is no longer listening.
- Backend was started successfully on port 8080 with explicit local defaults: `HERMES_API_BASE_URL=http://127.0.0.1:8642`, `OPENAI_API_BASE_URL=http://127.0.0.1:8642`, `ENABLE_OLLAMA_API=false`, `ENABLE_OPENAI_API=true`, `ENABLE_WEB_SEARCH=false`, `VECTOR_DB=none`, `STORAGE_PROVIDER=local`, `ARTIFACT_STORAGE_PROVIDER=local`, `CORS_ALLOW_ORIGIN=http://localhost:5173`.
- Verified backend health: `curl http://localhost:8080/health` returned `{"status":true}`.
- Startup dependency correction discovered: current `backend/requirements.txt` misses runtime imports `typer`, `beautifulsoup4`, and `langchain-core`; manual startup used temporary `uv run --with typer --with beautifulsoup4 --with langchain-core ...` until requirements are fixed.
- The active backend process loads packages from uv's ephemeral cache environment, not a project `.venv`: `/Users/yangxiaofeng/.cache/uv/archive-v0/6Z41uENv_WjvlgwNIjAMq/lib/python3.12/site-packages`.
- Startup coupling correction made: `backend/open_webui/utils/oauth.py` no longer imports `validate_url` from `open_webui.retrieval.web.utils`; it uses a local lightweight http/https URL validator, avoiding a startup-time dependency on retrieval/langchain-community.
- Remaining follow-up: add the verified missing runtime packages to `backend/requirements.txt` or further trim the code paths that require them, then re-run the backend without temporary `--with` packages.
- Update on 2026-05-15: Hermes-only startup trim removed the active startup dependency on `typer`, `beautifulsoup4`, and `langchain-core` by simplifying `open_webui/__init__.py`, setting `CHANGELOG = {}` instead of parsing changelog HTML in `env.py`, and replacing the LangChain tool schema conversion in `utils/tools.py` with a local Pydantic JSON-schema adapter. Static grep for those imports in the active startup files returned no matches, and `python3 -m py_compile` passed for the changed files.
- Update on 2026-05-15: backend was restarted successfully on port 8080 without the extra `--with typer --with beautifulsoup4 --with langchain-core` arguments. The working manual command uses `uv run --with-requirements backend/requirements.txt uvicorn open_webui.main:app --host 0.0.0.0 --port 8080 --app-dir backend` plus the Hermes/local env defaults. For same-origin testing at `http://localhost:8080`, set `CORS_ALLOW_ORIGIN='http://localhost:8080;http://127.0.0.1:8080;http://localhost:5173'`; using only `http://localhost:5173` causes Socket.IO to reject `http://localhost:8080`, which can break live streaming in manual tests.
- Update on 2026-05-15 after restoring chat background tasks and initial-title fallback: backend is running in detached `screen` session `oui-hermes-backend` on port 8080, with Python PID `23623`; `curl http://127.0.0.1:8080/health` returned `{"status":true}`. Stop it with `screen -S oui-hermes-backend -X quit` if needed.

## Chat Streaming UI Fix

Status: revised after user retest on 2026-05-15

- User-reported symptom: sending a chat message produced an upstream/Hermes answer and persisted it, but the current page did not show real-time streaming output until refresh.
- Verified frontend risk: `src/lib/components/chat/Chat.svelte` registered `chatEventHandler` only once against the value of `$socket` at component mount. If the root layout initialized/replaced the socket after the chat component mounted, the active chat page had no `events` listener even though the backend continued writing responses to the chat DB.
- User retest found the previous fix was insufficient and also caught a contract violation: frontend still sent a `messages` array that could include Open WebUI system content, and `files` was assembled from `chatFiles`, which could include historical attachments.
- Revised fix: `Chat.svelte` now sends an explicit single current-turn user message only (`messages: [{ role: "user", content, files }]`), uses only current user message attachments for the request-level `files`, and handles socket events for any message id already present in this chat component's local history even if the incoming generated `chat_id` does not yet match `$chatId`.
- Revised backend fix: `backend/open_webui/socket/main.py` event emitter now prefers direct socket delivery to `request_info.session_id` when present, falling back to `user:{user_id}` room only when no session id exists. This reduces live stream loss from room join / multi-tab state.
- Additional correction: OUI background model tasks were still able to send full chat context after the main answer for title/tags/follow-up generation. Frontend now sends `background_tasks: {}` for chat completions, and backend `background_tasks_handler` returns immediately when `metadata.hermes_session_delta` is set.
- Correction on 2026-05-15: the previous background-task disablement was overbroad and is superseded. Chat title, tags, and follow-up generation are restored. Frontend chat requests again send `title_generation`/`tags_generation` for new root chats and `follow_up_generation` for responses. Task completions now sanitize task metadata and temporarily replace `request.state.metadata` during task calls so title/tags/follow-up do not inherit `hermes_session_delta` or `X-Hermes-Session-Id`; configured `TASK_MODEL_EXTERNAL` can therefore run these tasks on a non-Hermes provider. Title fallback now uses the user's message text, truncated to 100 characters, before falling back to `New Chat`.
- Correction follow-up on 2026-05-15: initial new-chat title creation no longer hardcodes `New Chat`. `backend/open_webui/main.py` and `src/lib/components/chat/Chat.svelte` now derive the first title from the current user message immediately, truncated to 100 characters, and background title generation can later overwrite it with a better generated title.
- Update on 2026-05-15: title generation timing was changed so a new chat's first root user message schedules title generation immediately after the chat row/history is inserted, in parallel with assistant response generation. The assistant completion path no longer receives `title_generation` for that first task, preventing duplicate title generation after the assistant finishes. Follow-up generation remains after assistant completion because it depends on the assistant answer; tags remain in the normal post-response background path. Task completion calls now run with an isolated request-state copy instead of mutating the live chat request's `request.state.metadata`, preventing parallel title generation from interfering with the assistant request.
- Verification for this correction: `python3 -m py_compile backend/open_webui/main.py backend/open_webui/routers/tasks.py backend/open_webui/utils/middleware.py` passed, and `npm run build` passed after formatting `src/lib/components/chat/Chat.svelte`.
- Verification after revision: `python3 -m py_compile backend/open_webui/socket/main.py backend/open_webui/utils/middleware.py backend/open_webui/utils/hermes.py backend/open_webui/routers/openai.py` passed. `npm run build` passed and rewrote repo-root `build/`. Backend was restarted; `curl http://127.0.0.1:8080/health` returned `{"status":true}` and `lsof` showed Python PID `38704` listening on TCP 8080.
- Remaining caveat: no authenticated end-to-end browser chat was executed by Codex in this step; the user should hard-refresh `http://localhost:8080/` and test a send. If streaming is still absent, the next evidence to collect is browser console socket logs plus one backend `events` payload for the affected chat/message ids.
- Superseded build warning note: the previous remaining `@xyflow/svelte` `isInputDOMNode` unused-import warning was fixed on 2026-05-15 by adding `scripts/patch-xyflow-svelte.mjs` and running it from `postinstall`, `prebuild`, and `prebuild:bigmem`.

## Chat Advanced Settings Removal

Status: implemented and locally verified on 2026-05-15

- User-facing chat advanced controls were removed for Hermes-only behavior. The navbar no longer exposes the Controls/knobs button, `ChatControls.svelte` no longer has a Controls tab or fallback, and the old `src/lib/components/chat/Controls/Controls.svelte` component was deleted.
- Chat/user settings no longer show or save per-user System Prompt / Advanced Parameters. This matches the Hermes boundary: Hermes owns system/agent prompt and model behavior; OUI should not expose per-chat/per-user prompt or generation params for Hermes sessions.
- Group/admin permissions no longer show `Allow Chat Controls`, `Allow Chat Valves`, `Allow Chat System Prompt`, or `Allow Chat Params`; default permissions for those fields are now false.
- Chat requests no longer merge or send `$settings.params`, persisted chat `params`, or stop tokens. Persisted chats/new chats also stop writing `system` and `params` fields from the chat UI path.
- Verification: `npm run build` passed. Targeted static searches for chat-side `AdvancedParams`, `Allow Chat Controls`, `Advanced Parameters`, `System Prompt`, `bind:params`, `$settings?.params`, and chat-controls permission gates returned no active hits under the chat/admin permission surfaces.

## User Context Injection Status

Status: verified from current code on 2026-05-15

- The original Open WebUI memory/user-context injection helper still exists as `chat_memory_handler()` in `backend/open_webui/utils/middleware.py`; it builds a `User Context:\n...` block from memory search results and appends it to the system message.
- For normal persisted Hermes chats, this injection is currently bypassed. `process_chat_payload()` sets `hermes_session_delta = bool(chat_id)`, reduces the outgoing payload to the current user message, clears `form_data['features']`, and later only processes feature-based memory/web/search injections under `if features and not hermes_session_delta`.
- This means the old memory-derived `User Context` block is not sent on normal Hermes chat turns after the Hermes session-delta cleanup. This is distinct from input-template variable replacement such as `{{USER_NAME}}`, `{{USER_EMAIL}}`, and `{{USER_LOCATION}}`, which still exists in `src/lib/components/chat/MessageInput.svelte`.

## Admin Extension Settings Visibility

Status: implemented and locally verified on 2026-05-15

- Goal: hide the admin settings `Integrations` tab, shown as `扩展功能` in zh-CN, without removing backend APIs or broad extension-related source files.
- Implementation: `src/lib/components/admin/Settings.svelte` no longer imports `Settings/Integrations.svelte`, no longer includes `integrations` in the recognized/enabled settings tabs, removes the tab/search keywords/icon branch, and removes the content render branch. Direct navigation to `/admin/settings/integrations` now falls back to the General settings tab.
- Verification: targeted grep for `integrations|Integrations` in `src/lib/components/admin/Settings.svelte` returned no matches; `git diff --check` passed; `npm run build` passed.

## Chat vs Task Model Scope

Status: implemented and locally verified on 2026-05-15

- Goal: only Hermes-backed models should be selectable for normal chat sessions; non-Hermes OpenAI-compatible connections such as OpenAI/Gemini should remain available for background tasks such as title, tags, and follow-up generation.
- Current implementation adds model usage metadata at the connection/model boundary. `OPENAI_API_CONFIGS` now normalizes `enable_chat`, `enable_task`, and `model_usage`. Correction: `HERMES_API_BASE_URL` is only used to infer a backwards-compatible default when old connection configs lack `enable_chat`; it is not a hard gate. Admin connection config is the source of truth for whether a connection's models may appear in chat or only be used by tasks.
- `/api/models` now defaults to `scope=chat`, so the global frontend model store and chat model selector receive only chat-enabled models. `/api/models?scope=task` returns all task-enabled models; `/api/models?scope=task-only` returns only task-enabled and chat-disabled models for Admin Settings → Interface task model selectors. `/api/models/base` defaults to all base models for admin management and also accepts `scope`.
- Chat completion now enforces the boundary server-side: `/api/chat/completions` and `/api/v1/chat/completions` reject task-only models with `400 This model is restricted to background tasks and cannot be used for chat.` Multi-model fanout is checked per target model. Arena fallback model selection also filters to chat-enabled models.
- Task generation remains enabled. `get_task_model_id` only honors configured task models if their `model_usage.task` is true, and task settings fetch `scope=task-only`, so External Task Model selects non-chat task-only models rather than mixing chat models into the task selector.
- Admin UI updates: connection editor includes `Allow in Chat` and `Allow for Tasks`; model management shows `Task only`, `Chat only`, or `Chat + Task`; model defaults/pinned-model config filters out task-only ids so they cannot be saved as chat defaults.
- Verification: `python3 -m py_compile backend/open_webui/utils/model_usage.py backend/open_webui/routers/openai.py backend/open_webui/main.py backend/open_webui/utils/models.py backend/open_webui/utils/task.py backend/open_webui/utils/chat.py` passed; `npm run build` passed; targeted `git diff --check` passed.

## Version Update Check Removal

Status: implemented and locally verified on 2026-05-18

- Goal: remove new-version checks and update reminders from OUI Hermes.
- Frontend release checking was removed from app startup, user About settings, and Admin General settings. The update toast component and the user setting `showUpdateToast` were removed, along with related settings-search keywords.
- SvelteKit version polling and root-layout auto-reload-on-version-change logic were removed. Socket reconnect no longer calls `/api/version` to compare app/deployment versions for forced reload; `/api/version` itself remains because sync/export code still uses current version metadata.
- Backend GitHub latest-release checking was removed: `/api/version/updates`, `ENABLE_VERSION_UPDATE_CHECK`, and the `enable_version_update_check` config feature are no longer active.
- Verification: `python3 -m py_compile backend/open_webui/main.py backend/open_webui/env.py` passed; targeted grep for active update-check/reminder symbols returned no matches outside locale catalogs; `git diff --check` passed; `npm run build` passed and rewrote `build/`.
- Caveat: unused translation catalog keys such as `Check for updates` may still remain until the locale parser cleanup is run; they are not active UI/runtime references.

## Xyflow Build Warning Patch

Status: implemented and locally verified on 2026-05-15

- `@xyflow/svelte@0.1.39` ships `dist/lib/components/KeyHandler/KeyHandler.svelte` with `isInputDOMNode` imported from `@xyflow/system`; Svelte/Rollup reports it as unused even though the dependency uses it in markup.
- Added `scripts/patch-xyflow-svelte.mjs`, which idempotently patches the installed dependency by removing the imported `isInputDOMNode` and injecting an equivalent local helper copied from `@xyflow/system` behavior.
- Added `postinstall`, `prebuild`, and `prebuild:bigmem` hooks so the patch survives fresh installs and is applied automatically before production builds.
- Verification: `npm run build` passed without the previous `@xyflow/svelte` warning.

## Attachment Storage / R2

Status: partially superseded by `Attachment Storage Config And Hermes URL Context` on 2026-05-15

- Attachment upload is not hardcoded to Cloudflare R2. `backend/open_webui/routers/files.py` calls the configured global `Storage.upload_file`, and `backend/open_webui/storage/provider.py` selects `local`, `s3`/`r2`, `gcs`, or `azure` from `STORAGE_PROVIDER`.
- R2 is implemented as an S3-compatible alias: `STORAGE_PROVIDER=r2` maps to `S3StorageProvider`, with config preferring `R2_*` variables and falling back to `S3_*` variables where applicable.
- Default storage remains local unless `STORAGE_PROVIDER` or `ARTIFACT_STORAGE_PROVIDER` is set.
- Local startup path caveat: `scripts/start-oui.sh` defaults `STORAGE_PROVIDER` and `ARTIFACT_STORAGE_PROVIDER` to `r2` if they are not already set, so using that script makes R2 the runtime default even though config.py's global fallback is local.
- With S3/R2 provider, uploads are first written into `UPLOAD_DIR` by `LocalStorageProvider.upload_file`, then uploaded to S3/R2, and `STORAGE_LOCAL_CACHE=true` leaves the local cached copy in place. Seeing a local file therefore does not by itself prove the canonical storage provider is local; the DB `files.path` value is the key evidence (`s3://...` vs local filesystem path).
- Image attachments and non-image attachments can appear different in model payloads: images are represented as `image_url` content parts for vision models, while non-image files are usually injected as `<attached_files>` with extracted text and/or a tokenized `/api/v1/files/{id}/content/direct` URL fallback.
- Review risk: `backend/open_webui/utils/middleware.py` imports `get_public_url_for_path` and `get_storage_provider_for_path` from `backend/open_webui/storage/provider.py`, but the current provider module only defines `get_storage_provider` and `S3StorageProvider.get_public_url`. This means the intended direct public URL / presigned URL path can fail and fall back to tokenized `/api/v1/files/{id}/content` URLs unless helper functions are added or the middleware is corrected.

## Attachment Storage Config And Hermes URL Context

Status: implemented and locally verified on 2026-05-15

- Goal: configure OUI user-uploaded attachment object storage from an Admin-only UI/API, and make Hermes consume only public attachment URLs from message context. Hermes is not the storage owner; it only receives `name + url` and reads objects from the configured storage.
- Backend added persistent runtime `STORAGE_CONFIG` defaults from existing S3/R2 env values, exposed as Admin-only `/api/v1/configs/storage` GET/POST and `/api/v1/configs/storage/verify`. Saved config overrides startup env defaults; blank secret fields preserve existing secrets; responses expose only `*_configured` booleans.
- Storage provider lookup now supports dynamic app config instead of relying only on a module-level singleton. S3/R2-compatible config includes provider, endpoint, bucket, region, access key, secret key, addressing style, key prefix, and public base URL.
- File uploads now reject filenames without an extension. S3/R2 object keys and generated public URLs preserve the original extension so Hermes can infer file type from URL suffix.
- Hermes direct message context now injects only:
  - `<system_default_context><current_conversation_user user_id="..." user_name="..." display_name="..." /></system_default_context>`
  - `<attached_files><file name="..." url="..." /></attached_files>`
    It does not inject locale, timezone, file id, size, content type, extracted text, or inline file body.
- For Hermes session-delta requests with attachments, missing public object-storage URL now raises a clear `400` asking Admin to configure attachment object storage. The Hermes path no longer falls back to local `/api/v1/files/.../content/direct` URLs.
- Frontend Admin Settings now includes an `Attachment Storage` page with provider, endpoint, bucket, region, credentials, addressing style, key prefix, and public base URL fields plus Save/Verify actions. Secrets are masked and never displayed back to the browser.
- Verification: `python3 -m py_compile backend/open_webui/config.py backend/open_webui/storage/provider.py backend/open_webui/routers/configs.py backend/open_webui/routers/files.py backend/open_webui/utils/middleware.py backend/open_webui/main.py` passed; `npm run build` passed; `git diff --check` passed.
- Remaining caveat: no live R2/S3 credentials were available in this run, so the real write/delete/public-URL verify flow was implemented but not exercised against an external bucket locally.
- Follow-up fix on 2026-05-18: MinIO/proxy deployments may return `405 Method Not Allowed` for public object `HEAD` even when `GET` works. Storage verify now tries `HEAD` first and falls back to a ranged `GET` on `405`, so MinIO public URL verification is not rejected solely because HEAD is unavailable.
- Runtime update on 2026-05-18: backend on port 8080 was restarted in `screen` session `oui-hermes-backend` after the MinIO verify fallback fix. `curl http://127.0.0.1:8080/health` returned `{"status":true}`. An unauthenticated `POST /api/v1/configs/storage/verify` returned `401 Not authenticated`, confirming the running route accepts POST and is no longer surfacing method mismatch at the route layer.
- Correction on 2026-05-18: the previous "Hermes direct attachment context injects" implementation was incomplete. `process_chat_payload()` injected `user_identity` / `attached_files`, but `routers/openai.py` then called `build_hermes_delta_payload()`, which re-read `metadata.user_message` and replaced the processed message with the original user message, dropping the XML context blocks. Fix: `build_hermes_delta_payload()` now prefers the already-processed payload user message and only falls back to `metadata.user_message` when needed. Regression test added in `backend/open_webui/test/utils/test_hermes.py`; verified with `PYTHONPATH=backend uv run --with-requirements backend/requirements.txt pytest backend/open_webui/test/utils/test_hermes.py -q`, `python3 -m py_compile backend/open_webui/utils/hermes.py backend/open_webui/test/utils/test_hermes.py`, `git diff --check`, and backend restart/health check on port 8080.
- Contract update on 2026-05-18: `user_identity` is replaced by the clearer default-session-context wrapper `<system_default_context><current_conversation_user ... /></system_default_context>`, so the model can distinguish OUI system-default conversation user context from the user's own text. `attached_files` remains a current-message attachment block.
- Attachment path update on 2026-05-18: new chats now use a frontend-preallocated `chat_id` before first upload/send, so uploaded file object keys can be grouped as `{key_prefix}/{chat_id}/{file_id}_{filename}` while preserving extensions and avoiding same-name overwrite. Upload metadata carries `chat_id`, and backend validates client chat ids with a strict safe-character regex before using them as object-key directories. Current Hermes contract keeps both image and non-image user-uploaded attachments in URL-only `<attached_files>`; images are not sent as OpenAI-compatible `image_url` parts on the Hermes session-delta path.

## External API Server Diff

Status: verified by `git diff --no-index` on 2026-05-13

- Compared source object: `/Users/yangxiaofeng/opensource/hermes-agent/gateway/platforms/api_server.py` at git `5621fc449a7c00f11168328c87e024a0203792c3`.
- Compared external file: `/Users/yangxiaofeng/Library/Containers/com.tencent.WeWorkMac/Data/Documents/Profiles/22895E5674E66DF4E6F928E8BDFCCB9A/Caches/Files/2026-05/adc807ff8be488bf4be2037c50cab52f/api_server.py`.
- External file is much larger: 3290 lines vs 1904 lines; diff is 1535 insertions and 149 deletions.
- Main verified deltas: multimodal/image content normalization, `X-Hermes-Session-Key` long-term memory scoping, detailed health and capabilities endpoints, Responses API streaming SSE, run status polling and stop endpoint, active run status tracking, 10 MB request body limit, safer port parsing, reasoning/tool lifecycle streaming improvements, response history deduplication, and server-side session auto-title scheduling.
- Syntax check passed for both files with `python -m py_compile`.

## Expert Agent Architecture

Status: verified from targeted local file inspection on 2026-05-14

- Expert Agent in OUI Hermes is primarily a local Hermes Skill catalog/editor and chat entry point, not a standalone Open WebUI-side agent runtime.
- Backend router `/api/v1/expert-agents` scans Hermes `SKILL.md` files under `HERMES_EXPERT_AGENT_SKILLS_DIR`, or defaults to `$HERMES_HOME/profiles/expertagent/skills` when present, otherwise `$HERMES_HOME/skills`.
- The backend excludes bundled/hidden skills and supports a visible allowlist through `HERMES_EXPERT_AGENT_HIDDEN_SKILLS` and `HERMES_EXPERT_AGENT_VISIBLE_SKILLS`.
- Skill metadata is parsed from YAML frontmatter. Hermes metadata is read from `metadata.hermes`; OUI-specific icon fields are read/written under `metadata.open_webui.expert_agent`.
- The API exposes list/detail and write endpoints. Detail returns full markdown content and the local filesystem path. Write endpoints update the `SKILL.md` file directly after minimal validation.
- Frontend `ExpertAgentDrawer` loads skill cards, opens detail/source views, edits icon/source metadata, and emits a start event.
- Starting an Expert Agent chat sets URL params or a store request, prefers the `expertagent` model id when available, saves `meta.expert_skill_name`, and submits a generated prompt that tells the model which expert skill is enabled.
- Review risks: write endpoints require only `get_verified_user` rather than admin permission; local filesystem paths are exposed; there is no DB/version/audit/locking layer; frontend may perform N+1 detail reads; UI metadata is coupled into Hermes source markdown.
- Hermes itself has a Web UI FastAPI endpoint `GET /api/skills` in `/Users/yangxiaofeng/opensource/hermes-agent/hermes_cli/web_server.py`, served by `python -m hermes_cli.main web` on the local dashboard port. It returns skill list metadata from `tools.skills_tool._find_all_skills()` plus `enabled` state, and `PUT /api/skills/toggle` toggles disabled skills. This is separate from the Hermes OpenAI-compatible gateway `gateway/platforms/api_server.py`, which does not expose skill list/detail routes.
- Hermes also has internal model tools `skills_list` and `skill_view` in `tools/skills_tool.py`, but those are tool-call functions registered for the agent, not direct HTTP endpoints for OUI.
