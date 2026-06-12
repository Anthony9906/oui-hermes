"""
AG-UI (Agent-User Interaction) event layer for Expert Agent.

Intercepts Hermes tool-call events from the SSE stream and emits
structured AG-UI events (STATE_SNAPSHOT, STEP_*, TOOL_CALL_*, etc.)
via the existing Socket.IO event_emitter.

Hermes exposes a lightweight emit_agui_artifact tool as the structured event
carrier; Open WebUI owns the translation and rendering logic.
"""

from __future__ import annotations

import json
import re
import time
from typing import Any

import logging

log = logging.getLogger("open_webui.agui")

# ── AG-UI Event Types ──────────────────────────────────────────────────────

AGUI_EVENT_PREFIX = "agui:"

# ── Artifact type detection ─────────────────────────────────────────────────

# Tool names that indicate artifact payload generation. write_file keeps the
# current compatibility path; the agui_* names are the no-file transport target.
ARTIFACT_WRITER_TOOLS = {
    "write_file",
    "agui_artifact",
    "emit_agui_artifact",
    "render_agui_artifact",
}

# Known artifact types extracted from JSON payloads
ARTIFACT_TYPES = {
    "agui-generic",
    "cylinder-selection-public",
    "generic-json",
    "generic-preview",
    "interaction-request",
    "motor-selection-public",
}

APPROVAL_OPTION_LABELS = {
    "once": "仅本次允许",
    "session": "本会话允许",
    "always": "始终允许",
    "deny": "拒绝",
}


def is_artifact_writer(tool_name: str) -> bool:
    """Check if a tool call is likely writing artifact payload data."""
    return tool_name in ARTIFACT_WRITER_TOOLS


