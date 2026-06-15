import argparse
import time
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP


BRIDGE_MARKER = 'openwebui.agui_bridge_mcp'
SERVER_NAME = 'agui-bridge-mcp'

mcp = FastMCP(
    SERVER_NAME,
    instructions=(
        'Use these tools for Open WebUI AG-UI. When the user asks to choose, pick, select, '
        'answer a multiple-choice question, or asks you to provide options for them to choose from, '
        'call ask_interactive_choice instead of writing the options only as plain text. '
        'Do not use this server for approvals.'
    ),
)


def _event(
    *,
    kind: str,
    run_id: str | None,
    status_message: str,
    **payload: Any,
) -> dict[str, Any]:
    return {
        'bridge': BRIDGE_MARKER,
        'mcp': SERVER_NAME,
        'kind': kind,
        'run_id': run_id or f'agui_{int(time.time() * 1000)}',
        'timestamp': int(time.time() * 1000),
        'status_message': status_message,
        **payload,
    }


@mcp.tool()
def emit_artifact_preview(
    artifact_type: Literal[
        'generic-preview',
        'generic-json',
        'agui-generic',
        'html-preview',
        'markdown-preview',
        'cylinder-selection-public',
        'motor-selection-public',
    ],
    payload: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Show an AG-UI artifact preview in Open WebUI.

    Use cylinder-selection-public and motor-selection-public for expo selection
    result payloads, html-preview for trusted HTML strings, markdown-preview for
    Markdown content, and generic-preview/generic-json for structured JSON payloads.
    """

    return _event(
        kind='artifact',
        artifact_type=artifact_type,
        payload=payload,
        run_id=run_id,
        status_message='Artifact preview emitted to Open WebUI.',
    )


@mcp.tool()
def ask_interactive_choice(
    title: str,
    message: str,
    options: list[Any],
    run_id: str | None = None,
    interaction_id: str | None = None,
    allow_custom: bool = True,
    custom_label: str = '自定义回答',
    custom_placeholder: str = '输入自定义内容',
) -> dict[str, Any]:
    """Open an interactive choice prompt for the user in Open WebUI.

    Use this whenever the user should select from options, including quiz questions,
    generated alternatives, next-step choices, configuration choices, and clarification
    questions with multiple possible answers. Do not answer the choice yourself after
    calling this tool; wait for the user's selection. This is not an approval flow.
    """

    return _event(
        kind='choice',
        id=interaction_id,
        title=title,
        message=message,
        options=options,
        allow_custom=allow_custom,
        custom_label=custom_label,
        custom_placeholder=custom_placeholder,
        run_id=run_id,
        status_message='Interactive choice emitted to Open WebUI.',
    )


def main() -> None:
    parser = argparse.ArgumentParser(description='Run the Open WebUI AG-UI bridge MCP server.')
    parser.add_argument(
        '--transport',
        default='streamable-http',
        choices=['streamable-http', 'sse', 'stdio'],
        help='MCP transport to use. Open WebUI MCP clients should use streamable-http.',
    )
    args = parser.parse_args()

    mcp.run(transport=args.transport)


if __name__ == '__main__':
    main()
