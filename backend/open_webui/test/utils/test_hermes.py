from open_webui.utils.hermes import build_hermes_delta_payload


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

    assert result['messages'] == payload['messages']
    assert '<system_default_context>' in result['messages'][0]['content']
    assert '<current_conversation_user' in result['messages'][0]['content']
    assert '<attached_files>' in result['messages'][0]['content']
    assert 'tools' not in result