def _parse_json_value(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    return value


def extract_artifact_payload(tool_args: dict | str) -> dict | None:
    """Try to extract artifact JSON payload from tool call arguments.

    Supports two transports:
    - write_file-compatible args: {"path": "...", "content": "{...}"}
    - direct AG-UI args: {"artifact_type": "...", "payload": {...}}
    """
    args: dict = {}
    if isinstance(tool_args, str):
        try:
            args = json.loads(tool_args)
        except (json.JSONDecodeError, TypeError):
            return None
    elif isinstance(tool_args, dict):
        args = tool_args
    else:
        return None

    candidates: list[Any] = []
    for key in (
        "payload",
        "artifact",
        "state",
        "snapshot",
        "content",
        "arguments",
        "args",
        "parameters",
        "params",
        "input",
        "tool_input",
    ):
        if key in args:
            candidates.append(_parse_json_value(args.get(key)))
    candidates.append(args)

    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        artifact = _extract_artifact_from_payload(candidate)
        if artifact:
            return artifact

    return None


def _extract_artifact_from_payload(payload: dict) -> dict | None:
    """Detect artifact payload by known fields."""
    # Direct AG-UI transport: {"artifact_type": "...", "payload": {...}}
    artifact_type = payload.get("artifact_type") or payload.get("type")
    direct_payload = payload.get("payload")
    if isinstance(artifact_type, str) and isinstance(direct_payload, dict):
        return _build_artifact_snapshot(direct_payload, artifact_type)

    # AG-UI StateSnapshot-like transport: {"snapshot": {"artifact": {...}}}
    snapshot = payload.get("snapshot")
    if isinstance(snapshot, dict):
        artifact = snapshot.get("artifact")
        if isinstance(artifact, dict):
            nested_type = artifact.get("artifact_type") or artifact.get("type")
            nested_payload = artifact.get("payload") or artifact.get("data")
            if isinstance(nested_type, str) and isinstance(nested_payload, dict):
                return _build_artifact_snapshot(nested_payload, nested_type)

    # Format 1: raw input JSON (mechanism + recommendations)
    if "mechanism" in payload and "recommendations" in payload:
        return _build_artifact_snapshot(payload, "cylinder-selection-public")

    # Format 2: complete payload JSON (type + data.recommendations)
    if "recommendations" in payload:
        recs = payload.get("recommendations", [])
        if isinstance(recs, list) and len(recs) > 0:
            art_type = payload.get("artifact_type") or payload.get("type", "cylinder-selection-public")
            art_data = payload.get("data", payload)
            return _build_artifact_snapshot(art_data, art_type)

    # Format 3: nested under data key
    data = payload.get("data", {})
    if isinstance(data, dict):
        recs = data.get("recommendations", [])
        if isinstance(recs, list) and len(recs) > 0:
            art_type = payload.get("artifact_type") or payload.get("type", "cylinder-selection-public")
            return _build_artifact_snapshot(data, art_type)

    return None


def _build_artifact_snapshot(payload: dict, artifact_type: str) -> dict:
    """Build a minimal artifact snapshot from raw payload data.

    The full template filling (build_payload.py logic) happens in the frontend
    StateRenderer component, which can apply template defaults client-side.
    """
    return {
        "artifact_type": artifact_type,
        "payload": payload,
    }


def extract_interaction_request(chunk: dict) -> dict | None:
    """Extract user-interaction requests from Hermes gateway events."""
    if not isinstance(chunk, dict):
        return None

    event_type = chunk.get("event")
    if event_type != "approval.request":
        return None

    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        choices = ["once", "session", "always", "deny"]

    command = chunk.get("command") or chunk.get("description") or ""
    description = chunk.get("description") or chunk.get("message") or ""
    run_id = str(chunk.get("run_id") or "")

    return {
        "id": str(chunk.get("approval_id") or f"approval_{run_id or int(time.time() * 1000)}"),
        "kind": "approval",
        "title": "需要授权确认",
        "message": description or command,
        "approval_id": chunk.get("approval_id"),
        "tool_call_id": chunk.get("tool_call_id"),
        "run_id": run_id,
        "options": [
            {
                "id": str(choice),
                "label": APPROVAL_OPTION_LABELS.get(str(choice), str(choice)),
                "value": str(choice),
                "description": command if str(choice) == "once" and command else "",
            }
            for choice in choices
        ],
        "allow_custom": False,
    }


# ── Step tracking ──────────────────────────────────────────────────────────

_KNOWN_STEP_TOOLS: dict[str, str] = {
    "skill_view": "读取参考数据",
    "read_file": "读取文件",
    "write_file": "生成数据",
    "agui_artifact": "生成预览",
    "emit_agui_artifact": "生成预览",
    "render_agui_artifact": "生成预览",
    "terminal": "执行脚本",
    "search_files": "搜索文件",
    "web_search": "网络搜索",
    "web_extract": "提取网页",
}


def tool_to_step_name(tool_name: str) -> str | None:
    """Map a tool name to a human-readable step name."""
    if tool_name in _KNOWN_STEP_TOOLS:
        return _KNOWN_STEP_TOOLS[tool_name]

    if not tool_name:
        return None

    label = re.sub(r"[_-]+", " ", tool_name).strip()
    return f"调用 {label}" if label else None


# ── AG-UI Event Emitter ────────────────────────────────────────────────────

class AguiEventEmitter:
    """Emits AG-UI events through the Socket.IO event_emitter.

    Tracks state across a single agent run to avoid duplicate emissions
    and maintain correct event sequencing.
    """

    def __init__(self, event_emitter):
        self._emit = event_emitter
        self._seen_tool_calls: set[str] = set()
        self._current_step: str | None = None
        self._artifact_emitted = False
        self._run_id = f"run_{int(time.time() * 1000)}"

    async def emit(self, event_type: str, data: dict) -> None:
        """Emit an AG-UI event via Socket.IO."""
        full_type = f"{AGUI_EVENT_PREFIX}{event_type}"
        payload = dict(data)
        payload.setdefault("run_id", self._run_id)
        payload.setdefault("timestamp", time.time())
        try:
            await self._emit({
                "type": full_type,
                "data": payload,
            })
        except Exception:
            log.exception("Failed to emit AG-UI event: %s", event_type)

    async def on_tool_start(self, tool_name: str, tool_call_id: str, tool_args: Any = None) -> None:
        """Handle tool call start."""
        if tool_call_id in self._seen_tool_calls:
            await self.emit("tool_call_start", {
                "tool_call_id": tool_call_id,
                "tool_name": tool_name,
                "tool_args": tool_args,
            })
            return
        self._seen_tool_calls.add(tool_call_id)

        # Emit step transition
        step_name = tool_to_step_name(tool_name)
        if step_name and step_name != self._current_step:
            if self._current_step:
                await self.emit("step_finished", {"step_name": self._current_step})
            self._current_step = step_name
            await self.emit("step_started", {"step_name": step_name})

        # Emit tool call start
        await self.emit("tool_call_start", {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
            "tool_args": tool_args,
        })

    async def on_tool_complete(self, tool_name: str, tool_call_id: str, result: Any = None) -> None:
        """Handle tool call completion."""
        await self.emit("tool_call_end", {
            "tool_call_id": tool_call_id,
            "tool_name": tool_name,
        })

    async def on_artifact_detected(self, artifact_type: str, payload: dict) -> None:
        """Emit a STATE_SNAPSHOT for artifact delivery."""
        if self._artifact_emitted:
            return
        self._artifact_emitted = True

        # Finish current step
        if self._current_step:
            await self.emit("step_finished", {"step_name": self._current_step})
            self._current_step = None

        await self.emit("state_snapshot", {
            "artifact_type": artifact_type,
            "payload": payload,
        })

    async def on_interaction_requested(self, payload: dict) -> None:
        """Emit an interaction request for frontend composer cards."""
        if self._current_step:
            await self.emit("step_finished", {"step_name": self._current_step})
            self._current_step = None

        await self.emit("interaction_request", payload)

    async def flush(self) -> None:
        """Finish any pending step."""
        if self._current_step:
            await self.emit("step_finished", {"step_name": self._current_step})
            self._current_step = None


# ── SSE Chunk Processor ────────────────────────────────────────────────────

def process_hermes_chunk_for_agui(
    chunk: Any,
    emitter: AguiEventEmitter | None = None,
) -> dict[str, Any]:
    """Process a single Hermes SSE chunk for AG-UI events.

    Called from the streaming response handler in middleware.py.
    This is a synchronous inspection function — actual emission is async,
    so the caller must await the emitter methods.

    Returns nothing; the caller should call the emitter methods based on
    the information extracted here.

    Design: this function is called in the hot SSE loop. It does minimal
    work — just inspection. The caller pattern is:

        if emitter:
            extract = process_hermes_chunk_for_agui(chunk, emitter=None)
            if extract.get("tool_start"):
                await emitter.on_tool_start(...)
            if extract.get("artifact"):
                await emitter.on_artifact_detected(...)
    """
    # Not a dict — skip
    if not isinstance(chunk, dict):
        return {}

    result: dict = {}

    # Detect tool calls in choices array (OpenAI format)
    choices = chunk.get("choices", [])
    for choice in choices:
        delta = choice.get("delta", {})
        tool_calls = delta.get("tool_calls", [])

        for tc in tool_calls:
            func = tc.get("function", {})
            name = func.get("name", "")
            call_id = tc.get("id", "")

            if name and call_id:
                result["tool_start"] = {
                    "tool_name": name,
                    "tool_call_id": call_id,
                    "tool_args": func.get("arguments", ""),
                }

                # Check if this is an artifact writer
                if is_artifact_writer(name):
                    args = func.get("arguments", "")
                    try:
                        if isinstance(args, str):
                            args = json.loads(args)
                    except json.JSONDecodeError:
                        pass
                    else:
                        artifact = extract_artifact_payload(args)
                        if artifact:
                            result["artifact"] = artifact

    # Also check for Hermes-native tool events
    tool_name = chunk.get("tool") or chunk.get("tool_name")
    if tool_name:
        function_payload = chunk.get("function") if isinstance(chunk.get("function"), dict) else {}
        result["tool_start"] = {
            "tool_name": str(tool_name),
            "tool_call_id": chunk.get("tool_call_id", f"call_{time.time()}"),
            "tool_args": (
                chunk.get("arguments")
                or chunk.get("args")
                or chunk.get("parameters")
                or chunk.get("params")
                or chunk.get("input")
                or chunk.get("tool_input")
                or function_payload.get("arguments")
            ),
        }

    return result


def extract_final_message_text(messages: list[dict]) -> str:
    """Extract the final assistant message text from accumulated messages.

    Used to strip fenced html iframe blocks since AG-UI renders the
    artifact natively.
    """
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("content"):
            text = msg["content"]
            # Strip fenced html code blocks (they contain iframes)
            text = re.sub(r"```html\s*<iframe[^>]*>.*?</iframe>\s*```", "", text, flags=re.DOTALL)
            return text.strip()
    return ""
