from __future__ import annotations

import copy
from typing import Any


HERMES_SESSION_HEADER = 'X-Hermes-Session-Id'


def is_temporary_chat_id(chat_id: Any) -> bool:
    return isinstance(chat_id, str) and chat_id.startswith('local:')


def get_hermes_session_id(metadata: dict | None) -> str | None:
    if not isinstance(metadata, dict):
        return None
    if not metadata.get('hermes_session_delta'):
        return None
    chat_id = metadata.get('chat_id')
    if not isinstance(chat_id, str) or not chat_id or is_temporary_chat_id(chat_id):
        return None
    return chat_id


def apply_hermes_session_header(headers: dict, metadata: dict | None) -> dict:
    session_id = get_hermes_session_id(metadata)
    if session_id:
        headers[HERMES_SESSION_HEADER] = session_id
    return headers


def extract_current_user_message(payload: dict, metadata: dict | None) -> dict | None:
    """Return the current user turn without historical/system messages."""
    metadata = metadata or {}
    user_message = metadata.get('user_message')
    if isinstance(user_message, dict):
        message = copy.deepcopy(user_message)
        message['role'] = 'user'
        return _clean_user_message(message)

    for message in reversed(payload.get('messages') or []):
        if isinstance(message, dict) and message.get('role') == 'user':
            return _clean_user_message(copy.deepcopy(message))

    return None


def _clean_user_message(message: dict) -> dict:
    allowed = {'role', 'content', 'files', 'name'}
    return {k: v for k, v in message.items() if k in allowed}


def build_hermes_delta_payload(payload: dict, metadata: dict | None) -> dict:
    """Strip Open WebUI context ownership from a chat-completions payload."""
    user_message = extract_current_user_message(payload, metadata)
    if not user_message:
        return payload

    sanitized = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            'messages',
            'tools',
            'tool_choice',
            'functions',
            'function_call',
            'system',
            'instructions',
        }
    }
    sanitized['messages'] = [user_message]
    return sanitized
