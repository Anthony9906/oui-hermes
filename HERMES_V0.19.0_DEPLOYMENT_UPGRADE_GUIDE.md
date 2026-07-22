# Hermes v0.19.0 Deployment Upgrade Guide

Last updated: 2026-07-22

This runbook upgrades the deployment server from the verified Hermes v0.18.2 enhanced baseline to the exact v0.19.0 enhanced baseline produced and tested on the development machine. It is intentionally branch- and commit-pinned: do not recreate the Runs changes by hand and do not update from upstream `main`.

The maintained copy is published in `Anthony9906/oui-hermes` on branch `codex/update-development-progress-20260721`. The deployment Codex may read this file from that remote branch without switching or rebuilding the deployed OUI source tree.

## Fixed Baselines

| Item | Version / reference |
| --- | --- |
| Deployment starting point | Hermes v0.18.2 on `expert/codex/production-v0.18.2` |
| Expected old HEAD | `3f1c4dce9a34095b59bbc1397dfb7e937d9d89d4` |
| Official new base | Hermes v0.19.0, tag `v2026.7.20`, commit `3ef6bbd201263d354fd83ec55b3c306ded2eb72a` |
| Enhanced deployment branch | `expert/codex/hermes-v0.19.0-gateway` |
| Required new HEAD | `5a7b1f3ffefc493e49cf77d7526f396bf5f2a6da` |
| Immutable deployment tag | `deploy/hermes-v0.19.0-gateway-20260722` |
| Fork remote | `https://github.com/Anthony9906/herems-expert.git` |

The v0.19.0 enhanced branch contains eight commits above the official release. They preserve reasoning/tool metadata, Dashboard multimodal rendering, API session titles, rich Runs tool events, real reasoning streaming, concurrent tool-event correlation, persisted Runs history, and profile-scoped Dashboard Gateway status.

## Profile Mapping

The two environments deliberately use different profile names:

| Environment | CLI profile | Profile directory |
| --- | --- | --- |
| Development machine | `expertagent` | `~/.hermes/profiles/expertagent/` |
| Deployment server | `expert-agent` | `~/.hermes/profiles/expert-agent/` |

Every deployment command in this document uses `-p expert-agent`. Do not rename the deployment profile, create an `expertagent` profile on the server, or copy development-machine profile state onto the server.

## Execution Rules For Codex

1. Execute the stages in order and show the evidence at each gate.
2. Before any write, confirm the source checkout, active profile, runtime Python, service manager, current commit, and dirty-tree state.
3. Never use `git reset --hard`, `git clean`, forced checkout, forced push, or an unreviewed stash.
4. Preserve deployment-owned `.env`, `config.yaml`, API keys, auth data, sessions, skills, cron data, pairing data, and databases.
5. Do not run the default `hermes update`: it targets upstream `origin/main`, which is newer than the tested v0.19.0 release and does not contain this fork branch.
6. Do not update Open WebUI or the AG-UI Bridge in the same change window. Restore OUI traffic only after Hermes passes its direct acceptance checks.
7. If any expected path, profile, SHA, service topology, port, Git state, migration result, or test result differs from this document, stop and ask the user before continuing.

## Stage 1 — Read-Only Preflight

Use the actual deployment account that owns the Hermes process.

```bash
cd ~/.hermes/hermes-agent

git status --short --branch
git remote -v
git rev-parse HEAD
git log -10 --oneline --decorate

command -v hermes
hermes --version
hermes -p expert-agent gateway status

ps -ef | grep '[h]ermes'
systemctl --user list-units 'hermes-gateway*'
systemctl --user list-unit-files 'hermes-gateway*'
```

Confirm all of the following before proceeding:

- The source checkout is `~/.hermes/hermes-agent`, or the real path has been identified and substituted consistently.
- The deployment profile is `expert-agent`.
- The starting version is v0.18.2.
- HEAD is `3f1c4dce9a34095b59bbc1397dfb7e937d9d89d4`.
- The working tree has no unexpected tracked or untracked source changes.
- The Gateway's Python executable belongs to the venv that will be updated.
- The Gateway, Dashboard, Open WebUI, and AG-UI Bridge owners/service managers are known.
- The Hermes API port is known; examples below assume `8642`.

If `expert` is absent, add it only after confirming no existing remote already represents the fork:

```bash
git remote add expert https://github.com/Anthony9906/herems-expert.git
git fetch expert --prune --tags
```

If `expert` exists with a different URL, stop for confirmation instead of replacing it.

## Stage 2 — Fetch And Verify The Published Target

