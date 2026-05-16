#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
ROOT_DIR=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)
SCRIPT_PATH="$SCRIPT_DIR/$(basename -- "${BASH_SOURCE[0]}")"

BACKEND_PORT="${BACKEND_PORT:-8080}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
ARTIFACT_SERVICE_DIR="${ARTIFACT_SERVICE_DIR:-$HOME/Documents/Hermes/local-artifact-preview-service}"
ARTIFACT_SERVICE_PORT="${ARTIFACT_SERVICE_PORT:-8787}"
ARTIFACT_SERVICE_HOST="${ARTIFACT_SERVICE_HOST:-0.0.0.0}"
ARTIFACT_SERVICE_BASE_URL="${ARTIFACT_SERVICE_BASE_URL:-http://localhost:$ARTIFACT_SERVICE_PORT}"
HERMES_PROFILE_ENV="${HERMES_PROFILE_ENV:-$HOME/.hermes/profiles/expertagent/.env}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"

BACKEND_LOG="$LOG_DIR/open-webui-backend.log"
FRONTEND_LOG="$LOG_DIR/open-webui-frontend.log"
ARTIFACT_SERVICE_LOG="$LOG_DIR/local-artifact-preview-service.log"

export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

info() {
	printf '[open-webui] %s\n' "$*"
}

require_cmd() {
	if ! command -v "$1" >/dev/null 2>&1; then
		printf '[open-webui] missing required command: %s\n' "$1" >&2
		exit 1
	fi
}

pids_on_port() {
	local port="$1"
	lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true
}

stop_port() {
	local name="$1"
	local port="$2"
	local pids

	pids=$(pids_on_port "$port")
	if [ -z "$pids" ]; then
		info "$name is not running on port $port"
		return
	fi

	info "$name is running on port $port, stopping pid(s): ${pids//$'\n'/ }"
	kill $pids 2>/dev/null || true

	for _ in {1..20}; do
		if [ -z "$(pids_on_port "$port")" ]; then
			info "$name stopped"
			return
		fi
		sleep 0.5
	done

	pids=$(pids_on_port "$port")
	if [ -n "$pids" ]; then
		info "$name did not stop gracefully, forcing pid(s): ${pids//$'\n'/ }"
		kill -9 $pids 2>/dev/null || true
	fi
}

wait_for_url() {
	local name="$1"
	local url="$2"
	local log_file="$3"

	for _ in {1..60}; do
		if curl -fsS "$url" >/dev/null 2>&1; then
			info "$name is ready: $url"
			return
		fi
		sleep 1
	done

	printf '[open-webui] %s did not become ready: %s\n' "$name" "$url" >&2
	printf '[open-webui] last log lines from %s:\n' "$log_file" >&2
	tail -n 80 "$log_file" >&2 || true
	exit 1
}

load_backend_env() {
	if [ -f "$ROOT_DIR/.env" ]; then
		set -a
		. "$ROOT_DIR/.env"
		set +a
	fi

	if [ -f "$HERMES_PROFILE_ENV" ]; then
		set -a
		. "$HERMES_PROFILE_ENV"
		set +a
	fi

	export PORT="$BACKEND_PORT"
	export HOST="$BACKEND_HOST"
	export STORAGE_PROVIDER="${STORAGE_PROVIDER:-local_artifact}"
	export LOCAL_ARTIFACT_BASE_URL="${LOCAL_ARTIFACT_BASE_URL:-$ARTIFACT_SERVICE_BASE_URL}"
	export LOCAL_ARTIFACT_BUCKET_DIR="${LOCAL_ARTIFACT_BUCKET_DIR:-$ARTIFACT_SERVICE_DIR/bucket}"
	export ARTIFACT_STORAGE_PROVIDER="${ARTIFACT_STORAGE_PROVIDER:-local_artifact}"
	export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-auto}"
	export S3_KEY_PREFIX="${S3_KEY_PREFIX:-open-webui}"
	export HERMES_API_BASE_URL="${HERMES_API_BASE_URL:-http://127.0.0.1:8642}"
	export OPENAI_API_BASE_URL="${OPENAI_API_BASE_URL:-$HERMES_API_BASE_URL}"
	export ENABLE_OLLAMA_API="${ENABLE_OLLAMA_API:-false}"
	export ENABLE_OPENAI_API="${ENABLE_OPENAI_API:-true}"
	export ENABLE_WEB_SEARCH="${ENABLE_WEB_SEARCH:-false}"
	export VECTOR_DB="${VECTOR_DB:-none}"
}

