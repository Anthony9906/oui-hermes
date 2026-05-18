from __future__ import annotations

import copy
import re
from typing import Any


HERMES_SESSION_HEADER = 'X-Hermes-Session-Id'
SAFE_CLIENT_CHAT_ID = re.compile(r'^[A-Za-z0-9_-]{1,128}$')
IMAGE_FILE_EXTENSIONS = {
    '.png',
    '.jpg',
    '.jpeg',
    '.webp',
    '.gif',
    '.bmp',
    '.tiff',
    '.tif',
    '.heic',
    '.heif',
}


def is_temporary_chat_id(chat_id: Any) -> bool:
    return isinstance(chat_id, str) and chat_id.startswith('local:')


def is_valid_client_chat_id(chat_id: Any) -> bool:
    return isinstance(chat_id, str) and bool(SAFE_CLIENT_CHAT_ID.fullmatch(chat_id))


def is_image_file_item(file: Any) -> bool:
    if not isinstance(file, dict):
        return False

    if file.get('type') == 'image':
        return True

    content_type = file.get('content_type') or (file.get('file') or {}).get('meta', {}).get('content_type')
    if isinstance(content_type, str) and content_type.lower().startswith('image/'):
        return True

    name_or_url = str(file.get('name') or file.get('filename') or file.get('url') or '').lower()
    return any(name_or_url.endswith(ext) for ext in IMAGE_FILE_EXTENSIONS)


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


def extract_processed_user_message(payload: dict) -> dict | None:
    """Return the latest user message from an already-processed payload."""
    for message in reversed(payload.get('messages') or []):
        if isinstance(message, dict) and message.get('role') == 'user':
            return _clean_user_message(copy.deepcopy(message))

    return None


def _clean_user_message(message: dict) -> dict:
    allowed = {'role', 'content', 'files', 'name'}
    return {k: v for k, v in message.items() if k in allowed}


def build_hermes_delta_payload(payload: dict, metadata: dict | None) -> dict:
    """Strip Open WebUI context ownership from a chat-completions payload."""
    user_message = extract_processed_user_message(payload) or extract_current_user_message(payload, metadata)
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