Fetching is safe before the maintenance window because it does not change the working tree:

```bash
cd ~/.hermes/hermes-agent
git fetch expert --prune --tags

git ls-remote --heads expert refs/heads/codex/hermes-v0.19.0-gateway
git rev-parse expert/codex/hermes-v0.19.0-gateway
git rev-list -n 1 deploy/hermes-v0.19.0-gateway-20260722
```

Both local resolutions must equal:

```text
5a7b1f3ffefc493e49cf77d7526f396bf5f2a6da
```

Stop if the branch and tag do not resolve to the same commit.

## Stage 3 — Maintenance Window And Consistent Backup

First prevent Open WebUI from starting new Runs. Use the deployment's existing maintenance or service-management method. Then gracefully stop the `expert-agent` Gateway and the Hermes Dashboard using whichever manager owns them.

For a Hermes-managed user service, the Gateway command is normally:

```bash
hermes -p expert-agent gateway stop
```

If systemd, Docker, tmux, screen, or a custom supervisor owns the process, stop it through that manager instead. Verify that no Hermes process is still writing profile state before taking the backup.

Create both a Git recovery reference and a state backup:

```bash
DEPLOY_STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$HOME/hermes-deployment-backups/$DEPLOY_STAMP"

mkdir -p "$BACKUP_DIR"

cd ~/.hermes/hermes-agent
git branch "backup/pre-v019-$DEPLOY_STAMP" HEAD
git bundle create "$BACKUP_DIR/hermes-agent.bundle" --all

tar -C ~/.hermes \
  --exclude='./hermes-agent' \
  -czf "$BACKUP_DIR/hermes-state.tgz" .

sha256sum \
  "$BACKUP_DIR/hermes-agent.bundle" \
  "$BACKUP_DIR/hermes-state.tgz"
```

The state archive must include the deployment server's own `profiles/expert-agent/` directory, including `state.db`, `state.db-wal`, and `state.db-shm` when present. Keep the backup path and generated backup branch name in the deployment report.

## Stage 4 — Switch To The Exact Enhanced Branch

If the branch does not yet exist locally:

```bash
cd ~/.hermes/hermes-agent
git switch --create codex/hermes-v0.19.0-gateway \
  --track expert/codex/hermes-v0.19.0-gateway
```

If it already exists locally, inspect it first. Only when it is the expected deployment branch:

```bash
git switch codex/hermes-v0.19.0-gateway
git merge --ff-only expert/codex/hermes-v0.19.0-gateway
```

Verify the result before installing anything:

```bash
git status --short --branch
git rev-parse HEAD
git describe --tags --always
```

Required HEAD:

```text
5a7b1f3ffefc493e49cf77d7526f396bf5f2a6da
```

Any conflict, non-fast-forward result, dirty tree, or different SHA is a hard stop.

## Stage 5 — Update The Runtime Venv

The venv must be the one referenced by the deployment service's `ExecStart` or running process. Do not update `.venv` while the service actually uses `venv`, or vice versa.

For the expected installer layout:

```bash
cd ~/.hermes/hermes-agent

venv/bin/python --version
venv/bin/python -c 'import sys; print(sys.executable); print(sys.prefix)'

export UV_PROJECT_ENVIRONMENT="$PWD/venv"
uv sync --extra all --extra dev --locked

venv/bin/hermes --version
```

Hermes v0.19.0 requires Python `>=3.11,<3.14`. Stop if dependency sync fails or updates a different environment.

## Stage 6 — Rebuild The Hermes Dashboard

The enhanced branch changes Dashboard source, so rebuild it explicitly rather than relying on a stale bundle:

```bash
cd ~/.hermes/hermes-agent

node --version
npm install --workspace web
npm run check --workspace web
npm run build --workspace web
```

Use Node `20.19+` or `22.12+`. Do not continue if type checking, tests, or the production build fails.

## Stage 7 — Check And Migrate Deployment Configuration

Run configuration checks against the deployment profile, not the development profile:

```bash
cd ~/.hermes/hermes-agent

venv/bin/hermes -p expert-agent config check
venv/bin/hermes -p expert-agent config migrate
```

Review prompts before accepting them. Stop if migration proposes removing existing values, changing API credentials, changing MCP endpoints, changing approval mode, or creating/using `profiles/expertagent/`.

The following deployment-owned values must remain intact:

- API Server bind address, port, and API key.
- Model/provider credentials and routing.
- `expert-agent` skills and `skills/experts/` contents.
- MCP and AG-UI Bridge endpoints.
- Manual approval configuration.
- Cron, pairing, session, and auth state.

