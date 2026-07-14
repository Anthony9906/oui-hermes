import json

from open_webui.utils.middleware import _upsert_hermes_tool_event


def _event(call_id: str, query: str, status: str = 'running') -> dict:
    return {
        'event': 'hermes.tool.progress',
        'tool': 'web_search',
        'toolCallId': call_id,
        'status': status,
        'args': {'query': query},
    }


def test_same_name_concurrent_tools_do_not_overwrite_each_other():
    output = []
    _upsert_hermes_tool_event(output, _event('call_a', 'alpha'))
    _upsert_hermes_tool_event(output, _event('call_b', 'beta'))

    assert [(item['call_id'], json.loads(item['arguments'])['arguments']) for item in output] == [
        ('call_a', {'query': 'alpha'}),
        ('call_b', {'query': 'beta'}),
    ]

    _upsert_hermes_tool_event(output, _event('call_b', 'beta', 'completed'))
    _upsert_hermes_tool_event(output, _event('call_a', 'alpha', 'completed'))

    assert len(output) == 2
    assert all(item['status'] == 'completed' for item in output)
