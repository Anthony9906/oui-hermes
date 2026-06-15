#!/usr/bin/env python3
"""
Reference Hermes tool for the legacy Open WebUI AG-UI integration.

Copy this file to Hermes as `tools/agui_tool.py` when using the legacy
Hermes-tool approach. The tool does not render UI and does not write files; its
structured arguments are the event payload that Open WebUI intercepts from the
streaming tool-call feed.
"""

import json
from typing import Any, Dict

from tools.registry import registry


EMIT_AGUI_ARTIFACT_SCHEMA = {
    "name": "emit_agui_artifact",
    "description": (
        "Directly emit a structured artifact payload for Open WebUI AG-UI rendering. "
        "Use this tool itself after completing calculations when the UI should render a preview. "
        "In Open WebUI, use artifact_type=interaction-request with payload.kind=choice "
        "when the user needs to choose from options or confirm a direction. "
        "Do not wrap it in terminal, execute_code, shell scripts, write_file, or uploads. "
        "For lightweight connectivity tests, prefer artifact_type=generic-preview with an ASCII-only payload. "
        "This tool does not write files or upload artifacts."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "artifact_type": {
                "type": "string",
                "description": (
                    "Renderer type. Use interaction-request for Open WebUI choice dialogs, "
                    "generic-preview for arbitrary test payloads, or cylinder-selection-public "
                    "for cylinder selection artifacts."
                ),
            },
            "payload": {
                "type": "object",
                "description": (
                    "Complete artifact payload for the frontend renderer. For "
                    "interaction-request choice dialogs, include kind='choice', title, "
                    "message, and options with id, label, and value."
                ),
            },
        },
        "required": ["artifact_type", "payload"],
    },
}


def _handle_emit_agui_artifact(args: Dict[str, Any], **kwargs) -> str:
    artifact_type = args.get("artifact_type")
    payload = args.get("payload")

    if not isinstance(artifact_type, str) or not artifact_type.strip():
        return json.dumps({"ok": False, "error": "artifact_type is required"})

    if not isinstance(payload, dict):
        return json.dumps({"ok": False, "error": "payload must be an object"})

    return json.dumps(
        {
            "ok": True,
            "artifact_type": artifact_type,
            "message": "Artifact payload emitted for AG-UI rendering.",
        },
        ensure_ascii=False,
    )


registry.register(
    name="emit_agui_artifact",
    toolset="agui",
    schema=EMIT_AGUI_ARTIFACT_SCHEMA,
    handler=_handle_emit_agui_artifact,
    emoji="AG",
    max_result_size_chars=2000,
)
