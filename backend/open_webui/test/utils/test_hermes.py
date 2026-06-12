from open_webui.utils.hermes import (
    OPEN_WEBUI_AGUI_INTERACTION_PROMPT,
    build_hermes_delta_payload,
    is_valid_client_chat_id,
)


def test_build_hermes_delta_payload_preserves_processed_user_context():
    payload = {
        'model': 'hermes',
        'messages': [
            {
                'role': 'user',
                'content': (
                    '<system_default_context>\n'
                    '<current_conversation_user user_id="u1" user_name="alice" display_name="Alice" />\n'
                    '</system_default_context>\n\n'
                    '<attached_files>\n'
                    '<file name="report.pdf" url="https://assets.example.com/report.pdf" />\n'
                    '</attached_files>\n\n'
                    'summarize this'
                ),
            }
        ],
        'tools': [{'type': 'function'}],
    }
    metadata = {
        'hermes_session_delta': True,
        'user_message': {
            'role': 'user',
            'content': 'summarize this',
            'files': [{'type': 'file', 'name': 'report.pdf'}],
        },
    }

    result = build_hermes_delta_payload(payload, metadata)

    assert result['messages'][0] == {
        'role': 'system',
        'content': OPEN_WEBUI_AGUI_INTERACTION_PROMPT,
    }
    assert result['messages'][1] == payload['messages'][0]
    assert '<system_default_context>' in result['messages'][1]['content']
    assert '<current_conversation_user' in result['messages'][1]['content']
    assert '<attached_files>' in result['messages'][1]['content']
    assert 'tools' not in result


def test_client_chat_id_validation_allows_safe_preallocated_ids_only():
    assert is_valid_client_chat_id('01JABC_def-123')
    assert is_valid_client_chat_id('550e8400-e29b-41d4-a716-446655440000')
    assert not is_valid_client_chat_id('../chat')
    assert not is_valid_client_chat_id('local:temporary')
    assert not is_valid_client_chat_id('chat/id')
    assert not is_valid_client_chat_id('')
