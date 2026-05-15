from typing import Iterable

from open_webui.config import HERMES_API_BASE_URL


def normalize_url(url: str | None) -> str:
    return (url or '').strip().rstrip('/')


def is_hermes_connection_url(url: str | None) -> bool:
    return normalize_url(url) == normalize_url(HERMES_API_BASE_URL)


def normalize_connection_model_usage(config: dict | None, url: str | None) -> dict:
    normalized = {**(config or {})}
    legacy_usage = normalized.get('model_usage') or {}

    if 'enable_chat' not in normalized:
        normalized['enable_chat'] = legacy_usage.get('chat', is_hermes_connection_url(url))

    if 'enable_task' not in normalized:
        normalized['enable_task'] = legacy_usage.get('task', True)

    normalized['model_usage'] = {
        'chat': bool(normalized.get('enable_chat')),
        'task': bool(normalized.get('enable_task')),
    }
    return normalized


def model_usage_from_connection_config(config: dict | None, url: str | None) -> dict:
    normalized = normalize_connection_model_usage(config, url)
    return normalized['model_usage']


def get_model_usage(model: dict | None) -> dict:
    model = model or {}
    usage = model.get('model_usage') or {}
    return {
        'chat': bool(usage.get('chat', True)),
        'task': bool(usage.get('task', True)),
    }


def is_chat_model(model: dict | None) -> bool:
    return get_model_usage(model).get('chat', True)


def is_task_model(model: dict | None) -> bool:
    return get_model_usage(model).get('task', True)


def filter_models_by_scope(models: Iterable[dict], scope: str | None) -> list[dict]:
    normalized_scope = (scope or 'chat').lower()
    if normalized_scope == 'all':
        return list(models)
    if normalized_scope in {'task-only', 'task_only'}:
        return [model for model in models if is_task_model(model) and not is_chat_model(model)]
    if normalized_scope == 'task':
        return [model for model in models if is_task_model(model)]
    return [model for model in models if is_chat_model(model)]
