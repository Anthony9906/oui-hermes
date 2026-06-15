# AG-UI Hermes Tool Legacy Integration

This branch preserves the first AG-UI integration approach: Open WebUI renders
AG-UI artifacts by intercepting Hermes streaming tool events, while Hermes
exposes a native `emit_agui_artifact` tool.

Use this branch only when you intentionally want the Hermes-side tool injection
approach. The production-preferred approach is the MCP bridge, which avoids
patching Hermes source code.

## Open WebUI Side

The Open WebUI code in this branch expects Hermes to expose a tool named
`emit_agui_artifact`.

Key files:

- `backend/open_webui/utils/agui.py`
  - Detects `emit_agui_artifact` and compatible artifact-writer tool calls.
  - Converts tool arguments into AG-UI Socket.IO events.
  - Supports `artifact_type="interaction-request"` for choice interactions.
- `backend/open_webui/utils/hermes.py`
  - Injects a Hermes API prompt telling the agent to call
    `emit_agui_artifact` for choice-style interactions.
- `backend/open_webui/utils/middleware.py`
  - Reads Hermes streaming tool events and forwards AG-UI events to the
    frontend event emitter.
- `src/lib/agui/`
  - Stores AG-UI state, renders previews, and renders interaction cards.
- `src/lib/components/chat/Chat.svelte`
  - Handles `agui:*` events and sends the selected option back as a normal
    user message.

## Hermes Side Reference Patch

The Hermes-side reference implementation is copied into:

- `docs/development/reference/hermes_agui_tool.py`

Apply the equivalent changes to Hermes only if you choose this legacy approach.

Required Hermes changes:

1. Add `tools/agui_tool.py` using the reference implementation.
2. Register the tool in `toolsets.py`:

```python
_HERMES_CORE_TOOLS = [
    # ...
    "emit_agui_artifact",
]

TOOLSETS = {
    # ...
    "agui": {
        "description": "AG-UI structured artifact event bridge",
        "tools": ["emit_agui_artifact"],
        "includes": [],
    },
}
```

3. Ensure the API server default toolset exposes the tool:

```python
"hermes-api-server": {
    "tools": [
        # existing default tools...
        "emit_agui_artifact",
    ],
}
```

4. Optionally expose it in the CLI/dashboard configurable toolsets:

```python
CONFIGURABLE_TOOLSETS = [
    # ...
    ("agui", "AG-UI Rendering", "emit_agui_artifact structured artifact bridge"),
]
```

## Validation

After applying the Hermes patch, verify from Open WebUI:

1. Ask Hermes to create an artifact preview. The streamed tool call should be
   `emit_agui_artifact`, and Open WebUI should open the AG-UI preview panel.
2. Ask Hermes to present a choice. It should call
   `emit_agui_artifact(artifact_type="interaction-request", payload=...)`, and
   Open WebUI should show an interaction card.
3. Ask Hermes to use `terminal` for `pwd`. If the agent says `terminal` is not
   available, inspect Hermes toolset resolution first. This legacy approach
   depends on Hermes tool registration and therefore can interact with toolset
   inference bugs.

## Known Risk

This branch intentionally patches Hermes behavior. That creates merge risk when
upgrading Hermes from upstream. Prefer the `agui-bridge-mcp` branch for a clean
Hermes installation.
