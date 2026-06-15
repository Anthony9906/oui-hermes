import json
import time
from typing import Any


AGUI_BRIDGE_MCP_NAME = 'agui-bridge-mcp'
AGUI_BRIDGE_MARKER = 'openwebui.agui_bridge_mcp'
SUPPORTED_ARTIFACT_TYPES = {
    'generic-preview',
    'generic-json',
    'html-preview',
    'markdown-preview',
}


def _parse_json_text(value: Any) -> Any:
    if not isinstance(value, str):
        return value

    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return value


def _normalize_timestamp(value: Any) -> int:
    if isinstance(value, (int, float)) and value > 0:
        return int(value if value > 1_000_000_000_000 else value * 1000)
    return int(time.time() * 1000)


def _normalize_option(option: Any, index: int) -> dict[str, Any] | None:
    if isinstance(option, str):
        return {'id': f'option_{index + 1}', 'label': option, 'value': option}

    if not isinstance(option, dict):
        return None

    value = option.get('value') or option.get('id') or option.get('label') or f'option_{index + 1}'
    label = option.get('label') or option.get('title') or option.get('name') or value

    normalized = {
        'id': str(option.get('id') or value),
        'label': str(label),
        'value': str(value),
    }

    description = option.get('description') or option.get('detail') or option.get('hint')
    if description:
        normalized['description'] = str(description)

    if option.get('metadata') is not None:
        normalized['metadata'] = option.get('metadata')

    return normalized


def _looks_like_agui_bridge_payload(value: Any) -> bool:
    return isinstance(value, dict) and (
        value.get('bridge') == AGUI_BRIDGE_MARKER
        or value.get('mcp') == AGUI_BRIDGE_MCP_NAME
        or value.get('server') == AGUI_BRIDGE_MCP_NAME
    )


def _extract_payload(value: Any) -> dict[str, Any] | None:
    value = _parse_json_text(value)

    if isinstance(value, list):
        for item in value:
            extracted = _extract_payload(item)
            if extracted:
                return extracted
        return None

    if not isinstance(value, dict):
        return None

    if _looks_like_agui_bridge_payload(value):
        return value

    for key in (
        'text',
        'results',
        'content',
        'result',
        'output',
        'response',
        'observation',
        'data',
        'payload',
        'tool_result',
        'toolResult',
    ):
        nested_value = value.get(key)
        if nested_value is not None and nested_value is not value:
            extracted = _extract_payload(nested_value)
            if extracted:
                return extracted

    for nested_value in value.values():
        if isinstance(nested_value, (dict, list)):
            if nested_value is value:
                continue
            extracted = _extract_payload(nested_value)
            if extracted:
                return extracted

    return None


def extract_agui_event(tool_result: Any) -> tuple[dict[str, Any] | None, str | None]:
    payload = _extract_payload(tool_result)
    if not payload:
        return None, None

    kind = payload.get('kind') or payload.get('type')

    if kind in {'approval', 'approval_request'}:
        return None, 'AG-UI approval bridge events are disabled in this product build.'

    run_id = str(payload.get('run_id') or payload.get('runId') or '')
    timestamp = _normalize_timestamp(payload.get('timestamp'))

    if kind in {'artifact', 'state_snapshot'}:
        artifact_type = str(payload.get('artifact_type') or payload.get('artifactType') or '')
        artifact_payload = payload.get('payload')

        if artifact_type not in SUPPORTED_ARTIFACT_TYPES or artifact_payload is None:
            return None, 'Unsupported AG-UI artifact payload.'

        return (
            {
                'type': 'agui:state_snapshot',
                'data': {
                    'artifact_type': artifact_type,
                    'payload': artifact_payload,
                    'run_id': run_id,
                    'timestamp': timestamp,
                },
            },
            payload.get('message') or 'AG-UI artifact preview is now visible to the user.',
        )

    if kind in {'interaction', 'interaction_request', 'choice'}:
        raw_options = payload.get('options') or payload.get('choices') or []
        options = [
            normalized
            for normalized in (
                _normalize_option(option, index) for index, option in enumerate(raw_options)
            )
            if normalized
        ]

        if not options:
            return None, 'AG-UI choice interaction requires at least one option.'

        interaction_payload = {
            'id': str(payload.get('id') or payload.get('interaction_id') or f'interaction_{timestamp}'),
            'kind': 'choice',
            'title': str(payload.get('title') or payload.get('heading') or '请选择下一步'),
            'message': str(payload.get('message') or payload.get('question') or payload.get('prompt') or ''),
            'options': options,
            'custom_label': str(payload.get('custom_label') or payload.get('customLabel') or '自定义回答'),
            'custom_placeholder': str(
                payload.get('custom_placeholder') or payload.get('customPlaceholder') or '输入自定义内容'
            ),
            'allow_custom': bool(payload.get('allow_custom', payload.get('allowCustom', True))),
        }

        return (
            {
                'type': 'agui:interaction_request',
                'data': {
                    'payload': interaction_payload,
                    'run_id': run_id,
                    'timestamp': timestamp,
                },
            },
            payload.get('message') or 'AG-UI choice interaction is waiting for the user.',
        )

    return None, 'Unsupported AG-UI bridge event.'