## Stage 8 — Offline Regression Tests

Before restarting production traffic:

```bash
cd ~/.hermes/hermes-agent

venv/bin/python -m pytest \
  tests/gateway/test_api_server.py \
  tests/gateway/test_api_server_runs.py \
  tests/hermes_cli/test_web_server_profile_unification.py

venv/bin/python -m py_compile \
  gateway/platforms/api_server.py \
  hermes_cli/web_server.py

git diff --check
git status --short --branch
```

The source tree must remain clean after installation, build, and tests. Investigate any generated tracked changes before continuing.

## Stage 9 — Start Hermes And Validate It Directly

Start the Gateway through its existing service manager. For a Hermes-managed user service:

```bash
venv/bin/hermes -p expert-agent gateway start
venv/bin/hermes -p expert-agent gateway status
```

Then verify the API directly before starting OUI traffic:

```bash
curl -fsS http://127.0.0.1:8642/health
```

Expected health payload includes:

```json
{"status":"ok","platform":"hermes-agent","version":"0.19.0"}
```

Also verify the authenticated models, capabilities, and sessions endpoints using the deployment's existing API key without printing the key in logs or chat.

If a Dashboard is deployed, restart it through its existing manager and verify its profile-scoped status endpoint, substituting the real Dashboard port:

```bash
curl -fsS 'http://127.0.0.1:9119/api/status?profile=expert-agent'
```

Required Dashboard facts:

- `version` is `0.19.0`.
- `hermes_home` ends with `/profiles/expert-agent`.
- `gateway_running` is `true`.
- `gateway_state` is `running`.
- `gateway_pid` matches the live `expert-agent` Gateway.
- `gateway_platforms.api_server.state` is `connected`.

## Stage 10 — Restore OUI And Run Integration Acceptance

After direct Hermes checks pass, start or restart the existing OUI backend so it refreshes Hermes capabilities. Do not rebuild or change OUI source as part of this Hermes-only upgrade.

Run the following acceptance matrix through OUI:

1. A no-tool Run streams real reasoning and one final answer without duplication.
2. A normal tool call shows arguments, progress, and result under the same `tool_call_id`.
3. Two parallel tool calls keep their arguments and results correctly correlated.
4. `once` approval resumes the existing Run and executes the approved action once.
5. `deny` resumes the Run without executing the guarded action.
6. Refreshing the browser restores message, reasoning, and tool history.
7. A new message can continue a restored conversation.
8. Existing attachments and AG-UI/MCP artifacts remain usable.

The known limitation remains: `session` approval is scoped to one Hermes Run and does not automatically authorize the same rule in a later chat message. Do not treat that accepted limitation as an upgrade failure.

## Observation Period

Keep the old backup branch and state archive. During the first business cycle, monitor:

- Hermes Gateway and API Server logs.
- OUI Runs/approval errors.
- Repeated or missing reasoning events.
- Tool-event ID mismatches.
- Session-history persistence after restarts.
- Gateway/Dashboard profile status.

Do not delete the backup until the user accepts the deployment.

## Rollback

Rollback code first; restore state only if evidence shows configuration or data migration damage.

1. Stop OUI traffic, Dashboard, and the `expert-agent` Gateway.
2. Switch to the recorded `backup/pre-v019-<timestamp>` branch.
3. Confirm HEAD returns to `3f1c4dce9a34095b59bbc1397dfb7e937d9d89d4`.
4. Point `UV_PROJECT_ENVIRONMENT` at the real runtime venv and run `uv sync --extra all --extra dev --locked` from the old commit.
5. Rebuild the old Dashboard bundle.
6. Run `hermes -p expert-agent config check`.
7. Start Hermes and validate v0.18.2 before restoring OUI traffic.

Restoring `hermes-state.tgz` overwrites deployment state and must not be done automatically. Only restore it after user confirmation and only when the v0.19.0 migration changed or damaged runtime state. Preserve the failed v0.19.0 state separately before any restoration so it remains available for diagnosis.

## Completion Evidence

The deployment handoff is complete only when the report includes:

- Pre-upgrade and post-upgrade SHAs.
- Backup directory and backup branch.
- Actual runtime Python path.
- Dependency, Dashboard build, and targeted test results.
- Config migration result.
- Gateway service manager and live PID.
- `/health` and profile-scoped Dashboard status results.
- OUI Runs/approval acceptance results.
- Any deviation, deferred issue, and rollback status.
