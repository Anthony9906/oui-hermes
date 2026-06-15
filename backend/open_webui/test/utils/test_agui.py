from open_webui.utils.agui import extract_agui_event


def test_extracts_artifact_event_from_bridge_payload():
    event, message = extract_agui_event(
        {
            'bridge': 'openwebui.agui_bridge_mcp',
            'kind': 'artifact',
            'artifact_type': 'markdown-preview',
            'payload': {'title': 'Spec', 'content': '# Hello'},
            'run_id': 'run_1',
            'timestamp': 1_000,
        }
    )

    assert message == 'AG-UI artifact preview is now visible to the user.'
    assert event == {
        'type': 'agui:state_snapshot',
        'data': {
            'artifact_type': 'markdown-preview',
            'payload': {'title': 'Spec', 'content': '# Hello'},
            'run_id': 'run_1',
            'timestamp': 1_000_000,
        },
    }


def test_extracts_choice_event_from_mcp_text_payload():
    event, message = extract_agui_event(
        '{"mcp":"agui-bridge-mcp","kind":"choice","title":"Pick","message":"Choose","options":["A","B"]}'
    )

    assert message == 'Choose'
    assert event['type'] == 'agui:interaction_request'
    assert event['data']['payload']['kind'] == 'choice'
    assert event['data']['payload']['options'][0] == {
        'id': 'option_1',
        'label': 'A',
        'value': 'A',
    }


def test_extracts_artifact_from_hermes_mcp_text_content_wrapper():
    event, message = extract_agui_event(
        {
            'tool_name': 'agui-bridge-mcp',
            'result': [
                {
                    'type': 'text',
                    'text': (
                        '{"bridge":"openwebui.agui_bridge_mcp","kind":"artifact",'
                        '"artifact_type":"generic-preview","payload":{"title":"From Hermes"}}'
                    ),
                }
            ],
        }
    )

    assert message == 'AG-UI artifact preview is now visible to the user.'
    assert event['type'] == 'agui:state_snapshot'
    assert event['data']['artifact_type'] == 'generic-preview'
    assert event['data']['payload'] == {'title': 'From Hermes'}


def test_ignores_approval_payloads():
    event, message = extract_agui_event(
        {
            'bridge': 'openwebui.agui_bridge_mcp',
            'kind': 'approval',
            'message': 'Approve?',
        }
    )

    assert event is None
    assert message == 'AG-UI approval bridge events are disabled in this product build.'
