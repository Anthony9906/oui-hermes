# Development Progress

Last updated: 2026-07-22

This is the compact handoff for the Hermes-focused Open WebUI fork. It keeps only the current baseline, durable integration contracts, verified behavior, active risks, and next actions; implementation chronology belongs in Git history.

## Current Baseline

| Area | Development baseline | Deployment status |
| --- | --- | --- |
| OUI-Hermes | `940a4f1e692981120ef700d857b1b452ccd07f99` from `origin/codex/hermes-run-approvals` | Same OUI baseline |
| Hermes Agent | v0.19.0 on `expert/codex/hermes-v0.19.0-gateway`, HEAD `5a7b1f3ffefc493e49cf77d7526f396bf5f2a6da` | Still v0.18.2 on `expert/codex/production-v0.18.2`, HEAD `3f1c4dce9a34095b59bbc1397dfb7e937d9d89d4` |
| Hermes release anchor | Official `v2026.7.20` plus eight local enhancement commits | Upgrade pending |
| Deployment artifact | Tag `deploy/hermes-v0.19.0-gateway-20260722` | Follow `HERMES_V0.19.0_DEPLOYMENT_UPGRADE_GUIDE.md` |

The development Hermes branch and deployment tag are published to `Anthony9906/herems-expert`. OUI's intentionally untracked `output/` and `tmp/` artifact directories remain outside version control.

## Environment Mapping

- Development profile: `expertagent`, stored under `~/.hermes/profiles/expertagent/`.
- Deployment profile: `expert-agent`, stored under `~/.hermes/profiles/expert-agent/`.
- Do not copy profile state between environments or normalize the two names.
- Standard development ports are Hermes `8642`, OUI backend `8080`, frontend `5173`, AG-UI Bridge `8000`, and MinIO `9000/9001` when enabled.
- OUI root `.env` is ignored by Git; API keys and other secrets must not be recorded here.

## Product And Integration Boundary

Open WebUI owns chat UX, authentication, uploads, storage, previews, approval UI, AG-UI rendering, and Expert Agent discovery. Hermes owns agent execution, Runs, reasoning/tool events, approvals, sessions, skills, and Gateway platforms.

Primary integration points:

- Runs adaptation: `backend/open_webui/utils/middleware.py`, `backend/open_webui/utils/hermes_runs.py`
- Approval proxy and UI: `backend/open_webui/routers/hermes_runs.py`, `src/lib/hermes-approvals/`
- AG-UI bridge and rendering: `backend/open_webui/mcp/agui_bridge/`, `src/lib/agui/`
- Expert Agent discovery: `backend/open_webui/routers/expert_agents.py`
- Hermes Gateway/API enhancements: `gateway/platforms/api_server.py`
- Hermes Dashboard profile status: `hermes_cli/web_server.py`

## Stable Runtime Contracts

### Runs, Reasoning, And Tools

- OUI enables Runs only when `HERMES_RUN_APPROVALS_ENABLED=true` and Hermes advertises the required capabilities.
- Only `reasoning.delta` becomes visible reasoning; progress-like text must not duplicate the final answer.
- Concurrent tools are correlated by `tool_call_id`; arguments, progress, and results must stay attached to the same call.
- Hermes progress events are display metadata, not instructions for OUI to execute tools locally.
- The v0.19.0 enhancement branch restores persisted Runs history and preserves reasoning/tool metadata across refresh and continuation.

### Approvals

- Approval decisions continue through the Hermes Runs approval endpoint, never as ordinary chat messages.
- Supported UI decisions are `once`, `session`, and `deny`; permanent `always` is intentionally absent.
- OUI holds active approval ownership, ordering, and idempotency in a process-local registry.
- Known limitation: Hermes keys approval state by `run_id`, so `session` currently applies within one Run rather than across later chat messages. This is accepted deferred work.

### AG-UI, Expert Agents, And Files

- Choice/custom-answer cards send structured content while the chat bubble shows natural language; approval cards remain a separate path.
- Team Expert Agent cards come only from `skills/experts/`.
- Open WebUI owns uploads, storage, preview URLs, model-accessible attachment URLs, and `<attached_files>` injection.
- `STORAGE_PROVIDER` and `ARTIFACT_STORAGE_PROVIDER` are independent; `local_artifact` is not a general upload provider.
- Historical chats cannot recover structured tool or media metadata that was never persisted.

## v0.19.0 Enhancement Set

The development branch is the official v0.19.0 release plus eight focused commits:

1. Preserve reasoning and tool-progress metadata.
2. Fix Dashboard multimodal session rendering.
3. Generate API Server session titles.
4. Expose rich Hermes Runs tool events.
5. Stream real reasoning from Runs.
6. Harden concurrent Agent Run tool events.
7. Restore persisted history for Agent Runs.
8. Scope Dashboard Gateway status to the selected profile.

The delta from the official release is limited to seven source/test files under the Gateway API, Dashboard API/UI, and their regression tests. Future Hermes upgrades should port this commit set onto the exact official release tag and validate it before changing deployment.

## Verified Development Behavior

- Hermes reports v0.19.0 and API Server `/health` returns healthy on `8642`.
- Dashboard profile status resolves `expertagent` state correctly and shows the live Gateway/API Server rather than default-profile stale state.
- Final Dashboard/profile regression suites passed 67 relevant tests; Python syntax and whitespace checks passed.
- Hermes Dashboard web tests, type checking, and production build passed during the v0.19.0 migration.
- Runs integration was exercised for real reasoning, approval allow/deny, parallel tool-call correlation, refresh, and persisted continuation.
- OUI's existing Runs/approval contract remains compatible; no OUI source upgrade is required solely for the Hermes v0.19.0 deployment.

## Active Risks

- Deployment still runs Hermes v0.18.2; do not assume development and deployment are currently identical.
- The approval registry is process-local; backend restart and multi-worker recovery need shared persistence or explicit recovery semantics.
- `session` approval wording and actual Run-scoped behavior remain mismatched across chat messages.
- Hermes exposes an unsandboxed terminal backend; restrict API reachability to trusted networks or introduce a sandbox before broader exposure.
- Dependency audits still contain unresolved npm findings; no automatic audit fix has been applied.

## Next Actions

1. Upgrade deployment Hermes with `HERMES_V0.19.0_DEPLOYMENT_UPGRADE_GUIDE.md`, using profile `expert-agent` and pinned commit `5a7b1f3ff`.
2. Re-run the deployment acceptance matrix for reasoning, concurrent tools, approvals, history, Dashboard profile state, attachments, and AG-UI artifacts.
3. Keep the v0.18.2 rollback branch and deployment state backup until the observation period is accepted.
4. Design the cross-message approval-scope fix without allowing one concurrent Run to authorize another.

## Maintenance Rule

Replace superseded statements instead of appending dated debugging history. Keep only current behavior, evidence, durable constraints, active risks, and the next few concrete actions.