run_backend() {
	mkdir -p "$LOG_DIR"
	load_backend_env
	cd "$ROOT_DIR"
	exec uv run --no-project --python 3.12 --with-requirements backend/requirements.txt \
		uvicorn open_webui.main:app \
		--app-dir backend \
		--host "$BACKEND_HOST" \
		--port "$BACKEND_PORT" \
		--forwarded-allow-ips "*"
}

run_frontend() {
	mkdir -p "$LOG_DIR"
	cd "$ROOT_DIR"
	exec npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
}

run_artifact_service() {
	mkdir -p "$LOG_DIR"
	if [ ! -d "$ARTIFACT_SERVICE_DIR" ]; then
		printf '[open-webui] local artifact service directory not found: %s\n' "$ARTIFACT_SERVICE_DIR" >&2
		exit 1
	fi

	cd "$ARTIFACT_SERVICE_DIR"
	export LOCAL_ARTIFACT_HOST="$ARTIFACT_SERVICE_HOST"
	export LOCAL_ARTIFACT_PORT="$ARTIFACT_SERVICE_PORT"
	export LOCAL_ARTIFACT_BASE_URL="$ARTIFACT_SERVICE_BASE_URL"
	exec uv run uvicorn app.main:app --host "$ARTIFACT_SERVICE_HOST" --port "$ARTIFACT_SERVICE_PORT"
}

case "${1:-}" in
	--run-backend)
		run_backend
		;;
	--run-frontend)
		run_frontend
		;;
	--run-artifact-service)
		run_artifact_service
		;;
esac

require_cmd lsof
require_cmd curl
require_cmd npm
require_cmd uv

mkdir -p "$LOG_DIR"

stop_port "local artifact service" "$ARTIFACT_SERVICE_PORT"
stop_port "frontend" "$FRONTEND_PORT"
stop_port "backend" "$BACKEND_PORT"

info "starting local artifact service on port $ARTIFACT_SERVICE_PORT"
: >"$ARTIFACT_SERVICE_LOG"
nohup /bin/bash "$SCRIPT_PATH" --run-artifact-service >"$ARTIFACT_SERVICE_LOG" 2>&1 &
info "local artifact service pid: $!; log: $ARTIFACT_SERVICE_LOG"

info "starting backend on port $BACKEND_PORT"
: >"$BACKEND_LOG"
nohup /bin/bash "$SCRIPT_PATH" --run-backend >"$BACKEND_LOG" 2>&1 &
info "backend pid: $!; log: $BACKEND_LOG"

info "starting frontend on port $FRONTEND_PORT"
: >"$FRONTEND_LOG"
nohup /bin/bash "$SCRIPT_PATH" --run-frontend >"$FRONTEND_LOG" 2>&1 &
info "frontend pid: $!; log: $FRONTEND_LOG"

wait_for_url "local artifact service" "http://127.0.0.1:$ARTIFACT_SERVICE_PORT/health" "$ARTIFACT_SERVICE_LOG"
wait_for_url "backend" "http://127.0.0.1:$BACKEND_PORT/health" "$BACKEND_LOG"
wait_for_url "frontend" "http://127.0.0.1:$FRONTEND_PORT/" "$FRONTEND_LOG"

info "done"
info "frontend:               http://localhost:$FRONTEND_PORT/"
info "backend:                http://localhost:$BACKEND_PORT/"
info "local artifact service: $ARTIFACT_SERVICE_BASE_URL/"
