import copy
import time
import logging
import sys
import os
import base64
import textwrap
import mimetypes

import asyncio
from aiocache import cached
from typing import Any, Optional
import random
import json
import html
import inspect
import re
import ast

from datetime import timedelta
from html.parser import HTMLParser
from urllib.parse import urlencode
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor


from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from starlette.responses import Response, StreamingResponse, JSONResponse


from open_webui.utils.misc import is_string_allowed
from open_webui.models.oauth_sessions import OAuthSessions
from open_webui.models.chats import Chats
from open_webui.models.folders import Folders
from open_webui.models.users import Users
from open_webui.socket.main import (
    get_event_call,
    get_event_emitter,
)
from open_webui.routers.tasks import (
    generate_queries,
    generate_title,
    generate_follow_ups,
    generate_image_prompt,
    generate_chat_tags,
)
from open_webui.utils.tools import get_builtin_tools
from open_webui.routers.pipelines import (
    process_pipeline_inlet_filter,
    process_pipeline_outlet_filter,
)

from open_webui.utils.webhook import post_webhook
from open_webui.models.users import UserModel
from open_webui.models.functions import Functions
from open_webui.models.models import Models

from open_webui.utils.sanitize import sanitize_code
from open_webui.utils.chat import generate_chat_completion
from open_webui.utils.task import (
    get_task_model_id,
    rag_template,
    tools_function_calling_generation_template,
)
from open_webui.utils.misc import (
    deep_update,
    extract_urls,
    get_message_list,
    add_or_update_system_message,
    add_or_update_user_message,
    set_last_user_message_content,
    get_last_user_message,
    get_last_user_message_item,
    get_last_assistant_message,
    get_system_message,
    merge_system_messages,
    replace_system_message_content,
    prepend_to_first_user_message_content,
    convert_logit_bias_input_to_json,
    get_content_from_message,
    convert_output_to_messages,
    strip_empty_content_blocks,
)
from open_webui.utils.tools import (
    get_tools,
    get_updated_tool_function,
    get_terminal_tools,
)
from open_webui.utils.access_control import has_connection_access
from open_webui.utils.plugin import load_function_module_by_id
from open_webui.utils.filter import (
    get_sorted_filter_ids,
    process_filter_functions,
)
from open_webui.utils.code_interpreter import execute_code_jupyter
from open_webui.utils.payload import apply_system_prompt_to_body
from open_webui.utils.response import normalize_usage
from open_webui.utils.mcp.client import MCPClient
from open_webui.utils.hermes import (
    apply_hermes_session_header,
    extract_current_user_message,
    is_temporary_chat_id,
)


class _DisabledForm:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


SearchForm = CreateImageForm = EditImageForm = QueryMemoryForm = _DisabledForm


async def process_web_search(*args, **kwargs):
    raise RuntimeError('Web search is disabled')


async def image_generations(*args, **kwargs):
    raise RuntimeError('Image generation is disabled')


async def image_edits(*args, **kwargs):
    raise RuntimeError('Image editing is disabled')


async def query_memory(*args, **kwargs):
    raise RuntimeError('Memories are disabled')


async def get_sources_from_items(*args, **kwargs):
    return []


async def convert_markdown_base64_images(*args, **kwargs):
    return args[0] if args else ''


async def get_file_url_from_base64(*args, **kwargs):
    raise RuntimeError('File uploads are disabled')


async def get_image_base64_from_url(*args, **kwargs):
    raise RuntimeError('Image handling is disabled')


async def get_image_url_from_base64(*args, **kwargs):
    raise RuntimeError('Image handling is disabled')


from open_webui.config import (
    CACHE_DIR,
    DEFAULT_VOICE_MODE_PROMPT_TEMPLATE,
    DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE,
    DEFAULT_CODE_INTERPRETER_PROMPT,
    CODE_INTERPRETER_PYODIDE_PROMPT,
    CODE_INTERPRETER_BLOCKED_MODULES,
)
from open_webui.env import (
    GLOBAL_LOG_LEVEL,
    ENABLE_CHAT_RESPONSE_BASE64_IMAGE_URL_CONVERSION,
    CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE,
    CHAT_RESPONSE_MAX_TOOL_CALL_RETRIES,
    BYPASS_MODEL_ACCESS_CONTROL,
    ENABLE_REALTIME_CHAT_SAVE,
    ENABLE_QUERIES_CACHE,
    RAG_SYSTEM_CONTEXT,
    ENABLE_FORWARD_USER_INFO_HEADERS,
    FORWARD_SESSION_INFO_HEADER_CHAT_ID,
    FORWARD_SESSION_INFO_HEADER_MESSAGE_ID,
    ENABLE_RESPONSES_API_STATEFUL,
)
from open_webui.utils.headers import include_user_info_headers
from open_webui.constants import TASKS

logging.basicConfig(stream=sys.stdout, level=GLOBAL_LOG_LEVEL)
log = logging.getLogger(__name__)


# We believe in one maker of all models, seen and unseen,
# and in the reasoning which proceeds from the architect.
# We look for the resurrection of dead processes and the
# inference of the world to come.
DEFAULT_REASONING_TAGS = [
    ('<think>', '</think>'),
    ('<thinking>', '</thinking>'),
    ('<reason>', '</reason>'),
    ('<reasoning>', '</reasoning>'),
    ('<thought>', '</thought>'),
    ('<Thought>', '</Thought>'),
    ('<|begin_of_thought|>', '<|end_of_thought|>'),
    ('◁think▷', '◁/think▷'),
]
DEFAULT_SOLUTION_TAGS = [('<|begin_of_solution|>', '<|end_of_solution|>')]
DEFAULT_CODE_INTERPRETER_TAGS = [('<code_interpreter>', '</code_interpreter>')]

ATTACHED_FILE_CONTENT_MAX_CHARS = int(os.getenv('ATTACHED_FILE_CONTENT_MAX_CHARS', '20000'))
ATTACHED_FILES_TOTAL_MAX_CHARS = int(os.getenv('ATTACHED_FILES_TOTAL_MAX_CHARS', '60000'))


def output_id(prefix: str) -> str:
    """Generate OR-style ID: prefix + 24-char hex UUID."""
    return f'{prefix}_{uuid4().hex[:24]}'


def _split_tool_calls(
    tool_calls: list[dict],
) -> list[dict]:
    """Expand tool calls whose arguments contain multiple back-to-back JSON objects.

    Some models (e.g. GPT-5.4) send multiple complete JSON argument objects
    under the same tool call index, producing concatenated invalid JSON like:
        '{"query":"A","count":5}{"query":"B","count":5}'

    Each such tool call is split into separate entries so each gets executed
    independently. Single-object arguments pass through unchanged.
    """

    def split_json_objects(raw: str) -> list[str]:
        decoder = json.JSONDecoder()
        results = []
        position = 0

        while position < len(raw):
            while position < len(raw) and raw[position].isspace():
                position += 1
            if position >= len(raw):
                break
            try:
                _, end = decoder.raw_decode(raw, position)
                results.append(raw[position:end].strip())
                position = end
            except json.JSONDecodeError:
                return [raw]

        return results or [raw]

    expanded = []
    for tool_call in tool_calls:
        arguments = tool_call.get('function', {}).get('arguments', '')
        split_arguments = split_json_objects(arguments)

        if len(split_arguments) <= 1:
            expanded.append(tool_call)
        else:
            for argument in split_arguments:
                cloned = copy.deepcopy(tool_call)
                cloned['id'] = f'call_{uuid4().hex[:24]}'
                cloned['function']['arguments'] = argument
                expanded.append(cloned)

    return expanded


def get_citation_source_from_tool_result(
    tool_name: str, tool_params: dict, tool_result: str, tool_id: str = ''
) -> list[dict]:
    """
    Parse a tool's result and convert it to source dicts for citation display.

    Follows the source format conventions from get_sources_from_items:
    - source: file/item info object with id, name, type
    - document: list of document contents
    - metadata: list of metadata objects with source, file_id, name fields

    Returns a list of sources (usually one, but query_knowledge_files may return multiple).
    """
    _EXPECTS_LIST = {'search_web', 'query_knowledge_files'}
    _EXPECTS_DICT = {'view_knowledge_file', 'view_file'}

    try:
        try:
            tool_result = json.loads(tool_result)
        except (json.JSONDecodeError, TypeError):
            pass  # keep tool_result as-is (e.g. fetch_url returns plain text)
        if isinstance(tool_result, dict) and 'error' in tool_result:
            return []

        # Validate tool_result type based on what the branch expects
        if tool_name in _EXPECTS_LIST and not isinstance(tool_result, list):
            return []
        elif tool_name in _EXPECTS_DICT and not isinstance(tool_result, dict):
            return []

        if tool_name == 'search_web':
            # Parse JSON array: [{"title": "...", "link": "...", "snippet": "..."}]
            results = tool_result
            documents = []
            metadata = []

            for result in results:
                title = result.get('title', '')
                link = result.get('link', '')
                snippet = result.get('snippet', '')

                documents.append(f'{title}\n{snippet}')
                metadata.append(
                    {
                        'source': link,
                        'name': title,
                        'url': link,
                    }
                )

            return [
                {
                    'source': {'name': 'search_web', 'id': 'search_web'},
                    'document': documents,
                    'metadata': metadata,
                }
            ]

        elif tool_name in ('view_knowledge_file', 'view_file'):
            file_data = tool_result
            filename = file_data.get('filename', 'Unknown File')
            file_id = file_data.get('id', '')
            knowledge_name = file_data.get('knowledge_name', '')

            return [
                {
                    'source': {
                        'id': file_id,
                        'name': filename,
                        'type': 'file',
                    },
                    'document': [file_data.get('content', '')],
                    'metadata': [
                        {
                            'file_id': file_id,
                            'name': filename,
                            'source': filename,
                            **({'knowledge_name': knowledge_name} if knowledge_name else {}),
                        }
                    ],
                }
            ]

        elif tool_name == 'fetch_url':
            url = tool_params.get('url', '')
            content = tool_result if isinstance(tool_result, str) else str(tool_result)
            snippet = content[:500] + ('...' if len(content) > 500 else '')

            return [
                {
                    'source': {'name': url or 'fetch_url', 'id': url or 'fetch_url'},
                    'document': [snippet],
                    'metadata': [
                        {
                            'source': url,
                            'name': url,
                            'url': url,
                        }
                    ],
                }
            ]

        elif tool_name == 'query_knowledge_files':
            chunks = tool_result

            # Group chunks by source for better citation display
            # Each unique source becomes a separate source entry
            sources_by_file = {}

            for chunk in chunks:
                source_name = chunk.get('source', 'Unknown')
                file_id = chunk.get('file_id', '')
                note_id = chunk.get('note_id', '')
                chunk_type = chunk.get('type', 'file')
                content = chunk.get('content', '')

                # Use file_id or note_id as the key
                key = file_id or note_id or source_name

                if key not in sources_by_file:
                    sources_by_file[key] = {
                        'source': {
                            'id': file_id or note_id,
                            'name': source_name,
                            'type': chunk_type,
                        },
                        'document': [],
                        'metadata': [],
                    }

                sources_by_file[key]['document'].append(content)
                sources_by_file[key]['metadata'].append(
                    {
                        'file_id': file_id,
                        'name': source_name,
                        'source': source_name,
                        **({'note_id': note_id} if note_id else {}),
                    }
                )

            # Return all grouped sources as a list
            if sources_by_file:
                return list(sources_by_file.values())

            # Empty result fallback
            return []

        else:
            # Fallback for other tools
            return [
                {
                    'source': {
                        'name': tool_name,
                        'type': 'tool',
                        'id': tool_id or tool_name,
                    },
                    'document': [str(tool_result)],
                    'metadata': [{'source': tool_name, 'name': tool_name}],
                }
            ]
    except Exception as e:
        log.exception(f'Error parsing tool result for {tool_name}: {e}')
        return [
            {
                'source': {'name': tool_name, 'type': 'tool'},
                'document': [str(tool_result)],
                'metadata': [{'source': tool_name}],
            }
        ]


def split_content_and_whitespace(content):
    content_stripped = content.rstrip()
    original_whitespace = content[len(content_stripped) :] if len(content) > len(content_stripped) else ''
    return content_stripped, original_whitespace


def is_opening_code_block(content):
    backtick_segments = content.split('```')
    # Even number of segments means the last backticks are opening a new block
    return len(backtick_segments) > 1 and len(backtick_segments) % 2 == 0


_OPENAI_TOOL_DISPLAY_NAMES = {
    'web_search_call': 'Web Search',
    'file_search_call': 'File Search',
    'computer_call': 'Computer Use',
}

_HERMES_TOOL_EVENT_TYPES = {
    'hermes.tool.progress',
    'tool',
    'tool_call',
    'tool_start',
    'tool_use',
    'tool_result',
    'tool_complete',
    'tool_done',
}

_HERMES_GENERIC_TOOL_NAMES = _HERMES_TOOL_EVENT_TYPES | {
    'tool',
    'tools',
    'function',
    'function_call',
    'call',
}
_HERMES_TOOL_NAME_KEYS = [
    'tool_name',
    'function_name',
    'skill_name',
    'command_name',
    'server_name',
    'tool',
    'name',
]
_HERMES_TOOL_ARGUMENT_KEYS = [
    'arguments',
    'args',
    'parameters',
    'params',
    'input',
    'tool_input',
]
_HERMES_TOOL_RESULT_KEYS = [
    'result',
    'output',
    'content',
    'text',
    'response',
    'observation',
    'stdout',
    'stderr',
    'error',
]
_HERMES_TOOL_PREVIEW_KEYS = [
    'label',
    'emoji',
    'command',
    'cmd',
    'query',
    'pattern',
    'target',
    'path',
    'file_path',
    'directory',
    'cwd',
    'working_directory',
    'file',
    'filename',
    'url',
    'description',
    'summary',
]


def _compact_json(value) -> str:
    if value is None:
        return ''
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return str(value)


def _parse_compact_json(value):
    if not isinstance(value, str):
        return value

    parsed = value
    for _ in range(2):
        if not isinstance(parsed, str):
            break
        try:
            parsed = json.loads(parsed)
        except Exception:
            break
    return parsed


def _normalize_tool_identifier(value) -> str:
    text = str(value or '').strip()
    if not text:
        return ''
    text = re.sub(r'Tool_tool$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Tool$', '', text, flags=re.IGNORECASE)
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', text)
    text = re.sub(r'[-\s]+', '_', text)
    return text.lower()


def _dict_get_ci(mapping: dict, keys: list[str]):
    normalized = {key.lower() for key in keys}
    for key, value in mapping.items():
        if str(key).lower() in normalized:
            return value
    return None


def _todo_item_id(item) -> str:
    if not isinstance(item, dict):
        return ''
    return str(_dict_get_ci(item, ['id']) or '').strip()


def _summarize_todos(todos: list) -> dict:
    summary = {
        'total': 0,
        'pending': 0,
        'in_progress': 0,
        'completed': 0,
        'cancelled': 0,
    }
    for item in todos:
        if not isinstance(item, dict):
            continue
        summary['total'] += 1
        status = str(_dict_get_ci(item, ['status']) or 'pending').strip().lower()
        status = status.replace('-', '_').replace(' ', '_')
        if status in {'complete', 'done', 'finished', 'success'}:
            status = 'completed'
        elif status in {'progress', 'running', 'active', 'working'}:
            status = 'in_progress'
        elif status in {'canceled', 'cancel', 'aborted'}:
            status = 'cancelled'
        if status not in {'pending', 'in_progress', 'completed', 'cancelled'}:
            status = 'pending'
        summary[status] += 1
    return summary


def _merge_todo_tool_arguments(existing_args, incoming_args):
    if not isinstance(incoming_args, dict):
        return incoming_args

    merged = dict(existing_args) if isinstance(existing_args, dict) else {}
    merged.update(incoming_args)

    incoming_todos = _dict_get_ci(incoming_args, ['todos'])
    if not isinstance(incoming_todos, list):
        return merged

    existing_todos = _dict_get_ci(existing_args, ['todos']) if isinstance(existing_args, dict) else None
    merge = bool(_dict_get_ci(incoming_args, ['merge']))
    if merge and isinstance(existing_todos, list):
        by_id = {
            _todo_item_id(item): dict(item)
            for item in existing_todos
            if isinstance(item, dict) and _todo_item_id(item)
        }
        ordered_ids = [
            _todo_item_id(item)
            for item in existing_todos
            if isinstance(item, dict) and _todo_item_id(item)
        ]
        appended = []
        for item in incoming_todos:
            if not isinstance(item, dict):
                continue
            item_id = _todo_item_id(item)
            if item_id and item_id in by_id:
                by_id[item_id].update(item)
            elif item_id:
                by_id[item_id] = dict(item)
                appended.append(item_id)
            else:
                appended.append('')
                by_id[''] = dict(item)

        merged_todos = [by_id[item_id] for item_id in ordered_ids if item_id in by_id]
        merged_todos.extend(by_id[item_id] for item_id in appended if item_id in by_id)
    else:
        merged_todos = incoming_todos

    merged['todos'] = merged_todos
    merged['summary'] = _summarize_todos(merged_todos)
    return merged


def _first_present(mapping: dict, keys: list[str]):
    return _dict_get_ci(mapping, keys)


def _collect_tool_preview_fields(data):
    preview = {}
    for value in _walk_values(data):
        if not isinstance(value, dict):
            continue
        for key in _HERMES_TOOL_PREVIEW_KEYS:
            item = _dict_get_ci(value, [key])
            if item not in (None, '') and key not in preview:
                preview[key] = item
    return preview


def _pack_tool_arguments_with_preview(data, arguments):
    preview = _collect_tool_preview_fields(data)
    if not preview:
        return arguments
    return {**preview, 'arguments': arguments}


def _nested_dict(mapping: dict, keys: list[str]) -> dict:
    for key in keys:
        value = _dict_get_ci(mapping, [key])
        if isinstance(value, dict):
            return value
    return {}


def _walk_values(value):
    yield value
    if isinstance(value, dict):
        for nested in value.values():
            yield from _walk_values(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from _walk_values(nested)


def _is_useful_tool_name(value) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip()
    if not text:
        return False
    return text.lower() not in _HERMES_GENERIC_TOOL_NAMES


def _is_empty_tool_value(value) -> bool:
    if value in (None, '', {}, []):
        return True
    if isinstance(value, str):
        text = value.strip()
        return text in {'', '{}', '[]', 'null'}
    return False


def _recursive_first_key(data, keys: list[str]):
    for value in _walk_values(data):
        if not isinstance(value, dict):
            continue
        item = _dict_get_ci(value, keys)
        if item is not None:
            return item
    return None


def _recursive_tool_name(data) -> str | None:
    for value in _walk_values(data):
        if not isinstance(value, dict):
            continue

        function_payload = value.get('function')
        if isinstance(function_payload, dict):
            name = function_payload.get('name')
            if _is_useful_tool_name(name):
                return name

        for key in _HERMES_TOOL_NAME_KEYS:
            name = value.get(key)
            if _is_useful_tool_name(name):
                return name
    return None


def _recursive_tool_arguments(data):
    arguments = _recursive_first_key(data, _HERMES_TOOL_ARGUMENT_KEYS)
    if not _is_empty_tool_value(arguments):
        return _pack_tool_arguments_with_preview(data, arguments)

    return _collect_tool_preview_fields(data)


def _recursive_tool_result(data):
    result = _recursive_first_key(data, _HERMES_TOOL_RESULT_KEYS)
    if _is_empty_tool_value(result):
        return result
    if isinstance(result, dict):
        # Avoid treating another wrapper object as the visible tool result.
        nested = _recursive_first_key(result, _HERMES_TOOL_RESULT_KEYS)
        return nested if nested is not None and nested is not result else result
    return result


def _get_hermes_event_type(data: dict, sse_event_type: str | None = None) -> str:
    event_value = data.get('event')
    event_type = sse_event_type or (event_value if isinstance(event_value, str) else None)
    event_type = event_type or data.get('type') or data.get('event_type') or data.get('name')
    return str(event_type or '').strip()


def _is_hermes_tool_event(data: dict, sse_event_type: str | None = None) -> bool:
    event_type = _get_hermes_event_type(data, sse_event_type).lower()
    if event_type in _HERMES_TOOL_EVENT_TYPES:
        return True
    if event_type.startswith('hermes.tool.'):
        return True
    if event_type.startswith('tool_') or event_type.startswith('tool.'):
        return True
    return any(key in data for key in ('tool_call', 'tool', 'tool_name')) and not data.get('choices')


def _extract_hermes_tool_payload(data: dict) -> dict:
    for key in ('tool_call', 'toolCall', 'tool_use', 'toolUse', 'tool', 'call', 'data', 'payload', 'content'):
        value = data.get(key)
        if isinstance(value, dict):
            return {**data, **value}
    return data


def _extract_hermes_tool_name(payload: dict) -> str:
    function_payload = _nested_dict(payload, ['function'])
    name = _recursive_tool_name(payload) or _first_present(
        payload,
        ['tool_name', 'name', 'function_name', 'skill_name', 'server_name'],
    )
    if not name:
        name = _first_present(function_payload, ['name'])
    return str(name or 'tool')


def _extract_hermes_tool_arguments(payload: dict) -> str:
    function_payload = _nested_dict(payload, ['function'])
    arguments = _recursive_tool_arguments(payload)
    if _is_empty_tool_value(arguments):
        arguments = _first_present(
            payload,
            ['arguments', 'args', 'parameters', 'params', 'input', 'tool_input'],
        )
    if _is_empty_tool_value(arguments):
        arguments = _first_present(function_payload, ['arguments'])
    return _compact_json(arguments if arguments is not None else {})


def _extract_hermes_tool_result(payload: dict) -> str:
    result = _recursive_tool_result(payload)
    if _is_empty_tool_value(result):
        result = _first_present(
            payload,
            ['result', 'output', 'content', 'text', 'response', 'observation', 'error'],
        )
    return _compact_json(result)


def _find_tool_call_item(output: list, call_id: str, name: str) -> dict | None:
    fallback = None
    for item in output:
        if item.get('type') != 'function_call':
            continue
        if call_id and item.get('call_id') == call_id:
            return item
        if item.get('name') == name and item.get('status') != 'completed':
            fallback = item
    return fallback


def _has_tool_call_output(output: list, call_id: str) -> bool:
    return any(
        item.get('type') == 'function_call_output' and item.get('call_id') == call_id
        for item in output
    )


def _hermes_display_call_ids(output: list) -> set[str]:
    return {
        item.get('call_id')
        for item in output
        if item.get('type') == 'function_call'
        and item.get('hermes_display_only')
        and item.get('call_id')
    }


def _merge_hermes_display_tool_call_arguments(output: list, tool_call: dict) -> bool:
    call_id = tool_call.get('id', '')
    if not call_id:
        return False

    func = tool_call.get('function') or {}
    name = func.get('name', '')
    arguments = func.get('arguments', '{}')
    if _is_empty_tool_value(arguments):
        return True

    item = _find_tool_call_item(output, call_id, name)
    if not item or not item.get('hermes_display_only'):
        return False

    parsed_arguments = _parse_compact_json(arguments)
    if _is_empty_tool_value(parsed_arguments):
        return True

    existing_arguments = _parse_compact_json(item.get('arguments', '{}'))
    existing_tool_args = (
        existing_arguments.get('arguments')
        if isinstance(existing_arguments, dict)
        else None
    )
    tool_name = name or (
        _dict_get_ci(existing_arguments, ['tool', 'name'])
        if isinstance(existing_arguments, dict)
        else ''
    )
    if _normalize_tool_identifier(tool_name) == 'todo':
        parsed_arguments = _merge_todo_tool_arguments(existing_tool_args, parsed_arguments)

    if isinstance(existing_arguments, dict):
        merged_arguments = {**existing_arguments}
        merged_arguments['arguments'] = parsed_arguments
    else:
        merged_arguments = {'arguments': parsed_arguments}

    item['arguments'] = _compact_json(merged_arguments)
    return True


def _skip_hermes_display_tool_calls(tool_calls: list[dict], output: list) -> list[dict]:
    hermes_display_call_ids = _hermes_display_call_ids(output)
    if not hermes_display_call_ids:
        return tool_calls
    for tool_call in tool_calls:
        if tool_call.get('id') and tool_call.get('id') in hermes_display_call_ids:
            _merge_hermes_display_tool_call_arguments(output, tool_call)
    return [
        tool_call
        for tool_call in tool_calls
        if not (tool_call.get('id') and tool_call.get('id') in hermes_display_call_ids)
    ]


def _upsert_hermes_tool_event(output: list, data: dict, sse_event_type: str | None = None) -> list:
    event_type = _get_hermes_event_type(data, sse_event_type).lower()
    payload = _extract_hermes_tool_payload(data)
    is_progress_event = event_type == 'hermes.tool.progress'
    name = _extract_hermes_tool_name(payload)
    call_id = str(
        _first_present(
            payload,
            ['call_id', 'tool_call_id', 'toolCallId', 'callId', 'id', 'uuid'],
        )
        or ''
    )
    arguments = _extract_hermes_tool_arguments(payload)
    result = _extract_hermes_tool_result(payload)
    status = str(payload.get('status') or '').lower()
    progress_done = status in {'completed', 'complete', 'done', 'failed', 'error'}
    done = (
        (is_progress_event and (progress_done or not status))
        or event_type in {'tool_result', 'tool_complete', 'tool_done'}
        or event_type.endswith('.result')
        or event_type.endswith('.complete')
        or event_type.endswith('_complete')
        or progress_done
        or bool(result)
    )

    tool_call = _find_tool_call_item(output, call_id, name)
    if tool_call is None:
        call_id = call_id or f'call_{uuid4().hex[:24]}'
        tool_call = {
            'type': 'function_call',
            'id': call_id,
            'call_id': call_id,
            'name': name,
            'arguments': arguments or '{}',
            'status': 'completed' if done else 'in_progress',
        }
        if status:
            tool_call['status'] = 'completed' if progress_done else status
        if is_progress_event:
            tool_call['hermes_display_only'] = True
        output.append(tool_call)
    else:
        call_id = tool_call.get('call_id') or call_id or f'call_{uuid4().hex[:24]}'
        tool_call['call_id'] = call_id
        tool_call['id'] = tool_call.get('id') or call_id
        tool_call['name'] = name or tool_call.get('name', 'tool')
        # Official Hermes progress emits rich display fields on "running",
        # then often sends only toolCallId/status on "completed"; preserve
        # the earlier label/emoji preview instead of replacing it with {}.
        if arguments and arguments != '{}':
            tool_call['arguments'] = arguments
        elif tool_call.get('arguments') in (None, ''):
            tool_call['arguments'] = '{}'
        if done:
            tool_call['status'] = 'completed'
        elif status:
            tool_call['status'] = status
        if is_progress_event:
            tool_call['hermes_display_only'] = True

    if done and result and not is_progress_event and not _has_tool_call_output(output, call_id):
        output.append(
            {
                'type': 'function_call_output',
                'id': output_id('fco'),
                'call_id': call_id,
                'output': [{'type': 'input_text', 'text': result}],
                'status': 'completed',
            }
        )

    return output


def _render_openai_tool_call_handler(item: dict, done: bool) -> str:
    """Render an OpenAI Responses API server-side tool item as a <details> block.

    Handles web_search_call, file_search_call, and computer_call items whose
    schemas are defined in the openai-python SDK (generated from OpenAPI spec).
    """
    item_type = item.get('type', '')
    call_id = item.get('id', '')
    display_name = _OPENAI_TOOL_DISPLAY_NAMES.get(item_type, item_type)

    # Build a short summary of what the tool did
    summary = ''
    if item_type == 'web_search_call':
        action = item.get('action', {})
        if isinstance(action, dict):
            atype = action.get('type', '')
            if atype == 'search':
                queries = action.get('queries') or []
                query = action.get('query', '')
                summary = (
                    f'Search: {", ".join(str(q) for q in queries)}'
                    if queries
                    else (f'Search: {query}' if query else '')
                )
            elif atype == 'open_page':
                summary = f'Open page: {action.get("url", "")}' if action.get('url') else ''
            elif atype == 'find_in_page':
                summary = f'Find in page: {action.get("pattern", "")}' if action.get('pattern') else ''
    elif item_type == 'file_search_call':
        queries = item.get('queries', [])
        if queries:
            summary = f'Queries: {", ".join(str(q) for q in queries)}'
    elif item_type == 'computer_call':
        action = item.get('action')
        actions = item.get('actions')
        if isinstance(action, dict):
            summary = f'Action: {action.get("type", "unknown")}'
        elif isinstance(actions, list) and actions:
            summary = f'Actions: {", ".join(a.get("type", "?") for a in actions if isinstance(a, dict))}'

    escaped_name = html.escape(display_name)
    if done:
        return f'<details type="tool_calls" done="true" id="{call_id}" name="{escaped_name}" arguments="">\n<summary>Tool Executed</summary>\n{html.escape(summary)}\n</details>\n'
    return f'<details type="tool_calls" done="false" id="{call_id}" name="{escaped_name}" arguments="">\n<summary>Executing...</summary>\n</details>\n'


def serialize_output(output: list) -> str:
    """
    Convert OR-aligned output items to HTML for display.
    For LLM consumption, use convert_output_to_messages() instead.
    """
    parts: list[str] = []

    # First pass: collect function_call_output items by call_id for lookup
    tool_outputs = {}
    for item in output:
        if item.get('type') == 'function_call_output':
            tool_outputs[item.get('call_id')] = item

    # Second pass: render items in order
    for idx, item in enumerate(output):
        item_type = item.get('type', '')

        if item_type == 'message':
            for content_part in item.get('content', []):
                if 'text' in content_part:
                    text = content_part.get('text', '').strip()
                    if text:
                        parts.append(text)

        elif item_type == 'function_call':
            call_id = item.get('call_id', '')
            name = item.get('name', '')
            arguments = item.get('arguments', '')
            status = item.get('status', '')
            escaped_status = html.escape(str(status)) if status else ''

            result_item = tool_outputs.get(call_id)
            if result_item:
                result_parts: list[str] = []
                for result_output in result_item.get('output', []):
                    if 'text' in result_output:
                        output_text = result_output.get('text', '')
                        result_parts.append(str(output_text) if not isinstance(output_text, str) else output_text)
                result_text = ''.join(result_parts)
                files = result_item.get('files')
                embeds = result_item.get('embeds', '')

                parts.append(
                    f'<details type="tool_calls" done="true" status="{escaped_status or "completed"}" id="{call_id}" name="{name}" arguments="{html.escape(json.dumps(arguments))}" files="{html.escape(json.dumps(files)) if files else ""}" embeds="{html.escape(json.dumps(embeds))}">\n<summary>Tool Executed</summary>\n{html.escape(json.dumps(result_text, ensure_ascii=False))}\n</details>'
                )
            elif item.get('status') == 'completed':
                parts.append(
                    f'<details type="tool_calls" done="true" status="{escaped_status or "completed"}" id="{call_id}" name="{name}" arguments="{html.escape(json.dumps(arguments))}">\n<summary>Tool Executed</summary>\n</details>'
                )
            else:
                parts.append(
                    f'<details type="tool_calls" done="false" status="{escaped_status or "running"}" id="{call_id}" name="{name}" arguments="{html.escape(json.dumps(arguments))}">\n<summary>Executing...</summary>\n</details>'
                )

        elif item_type == 'function_call_output':
            # Already handled inline with function_call above
            pass

        elif item_type in _OPENAI_TOOL_DISPLAY_NAMES:
            status = item.get('status', 'in_progress')
            done = status in ('completed', 'failed', 'incomplete') or idx != len(output) - 1
            parts.append(_render_openai_tool_call_handler(item, done).rstrip('\n'))

        elif item_type == 'reasoning':
            reasoning_parts: list[str] = []
            # Check for 'summary' (new structure) or 'content' (legacy/fallback)
            source_list = item.get('summary', []) or item.get('content', [])
            for content_part in source_list:
                if 'text' in content_part:
                    reasoning_parts.append(content_part.get('text', ''))
                elif 'summary' in content_part:  # Handle potential nested logic if any
                    pass

            reasoning_content = ''.join(reasoning_parts).strip()

            duration = item.get('duration')
            status = item.get('status', 'in_progress')

            # Infer completion: if this reasoning item is NOT the last item,
            # render as done (a subsequent item means reasoning is complete)
            is_last_item = idx == len(output) - 1

            display = html.escape(
                '\n'.join(
                    (f'> {line}' if not line.startswith('>') else line) for line in reasoning_content.splitlines()
                )
            )

            if status == 'completed' or duration is not None or not is_last_item:
                parts.append(
                    f'<details type="reasoning" done="true" duration="{duration or 0}">\n<summary>Thought for {duration or 0} seconds</summary>\n{display}\n</details>'
                )
            else:
                parts.append(
                    f'<details type="reasoning" done="false">\n<summary>Thinking…</summary>\n{display}\n</details>'
                )

        elif item_type == 'open_webui:code_interpreter':
            # Code interpreter needs to inspect/mutate prior accumulated content
            # to strip trailing unclosed code fences — materialize only here.
            content = '\n'.join(parts)
            content_stripped, original_whitespace = split_content_and_whitespace(content)
            if is_opening_code_block(content_stripped):
                content = content_stripped.rstrip('`').rstrip() + original_whitespace
            else:
                content = content_stripped + original_whitespace

            # Re-split back into parts list after mutation
            parts = [content] if content else []

            # Render the code_interpreter item as a <details> block
            # so the frontend Collapsible renders "Analyzing..."/"Analyzed".
            code = item.get('code', '').strip()
            lang = item.get('lang', 'python')
            status = item.get('status', 'in_progress')
            duration = item.get('duration')
            is_last_item = idx == len(output) - 1

            # Build inner content: code block
            display = ''
            if code:
                display = f'```{lang}\n{code}\n```'

            # Build output attribute as HTML-escaped JSON for CodeBlock.svelte
            ci_output = item.get('output')
            output_attr = ''
            if ci_output:
                if isinstance(ci_output, dict):
                    output_json = json.dumps(ci_output, ensure_ascii=False)
                else:
                    output_json = json.dumps({'result': str(ci_output)}, ensure_ascii=False)
                output_attr = f' output="{html.escape(output_json)}"'

            if status == 'completed' or duration is not None or not is_last_item:
                parts.append(
                    f'<details type="code_interpreter" done="true" duration="{duration or 0}"{output_attr}>\n<summary>Analyzed</summary>\n{display}\n</details>'
                )
            else:
                parts.append(
                    f'<details type="code_interpreter" done="false"{output_attr}>\n<summary>Analyzing…</summary>\n{display}\n</details>'
                )

    return '\n'.join(parts).strip()


def deep_merge(target, source):
    """
    Merge source into target recursively (returning new structure).
    - Dicts: Recursive merge.
    - Strings: Concatenation.
    - Others: Overwrite.
    """
    if isinstance(target, dict) and isinstance(source, dict):
        new_target = target.copy()
        for k, v in source.items():
            if k in new_target:
                new_target[k] = deep_merge(new_target[k], v)
            else:
                new_target[k] = v
        return new_target
    elif isinstance(target, str) and isinstance(source, str):
        return target + source
    else:
        return source


def handle_responses_streaming_event(
    data: dict,
    current_output: list,
) -> tuple[list, dict | None]:
    """
    Handle Responses API streaming events in a pure functional way.

    Args:
        data: The event data
        current_output: List of output items (treated as immutable)

    Returns:
        tuple[list, dict | None]: (new_output, metadata)
        - new_output: The updated output list.
        - metadata: Metadata to emit (e.g. usage), {} if update occurred, None if skip.
    """
    # Default: no change
    # Note: treating current_output as immutable, but avoiding full deepcopy for perf.
    # We will shallow copy only if we need to modify the list structure or items.

    event_type = data.get('type', '')

    if event_type == 'response.output_item.added':
        item = data.get('item', {})
        if item:
            new_output = list(current_output)
            new_output.append(item)
            return new_output, None
        return current_output, None

    elif event_type == 'response.content_part.added':
        part = data.get('part', {})
        output_index = data.get('output_index', len(current_output) - 1)

        if current_output and 0 <= output_index < len(current_output):
            new_output = list(current_output)
            # Copy the item to mutate it
            item = new_output[output_index].copy()
            new_output[output_index] = item

            if 'content' not in item:
                item['content'] = []
            else:
                # Copy content list
                item['content'] = list(item['content'])

            if item.get('type') == 'reasoning':
                # Reasoning items should not have content parts
                pass
            else:
                item['content'].append(part)
            return new_output, None
        return current_output, None

    elif event_type == 'response.reasoning_summary_part.added':
        part = data.get('part', {})
        output_index = data.get('output_index', len(current_output) - 1)

        if current_output and 0 <= output_index < len(current_output):
            new_output = list(current_output)
            item = new_output[output_index].copy()
            new_output[output_index] = item

            if 'summary' not in item:
                item['summary'] = []
            else:
                item['summary'] = list(item['summary'])

            item['summary'].append(part)
            return new_output, None
        return current_output, None

    elif event_type.startswith('response.') and event_type.endswith('.delta'):
        # Generic Delta Handling
        parts = event_type.split('.')
        if len(parts) >= 3:
            delta_type = parts[1]
            delta = data.get('delta', '')

            output_index = data.get('output_index', len(current_output) - 1)

            if current_output and 0 <= output_index < len(current_output):
                new_output = list(current_output)
                item = new_output[output_index].copy()
                new_output[output_index] = item
                item_type = item.get('type', '')

                # Determine target field and object based on delta_type and item_type
                if delta_type == 'function_call_arguments':
                    key = 'arguments'
                    if item_type == 'function_call':
                        # Function call args are usually strings
                        item[key] = item.get(key, '') + str(delta)
                else:
                    # Generic handling, refined by item type below
                    pass

                    if item_type == 'message':
                        # Message items: "text"/"output_text" -> "text"
                        # "reasoning_text" -> Skipped (should use reasoning item)
                        if delta_type in ['text', 'output_text']:
                            key = 'text'
                        elif delta_type in ['reasoning_text', 'reasoning_summary_text']:
                            # Skip reasoning updates for message items
                            return new_output, None
                        else:
                            key = delta_type

                        content_index = data.get('content_index', 0)
                        if 'content' not in item:
                            item['content'] = []
                        else:
                            item['content'] = list(item['content'])
                        content_list = item['content']

                        while len(content_list) <= content_index:
                            content_list.append({'type': 'text', 'text': ''})

                        # Copy the part to mutate it
                        part = content_list[content_index].copy()
                        content_list[content_index] = part

                        current_val = part.get(key)
                        if current_val is None:
                            # Initialize based on delta type
                            current_val = {} if isinstance(delta, dict) else ''

                        part[key] = deep_merge(current_val, delta)

                    elif item_type == 'reasoning':
                        # Reasoning items: "reasoning_text"/"reasoning_summary_text" -> "text"
                        # "text"/"output_text" -> Skipped (should use message item)
                        if delta_type == 'reasoning_summary_text':
                            # Summary updates -> item['summary']
                            key = 'text'
                            summary_index = data.get('summary_index', 0)
                            if 'summary' not in item:
                                item['summary'] = []
                            else:
                                item['summary'] = list(item['summary'])
                            summary_list = item['summary']

                            while len(summary_list) <= summary_index:
                                summary_list.append({'type': 'summary_text', 'text': ''})

                            part = summary_list[summary_index].copy()
                            summary_list[summary_index] = part

                            target_val = part.get(key, '')
                            part[key] = deep_merge(target_val, delta)

                        elif delta_type == 'reasoning_text':
                            # Reasoning body updates -> item['content']
                            key = 'text'
                            content_index = data.get('content_index', 0)
                            if 'content' not in item:
                                item['content'] = []
                            else:
                                item['content'] = list(item['content'])
                            content_list = item['content']

                            while len(content_list) <= content_index:
                                # Reasoning content parts default to text
                                content_list.append({'type': 'text', 'text': ''})

                            part = content_list[content_index].copy()
                            content_list[content_index] = part

                            target_val = part.get(key, '')
                            part[key] = deep_merge(target_val, delta)

                        elif delta_type in ['text', 'output_text']:
                            return new_output, None
                        else:
                            # Fallback just in case other deltas target reasoning?
                            pass

                    else:
                        # Fallback for other item types
                        if delta_type in ['text', 'output_text']:
                            key = 'text'
                        else:
                            key = delta_type

                        current_val = item.get(key)
                        if current_val is None:
                            current_val = {} if isinstance(delta, dict) else ''
                        item[key] = deep_merge(current_val, delta)

            return new_output, None

    elif event_type.startswith('response.') and event_type.endswith('.done'):
        # Delta Events: response.content_part.done, response.text.done, etc.
        parts = event_type.split('.')
        if len(parts) >= 3:
            type_name = parts[1]

            # 1. Handle specific Delta "done" signals
            if type_name == 'content_part':
                # "Signaling that no further changes will occur to a content part"
                # If payloads contains the full part, we could update it.
                # Usually purely signaling in standard implementation, but we check payload.
                part = data.get('part')
                output_index = data.get('output_index', len(current_output) - 1)

                if part and current_output and 0 <= output_index < len(current_output):
                    new_output = list(current_output)
                    item = new_output[output_index].copy()
                    new_output[output_index] = item

                    if 'content' in item:
                        item['content'] = list(item['content'])
                        content_index = data.get('content_index', len(item['content']) - 1)
                        if 0 <= content_index < len(item['content']):
                            item['content'][content_index] = part
                            return new_output, {}
                return current_output, None

            elif type_name == 'reasoning_summary_part':
                part = data.get('part')
                output_index = data.get('output_index', len(current_output) - 1)

                if part and current_output and 0 <= output_index < len(current_output):
                    new_output = list(current_output)
                    item = new_output[output_index].copy()
                    new_output[output_index] = item

                    if 'summary' in item:
                        item['summary'] = list(item['summary'])
                        summary_index = data.get('summary_index', len(item['summary']) - 1)
                        if 0 <= summary_index < len(item['summary']):
                            item['summary'][summary_index] = part
                            return new_output, {}
                return current_output, None

            # 2. Skip Output Item done (handled specifically below)
            if type_name == 'output_item':
                pass

            # 3. Generic Field Done (text.done, audio.done)
            elif type_name not in ['completed', 'failed']:
                output_index = data.get('output_index', len(current_output) - 1)
                if current_output and 0 <= output_index < len(current_output):
                    key = (
                        'text'
                        if type_name
                        in [
                            'text',
                            'output_text',
                            'reasoning_text',
                            'reasoning_summary_text',
                        ]
                        else type_name
                    )
                    if type_name == 'function_call_arguments':
                        key = 'arguments'

                    if key in data:
                        final_value = data[key]
                        new_output = list(current_output)
                        item = new_output[output_index].copy()
                        new_output[output_index] = item
                        item_type = item.get('type', '')

                        if type_name == 'function_call_arguments':
                            if item_type == 'function_call':
                                item['arguments'] = final_value
                        elif item_type == 'message':
                            content_index = data.get('content_index', 0)
                            if 'content' in item:
                                item['content'] = list(item['content'])
                                if len(item['content']) > content_index:
                                    part = item['content'][content_index].copy()
                                    item['content'][content_index] = part
                                    part[key] = final_value
                        elif item_type == 'reasoning':
                            item['status'] = 'completed'
                        else:
                            item[key] = final_value

                        return new_output, {}

        return current_output, None

    elif event_type == 'response.output_item.done':
        # Delta Event: Output item complete
        item = data.get('item')
        output_index = data.get('output_index', len(current_output) - 1)

        new_output = list(current_output)
        if item and 0 <= output_index < len(current_output):
            new_output[output_index] = item
        elif item:
            new_output.append(item)
        return new_output, {}

    elif event_type == 'response.completed':
        # State Machine Event: Completed
        response_data = data.get('response', {})
        final_output = response_data.get('output')

        new_output = final_output if final_output is not None else current_output

        # Ensure reasoning items are marked as completed in the final output
        if new_output:
            for item in new_output:
                if item.get('type') == 'reasoning' and item.get('status') != 'completed':
                    item['status'] = 'completed'

        return new_output, {
            'usage': response_data.get('usage'),
            'done': True,
            'response_id': response_data.get('id'),
        }

    elif event_type == 'response.in_progress':
        # State Machine Event: In Progress
        # We could extract metadata if needed, but for now just acknowledge iteration
        return current_output, None

    elif event_type == 'response.failed':
        # State Machine Event: Failed
        error = data.get('response', {}).get('error', {})
        return current_output, {'error': error}

    else:
        return current_output, None


def get_source_context(sources: list, source_ids: dict = None, include_content: bool = True) -> str:
    """
    Build <source> tag context string from citation sources.
    """
    context_string = ''
    if source_ids is None:
        source_ids = {}
    for source in sources:
        for doc, meta in zip(source.get('document', []), source.get('metadata', [])):
            source_id = meta.get('source') or source.get('source', {}).get('id') or 'N/A'
            if source_id not in source_ids:
                source_ids[source_id] = len(source_ids) + 1
            src_name = source.get('source', {}).get('name')
            src_type = source.get('source', {}).get('type')
            src_rid = source.get('source', {}).get('id')
            body = doc if include_content else ''
            context_string += (
                f'<source id="{source_ids[source_id]}"'
                + (f' name="{src_name}"' if src_name else '')
                + (f' resource-type="{src_type}"' if src_type else '')
                + (f' resource-id="{src_rid}"' if src_rid else '')
                + f'>{body}</source>\n'
            )
    return context_string


def apply_source_context_to_messages(
    request: Request,
    messages: list,
    sources: list,
    user_message: str,
    include_content: bool = True,
) -> list:
    """
    Build source context from citation sources and apply to messages.
    Uses RAG template to format context for model consumption.

    When include_content is False, emit <source> tags with id/name but no
    document body — useful when the content is already present elsewhere
    (e.g. in a tool result message) and only citation markers are needed.
    """
    if not sources or not user_message:
        return messages

    context = get_source_context(sources, include_content=include_content)

    context = context.strip()
    if not context:
        return messages

    if RAG_SYSTEM_CONTEXT:
        return add_or_update_system_message(
            rag_template(request.app.state.config.RAG_TEMPLATE, context, user_message),
            messages,
            append=True,
        )
    else:
        return add_or_update_user_message(
            rag_template(request.app.state.config.RAG_TEMPLATE, context, user_message),
            messages,
            append=False,
        )


async def process_tool_result(
    request,
    tool_function_name,
    tool_result,
    tool_type,
    direct_tool=False,
    metadata=None,
    user=None,
):
    tool_result_embeds = []
    EXTERNAL_TOOL_TYPES = ('external', 'action', 'terminal')

    # Support (HTMLResponse, result_context) tuples: the optional second
    # element lets tool authors provide the LLM with actionable context
    # about the generated embed instead of the generic fallback message.
    result_context = None
    if isinstance(tool_result, tuple) and len(tool_result) == 2 and isinstance(tool_result[0], HTMLResponse):
        tool_result, result_context = tool_result

    if isinstance(tool_result, HTMLResponse):
        content_disposition = tool_result.headers.get('Content-Disposition', '')
        if 'inline' in content_disposition:
            content = tool_result.body.decode('utf-8', 'replace')
            tool_result_embeds.append(content)

            if 200 <= tool_result.status_code < 300:
                if result_context is not None and isinstance(result_context, (str, dict, list)):
                    tool_result = result_context
                else:
                    tool_result = {
                        'status': 'success',
                        'code': 'ui_component',
                        'message': f'{tool_function_name}: Embedded UI result is active and visible to the user.',
                    }
            elif 400 <= tool_result.status_code < 500:
                tool_result = {
                    'status': 'error',
                    'code': 'ui_component',
                    'message': f'{tool_function_name}: Client error {tool_result.status_code} from embedded UI result.',
                }
            elif 500 <= tool_result.status_code < 600:
                tool_result = {
                    'status': 'error',
                    'code': 'ui_component',
                    'message': f'{tool_function_name}: Server error {tool_result.status_code} from embedded UI result.',
                }
            else:
                tool_result = {
                    'status': 'error',
                    'code': 'ui_component',
                    'message': f'{tool_function_name}: Unexpected status code {tool_result.status_code} from embedded UI result.',
                }
        else:
            tool_result = tool_result.body.decode('utf-8', 'replace')

    elif (tool_type in EXTERNAL_TOOL_TYPES and isinstance(tool_result, tuple)) or (
        direct_tool and isinstance(tool_result, list) and len(tool_result) == 2
    ):
        tool_result, tool_response_headers = tool_result

        try:
            if not isinstance(tool_response_headers, dict):
                tool_response_headers = dict(tool_response_headers)
        except Exception as e:
            tool_response_headers = {}
            log.debug(e)

        if tool_response_headers and isinstance(tool_response_headers, dict):
            content_disposition = tool_response_headers.get(
                'Content-Disposition',
                tool_response_headers.get('content-disposition', ''),
            )

            if 'inline' in content_disposition:
                content_type = tool_response_headers.get(
                    'Content-Type',
                    tool_response_headers.get('content-type', ''),
                )
                location = tool_response_headers.get(
                    'Location',
                    tool_response_headers.get('location', ''),
                )

                if 'text/html' in content_type:
                    # Support (html_content, result_context) nested tuple
                    result_context = None
                    html_content = tool_result
                    if isinstance(tool_result, (tuple, list)) and len(tool_result) == 2:
                        html_content, result_context = tool_result

                    # Display as iframe embed
                    tool_result_embeds.append(html_content)
                    if result_context is not None and isinstance(result_context, (str, dict, list)):
                        tool_result = result_context
                    else:
                        tool_result = {
                            'status': 'success',
                            'code': 'ui_component',
                            'message': f'{tool_function_name}: Embedded UI result is active and visible to the user.',
                        }
                elif location:
                    # Support (html_content, result_context) nested tuple for location embeds
                    result_context = None
                    if isinstance(tool_result, (tuple, list)) and len(tool_result) == 2:
                        _, result_context = tool_result

                    tool_result_embeds.append(location)
                    if result_context is not None and isinstance(result_context, (str, dict, list)):
                        tool_result = result_context
                    else:
                        tool_result = {
                            'status': 'success',
                            'code': 'ui_component',
                            'message': f'{tool_function_name}: Embedded UI result is active and visible to the user.',
                        }

    tool_result_files = []

    # Detect base64 image data URIs from tool results (e.g. binary image
    # responses from execute_tool_server).  Move the data URI to
    # tool_result_files and replace tool_result with a text summary.
    if isinstance(tool_result, str) and tool_result.startswith('data:image/'):
        tool_result_files.append({'type': 'image', 'url': tool_result})
        tool_result = f'{tool_function_name}: Image file read successfully.'

    if isinstance(tool_result, list):
        if tool_type == 'mcp':  # MCP
            tool_response = []
            for item in tool_result:
                if isinstance(item, dict):
                    if item.get('type') == 'text':
                        text = item.get('text', '')
                        if isinstance(text, str):
                            try:
                                text = json.loads(text)
                            except json.JSONDecodeError:
                                pass
                        tool_response.append(text)
                    elif item.get('type') in ['image', 'audio']:
                        file_url = await get_file_url_from_base64(
                            request,
                            f'data:{item.get("mimeType")};base64,{item.get("data", item.get("blob", ""))}',
                            {
                                'chat_id': metadata.get('chat_id', None),
                                'message_id': metadata.get('message_id', None),
                                'session_id': metadata.get('session_id', None),
                                'result': item,
                            },
                            user,
                        )

                        tool_result_files.append(
                            {
                                'type': item.get('type', 'data'),
                                'url': file_url,
                            }
                        )
                    elif item.get('type') == 'resource':
                        resource = item.get('resource', {})
                        text = resource.get('text', '')
                        if isinstance(text, str) and text:
                            try:
                                text = json.loads(text)
                            except json.JSONDecodeError:
                                pass
                            tool_response.append(text)
            tool_result = tool_response[0] if len(tool_response) == 1 else tool_response
        else:  # OpenAPI
            for item in tool_result:
                if isinstance(item, str) and item.startswith('data:'):
                    tool_result_files.append(
                        {
                            'type': 'data',
                            'content': item,
                        }
                    )
                    tool_result.remove(item)

    if isinstance(tool_result, list):
        tool_result = {'results': tool_result}

    if isinstance(tool_result, dict) or isinstance(tool_result, list):
        tool_result = json.dumps(tool_result, indent=2, ensure_ascii=False)

    # Safety: ensure tool_result is always a string (or None) to prevent
    # downstream TypeError when concatenating (e.g. if an upstream callable
    # returned a tuple that was not unpacked by the branches above).
    if tool_result is not None and not isinstance(tool_result, str):
        if isinstance(tool_result, tuple):
            # execute_tool_server returns (data, headers); unpack the data part
            tool_result = json.dumps(tool_result[0], indent=2, ensure_ascii=False) if len(tool_result) > 0 else ''
        else:
            tool_result = str(tool_result)

    return tool_result, tool_result_files, tool_result_embeds


async def terminal_event_handler(
    tool_function_name: str,
    tool_function_params: dict,
    tool_result,
    event_emitter,
):
    """Emit terminal:* events for Open Terminal tools.

    - display_file  → emits 'terminal:display_file' to open the file preview.
    - write_file / replace_file_content → emits 'terminal:write_file' to refresh.
    - run_command → emits 'terminal:run_command' with cwd to refresh if relevant.
    """
    if not event_emitter:
        return

    if tool_function_name == 'display_file':
        path = tool_function_params.get('path', '')
        if not path:
            return
        # Only emit if the file actually exists
        parsed = tool_result
        if isinstance(parsed, str):
            try:
                parsed = json.loads(parsed)
            except (json.JSONDecodeError, TypeError):
                pass
        if isinstance(parsed, dict) and parsed.get('exists') is False:
            return

        await event_emitter(
            {
                'type': f'terminal:{tool_function_name}',
                'data': {'path': path},
            }
        )
    elif tool_function_name in ('write_file', 'replace_file_content'):
        path = tool_function_params.get('path', '')
        if not path:
            return
        await event_emitter(
            {
                'type': f'terminal:{tool_function_name}',
                'data': {'path': path},
            }
        )
    elif tool_function_name == 'run_command':
        await event_emitter(
            {
                'type': 'terminal:run_command',
                'data': {},
            }
        )


async def chat_completion_tools_handler(
    request: Request, body: dict, extra_params: dict, user: UserModel, models, tools
) -> tuple[dict, dict]:
    async def get_content_from_response(response) -> Optional[str]:
        content = None
        if hasattr(response, 'body_iterator'):
            async for chunk in response.body_iterator:
                data = json.loads(chunk.decode('utf-8', 'replace'))
                content = data['choices'][0]['message']['content']

            # Cleanup any remaining background tasks if necessary
            if response.background is not None:
                await response.background()
        else:
            content = response['choices'][0]['message']['content']
        return content

    def get_tools_function_calling_payload(messages, task_model_id, content):
        user_message = get_last_user_message(messages)

        if user_message and messages and messages[-1]['role'] == 'user':
            # Remove the last user message to avoid duplication
            messages = messages[:-1]

        recent_messages = messages[-4:] if len(messages) > 4 else messages
        chat_history = '\n'.join(
            f'{message["role"].upper()}: """{get_content_from_message(message)}"""' for message in recent_messages
        )

        prompt = f'History:\n{chat_history}\nQuery: {user_message}' if chat_history else f'Query: {user_message}'

        return {
            'model': task_model_id,
            'messages': [
                {'role': 'system', 'content': content},
                {'role': 'user', 'content': prompt},
            ],
            'stream': False,
            'metadata': {'task': str(TASKS.FUNCTION_CALLING)},
        }

    event_caller = extra_params['__event_call__']
    event_emitter = extra_params['__event_emitter__']
    metadata = extra_params['__metadata__']

    task_model_id = get_task_model_id(
        body['model'],
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    skip_files = False
    sources = []

    specs = [tool['spec'] for tool in tools.values()]
    tools_specs = json.dumps(specs, ensure_ascii=False)

    if request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE != '':
        template = request.app.state.config.TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE
    else:
        template = DEFAULT_TOOLS_FUNCTION_CALLING_PROMPT_TEMPLATE

    tools_function_calling_prompt = tools_function_calling_generation_template(template, tools_specs)
    payload = get_tools_function_calling_payload(body['messages'], task_model_id, tools_function_calling_prompt)

    try:
        response = await generate_chat_completion(request, form_data=payload, user=user)
        log.debug(f'{response=}')
        content = await get_content_from_response(response)
        log.debug(f'{content=}')

        if not content:
            return body, {}

        try:
            content = content[content.find('{') : content.rfind('}') + 1]
            if not content:
                raise Exception('No JSON object found in the response')

            result = json.loads(content)

            async def tool_call_handler(tool_call):
                nonlocal skip_files

                log.debug(f'{tool_call=}')

                tool_function_name = tool_call.get('name', None)
                if tool_function_name not in tools:
                    return body, {}

                tool_function_params = tool_call.get('parameters', {})

                tool = None
                tool_type = ''
                direct_tool = False

                try:
                    tool = tools[tool_function_name]
                    tool_type = tool.get('type', '')
                    direct_tool = tool.get('direct', False)

                    spec = tool.get('spec', {})
                    allowed_params = spec.get('parameters', {}).get('properties', {}).keys()
                    tool_function_params = {k: v for k, v in tool_function_params.items() if k in allowed_params}

                    if tool.get('direct', False):
                        tool_result = await event_caller(
                            {
                                'type': 'execute:tool',
                                'data': {
                                    'id': str(uuid4()),
                                    'name': tool_function_name,
                                    'params': tool_function_params,
                                    'server': tool.get('server', {}),
                                    'session_id': metadata.get('session_id', None),
                                },
                            }
                        )
                    else:
                        tool_function = tool['callable']
                        tool_result = await tool_function(**tool_function_params)

                except Exception as e:
                    tool_result = str(e)

                tool_result, tool_result_files, tool_result_embeds = await process_tool_result(
                    request,
                    tool_function_name,
                    tool_result,
                    tool_type,
                    direct_tool,
                    metadata,
                    user,
                )

                if event_emitter:
                    await terminal_event_handler(
                        tool_function_name,
                        tool_function_params,
                        tool_result,
                        event_emitter,
                    )

                    if tool_result_files:
                        await event_emitter(
                            {
                                'type': 'files',
                                'data': {
                                    'files': tool_result_files,
                                },
                            }
                        )

                    if tool_result_embeds:
                        await event_emitter(
                            {
                                'type': 'embeds',
                                'data': {
                                    'embeds': tool_result_embeds,
                                },
                            }
                        )

                if tool_result:
                    tool = tools[tool_function_name]
                    tool_id = tool.get('tool_id', '')

                    tool_name = f'{tool_id}/{tool_function_name}' if tool_id else f'{tool_function_name}'

                    # Citation is enabled for this tool
                    sources.append(
                        {
                            'source': {
                                'name': (f'{tool_name}'),
                            },
                            'document': [str(tool_result)],
                            'metadata': [
                                {
                                    'source': (f'{tool_name}'),
                                    'parameters': tool_function_params,
                                }
                            ],
                            'tool_result': True,
                        }
                    )

                    if tools[tool_function_name].get('metadata', {}).get('file_handler', False):
                        skip_files = True

            # check if "tool_calls" in result
            if result.get('tool_calls'):
                for tool_call in result.get('tool_calls'):
                    await tool_call_handler(tool_call)
            else:
                await tool_call_handler(result)

        except Exception as e:
            log.debug(f'Error: {e}')
            content = None
    except Exception as e:
        log.debug(f'Error: {e}')
        content = None

    log.debug(f'tool_contexts: {sources}')

    if skip_files and 'files' in body.get('metadata', {}):
        del body['metadata']['files']

    return body, {'sources': sources}


async def chat_memory_handler(request: Request, form_data: dict, extra_params: dict, user):
    try:
        results = await query_memory(
            request,
            QueryMemoryForm(
                **{
                    'content': get_last_user_message(form_data['messages']) or '',
                    'k': 3,
                }
            ),
            user,
        )
    except Exception as e:
        log.debug(e)
        results = None

    user_context = ''
    if results and hasattr(results, 'documents'):
        if results.documents and len(results.documents) > 0:
            for doc_idx, doc in enumerate(results.documents[0]):
                created_at_date = 'Unknown Date'

                if results.metadatas[0][doc_idx].get('created_at'):
                    created_at_timestamp = results.metadatas[0][doc_idx]['created_at']
                    created_at_date = time.strftime('%Y-%m-%d', time.localtime(created_at_timestamp))

                user_context += f'{doc_idx + 1}. [{created_at_date}] {doc}\n'

    form_data['messages'] = add_or_update_system_message(
        f'User Context:\n{user_context}\n', form_data['messages'], append=True
    )

    return form_data


async def chat_web_search_handler(request: Request, form_data: dict, extra_params: dict, user):
    event_emitter = extra_params['__event_emitter__']
    await event_emitter(
        {
            'type': 'status',
            'data': {
                'action': 'web_search',
                'description': 'Searching the web',
                'done': False,
            },
        }
    )

    messages = form_data['messages']
    user_message = get_last_user_message(messages)

    queries = []
    try:
        res = await generate_queries(
            request,
            {
                'model': form_data['model'],
                'messages': messages,
                'prompt': user_message,
                'type': 'web_search',
                'chat_id': extra_params.get('__chat_id__'),
            },
            user,
        )

        response = res['choices'][0]['message']['content']

        try:
            bracket_start = response.rfind('{')
            bracket_end = response.rfind('}') + 1

            if bracket_start == -1 or bracket_end == -1:
                raise Exception('No JSON object found in the response')

            response = response[bracket_start:bracket_end]
            queries = json.loads(response)
            queries = queries.get('queries', [])
        except Exception as e:
            queries = [response]

        if ENABLE_QUERIES_CACHE:
            request.state.cached_queries = queries

    except Exception as e:
        log.exception(e)
        queries = [user_message or '']

    # Check if generated queries are empty
    if len(queries) == 1 and queries[0].strip() == '':
        queries = [user_message or '']

    # Check if queries are not found
    if len(queries) == 0:
        await event_emitter(
            {
                'type': 'status',
                'data': {
                    'action': 'web_search',
                    'description': 'No search query generated',
                    'done': True,
                },
            }
        )
        return form_data

    await event_emitter(
        {
            'type': 'status',
            'data': {
                'action': 'web_search_queries_generated',
                'queries': queries,
                'done': False,
            },
        }
    )

    try:
        results = await process_web_search(
            request,
            SearchForm(queries=queries),
            user=user,
        )

        if results:
            files = form_data.get('files', [])

            if results.get('collection_names'):
                for col_idx, collection_name in enumerate(results.get('collection_names')):
                    files.append(
                        {
                            'collection_name': collection_name,
                            'name': ', '.join(queries),
                            'type': 'web_search',
                            'urls': results['filenames'],
                            'queries': queries,
                        }
                    )
            elif results.get('docs'):
                # Invoked when bypass embedding and retrieval is set to True
                docs = results['docs']
                files.append(
                    {
                        'docs': docs,
                        'name': ', '.join(queries),
                        'type': 'web_search',
                        'urls': results['filenames'],
                        'queries': queries,
                    }
                )

            form_data['files'] = files

            await event_emitter(
                {
                    'type': 'status',
                    'data': {
                        'action': 'web_search',
                        'description': 'Searched {{count}} sites',
                        'urls': results['filenames'],
                        'items': results.get('items', []),
                        'done': True,
                    },
                }
            )
        else:
            await event_emitter(
                {
                    'type': 'status',
                    'data': {
                        'action': 'web_search',
                        'description': 'No search results found',
                        'done': True,
                        'error': True,
                    },
                }
            )

    except Exception as e:
        log.exception(e)
        await event_emitter(
            {
                'type': 'status',
                'data': {
                    'action': 'web_search',
                    'description': 'An error occurred while searching the web',
                    'queries': queries,
                    'done': True,
                    'error': True,
                },
            }
        )

    return form_data


def get_images_from_messages(message_list):
    images = []

    for message in reversed(message_list):
        message_images = []
        for file in message.get('files', []):
            if file.get('type') == 'image':
                message_images.append(file.get('url'))
            elif file.get('content_type', '').startswith('image/'):
                message_images.append(file.get('url'))

        if message_images:
            images.append(message_images)

    return images


async def get_model_image_url_from_file(file: dict, request: Request) -> str:
    url = file.get('url') or ''
    if url.startswith('data:image/'):
        log.warning('Skipping inline data image for model request; uploaded images must be stored as files first')
        return ''
    if url.startswith(('http://', 'https://')):
        return url

    file_id = url
    match = re.search(r'/api/v1/files/([^/]+)/content', url)
    if match:
        file_id = match.group(1)

    try:
        from open_webui.models.files import Files
        from open_webui.storage.provider import get_public_url_for_path

        file_item = await Files.get_file_by_id(file_id)
        if file_item:
            public_url = get_public_url_for_path(file_item.path)
            if public_url:
                return public_url

            if isinstance(file_item.path, str) and file_item.path.startswith('s3://'):
                direct_url = await get_file_access_url({'id': file_id}, request)
                if direct_url:
                    return direct_url
    except Exception as e:
        log.debug(f'Failed to resolve image file URL: {e}')

    base_url = str(request.app.state.config.WEBUI_URL or request.base_url).rstrip('/')
    if url.startswith('/'):
        return f'{base_url}{url}'
    return f'{base_url}/api/v1/files/{file_id}/content'


async def get_image_urls(delta_images, request, metadata, user) -> list[str]:
    if not isinstance(delta_images, list):
        return []

    image_urls = []
    for img in delta_images:
        if not isinstance(img, dict) or img.get('type') != 'image_url':
            continue

        url = img.get('image_url', {}).get('url')
        if not url:
            continue

        if url.startswith('data:image/png;base64'):
            url = await get_image_url_from_base64(request, url, metadata, user)

        image_urls.append(url)

    return image_urls


async def add_file_context(messages: list, chat_id: str, user) -> list:
    """
    Add file URLs to messages for native function calling.
    """
    if not chat_id or chat_id.startswith('local:'):
        return messages

    chat = await Chats.get_chat_by_id_and_user_id(chat_id, user.id)
    if not chat:
        return messages

    history = chat.chat.get('history', {})
    stored_messages = get_message_list(history.get('messages', {}), history.get('currentId'))

    def format_file_tag(file):
        attrs = f'type="{file.get("type", "file")}" url="{file["url"]}"'
        if file.get('content_type'):
            attrs += f' content_type="{file["content_type"]}"'
        if file.get('name'):
            attrs += f' name="{file["name"]}"'
        return f'<file {attrs}/>'

    # Pair only user-role messages from both lists to avoid misalignment.
    # After process_messages_with_output(), assistant messages with tool calls
    # are expanded into multiple messages (assistant + tool results), making
    # the payload message list longer than the stored message list. A naive
    # positional zip() would pair user messages with wrong stored messages,
    # causing later images to lose their file context (see #21878).
    user_messages = [m for m in messages if m.get('role') == 'user']
    stored_user_messages = [m for m in stored_messages if m.get('role') == 'user']

    for message, stored_message in zip(user_messages, stored_user_messages):
        files_with_urls = [
            file
            for file in stored_message.get('files', [])
            if file.get('url') and not file.get('url').startswith('data:')
        ]
        if not files_with_urls:
            continue

        file_tags = [format_file_tag(file) for file in files_with_urls]
        file_context = '<attached_files>\n' + '\n'.join(file_tags) + '\n</attached_files>\n\n'

        content = message.get('content', '')
        if isinstance(content, list):
            message['content'] = [{'type': 'text', 'text': file_context}] + content
        else:
            message['content'] = file_context + content

    return messages


def _extract_file_id(file: dict) -> str:
    file_id = str(file.get('id') or file.get('url') or '').strip()
    match = re.search(r'/api/v1/files/([^/]+)/content', file_id)
    if match:
        return match.group(1)
    return file_id


async def get_file_access_url(file: dict, request: Request) -> str:
    """Return a model-accessible URL for an uploaded file without RAG processing."""
    file_id = _extract_file_id(file)

    if not file_id:
        return ''

    try:
        from open_webui.models.files import Files
        from open_webui.storage.provider import get_public_url_for_path, get_storage_provider_for_path

        file_item = await Files.get_file_by_id(file_id)
        if file_item:
            public_url = get_public_url_for_path(file_item.path)
            if public_url:
                return public_url

        if file_item and isinstance(file_item.path, str) and file_item.path.startswith('s3://'):
            storage = get_storage_provider_for_path(file_item.path)
            s3_key = storage._extract_s3_key(file_item.path)
            if getattr(storage, 'public_base_url', None):
                public_url = storage.get_public_url(file_item.path)
                if public_url:
                    return public_url

            return await asyncio.to_thread(
                storage.s3_client.generate_presigned_url,
                'get_object',
                Params={'Bucket': storage.bucket_name, 'Key': s3_key},
                ExpiresIn=3600,
            )
    except Exception as e:
        log.debug(f'Failed to generate direct file access URL for {file_id}: {e}')

    from open_webui.utils.auth import create_token

    token = create_token(
        {
            'sub': 'hermes-file-access',
            'scope': 'file_content',
            'file_id': file_id,
        },
        expires_delta=timedelta(hours=1),
    )
    base_url = str(request.app.state.config.WEBUI_URL or request.base_url).rstrip('/')
    return f'{base_url}/api/v1/files/{file_id}/content/direct?{urlencode({"token": token})}'


class _HTMLTextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self._parts = []

    def handle_starttag(self, tag, attrs):
        if tag in {'script', 'style', 'noscript'}:
            self._skip_depth += 1
        elif tag in {'p', 'br', 'div', 'section', 'article', 'li', 'tr', 'h1', 'h2', 'h3', 'h4'}:
            self._parts.append('\n')

    def handle_endtag(self, tag):
        if tag in {'script', 'style', 'noscript'} and self._skip_depth > 0:
            self._skip_depth -= 1
        elif tag in {'p', 'div', 'section', 'article', 'li', 'tr', 'h1', 'h2', 'h3', 'h4'}:
            self._parts.append('\n')

    def handle_data(self, data):
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self._parts.append(text)

    def text(self) -> str:
        return re.sub(r'\n{3,}', '\n\n', re.sub(r'[ \t]+', ' ', ' '.join(self._parts))).strip()


def _decode_text_bytes(raw: bytes) -> str:
    for encoding in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', errors='replace')


def _truncate_attached_file_content(content: str, max_chars: int) -> tuple[str, bool]:
    if max_chars <= 0:
        return '', bool(content)
    if len(content) <= max_chars:
        return content, False
    return content[:max_chars].rstrip(), True


def _cdata(content: str) -> str:
    return content.replace(']]>', ']]]]><![CDATA[>')


def _extract_pdf_text(file_path, max_chars: int) -> tuple[str, bool]:
    try:
        from pypdf import PdfReader
    except Exception as e:
        log.debug(f'PDF text extraction is unavailable: {e}')
        return '', False

    text_parts = []
    truncated = False
    reader = PdfReader(str(file_path))
    for page in reader.pages:
        page_text = page.extract_text() or ''
        if not page_text.strip():
            continue
        remaining = max_chars - sum(len(part) for part in text_parts)
        if remaining <= 0:
            truncated = True
            break
        if len(page_text) > remaining:
            text_parts.append(page_text[:remaining])
            truncated = True
            break
        text_parts.append(page_text)

    return '\n\n'.join(part.strip() for part in text_parts if part.strip()).strip(), truncated


def _extract_text_or_html(file_path, content_type: str, max_chars: int) -> tuple[str, bool]:
    with open(file_path, 'rb') as f:
        raw = f.read(max(max_chars * 4, 8192) + 1)

    decoded = _decode_text_bytes(raw)
    truncated_by_read = len(raw) > max(max_chars * 4, 8192)

    if 'html' in content_type or str(file_path).lower().endswith(('.html', '.htm')):
        parser = _HTMLTextExtractor()
        parser.feed(decoded)
        decoded = parser.text()

    content, truncated_by_chars = _truncate_attached_file_content(decoded.strip(), max_chars)
    return content, truncated_by_read or truncated_by_chars


async def get_file_text_content(file: dict, request: Request, max_chars: int) -> tuple[str, bool]:
    """Extract lightweight PDF/text/html content for model context."""
    if max_chars <= 0:
        return '', False

    file_id = _extract_file_id(file)
    if not file_id:
        return '', False

    try:
        from pathlib import Path

        from open_webui.models.files import Files
        from open_webui.storage.provider import get_storage_provider_for_path

        file_item = await Files.get_file_by_id(file_id)
        if not file_item:
            return '', False

        content_type = (
            file.get('content_type')
            or (file.get('file') or {}).get('meta', {}).get('content_type')
            or (file_item.meta or {}).get('content_type')
            or mimetypes.guess_type(file_item.filename or '')[0]
            or ''
        ).lower()
        filename = (
            file.get('name')
            or file.get('filename')
            or (file_item.meta or {}).get('name')
            or file_item.filename
            or ''
        )
        filename_lower = filename.lower()

        existing_content = (file_item.data or {}).get('content')
        if isinstance(existing_content, str) and existing_content.strip():
            return _truncate_attached_file_content(existing_content.strip(), max_chars)

        supports_pdf = content_type == 'application/pdf' or filename_lower.endswith('.pdf')
        supports_text = (
            content_type.startswith('text/')
            or any(token in content_type for token in ('json', 'xml', 'csv', 'markdown', 'javascript', 'html'))
            or filename_lower.endswith(
                (
                    '.txt',
                    '.md',
                    '.markdown',
                    '.csv',
                    '.json',
                    '.jsonl',
                    '.xml',
                    '.html',
                    '.htm',
                    '.py',
                    '.js',
                    '.ts',
                    '.tsx',
                    '.jsx',
                    '.css',
                    '.scss',
                    '.yaml',
                    '.yml',
                    '.toml',
                    '.ini',
                    '.log',
                )
            )
        )
        if not supports_pdf and not supports_text:
            return '', False

        storage = get_storage_provider_for_path(file_item.path)
        file_path = Path(await asyncio.to_thread(storage.get_file, file_item.path))
        if not file_path.is_file():
            return '', False

        if supports_pdf:
            return await asyncio.to_thread(_extract_pdf_text, file_path, max_chars)
        return await asyncio.to_thread(_extract_text_or_html, file_path, content_type, max_chars)
    except Exception as e:
        log.debug(f'Failed to extract attached file content for {file_id}: {e}')
        return '', False


async def add_direct_file_context(
    messages: list,
    files: list,
    request: Request,
    content_file_ids: set[str] | None = None,
) -> list:
    """Inject file URLs into the latest user message; extract text only for selected files."""
    if not messages or not files:
        return messages

    file_tags = []
    remaining_chars = ATTACHED_FILES_TOTAL_MAX_CHARS
    for file in files:
        if not isinstance(file, dict):
            continue
        if file.get('type') != 'file':
            continue

        url = await get_file_access_url(file, request)
        if not url:
            continue

        attrs = f'type="file" url="{html.escape(url, quote=True)}"'
        name = file.get('name') or file.get('filename')
        content_type = file.get('content_type') or (file.get('file') or {}).get('meta', {}).get('content_type')
        if content_type:
            attrs += f' content_type="{html.escape(str(content_type), quote=True)}"'
        if name:
            attrs += f' name="{html.escape(str(name), quote=True)}"'

        file_id = _extract_file_id(file)
        should_extract_content = content_file_ids is None or file_id in content_file_ids

        content = ''
        content_truncated = False
        if should_extract_content and remaining_chars > 0:
            max_chars = min(ATTACHED_FILE_CONTENT_MAX_CHARS, remaining_chars)
            content, content_truncated = await get_file_text_content(file, request, max_chars)
            remaining_chars -= len(content)

        if content:
            if content_truncated:
                attrs += ' content_truncated="true"'
            file_tags.append(f'<file {attrs}>\n<content><![CDATA[{_cdata(content)}]]></content>\n</file>')
        else:
            file_tags.append(f'<file {attrs}/>')

    if not file_tags:
        return messages

    file_context = '<attached_files>\n' + '\n'.join(file_tags) + '\n</attached_files>\n\n'

    for message in reversed(messages):
        if message.get('role') != 'user':
            continue
        content = message.get('content', '')
        if isinstance(content, list):
            message['content'] = [{'type': 'text', 'text': file_context}] + content
        else:
            message['content'] = file_context + str(content or '')
        break

    return messages


async def add_current_turn_image_context(message: dict, request: Request) -> dict:
    image_files = [
        file
        for file in message.get('files', []) or []
        if isinstance(file, dict)
        and (file.get('type') == 'image' or (file.get('content_type') or '').startswith('image/'))
    ]
    if not image_files:
        return message

    image_parts = []
    for file in image_files:
        image_url = await get_model_image_url_from_file(file, request)
        if image_url:
            image_parts.append({'type': 'image_url', 'image_url': {'url': image_url}})

    if not image_parts:
        return message

    content = message.get('content', '')
    if isinstance(content, list):
        message['content'] = [*content, *image_parts]
    else:
        message['content'] = [{'type': 'text', 'text': str(content or '')}, *image_parts]
    return message


async def chat_image_generation_handler(request: Request, form_data: dict, extra_params: dict, user):
    metadata = extra_params.get('__metadata__', {})
    chat_id = metadata.get('chat_id', None)
    __event_emitter__ = extra_params.get('__event_emitter__', None)

    if not chat_id or not isinstance(chat_id, str) or not __event_emitter__:
        return form_data

    if chat_id.startswith('local:'):
        message_list = form_data.get('messages', [])
    else:
        chat = await Chats.get_chat_by_id_and_user_id(chat_id, user.id)
        await __event_emitter__(
            {
                'type': 'status',
                'data': {'description': 'Creating image', 'done': False},
            }
        )

        messages_map = chat.chat.get('history', {}).get('messages', {})
        message_id = chat.chat.get('history', {}).get('currentId')
        message_list = get_message_list(messages_map, message_id)

    user_message = get_last_user_message(message_list)

    prompt = user_message
    message_images = get_images_from_messages(message_list)

    # Limit to first 2 sets of images
    # We may want to change this in the future to allow more images
    input_images = []
    for idx, images in enumerate(message_images):
        if idx >= 2:
            break
        for image in images:
            input_images.append(image)

    system_message_content = ''

    if len(input_images) > 0 and request.app.state.config.ENABLE_IMAGE_EDIT:
        # Edit image(s)
        try:
            images = await image_edits(
                request=request,
                form_data=EditImageForm(**{'prompt': prompt, 'image': input_images}),
                metadata={
                    'chat_id': metadata.get('chat_id', None),
                    'message_id': metadata.get('message_id', None),
                },
                user=user,
            )

            await __event_emitter__(
                {
                    'type': 'status',
                    'data': {'description': 'Image created', 'done': True},
                }
            )

            await __event_emitter__(
                {
                    'type': 'files',
                    'data': {
                        'files': [
                            {
                                'type': 'image',
                                'url': image['url'],
                            }
                            for image in images
                        ]
                    },
                }
            )

            system_message_content = '<context>The requested image has been edited and created and is now being shown to the user. Let them know that it has been generated.</context>'
        except Exception as e:
            log.debug(e)

            error_message = ''
            if isinstance(e, HTTPException):
                if e.detail and isinstance(e.detail, dict):
                    error_message = e.detail.get('message', str(e.detail))
                else:
                    error_message = str(e.detail)

            await __event_emitter__(
                {
                    'type': 'status',
                    'data': {
                        'description': f'An error occurred while generating an image',
                        'done': True,
                    },
                }
            )

            system_message_content = f'<context>Image generation was attempted but failed. The system is currently unable to generate the image. Tell the user that the following error occurred: {error_message}</context>'

    else:
        # Create image(s)
        if request.app.state.config.ENABLE_IMAGE_PROMPT_GENERATION:
            try:
                res = await generate_image_prompt(
                    request,
                    {
                        'model': form_data['model'],
                        'messages': form_data['messages'],
                        'chat_id': metadata.get('chat_id'),
                    },
                    user,
                )

                response = res['choices'][0]['message']['content']

                try:
                    bracket_start = response.rfind('{')
                    bracket_end = response.rfind('}') + 1

                    if bracket_start == -1 or bracket_end == -1:
                        raise Exception('No JSON object found in the response')

                    response = response[bracket_start:bracket_end]
                    response = json.loads(response)
                    prompt = response.get('prompt', [])
                except Exception as e:
                    prompt = user_message

            except Exception as e:
                log.exception(e)
                prompt = user_message

        try:
            images = await image_generations(
                request=request,
                form_data=CreateImageForm(**{'prompt': prompt}),
                metadata={
                    'chat_id': metadata.get('chat_id', None),
                    'message_id': metadata.get('message_id', None),
                },
                user=user,
            )

            await __event_emitter__(
                {
                    'type': 'status',
                    'data': {'description': 'Image created', 'done': True},
                }
            )

            await __event_emitter__(
                {
                    'type': 'files',
                    'data': {
                        'files': [
                            {
                                'type': 'image',
                                'url': image['url'],
                            }
                            for image in images
                        ]
                    },
                }
            )

            system_message_content = '<context>The requested image has been created by the system successfully and is now being shown to the user. Let the user know that the image they requested has been generated and is now shown in the chat.</context>'
        except Exception as e:
            log.debug(e)

            error_message = ''
            if isinstance(e, HTTPException):
                if e.detail and isinstance(e.detail, dict):
                    error_message = e.detail.get('message', str(e.detail))
                else:
                    error_message = str(e.detail)

            await __event_emitter__(
                {
                    'type': 'status',
                    'data': {
                        'description': f'An error occurred while generating an image',
                        'done': True,
                    },
                }
            )

            system_message_content = f'<context>Image generation was attempted but failed because of an error. The system is currently unable to generate the image. Tell the user that the following error occurred: {error_message}</context>'

    if system_message_content:
        form_data['messages'] = add_or_update_system_message(system_message_content, form_data['messages'])

    return form_data


async def chat_completion_files_handler(
    request: Request, body: dict, extra_params: dict, user: UserModel
) -> tuple[dict, dict[str, list]]:
    __event_emitter__ = extra_params['__event_emitter__']
    sources = []

    if files := body.get('metadata', {}).get('files', None):
        # Check if all files are in full context mode
        all_full_context = all(item.get('context') == 'full' for item in files)

        queries = []
        if not all_full_context:
            try:
                queries_response = await generate_queries(
                    request,
                    {
                        'model': body['model'],
                        'messages': body['messages'],
                        'type': 'retrieval',
                        'chat_id': body.get('metadata', {}).get('chat_id'),
                    },
                    user,
                )
                queries_response = queries_response['choices'][0]['message']['content']

                try:
                    bracket_start = queries_response.rfind('{')
                    bracket_end = queries_response.rfind('}') + 1

                    if bracket_start == -1 or bracket_end == -1:
                        raise Exception('No JSON object found in the response')

                    queries_response = queries_response[bracket_start:bracket_end]
                    queries_response = json.loads(queries_response)
                except Exception as e:
                    queries_response = {'queries': [queries_response]}

                queries = queries_response.get('queries', [])
            except Exception:
                pass

            await __event_emitter__(
                {
                    'type': 'status',
                    'data': {
                        'action': 'queries_generated',
                        'queries': queries,
                        'done': False,
                    },
                }
            )

        if len(queries) == 0:
            queries = [get_last_user_message(body['messages']) or '']

        try:
            # Directly await async get_sources_from_items (no thread needed - fully async now)
            sources = await get_sources_from_items(
                request=request,
                items=files,
                queries=queries,
                embedding_function=lambda query, prefix: request.app.state.EMBEDDING_FUNCTION(
                    query, prefix=prefix, user=user
                ),
                k=request.app.state.config.TOP_K,
                reranking_function=(
                    (lambda query, documents: request.app.state.RERANKING_FUNCTION(query, documents, user=user))
                    if request.app.state.RERANKING_FUNCTION
                    else None
                ),
                k_reranker=request.app.state.config.TOP_K_RERANKER,
                r=request.app.state.config.RELEVANCE_THRESHOLD,
                hybrid_bm25_weight=request.app.state.config.HYBRID_BM25_WEIGHT,
                hybrid_search=request.app.state.config.ENABLE_RAG_HYBRID_SEARCH,
                full_context=all_full_context or request.app.state.config.RAG_FULL_CONTEXT,
                user=user,
            )
        except Exception as e:
            log.exception(e)

        log.debug(f'rag_contexts:sources: {sources}')

        unique_ids = set()
        for source in sources or []:
            if not source or len(source.keys()) == 0:
                continue

            documents = source.get('document') or []
            metadatas = source.get('metadata') or []
            src_info = source.get('source') or {}

            for index, _ in enumerate(documents):
                metadata = metadatas[index] if index < len(metadatas) else None
                _id = (metadata or {}).get('source') or (src_info or {}).get('id') or 'N/A'
                unique_ids.add(_id)

        sources_count = len(unique_ids)
        await __event_emitter__(
            {
                'type': 'status',
                'data': {
                    'action': 'sources_retrieved',
                    'count': sources_count,
                    'done': True,
                },
            }
        )

    return body, {'sources': sources}


def apply_params_to_form_data(form_data, model):
    params = form_data.pop('params', {})
    custom_params = params.pop('custom_params', {})

    open_webui_params = {
        'stream_response': bool,
        'stream_delta_chunk_size': int,
        'function_calling': str,
        'reasoning_tags': list,
        'system': str,
    }

    for key in list(params.keys()):
        if key in open_webui_params:
            del params[key]

    if custom_params:
        # Attempt to parse custom_params if they are strings
        for key, value in custom_params.items():
            if isinstance(value, str):
                try:
                    # Attempt to parse the string as JSON
                    custom_params[key] = json.loads(value)
                except json.JSONDecodeError:
                    # If it fails, keep the original string
                    pass

        # If custom_params are provided, merge them into params
        params = deep_update(params, custom_params)

    if model.get('owned_by') == 'ollama':
        # Ollama specific parameters
        form_data['options'] = params
    else:
        if isinstance(params, dict):
            for key, value in params.items():
                if value is not None:
                    form_data[key] = value

        if 'logit_bias' in params and params['logit_bias'] is not None:
            try:
                logit_bias = convert_logit_bias_input_to_json(params['logit_bias'])

                if logit_bias:
                    form_data['logit_bias'] = json.loads(logit_bias)
            except Exception as e:
                log.exception(f'Error parsing logit_bias: {e}')

    return form_data


async def convert_url_images_to_base64(form_data):
    messages = form_data.get('messages', [])

    for message in messages:
        content = message.get('content')
        if not isinstance(content, list):
            continue

        new_content = []

        for item in content:
            if not isinstance(item, dict) or item.get('type') != 'image_url':
                new_content.append(item)
                continue

            image_url = item.get('image_url', {}).get('url', '')
            if image_url.startswith('data:image/'):
                new_content.append(item)
                continue

            try:
                base64_data = await get_image_base64_from_url(image_url)
                if base64_data:
                    new_content.append(
                        {
                            'type': 'image_url',
                            'image_url': {'url': base64_data},
                        }
                    )
                else:
                    new_content.append(item)
            except Exception as e:
                log.debug(f'Error converting image URL to base64: {e}')
                new_content.append(item)

        message['content'] = new_content

    return form_data


async def load_messages_from_db(chat_id: str, message_id: str) -> Optional[list[dict]]:
    """
    Load the message chain from DB up to message_id,
    keeping only LLM-relevant fields (role, content, output).
    """
    messages_map = await Chats.get_messages_map_by_chat_id(chat_id)
    if not messages_map:
        return None

    db_messages = get_message_list(messages_map, message_id)
    if not db_messages:
        return None

    return [{k: v for k, v in msg.items() if k in ('role', 'content', 'output', 'files')} for msg in db_messages]


def process_messages_with_output(messages: list[dict]) -> list[dict]:
    """
    Process messages with OR-aligned output items for LLM consumption.

    For assistant messages with 'output' field, produces properly formatted
    OpenAI-style messages (tool_calls + tool results). Strips 'output' before LLM.
    """
    processed = []

    for message in messages:
        if message.get('role') == 'assistant' and message.get('output'):
            # Use output items for clean OpenAI-format messages
            output_messages = convert_output_to_messages(message['output'], raw=True)
            if output_messages:
                processed.extend(output_messages)
                continue

        # Strip 'output' field before adding (LLM shouldn't see it)
        clean_message = {k: v for k, v in message.items() if k != 'output'}
        processed.append(clean_message)

    return processed


SKILL_MENTION_RE = re.compile(r'<\$([^|>]+)\|?[^>]*>')


def _get_text_parts(message: dict) -> list[str]:
    """Return all text segments from a message's content."""
    content = message.get('content')
    if isinstance(content, str):
        return [content]
    if isinstance(content, list):
        return [p.get('text', '') for p in content if isinstance(p, dict) and p.get('type') == 'text']
    return []


def extract_skill_ids_from_messages(messages: list[dict]) -> set[str]:
    """Extract skill IDs from <$skillId|label> mention tags in messages."""
    ids: set[str] = set()
    for message in messages:
        for text in _get_text_parts(message):
            ids.update(m.group(1) for m in SKILL_MENTION_RE.finditer(text))
    return ids


def strip_skill_mentions(messages: list[dict]) -> None:
    """Strip <$skillId|label> mention tags from message content in-place."""
    strip_re = re.compile(r'<\$[^>]+>')
    for message in messages:
        content = message.get('content')
        if isinstance(content, str) and strip_re.search(content):
            message['content'] = strip_re.sub('', content).strip()
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get('type') == 'text':
                    text = part.get('text', '')
                    if strip_re.search(text):
                        part['text'] = strip_re.sub('', text).strip()


async def process_chat_payload(request, form_data, user, metadata, model):
    # Pipeline Inlet -> Filter Inlet -> Chat Memory -> Chat Web Search -> Chat Image Generation
    # -> Chat Code Interpreter (Form Data Update) -> (Default) Chat Tools Function Calling
    # -> Chat Files

    # Arena model resolution — pick the sub-model now so all downstream
    # processing (knowledge, capabilities, tools, params) uses its settings
    # instead of the empty arena wrapper.
    if model.get('owned_by') == 'arena':
        arena_model_ids = model.get('info', {}).get('meta', {}).get('model_ids')
        arena_filter_mode = model.get('info', {}).get('meta', {}).get('filter_mode')
        if arena_model_ids and arena_filter_mode == 'exclude':
            arena_model_ids = [
                available_model['id']
                for available_model in request.app.state.MODELS.values()
                if available_model.get('owned_by') != 'arena' and available_model['id'] not in arena_model_ids
            ]

        if isinstance(arena_model_ids, list) and arena_model_ids:
            selected_model_id = random.choice(arena_model_ids)
        else:
            arena_model_ids = [
                available_model['id']
                for available_model in request.app.state.MODELS.values()
                if available_model.get('owned_by') != 'arena'
            ]
            selected_model_id = random.choice(arena_model_ids)

        selected_model = request.app.state.MODELS.get(selected_model_id)
        if selected_model:
            model = selected_model
            form_data['model'] = selected_model_id
            metadata['selected_model_id'] = selected_model_id

    form_data = apply_params_to_form_data(form_data, model)
    log.debug(f'form_data: {form_data}')

    chat_id = metadata.get('chat_id')
    user_message_id = metadata.get('user_message_id')
    if is_temporary_chat_id(chat_id):
        raise HTTPException(status_code=400, detail='Temporary chats are disabled for Hermes sessions.')

    hermes_session_delta = bool(chat_id)
    if hermes_session_delta:
        current_user_message = extract_current_user_message(form_data, metadata)
        if not current_user_message:
            raise HTTPException(status_code=400, detail='Hermes session requests require a current user message.')
        current_user_message = await add_current_turn_image_context(current_user_message, request)
        current_user_message.pop('files', None)
        form_data['messages'] = [current_user_message]
        metadata['hermes_session_delta'] = True
        metadata['tool_ids'] = []
        metadata['filter_ids'] = []
        form_data['features'] = {}
        form_data.pop('tools', None)
        form_data.pop('tool_choice', None)
    else:
        # Load messages from DB when available — DB preserves structured
        # output items which the frontend strips. The Hermes session path
        # above deliberately skips this because Hermes owns history.
        if chat_id and user_message_id:
            db_messages = await load_messages_from_db(chat_id, user_message_id)
            if db_messages:
                system_message = get_system_message(form_data.get('messages', []))
                form_data['messages'] = [system_message, *db_messages] if system_message else db_messages

                last_user_message_index = None
                for index, message in enumerate(form_data['messages']):
                    if message.get('role') == 'user':
                        last_user_message_index = index

                for index, message in enumerate(form_data['messages']):
                    if index == last_user_message_index and message.get('role') == 'user':
                        message = await add_current_turn_image_context(message, request)
                    message.pop('files', None)

        form_data['messages'] = process_messages_with_output(form_data.get('messages', []))

        system_message = get_system_message(form_data.get('messages', []))
        if system_message:  # Chat Controls/User Settings
            try:
                form_data = apply_system_prompt_to_body(
                    system_message.get('content'), form_data, metadata, user, replace=True
                )  # Required to handle system prompt variables
            except Exception:
                pass

    form_data = await convert_url_images_to_base64(form_data)

    event_emitter = await get_event_emitter(metadata)
    event_caller = await get_event_call(metadata)

    extra_params = {
        '__event_emitter__': event_emitter,
        '__event_call__': event_caller,
        '__user__': user.model_dump() if isinstance(user, UserModel) else {},
        '__metadata__': metadata,
        '__oauth_token__': await get_system_oauth_token(request, user),
        '__request__': request,
        '__model__': model,
        '__chat_id__': metadata.get('chat_id'),
        '__message_id__': metadata.get('message_id'),
    }
    # Initialize events to store additional event to be sent to the client
    # Initialize contexts and citation
    if getattr(request.state, 'direct', False) and hasattr(request.state, 'model'):
        models = {
            request.state.model['id']: request.state.model,
        }
    else:
        models = request.app.state.MODELS

    task_model_id = get_task_model_id(
        form_data['model'],
        request.app.state.config.TASK_MODEL,
        request.app.state.config.TASK_MODEL_EXTERNAL,
        models,
    )

    events = []
    sources = []

    # Folder "Project" handling
    # Check if the request has chat_id and is inside of a folder
    # Uses lightweight column query — only fetches folder_id, not the full chat JSON blob
    chat_id = metadata.get('chat_id', None)
    folder_id = None
    if chat_id and user:
        folder_id = await Chats.get_chat_folder_id(chat_id, user.id)

    # Fallback: use folder_id from metadata (temporary chats have no DB record)
    if not folder_id:
        folder_id = metadata.get('folder_id', None)

    if folder_id and user and not hermes_session_delta:
        folder = await Folders.get_folder_by_id_and_user_id(folder_id, user.id)

        if folder and folder.data:
            if 'system_prompt' in folder.data:
                form_data = apply_system_prompt_to_body(folder.data['system_prompt'], form_data, metadata, user)
            if 'files' in folder.data:
                if metadata.get('params', {}).get('function_calling') != 'native':
                    form_data['files'] = [
                        *folder.data['files'],
                        *form_data.get('files', []),
                    ]
                else:
                    # Native FC: skip RAG injection, builtin tools
                    # will read folder knowledge from metadata.
                    metadata['folder_knowledge'] = folder.data['files']

    # Model "Knowledge" handling
    user_message = get_last_user_message(form_data['messages'])
    model_knowledge = model.get('info', {}).get('meta', {}).get('knowledge', False)

    if model_knowledge and not hermes_session_delta and metadata.get('params', {}).get('function_calling') != 'native':
        await event_emitter(
            {
                'type': 'status',
                'data': {
                    'action': 'knowledge_search',
                    'query': user_message,
                    'done': False,
                },
            }
        )

        knowledge_files = []
        for item in model_knowledge:
            if item.get('collection_name'):
                knowledge_files.append(
                    {
                        'id': item.get('collection_name'),
                        'name': item.get('name'),
                        'legacy': True,
                    }
                )
            elif item.get('collection_names'):
                knowledge_files.append(
                    {
                        'name': item.get('name'),
                        'type': 'collection',
                        'collection_names': item.get('collection_names'),
                        'legacy': True,
                    }
                )
            else:
                knowledge_files.append(item)

        files = form_data.get('files', [])
        files.extend(knowledge_files)
        form_data['files'] = files

    variables = form_data.pop('variables', None)

    if not hermes_session_delta:
        # Process the form_data through the pipeline
        try:
            form_data = await process_pipeline_inlet_filter(request, form_data, user, models)
        except Exception as e:
            raise e

        try:
            filter_ids = await get_sorted_filter_ids(request, model, metadata.get('filter_ids', []))
            filter_functions = await Functions.get_functions_by_ids(filter_ids)

            form_data, flags = await process_filter_functions(
                request=request,
                filter_functions=filter_functions,
                filter_type='inlet',
                form_data=form_data,
                extra_params=extra_params,
            )
        except Exception as e:
            raise Exception(f'{e}')

    features = form_data.pop('features', None) or {}
    extra_params['__features__'] = features
    if features and not hermes_session_delta:
        if 'voice' in features and features['voice']:
            if request.app.state.config.VOICE_MODE_PROMPT_TEMPLATE != None:
                if request.app.state.config.VOICE_MODE_PROMPT_TEMPLATE != '':
                    template = request.app.state.config.VOICE_MODE_PROMPT_TEMPLATE
                else:
                    template = DEFAULT_VOICE_MODE_PROMPT_TEMPLATE

                form_data['messages'] = add_or_update_system_message(
                    template,
                    form_data['messages'],
                )

        if 'memory' in features and features['memory']:
            # Skip forced memory injection when native FC is enabled - model can use memory tools
            if metadata.get('params', {}).get('function_calling') != 'native':
                form_data = await chat_memory_handler(request, form_data, extra_params, user)

        if 'web_search' in features and features['web_search']:
            # Skip forced RAG web search when native FC is enabled - model can use web_search tool
            if metadata.get('params', {}).get('function_calling') != 'native':
                form_data = await chat_web_search_handler(request, form_data, extra_params, user)

        if 'image_generation' in features and features['image_generation']:
            # Skip forced image generation when native FC is enabled - model can use generate_image tool
            if metadata.get('params', {}).get('function_calling') != 'native':
                form_data = await chat_image_generation_handler(request, form_data, extra_params, user)

        if 'code_interpreter' in features and features['code_interpreter']:
            engine = getattr(request.app.state.config, 'CODE_INTERPRETER_ENGINE', 'disabled')

            # Skip XML-tag prompt injection when native FC is enabled —
            # execute_code will be injected as a builtin tool instead
            if metadata.get('params', {}).get('function_calling') != 'native':
                prompt = (
                    request.app.state.config.CODE_INTERPRETER_PROMPT_TEMPLATE
                    if request.app.state.config.CODE_INTERPRETER_PROMPT_TEMPLATE != ''
                    else DEFAULT_CODE_INTERPRETER_PROMPT
                )

                if engine != 'jupyter':
                    prompt += CODE_INTERPRETER_PYODIDE_PROMPT

                form_data['messages'] = add_or_update_user_message(
                    prompt,
                    form_data['messages'],
                )
            else:
                if engine != 'jupyter':
                    form_data['messages'] = add_or_update_system_message(
                        CODE_INTERPRETER_PYODIDE_PROMPT,
                        form_data['messages'],
                        append=True,
                    )

    tool_ids = form_data.pop('tool_ids', None)
    terminal_id = form_data.pop('terminal_id', None)
    files = form_data.pop('files', None)
    form_data.pop('folder_id', None)
    if hermes_session_delta:
        tool_ids = None
        terminal_id = None
        form_data.pop('skill_ids', None)

    # Caller-provided OpenAI-style tools take precedence over server-side
    # tool resolution (tool_ids, MCP servers, builtin tools).
    payload_tools = form_data.get('tools', None)

    # Skills — extract IDs from message content (<$skillId|label> tags) so
    # persisted chats work without relying on the frontend to send skill_ids.
    user_skill_ids = set(form_data.pop('skill_ids', None) or [])
    user_skill_ids |= extract_skill_ids_from_messages(form_data.get('messages', []))
    model_skill_ids = set(model.get('info', {}).get('meta', {}).get('skillIds', []))

    all_skill_ids = set() if hermes_session_delta else user_skill_ids | model_skill_ids
    available_skills = []
    if all_skill_ids:
        from open_webui.models.skills import Skills as SkillsModel

        accessible_skill_ids = {s.id for s in await SkillsModel.get_skills_by_user_id(user.id, 'read')}
        available_skills = []
        for sid in all_skill_ids:
            if sid in accessible_skill_ids:
                s = await SkillsModel.get_skill_by_id(sid)
                if s and s.is_active:
                    available_skills.append(s)

        skill_descriptions = ''
        for skill in available_skills:
            if skill.id in user_skill_ids:
                # User-selected: inject full content
                form_data['messages'] = add_or_update_system_message(
                    f'<skill name="{skill.name}">\n{skill.content}\n</skill>',
                    form_data['messages'],
                    append=True,
                )
            else:
                # Model-attached: name+description only
                skill_descriptions += f'<skill>\n<id>{skill.id}</id>\n<name>{skill.name}</name>\n<description>{skill.description or ""}</description>\n</skill>\n'

        if skill_descriptions:
            form_data['messages'] = add_or_update_system_message(
                f'<available_skills>\n{skill_descriptions}</available_skills>',
                form_data['messages'],
                append=True,
            )

    # Strip <$skillId|label> mention tags so the model doesn't see raw markup.
    strip_skill_mentions(form_data.get('messages', []))

    prompt = get_last_user_message(form_data['messages'])
    # TODO: re-enable URL extraction from prompt
    # urls = []
    # if prompt and len(prompt or "") < 500 and (not files or len(files) == 0):
    #     urls = extract_urls(prompt)

    if files:
        if not files:
            files = []

        for file_item in files:
            if file_item.get('type', 'file') == 'folder':
                # Get folder files
                folder_id = file_item.get('id', None)
                if folder_id:
                    folder = await Folders.get_folder_by_id_and_user_id(folder_id, user.id)
                    if folder and folder.data and 'files' in folder.data:
                        files = [f for f in files if f.get('id', None) != folder_id]
                        files = [*files, *folder.data['files']]

        # files = [*files, *[{"type": "url", "url": url, "name": url} for url in urls]]
        # Remove duplicate files based on their content
        files = list({json.dumps(f, sort_keys=True): f for f in files}.values())

    metadata = {
        **metadata,
        'model_id': form_data.get('model'),
        'tool_ids': tool_ids,
        'terminal_id': terminal_id,
        'files': files,
    }
    form_data['metadata'] = metadata

    if files:
        current_user_files = (metadata.get('user_message') or {}).get('files')
        current_file_ids = None
        if current_user_files is not None:
            current_file_ids = {
                file_id
                for file_id in (
                    _extract_file_id(file)
                    for file in current_user_files
                    if isinstance(file, dict) and file.get('type') == 'file'
                )
                if file_id
            }
        form_data['messages'] = await add_direct_file_context(
            form_data.get('messages', []),
            files,
            request,
            current_file_ids,
        )
        metadata['direct_files'] = files
        metadata['files'] = []
        form_data['metadata'] = metadata
        request.state.metadata = metadata

    # When the caller provides an explicit OpenAI-style `tools` array in the
    # request body, skip all server-side tool resolution and pass the caller's
    # tools through to the model unchanged.
    if not payload_tools and not hermes_session_delta:
        # Server side tools
        tool_ids = metadata.get('tool_ids', None)
        # Client side tools
        direct_tool_servers = metadata.get('tool_servers', None)

        log.debug(f'{tool_ids=}')
        log.debug(f'{direct_tool_servers=}')

        tools_dict = {}

        mcp_clients = {}
        mcp_tools_dict = {}

        if tool_ids:
            for tool_id in tool_ids:
                if tool_id.startswith('server:mcp:'):
                    try:
                        server_id = tool_id[len('server:mcp:') :]

                        mcp_server_connection = None
                        for server_connection in request.app.state.config.TOOL_SERVER_CONNECTIONS:
                            if (
                                server_connection.get('type', '') == 'mcp'
                                and server_connection.get('info', {}).get('id') == server_id
                            ):
                                mcp_server_connection = server_connection
                                break

                        if not mcp_server_connection:
                            log.error(f'MCP server with id {server_id} not found')
                            continue

                        # Check access control for MCP server
                        if not await has_connection_access(user, mcp_server_connection):
                            log.warning(f'Access denied to MCP server {server_id} for user {user.id}')
                            continue

                        auth_type = mcp_server_connection.get('auth_type', '')
                        headers = {}
                        if auth_type == 'bearer':
                            headers['Authorization'] = f'Bearer {mcp_server_connection.get("key", "")}'
                        elif auth_type == 'none':
                            # No authentication
                            pass
                        elif auth_type == 'session':
                            headers['Authorization'] = f'Bearer {request.state.token.credentials}'
                        elif auth_type == 'system_oauth':
                            oauth_token = extra_params.get('__oauth_token__', None)
                            if oauth_token:
                                headers['Authorization'] = f'Bearer {oauth_token.get("access_token", "")}'
                        elif auth_type in ('oauth_2.1', 'oauth_2.1_static'):
                            try:
                                splits = server_id.split(':')
                                server_id = splits[-1] if len(splits) > 1 else server_id

                                oauth_token = await request.app.state.oauth_client_manager.get_oauth_token(
                                    user.id, f'mcp:{server_id}'
                                )

                                if oauth_token:
                                    headers['Authorization'] = f'Bearer {oauth_token.get("access_token", "")}'
                            except Exception as e:
                                log.error(f'Error getting OAuth token: {e}')
                                oauth_token = None

                        connection_headers = mcp_server_connection.get('headers', None)
                        if connection_headers and isinstance(connection_headers, dict):
                            for key, value in connection_headers.items():
                                headers[key] = value

                        # Add user info headers if enabled
                        if ENABLE_FORWARD_USER_INFO_HEADERS and user:
                            headers = include_user_info_headers(headers, user)
                            if metadata and metadata.get('chat_id'):
                                headers[FORWARD_SESSION_INFO_HEADER_CHAT_ID] = metadata.get('chat_id')
                            if metadata and metadata.get('message_id'):
                                headers[FORWARD_SESSION_INFO_HEADER_MESSAGE_ID] = metadata.get('message_id')
                        apply_hermes_session_header(headers, metadata)

                        mcp_clients[server_id] = MCPClient()
                        await mcp_clients[server_id].connect(
                            url=mcp_server_connection.get('url', ''),
                            headers=headers if headers else None,
                        )

                        function_name_filter_list = mcp_server_connection.get('config', {}).get(
                            'function_name_filter_list', ''
                        )

                        if isinstance(function_name_filter_list, str):
                            function_name_filter_list = function_name_filter_list.split(',')

                        tool_specs = await mcp_clients[server_id].list_tool_specs()
                        for tool_spec in tool_specs:

                            async def make_tool_function(client, function_name):
                                async def tool_function(**kwargs):
                                    return await client.call_tool(
                                        function_name,
                                        function_args=kwargs,
                                    )

                                return tool_function

                            if function_name_filter_list:
                                if not is_string_allowed(tool_spec['name'], function_name_filter_list):
                                    # Skip this function
                                    continue

                            tool_function = await make_tool_function(mcp_clients[server_id], tool_spec['name'])

                            mcp_tools_dict[f'{server_id}_{tool_spec["name"]}'] = {
                                'spec': {
                                    **tool_spec,
                                    'name': f'{server_id}_{tool_spec["name"]}',
                                },
                                'callable': tool_function,
                                'type': 'mcp',
                                'client': mcp_clients[server_id],
                                'direct': False,
                            }
                    except Exception as e:
                        log.debug(e)
                        if event_emitter:
                            await event_emitter(
                                {
                                    'type': 'chat:message:error',
                                    'data': {'error': {'content': f"Failed to connect to MCP server '{server_id}'"}},
                                }
                            )
                        continue

            tools_dict = await get_tools(
                request,
                tool_ids,
                user,
                {
                    **extra_params,
                    '__model__': models[task_model_id],
                    '__messages__': form_data['messages'],
                    '__files__': metadata.get('files', []),
                },
            )

            if mcp_tools_dict:
                tools_dict = {**tools_dict, **mcp_tools_dict}

        # Resolve terminal tools if terminal_id is set (outside tool_ids check
        # so system terminals work even when no other tools are selected)
        terminal_capability = (model.get('info', {}).get('meta', {}).get('capabilities') or {}).get('terminal', True)
        if terminal_id and terminal_capability:
            try:
                terminal_result = await get_terminal_tools(
                    request,
                    terminal_id,
                    user,
                    extra_params,
                )
                if isinstance(terminal_result, tuple):
                    terminal_tools, system_prompt = terminal_result
                else:
                    terminal_tools = terminal_result
                    system_prompt = None
                if terminal_tools:
                    tools_dict = {**tools_dict, **terminal_tools}
                if system_prompt:
                    form_data['messages'] = add_or_update_system_message(
                        system_prompt,
                        form_data['messages'],
                        append=True,
                    )
            except Exception as e:
                log.exception(e)

        if direct_tool_servers:
            for tool_server in direct_tool_servers:
                system_prompt = tool_server.pop('system_prompt', None)
                if system_prompt:
                    form_data['messages'] = add_or_update_system_message(
                        system_prompt,
                        form_data['messages'],
                        append=True,
                    )

                tool_specs = tool_server.pop('specs', [])

                for tool in tool_specs:
                    tools_dict[tool['name']] = {
                        'spec': tool,
                        'direct': True,
                        'server': tool_server,
                    }

        if mcp_clients:
            metadata['mcp_clients'] = mcp_clients

        # Inject builtin tools for native function calling based on enabled features and model capability
        # Check if builtin_tools capability is enabled for this model (defaults to True if not specified)
        builtin_tools_enabled = (model.get('info', {}).get('meta', {}).get('capabilities') or {}).get(
            'builtin_tools', True
        )
        if metadata.get('params', {}).get('function_calling') == 'native' and builtin_tools_enabled:
            # Add file context to user messages
            chat_id = metadata.get('chat_id')
            form_data['messages'] = await add_file_context(form_data.get('messages', []), chat_id, user)
            builtin_tools = await get_builtin_tools(
                request,
                {
                    **extra_params,
                    '__event_emitter__': event_emitter,
                    '__skill_ids__': [s.id for s in available_skills if s.id not in user_skill_ids],
                },
                features,
                model,
            )
            for name, tool_dict in builtin_tools.items():
                if name not in tools_dict:
                    tools_dict[name] = tool_dict

        if tools_dict:
            # Always store resolved tools in metadata so downstream consumers
            # (e.g. pipe functions) can access all tools including MCP and builtins.
            metadata['tools'] = tools_dict

            if metadata.get('params', {}).get('function_calling') == 'native':
                # If the function calling is native, then call the tools function calling handler
                form_data['tools'] = [
                    {'type': 'function', 'function': tool.get('spec', {})} for tool in tools_dict.values()
                ]
            else:
                # If the function calling is not native, then call the tools function calling handler
                try:
                    form_data, flags = await chat_completion_tools_handler(
                        request, form_data, extra_params, user, models, tools_dict
                    )
                    sources.extend(flags.get('sources', []))
                except Exception as e:
                    log.exception(e)

    # Check if file context extraction is enabled for this model (default True)
    file_context_enabled = (model.get('info', {}).get('meta', {}).get('capabilities') or {}).get('file_context', True)

    if file_context_enabled and not hermes_session_delta:
        try:
            form_data, flags = await chat_completion_files_handler(request, form_data, extra_params, user)
            sources.extend(flags.get('sources', []))
        except Exception as e:
            log.exception(e)

    # Save the pre-RAG message state so the native tool call loop can
    # restore to the true original (before file-source injection) rather
    # than a snapshot that already has the RAG template baked in.
    system_message = None if hermes_session_delta else get_system_message(form_data['messages'])
    metadata['system_prompt'] = None if hermes_session_delta else get_content_from_message(system_message) if system_message else None
    metadata['user_prompt'] = get_last_user_message(form_data['messages'])
    metadata['sources'] = sources[:] if sources else []

    # If context is not empty, insert it into the messages
    if sources and prompt and not hermes_session_delta:
        form_data['messages'] = apply_source_context_to_messages(request, form_data['messages'], sources, prompt)

    # If there are citations, add them to the data_items
    sources = [
        source
        for source in sources
        if source.get('source', {}).get('name', '') or source.get('source', {}).get('id', '')
    ]

    if len(sources) > 0:
        events.append({'sources': sources})

    if model_knowledge:
        await event_emitter(
            {
                'type': 'status',
                'data': {
                    'action': 'knowledge_search',
                    'query': user_message,
                    'done': True,
                    'hidden': True,
                },
            }
        )

    # Strip empty text content blocks from multimodal messages
    # to prevent errors from providers like Gemini and Claude
    form_data['messages'] = strip_empty_content_blocks(form_data.get('messages', []))

    # Merge any duplicate system messages into a single message at position 0
    # to prevent template parsing errors with strict chat templates (e.g. Qwen)
    if not hermes_session_delta:
        form_data['messages'] = merge_system_messages(form_data.get('messages', []))

    return form_data, metadata, events


async def get_event_emitter_and_caller(metadata):
    event_emitter = None
    event_caller = None

    # event_emitter only needs user_id + chat_id + message_id.
    # It broadcasts to user:{user_id} room AND persists to DB,
    # so it works for backend-initiated calls (automations, API).
    if metadata.get('chat_id') and metadata.get('message_id'):
        event_emitter = await get_event_emitter(metadata)

    # event_caller needs session_id — it calls back to a specific
    # websocket session used by direct tools.
    if metadata.get('session_id') and metadata.get('chat_id') and metadata.get('message_id'):
        event_caller = await get_event_call(metadata)

    return event_emitter, event_caller


async def build_chat_response_context(request, form_data, user, model, metadata, tasks, events):
    event_emitter, event_caller = await get_event_emitter_and_caller(metadata)
    return {
        'request': request,
        'form_data': form_data,
        'user': user,
        'model': model,
        'metadata': metadata,
        'tasks': tasks,
        'events': events,
        'event_emitter': event_emitter,
        'event_caller': event_caller,
    }


def get_response_data(response):
    if isinstance(response, list) and len(response) == 1:
        # If the response is a single-item list, unwrap it #17213
        response = response[0]

    if isinstance(response, JSONResponse):
        if isinstance(response.body, bytes):
            try:
                response_data = json.loads(response.body.decode('utf-8', 'replace'))
            except json.JSONDecodeError:
                response_data = {'error': {'detail': 'Invalid JSON response'}}
        else:
            response_data = response
    elif isinstance(response, dict):
        response_data = response
    else:
        response_data = None

    return response, response_data


def merge_events_into_response(response_data, events):
    if events and isinstance(events, list):
        extra_response = {}
        for event in events:
            if isinstance(event, dict):
                extra_response.update(event)
            else:
                extra_response[event] = True

        return {
            **extra_response,
            **response_data,
        }
    return response_data


def build_response_object(response, response_data):
    if isinstance(response, dict):
        return response_data
    if isinstance(response, JSONResponse):
        return JSONResponse(
            content=response_data,
            headers=response.headers,
            status_code=response.status_code,
        )
    return response


async def get_system_oauth_token(request, user):
    """Get the system OAuth token for a user.

    Primary path: use the oauth_session_id cookie (browser requests).
    Fallback: look up the user's most recent OAuth session from the DB
    (covers automations, API calls, and other cookie-less contexts).
    """
    oauth_token = None
    try:
        oauth_session_id = request.cookies.get('oauth_session_id', None)
        if oauth_session_id:
            oauth_token = await request.app.state.oauth_manager.get_oauth_token(
                user.id,
                oauth_session_id,
            )

        # Fallback: no cookie (automation, API key, etc.) — use most recent session
        if oauth_token is None:
            from open_webui.models.oauth_sessions import OAuthSessions

            sessions = await OAuthSessions.get_sessions_by_user_id(user.id)
            if sessions:
                best = max(sessions, key=lambda s: s.updated_at)
                oauth_token = await request.app.state.oauth_manager.get_oauth_token(
                    user.id,
                    best.id,
                )
    except Exception as e:
        log.error(f'Error getting OAuth token: {e}')
    return oauth_token


async def background_tasks_handler(ctx):
    request = ctx['request']
    form_data = ctx['form_data']
    user = ctx['user']
    metadata = ctx['metadata']
    tasks = ctx['tasks']
    event_emitter = ctx['event_emitter']

    if metadata.get('hermes_session_delta'):
        return

    message = None
    messages = []

    if 'chat_id' in metadata and not metadata['chat_id'].startswith('local:'):
        messages_map = await Chats.get_messages_map_by_chat_id(metadata['chat_id'])
        message = messages_map.get(metadata['message_id']) if messages_map else None

        message_list = get_message_list(messages_map, metadata['message_id'])

        # Remove details tags and files from the messages.
        # as get_message_list creates a new list, it does not affect
        # the original messages outside of this handler

        messages = []
        for message in message_list:
            content = message.get('content', '')
            if isinstance(content, list):
                for item in content:
                    if item.get('type') == 'text':
                        content = item['text']
                        break

            if isinstance(content, str):
                content = re.sub(
                    r'<details\b[^>]*>.*?<\/details>|!\[.*?\]\(.*?\)',
                    '',
                    content,
                    flags=re.S | re.I,
                ).strip()

            messages.append(
                {
                    **message,
                    'role': message.get('role', 'assistant'),  # Safe fallback for missing role
                    'content': content,
                }
            )
    else:
        # Local temp chat, get the model and message from the form_data
        message = get_last_user_message_item(form_data.get('messages', []))
        messages = form_data.get('messages', [])
        if message:
            message['model'] = form_data.get('model')

    if message and 'model' in message:
        if tasks and messages:
            if TASKS.FOLLOW_UP_GENERATION in tasks and tasks[TASKS.FOLLOW_UP_GENERATION]:
                res = await generate_follow_ups(
                    request,
                    {
                        'model': message['model'],
                        'messages': messages,
                        'message_id': metadata['message_id'],
                        'chat_id': metadata['chat_id'],
                    },
                    user,
                )

                if res and isinstance(res, dict):
                    if len(res.get('choices', [])) == 1:
                        response_message = res.get('choices', [])[0].get('message', {})

                        follow_ups_string = response_message.get('content') or response_message.get(
                            'reasoning_content', ''
                        )
                    else:
                        follow_ups_string = ''

                    follow_ups_string = follow_ups_string[
                        follow_ups_string.find('{') : follow_ups_string.rfind('}') + 1
                    ]

                    try:
                        follow_ups = json.loads(follow_ups_string).get('follow_ups', [])
                        await event_emitter(
                            {
                                'type': 'chat:message:follow_ups',
                                'data': {
                                    'follow_ups': follow_ups,
                                },
                            }
                        )

                        if not metadata.get('chat_id', '').startswith('local:'):
                            await Chats.upsert_message_to_chat_by_id_and_message_id(
                                metadata['chat_id'],
                                metadata['message_id'],
                                {
                                    'followUps': follow_ups,
                                },
                            )

                    except Exception as e:
                        pass

            if not metadata.get('chat_id', '').startswith('local:'):  # Only update titles and tags for non-temp chats
                if TASKS.TITLE_GENERATION in tasks:
                    user_message = get_last_user_message(messages)
                    if user_message and len(user_message) > 100:
                        user_message = user_message[:100] + '...'

                    title = None
                    if tasks[TASKS.TITLE_GENERATION]:
                        res = await generate_title(
                            request,
                            {
                                'model': message['model'],
                                'messages': messages,
                                'chat_id': metadata['chat_id'],
                            },
                            user,
                        )

                        if res and isinstance(res, dict):
                            if len(res.get('choices', [])) == 1:
                                response_message = res.get('choices', [])[0].get('message', {})

                                title_string = (
                                    response_message.get('content')
                                    or response_message.get(
                                        'reasoning_content',
                                    )
                                    or message.get('content', user_message)
                                )
                            else:
                                title_string = ''

                            title_string = title_string[title_string.find('{') : title_string.rfind('}') + 1]

                            try:
                                title = json.loads(title_string).get('title', user_message)
                            except Exception as e:
                                title = ''

                            if not title:
                                title = messages[0].get('content', user_message)

                            await Chats.update_chat_title_by_id(metadata['chat_id'], title)

                            await event_emitter(
                                {
                                    'type': 'chat:title',
                                    'data': title,
                                }
                            )

                    if title == None and len(messages) == 2 and (not messages_map or len(messages_map) <= 2):
                        title = messages[0].get('content', user_message)

                        await Chats.update_chat_title_by_id(metadata['chat_id'], title)

                        await event_emitter(
                            {
                                'type': 'chat:title',
                                'data': message.get('content', user_message),
                            }
                        )

                if TASKS.TAGS_GENERATION in tasks and tasks[TASKS.TAGS_GENERATION]:
                    res = await generate_chat_tags(
                        request,
                        {
                            'model': message['model'],
                            'messages': messages,
                            'chat_id': metadata['chat_id'],
                        },
                        user,
                    )

                    if res and isinstance(res, dict):
                        if len(res.get('choices', [])) == 1:
                            response_message = res.get('choices', [])[0].get('message', {})

                            tags_string = response_message.get('content') or response_message.get(
                                'reasoning_content', ''
                            )
                        else:
                            tags_string = ''

                        tags_string = tags_string[tags_string.find('{') : tags_string.rfind('}') + 1]

                        try:
                            tags = json.loads(tags_string).get('tags', [])
                            await Chats.update_chat_tags_by_id(metadata['chat_id'], tags, user)

                            await event_emitter(
                                {
                                    'type': 'chat:tags',
                                    'data': tags,
                                }
                            )
                        except Exception as e:
                            pass


async def outlet_filter_handler(ctx):
    """Run outlet filters inline after chat completion.

    Replaces the separate POST /api/chat/completed round-trip.
    Persists outlet-modified content to DB and emits a chat:outlet event
    so the frontend can sync its in-memory state.

    For temp chats (local: prefix), messages are built from form_data
    plus the assistant response message stored in ctx['assistant_message'],
    since temp chats have no DB-persisted history.
    """
    request = ctx['request']
    user = ctx['user']
    model = ctx['model']
    metadata = ctx['metadata']
    event_emitter = ctx.get('event_emitter')
    event_caller = ctx.get('event_caller')

    chat_id = metadata.get('chat_id', '')
    message_id = metadata.get('message_id')

    if not chat_id or not message_id:
        return

    is_temp_chat = chat_id.startswith('local:')

    try:
        messages_map = None

        if is_temp_chat:
            # Temp chats have no DB record — build message list from
            # the in-memory form_data plus the assistant response.
            form_messages = ctx.get('form_data', {}).get('messages', [])
            assistant_message = ctx.get('assistant_message', {})

            message_list = [
                {
                    'role': m.get('role'),
                    'content': m.get('content', ''),
                }
                for m in form_messages
            ]

            # Append the full assistant message (content, output, usage, etc.)
            if assistant_message:
                message_list.append(
                    {
                        'id': message_id,
                        'role': 'assistant',
                        **assistant_message,
                    }
                )
        else:
            messages_map = await Chats.get_messages_map_by_chat_id(chat_id)
            if not messages_map:
                return

            message_list = get_message_list(messages_map, message_id)
            if not message_list:
                return

        model_id = model.get('id') if isinstance(model, dict) else model

        outlet_data = {
            'model': model_id,
            'messages': [
                {
                    'id': m.get('id'),
                    'role': m.get('role'),
                    'content': m.get('content', ''),
                    'info': m.get('info'),
                    'timestamp': m.get('timestamp'),
                    **({'output': m['output']} if m.get('output') else {}),
                    **({'usage': m['usage']} if m.get('usage') else {}),
                    **({'sources': m['sources']} if m.get('sources') else {}),
                }
                for m in message_list
            ],
            'filter_ids': metadata.get('filter_ids', []),
            'chat_id': chat_id,
            'session_id': metadata.get('session_id'),
            'id': message_id,
        }

        # Pipeline outlet filters
        models = request.app.state.MODELS
        try:
            outlet_data = await process_pipeline_outlet_filter(request, outlet_data, user, models)
        except Exception as e:
            log.debug(f'Pipeline outlet filter error: {e}')

        # Function outlet filters
        extra_params = {
            '__event_emitter__': event_emitter,
            '__event_call__': event_caller,
            '__user__': user.model_dump() if isinstance(user, UserModel) else {},
            '__metadata__': metadata,
            '__request__': request,
            '__model__': model,
        }

        filter_ids = await get_sorted_filter_ids(request, model, metadata.get('filter_ids', []))
        filter_functions = await Functions.get_functions_by_ids(filter_ids)

        outlet_result, _ = await process_filter_functions(
            request=request,
            filter_functions=filter_functions,
            filter_type='outlet',
            form_data=outlet_data,
            extra_params=extra_params,
        )

        # Persist outlet-modified content and notify frontend
        # (skip DB persistence for temp chats — they have no DB record)
        if outlet_result and outlet_result.get('messages'):
            if not is_temp_chat and messages_map:
                for message in outlet_result['messages']:
                    outlet_message_id = message.get('id')
                    if outlet_message_id and outlet_message_id in messages_map:
                        original_message = messages_map[outlet_message_id]
                        if original_message.get('content') != message.get('content'):
                            await Chats.upsert_message_to_chat_by_id_and_message_id(
                                chat_id,
                                outlet_message_id,
                                {
                                    'content': message['content'],
                                    'originalContent': original_message.get('content'),
                                },
                            )

            if event_emitter:
                await event_emitter(
                    {
                        'type': 'chat:outlet',
                        'data': {'messages': outlet_result['messages']},
                    }
                )
    except Exception as e:
        log.debug(f'Error running outlet filters: {e}')


async def non_streaming_chat_response_handler(response, ctx):
    request = ctx['request']

    user = ctx['user']
    metadata = ctx['metadata']
    events = ctx['events']

    event_emitter = ctx['event_emitter']

    response, response_data = get_response_data(response)
    if response_data is None:
        return response

    if event_emitter:
        try:
            if 'error' in response_data:
                error = response_data.get('error')

                if isinstance(error, dict):
                    error = error.get('detail', error)
                else:
                    error = str(error)

                log.error('Provider returned error (non-streaming): %s', error)

                await Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata['chat_id'],
                    metadata['message_id'],
                    {
                        'error': {'content': error},
                    },
                )
                if isinstance(error, str) or isinstance(error, dict):
                    await event_emitter(
                        {
                            'type': 'chat:message:error',
                            'data': {'error': {'content': error}},
                        }
                    )

            if 'selected_model_id' in response_data:
                await Chats.upsert_message_to_chat_by_id_and_message_id(
                    metadata['chat_id'],
                    metadata['message_id'],
                    {
                        'selectedModelId': response_data['selected_model_id'],
                    },
                )

            choices = response_data.get('choices', [])
            if choices and choices[0].get('message', {}).get('content'):
                content = response_data['choices'][0]['message']['content']

                if content:
                    await event_emitter(
                        {
                            'type': 'chat:completion',
                            'data': response_data,
                        }
                    )

                    title = await Chats.get_chat_title_by_id(metadata['chat_id'])

                    # Use output from backend if provided (OR-compliant backends),
                    # otherwise generate from response content
                    response_output = response_data.get('output')
                    if not response_output:
                        response_output = [
                            {
                                'type': 'message',
                                'id': output_id('msg'),
                                'status': 'completed',
                                'role': 'assistant',
                                'content': [{'type': 'output_text', 'text': content}],
                            }
                        ]

                    await event_emitter(
                        {
                            'type': 'chat:completion',
                            'data': {
                                'done': True,
                                'content': content,
                                'output': response_output,
                                'title': title,
                            },
                        }
                    )

                    # Save message in the database
                    usage = normalize_usage(response_data.get('usage', {}) or {})

                    await Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata['chat_id'],
                        metadata['message_id'],
                        {
                            'done': True,
                            'role': 'assistant',
                            'content': content,
                            'output': response_output,
                            **({'usage': usage} if usage else {}),
                        },
                    )

                    # Send a webhook notification if the user is not active
                    if request.app.state.config.ENABLE_USER_WEBHOOKS and not await Users.is_user_active(user.id):
                        webhook_url = await Users.get_user_webhook_url_by_id(user.id)
                        if webhook_url:
                            await post_webhook(
                                request.app.state.WEBUI_NAME,
                                webhook_url,
                                f'{content}\n\n{title} - {request.app.state.config.WEBUI_URL}/c/{metadata["chat_id"]}',
                                {
                                    'action': 'chat',
                                    'message': content,
                                    'title': title,
                                    'url': f'{request.app.state.config.WEBUI_URL}/c/{metadata["chat_id"]}',
                                },
                            )

                    await background_tasks_handler(ctx)
                    ctx['assistant_message'] = {
                        'content': content,
                        'output': response_output,
                        **({'usage': usage} if usage else {}),
                    }
                    await outlet_filter_handler(ctx)

            response = build_response_object(response, merge_events_into_response(response_data, events))
        except Exception as e:
            log.debug(f'Error occurred while processing request: {e}')
            pass

        return response

    if isinstance(response, dict):
        response = merge_events_into_response(response_data, events)

    return response


async def streaming_chat_response_handler(response, ctx):
    request = ctx['request']

    form_data = ctx['form_data']

    user = ctx['user']
    model = ctx['model']

    metadata = ctx['metadata']
    events = ctx['events']

    event_emitter = ctx['event_emitter']
    event_caller = ctx['event_caller']

    extra_params = {
        '__event_emitter__': event_emitter,
        '__event_call__': event_caller,
        '__user__': user.model_dump() if isinstance(user, UserModel) else {},
        '__metadata__': metadata,
        '__oauth_token__': await get_system_oauth_token(request, user),
        '__request__': request,
        '__model__': model,
    }

    filter_functions = [
        await Functions.get_function_by_id(filter_id)
        for filter_id in await get_sorted_filter_ids(request, model, metadata.get('filter_ids', []))
    ]

    # Standard streaming response handler
    # event_caller is optional — only needed for direct (client-side) tools
    # Server-side tools work without it.
    if event_emitter:
        task_id = str(uuid4())  # Create a unique task ID.
        model_id = form_data.get('model', '')

        # Handle as a background task
        async def response_handler(response, events):
            def tag_output_handler(content_type, tags, output):
                """
                Detect special tags (reasoning, solution, code_interpreter) in streaming
                content and create corresponding OR-aligned output items directly.
                Operates on output items instead of content_blocks.

                Uses the text from the output items themselves for tag detection,
                eliminating state divergence between accumulated content and items.
                """
                end_flag = False

                def extract_attributes(tag_content):
                    """Extract attributes from a tag if they exist."""
                    attributes = {}
                    if not tag_content:
                        return attributes
                    matches = re.findall(r'(\w+)\s*=\s*"([^"]+)"', tag_content)
                    for key, value in matches:
                        attributes[key] = value
                    return attributes

                def get_last_text(out):
                    """Get text from last message item, or empty string."""
                    if out and out[-1].get('type') == 'message':
                        parts = out[-1].get('content', [])
                        if parts and parts[-1].get('type') == 'output_text':
                            return parts[-1].get('text', '')
                    return ''

                def set_last_text(out, text):
                    """Set text on last message item's output_text."""
                    if out and out[-1].get('type') == 'message':
                        parts = out[-1].get('content', [])
                        if parts and parts[-1].get('type') == 'output_text':
                            parts[-1]['text'] = text

                # Map content_type to output item type
                output_type_map = {
                    'reasoning': 'reasoning',
                    'solution': 'message',  # solution tags just produce text
                    'code_interpreter': 'open_webui:code_interpreter',
                }
                output_item_type = output_type_map.get(content_type, content_type)

                last_type = output[-1].get('type', '') if output else ''

                if last_type == 'message':
                    # Use the output item's own text for tag detection
                    item_text = get_last_text(output)
                    for start_tag, end_tag in tags:
                        start_tag_pattern = rf'{re.escape(start_tag)}'
                        if start_tag.startswith('<') and start_tag.endswith('>'):
                            start_tag_pattern = rf'<{re.escape(start_tag[1:-1])}(\s.*?)?>'

                        match = re.search(start_tag_pattern, item_text)
                        if match:
                            try:
                                attr_content = match.group(1) if match.group(1) else ''
                            except Exception:
                                attr_content = ''

                            attributes = extract_attributes(attr_content)

                            before_tag = item_text[: match.start()]
                            after_tag = item_text[match.end() :]

                            # Keep only text before the tag in the message
                            set_last_text(output, before_tag)

                            if not before_tag.strip():
                                # Remove empty message item
                                if output and output[-1].get('type') == 'message':
                                    output.pop()

                            # Append the new output item
                            if output_item_type == 'reasoning':
                                output.append(
                                    {
                                        'type': 'reasoning',
                                        'id': output_id('r'),
                                        'status': 'in_progress',
                                        'start_tag': start_tag,
                                        'end_tag': end_tag,
                                        'attributes': attributes,
                                        'content': [],
                                        'summary': None,
                                        'started_at': time.time(),
                                    }
                                )
                            elif output_item_type == 'open_webui:code_interpreter':
                                output.append(
                                    {
                                        'type': 'open_webui:code_interpreter',
                                        'id': output_id('ci'),
                                        'status': 'in_progress',
                                        'start_tag': start_tag,
                                        'end_tag': end_tag,
                                        'attributes': attributes,
                                        'lang': attributes.get('lang', 'python'),
                                        'code': '',
                                        'output': None,
                                        'started_at': time.time(),
                                    }
                                )
                            else:
                                # solution or other text-producing tag
                                output.append(
                                    {
                                        'type': 'message',
                                        'id': output_id('msg'),
                                        'status': 'in_progress',
                                        'role': 'assistant',
                                        'content': [{'type': 'output_text', 'text': ''}],
                                        '_tag_type': content_type,
                                        'start_tag': start_tag,
                                        'end_tag': end_tag,
                                        'attributes': attributes,
                                        'started_at': time.time(),
                                    }
                                )

                            if after_tag:
                                # Set the after_tag content on the new item
                                if output_item_type == 'reasoning':
                                    output[-1]['content'] = [{'type': 'output_text', 'text': after_tag}]
                                elif output_item_type == 'open_webui:code_interpreter':
                                    output[-1]['code'] = after_tag
                                else:
                                    set_last_text(output, after_tag)

                                _, recursive_end = tag_output_handler(content_type, tags, output)
                                if recursive_end:
                                    end_flag = True

                            break

                elif (
                    (last_type == 'reasoning' and content_type == 'reasoning')
                    or (last_type == 'open_webui:code_interpreter' and content_type == 'code_interpreter')
                    or (last_type == 'message' and output[-1].get('_tag_type') == content_type)
                ):
                    item = output[-1]
                    start_tag = item.get('start_tag', '')
                    end_tag = item.get('end_tag', '')

                    end_tag_pattern = rf'{re.escape(end_tag)}'

                    # Get the block content from the item itself
                    if last_type == 'reasoning':
                        parts = item.get('content', [])
                        block_content = ''
                        if parts and parts[-1].get('type') == 'output_text':
                            block_content = parts[-1].get('text', '')
                    elif last_type == 'open_webui:code_interpreter':
                        block_content = item.get('code', '')
                    else:
                        block_content = get_last_text(output)

                    if re.search(end_tag_pattern, block_content):
                        end_flag = True

                        # Strip start and end tags from content
                        start_tag_pattern = rf'{re.escape(start_tag)}'
                        if start_tag.startswith('<') and start_tag.endswith('>'):
                            start_tag_pattern = rf'<{re.escape(start_tag[1:-1])}(\s.*?)?>'
                        block_content = re.sub(start_tag_pattern, '', block_content).strip()

                        end_tag_regex = re.compile(end_tag_pattern, re.DOTALL)
                        split_content = end_tag_regex.split(block_content, maxsplit=1)

                        block_content = split_content[0].strip() if split_content else ''
                        leftover_content = split_content[1].strip() if len(split_content) > 1 else ''

                        if block_content:
                            # Update the item with final content
                            if last_type == 'reasoning':
                                item['content'] = [{'type': 'output_text', 'text': block_content}]
                                item['ended_at'] = time.time()
                                item['duration'] = int(item['ended_at'] - item['started_at'])
                                item['status'] = 'completed'
                            elif last_type == 'open_webui:code_interpreter':
                                item['code'] = block_content
                                item['ended_at'] = time.time()
                                item['duration'] = int(item['ended_at'] - item['started_at'])
                            else:
                                set_last_text(output, block_content)
                                item['ended_at'] = time.time()

                            # Reset by appending a new message item for leftover
                            output.append(
                                {
                                    'type': 'message',
                                    'id': output_id('msg'),
                                    'status': 'in_progress',
                                    'role': 'assistant',
                                    'content': [
                                        {
                                            'type': 'output_text',
                                            'text': leftover_content,
                                        }
                                    ],
                                }
                            )
                        else:
                            # Remove the block if content is empty
                            output.pop()
                            output.append(
                                {
                                    'type': 'message',
                                    'id': output_id('msg'),
                                    'status': 'in_progress',
                                    'role': 'assistant',
                                    'content': [
                                        {
                                            'type': 'output_text',
                                            'text': leftover_content,
                                        }
                                    ],
                                }
                            )

                return output, end_flag

            message = await Chats.get_message_by_id_and_message_id(metadata['chat_id'], metadata['message_id'])

            tool_calls = []

            last_assistant_message = None
            try:
                if form_data['messages'][-1]['role'] == 'assistant':
                    last_assistant_message = get_last_assistant_message(form_data['messages'])
            except Exception as e:
                pass

            content = (
                message.get('content', '') if message else last_assistant_message if last_assistant_message else ''
            )

            # Initialize output: use existing from message if continuing, else create new
            existing_output = message.get('output') if message else None
            if existing_output:
                output = existing_output
            else:
                # Only create an initial message item if there is content to initialize with
                if content:
                    output = [
                        {
                            'type': 'message',
                            'id': output_id('msg'),
                            'status': 'in_progress',
                            'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': content}],
                        }
                    ]
                else:
                    output = []

            usage = None
            prior_output = []
            last_response_id = None

            def full_output():
                return prior_output + output if prior_output else output

            reasoning_tags_param = metadata.get('params', {}).get('reasoning_tags')
            DETECT_REASONING_TAGS = reasoning_tags_param is not False
            DETECT_CODE_INTERPRETER = metadata.get('features', {}).get('code_interpreter', False)

            reasoning_tags = []
            if DETECT_REASONING_TAGS:
                if isinstance(reasoning_tags_param, list) and len(reasoning_tags_param) == 2:
                    reasoning_tags = [(reasoning_tags_param[0], reasoning_tags_param[1])]
                else:
                    reasoning_tags = DEFAULT_REASONING_TAGS

            try:
                for event in events:
                    await event_emitter(
                        {
                            'type': 'chat:completion',
                            'data': event,
                        }
                    )

                    # Save message in the database
                    await Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata['chat_id'],
                        metadata['message_id'],
                        {
                            **event,
                        },
                    )

                async def stream_body_handler(response, form_data):
                    nonlocal content
                    nonlocal usage
                    nonlocal output
                    nonlocal prior_output
                    nonlocal last_response_id

                    response_tool_calls = []

                    delta_count = 0
                    delta_chunk_size = max(
                        CHAT_RESPONSE_STREAM_DELTA_CHUNK_SIZE,
                        int(metadata.get('params', {}).get('stream_delta_chunk_size') or 1),
                    )
                    last_delta_data = None
                    sse_event_type = None

                    async def flush_pending_delta_data(threshold: int = 0):
                        nonlocal delta_count
                        nonlocal last_delta_data

                        if delta_count >= threshold and last_delta_data:
                            await event_emitter(
                                {
                                    'type': 'chat:completion',
                                    'data': last_delta_data,
                                }
                            )
                            delta_count = 0
                            last_delta_data = None

                    async for line in response.body_iterator:
                        line = line.decode('utf-8', 'replace') if isinstance(line, bytes) else line
                        data = line

                        if '\n' in data.strip() and not data.startswith('data:'):
                            data_line = None
                            for raw_line in data.splitlines():
                                if raw_line.startswith('event:'):
                                    sse_event_type = raw_line[len('event:') :].strip()
                                elif raw_line.startswith('data:'):
                                    data_line = raw_line
                                    break
                            if data_line is None:
                                continue
                            data = data_line

                        # Skip empty lines
                        if not data.strip():
                            continue

                        if data.startswith('event:'):
                            sse_event_type = data[len('event:') :].strip()
                            continue

                        # "data:" is the prefix for each event
                        if not data.startswith('data:'):
                            continue

                        # Remove the prefix
                        data = data[len('data:') :].strip()

                        try:
                            data = json.loads(data)
                            current_sse_event_type = sse_event_type
                            sse_event_type = None

                            data, _ = await process_filter_functions(
                                request=request,
                                filter_functions=filter_functions,
                                filter_type='stream',
                                form_data=data,
                                extra_params={'__body__': form_data, **extra_params},
                            )

                            if data:
                                if _is_hermes_tool_event(data, current_sse_event_type):
                                    await flush_pending_delta_data()
                                    output = _upsert_hermes_tool_event(output, data, current_sse_event_type)
                                    await event_emitter(
                                        {
                                            'type': 'chat:completion',
                                            'data': {
                                                'content': serialize_output(full_output()),
                                                'output': full_output(),
                                            },
                                        }
                                    )
                                    continue

                                if 'event' in data and not getattr(request.state, 'direct', False):
                                    await event_emitter(data.get('event', {}))

                                if 'selected_model_id' in data:
                                    model_id = data['selected_model_id']
                                    await Chats.upsert_message_to_chat_by_id_and_message_id(
                                        metadata['chat_id'],
                                        metadata['message_id'],
                                        {
                                            'selectedModelId': model_id,
                                        },
                                    )
                                    await event_emitter(
                                        {
                                            'type': 'chat:completion',
                                            'data': data,
                                        }
                                    )
                                # Check for Responses API events (type field starts with "response.")
                                elif data.get('type', '').startswith('response.'):
                                    output, response_metadata = handle_responses_streaming_event(data, output)

                                    # Emit citation sources from finalized output items
                                    # (mirrors Chat Completions annotation handling at delta level)
                                    if data.get('type') == 'response.output_item.done':
                                        item = data.get('item', {})
                                        if item.get('type') == 'message':
                                            for part in item.get('content', []):
                                                for annotation in part.get('annotations', []):
                                                    if annotation.get('type') == 'url_citation':
                                                        # Handle both flat (Responses API) and nested (Chat Completions) formats
                                                        url_citation = annotation.get('url_citation', annotation)

                                                        url = url_citation.get('url', '')
                                                        title = url_citation.get('title', url)

                                                        if url:
                                                            await event_emitter(
                                                                {
                                                                    'type': 'source',
                                                                    'data': {
                                                                        'source': {
                                                                            'name': title,
                                                                            'url': url,
                                                                        },
                                                                        'document': [title],
                                                                        'metadata': [
                                                                            {
                                                                                'source': url,
                                                                                'name': title,
                                                                            }
                                                                        ],
                                                                    },
                                                                }
                                                            )

                                    processed_data = {
                                        'output': full_output(),
                                        'content': serialize_output(full_output()),
                                    }

                                    # print(data)
                                    # print(processed_data)

                                    # Merge any metadata (usage, etc.)
                                    # Strip 'done' — response.completed emits
                                    # it but we may still need to execute tool
                                    # calls. The outer middleware manages the
                                    # actual completion signal.
                                    if response_metadata:
                                        if ENABLE_RESPONSES_API_STATEFUL:
                                            response_id = response_metadata.pop('response_id', None)
                                            if response_id:
                                                last_response_id = response_id
                                        processed_data.update(response_metadata)
                                        processed_data.pop('done', None)

                                    await event_emitter(
                                        {
                                            'type': 'chat:completion',
                                            'data': processed_data,
                                        }
                                    )
                                    continue
                                else:
                                    choices = data.get('choices', [])

                                    # Normalize usage data to standard format
                                    raw_usage = data.get('usage', {}) or {}
                                    raw_usage.update(data.get('timings', {}))  # llama.cpp
                                    if raw_usage:
                                        usage = normalize_usage(raw_usage)
                                        await event_emitter(
                                            {
                                                'type': 'chat:completion',
                                                'data': {
                                                    'usage': usage,
                                                },
                                            }
                                        )

                                    if not choices:
                                        error = data.get('error', {})
                                        if error:
                                            log.error('Provider returned error (streaming): %s', error)
                                            try:
                                                await Chats.upsert_message_to_chat_by_id_and_message_id(
                                                    metadata['chat_id'],
                                                    metadata['message_id'],
                                                    {
                                                        'error': {'content': error},
                                                    },
                                                )
                                            except Exception:
                                                pass
                                            await event_emitter(
                                                {
                                                    'type': 'chat:completion',
                                                    'data': {
                                                        'error': error,
                                                    },
                                                }
                                            )
                                        continue

                                    delta = choices[0].get('delta', {})

                                    # Handle delta annotations
                                    annotations = delta.get('annotations')
                                    if annotations:
                                        for annotation in annotations:
                                            if (
                                                annotation.get('type') == 'url_citation'
                                                and 'url_citation' in annotation
                                            ):
                                                url_citation = annotation['url_citation']

                                                url = url_citation.get('url', '')
                                                title = url_citation.get('title', url)

                                                await event_emitter(
                                                    {
                                                        'type': 'source',
                                                        'data': {
                                                            'source': {
                                                                'name': title,
                                                                'url': url,
                                                            },
                                                            'document': [title],
                                                            'metadata': [
                                                                {
                                                                    'source': url,
                                                                    'name': title,
                                                                }
                                                            ],
                                                        },
                                                    }
                                                )

                                    delta_tool_calls = delta.get('tool_calls', None)
                                    if delta_tool_calls:
                                        for delta_tool_call in delta_tool_calls:
                                            tool_call_index = delta_tool_call.get('index')

                                            if tool_call_index is not None:
                                                # Check if the tool call already exists
                                                current_response_tool_call = None
                                                for response_tool_call in response_tool_calls:
                                                    if response_tool_call.get('index') == tool_call_index:
                                                        current_response_tool_call = response_tool_call
                                                        break

                                                if current_response_tool_call is None:
                                                    # Add the new tool call
                                                    delta_tool_call.setdefault('function', {})
                                                    delta_tool_call['function'].setdefault('name', '')
                                                    delta_tool_call['function'].setdefault('arguments', '')
                                                    response_tool_calls.append(delta_tool_call)
                                                else:
                                                    # Update the existing tool call
                                                    delta_name = delta_tool_call.get('function', {}).get('name')
                                                    delta_arguments = delta_tool_call.get('function', {}).get(
                                                        'arguments'
                                                    )

                                                    if delta_name:
                                                        current_response_tool_call['function']['name'] = delta_name

                                                    if delta_arguments:
                                                        current_response_tool_call['function']['arguments'] += (
                                                            delta_arguments
                                                        )

                                        # Emit pending tool calls in real-time
                                        if response_tool_calls:
                                            # Flush any pending text first
                                            await flush_pending_delta_data()

                                            # Build pending function_call output items for display
                                            pending_fc_items = []
                                            hermes_display_call_ids = _hermes_display_call_ids(full_output())
                                            for tc in response_tool_calls:
                                                call_id = tc.get('id', '')
                                                if call_id and call_id in hermes_display_call_ids:
                                                    _merge_hermes_display_tool_call_arguments(output, tc)
                                                    continue
                                                func = tc.get('function', {})
                                                pending_fc_items.append(
                                                    {
                                                        'type': 'function_call',
                                                        'id': call_id or output_id('fc'),
                                                        'call_id': call_id,
                                                        'name': func.get('name', ''),
                                                        'arguments': func.get('arguments', '{}'),
                                                        'status': 'in_progress',
                                                    }
                                                )

                                            await event_emitter(
                                                {
                                                    'type': 'chat:completion',
                                                    'data': {
                                                        'content': serialize_output(full_output() + pending_fc_items),
                                                    },
                                                }
                                            )

                                    image_urls = await get_image_urls(delta.get('images', []), request, metadata, user)
                                    if image_urls:
                                        image_file_list = [{'type': 'image', 'url': url} for url in image_urls]
                                        message_files = await Chats.add_message_files_by_id_and_message_id(
                                            metadata['chat_id'],
                                            metadata['message_id'],
                                            image_file_list,
                                        )
                                        if message_files is None:
                                            message_files = image_file_list

                                        await event_emitter(
                                            {
                                                'type': 'files',
                                                'data': {'files': message_files},
                                            }
                                        )

                                    value = delta.get('content')

                                    reasoning_content = (
                                        delta.get('reasoning_content')
                                        or delta.get('reasoning')
                                        or delta.get('thinking')
                                    )
                                    if reasoning_content:
                                        if not output or output[-1].get('type') != 'reasoning':
                                            reasoning_item = {
                                                'type': 'reasoning',
                                                'id': output_id('r'),
                                                'status': 'in_progress',
                                                'start_tag': '<think>',
                                                'end_tag': '</think>',
                                                'attributes': {'type': 'reasoning_content'},
                                                'content': [],
                                                'summary': None,
                                                'started_at': time.time(),
                                            }
                                            output.append(reasoning_item)
                                        else:
                                            reasoning_item = output[-1]

                                        # Append to reasoning content
                                        parts = reasoning_item.get('content', [])
                                        if parts and parts[-1].get('type') == 'output_text':
                                            parts[-1]['text'] += reasoning_content
                                        else:
                                            reasoning_item['content'] = [
                                                {
                                                    'type': 'output_text',
                                                    'text': reasoning_content,
                                                }
                                            ]

                                        data = {'content': serialize_output(full_output())}

                                    if value:
                                        if (
                                            output
                                            and output[-1].get('type') == 'reasoning'
                                            and output[-1].get('attributes', {}).get('type') == 'reasoning_content'
                                        ):
                                            reasoning_item = output[-1]
                                            reasoning_item['ended_at'] = time.time()
                                            reasoning_item['duration'] = int(
                                                reasoning_item['ended_at'] - reasoning_item['started_at']
                                            )
                                            reasoning_item['status'] = 'completed'

                                            output.append(
                                                {
                                                    'type': 'message',
                                                    'id': output_id('msg'),
                                                    'status': 'in_progress',
                                                    'role': 'assistant',
                                                    'content': [
                                                        {
                                                            'type': 'output_text',
                                                            'text': '',
                                                        }
                                                    ],
                                                }
                                            )

                                        if ENABLE_CHAT_RESPONSE_BASE64_IMAGE_URL_CONVERSION:
                                            value = await convert_markdown_base64_images(
                                                request,
                                                value,
                                                {
                                                    'chat_id': metadata.get('chat_id', None),
                                                    'message_id': metadata.get('message_id', None),
                                                },
                                                user,
                                            )

                                        content = f'{content}{value}'

                                        # Check if we're inside a tag-based block
                                        # (reasoning, code_interpreter, or solution).
                                        # If so, append to the existing in-progress
                                        # item instead of creating a new message —
                                        # otherwise tag_output_handler re-detects the
                                        # start tag on every chunk and fragments the
                                        # output.
                                        last_item = output[-1] if output else None
                                        last_item_type = last_item.get('type', '') if last_item else ''
                                        inside_tag_block = (
                                            last_item is not None
                                            and last_item.get('status') == 'in_progress'
                                            and last_item.get('attributes', {}).get('type') != 'reasoning_content'
                                            and (
                                                last_item_type == 'reasoning'
                                                or last_item_type == 'open_webui:code_interpreter'
                                                or (
                                                    last_item_type == 'message'
                                                    and last_item.get('_tag_type') is not None
                                                )
                                            )
                                        )

                                        if inside_tag_block:
                                            # Append to the existing tag-based item
                                            if last_item_type == 'open_webui:code_interpreter':
                                                last_item['code'] = last_item.get('code', '') + value
                                            elif last_item_type == 'reasoning':
                                                parts = last_item.get('content', [])
                                                if parts and parts[-1].get('type') == 'output_text':
                                                    parts[-1]['text'] += value
                                                else:
                                                    last_item['content'] = [
                                                        {
                                                            'type': 'output_text',
                                                            'text': value,
                                                        }
                                                    ]
                                            else:
                                                # solution or other _tag_type message
                                                msg_parts = last_item.get('content', [])
                                                if msg_parts and msg_parts[-1].get('type') == 'output_text':
                                                    msg_parts[-1]['text'] += value
                                                else:
                                                    last_item['content'] = [
                                                        {
                                                            'type': 'output_text',
                                                            'text': value,
                                                        }
                                                    ]
                                        else:
                                            if not output or output[-1].get('type') != 'message':
                                                output.append(
                                                    {
                                                        'type': 'message',
                                                        'id': output_id('msg'),
                                                        'status': 'in_progress',
                                                        'role': 'assistant',
                                                        'content': [
                                                            {
                                                                'type': 'output_text',
                                                                'text': '',
                                                            }
                                                        ],
                                                    }
                                                )

                                            # Append value to last message item's text
                                            msg_parts = output[-1].get('content', [])
                                            if msg_parts and msg_parts[-1].get('type') == 'output_text':
                                                msg_parts[-1]['text'] += value
                                            else:
                                                output[-1]['content'] = [
                                                    {
                                                        'type': 'output_text',
                                                        'text': value,
                                                    }
                                                ]

                                        if DETECT_REASONING_TAGS:
                                            output, _ = tag_output_handler(
                                                'reasoning',
                                                reasoning_tags,
                                                output,
                                            )

                                            output, _ = tag_output_handler(
                                                'solution',
                                                DEFAULT_SOLUTION_TAGS,
                                                output,
                                            )

                                        if DETECT_CODE_INTERPRETER:
                                            output, end = tag_output_handler(
                                                'code_interpreter',
                                                DEFAULT_CODE_INTERPRETER_TAGS,
                                                output,
                                            )

                                            if end:
                                                break

                                        if ENABLE_REALTIME_CHAT_SAVE:
                                            # Save message in the database
                                            await Chats.upsert_message_to_chat_by_id_and_message_id(
                                                metadata['chat_id'],
                                                metadata['message_id'],
                                                {
                                                    'content': serialize_output(full_output()),
                                                    'output': full_output(),
                                                },
                                            )
                                        else:
                                            data = {
                                                'content': serialize_output(full_output()),
                                            }

                                if delta:
                                    delta_count += 1
                                    last_delta_data = data
                                    if delta_count >= delta_chunk_size:
                                        await flush_pending_delta_data(delta_chunk_size)
                                else:
                                    await event_emitter(
                                        {
                                            'type': 'chat:completion',
                                            'data': data,
                                        }
                                    )
                        except (asyncio.CancelledError, KeyboardInterrupt):
                            raise
                        except Exception as e:
                            done = 'data: [DONE]' in line
                            if done:
                                pass
                            else:
                                log.debug(f'Error: {e}')
                                continue
                    await flush_pending_delta_data()

                    if output:
                        # Clean up the last message item
                        if output[-1].get('type') == 'message':
                            parts = output[-1].get('content', [])
                            if parts and parts[-1].get('type') == 'output_text':
                                parts[-1]['text'] = parts[-1]['text'].strip()

                                if not parts[-1]['text']:
                                    output.pop()

                                    if not output:
                                        output.append(
                                            {
                                                'type': 'message',
                                                'id': output_id('msg'),
                                                'status': 'in_progress',
                                                'role': 'assistant',
                                                'content': [{'type': 'output_text', 'text': ''}],
                                            }
                                        )

                        if output[-1].get('type') == 'reasoning':
                            reasoning_item = output[-1]
                            if reasoning_item.get('ended_at') is None:
                                reasoning_item['ended_at'] = time.time()
                                reasoning_item['duration'] = int(
                                    reasoning_item['ended_at'] - reasoning_item['started_at']
                                )
                                reasoning_item['status'] = 'completed'

                    if response_tool_calls:
                        executable_tool_calls = _skip_hermes_display_tool_calls(
                            response_tool_calls,
                            full_output(),
                        )
                        if executable_tool_calls:
                            tool_calls.append(_split_tool_calls(executable_tool_calls))

                    # Responses API path: extract function_call items from output
                    if not response_tool_calls and output:
                        # Collect call_ids that already have results,
                        # including those from prior_output so we don't
                        # re-process tool calls from a previous turn.
                        handled_call_ids = {
                            item.get('call_id')
                            for item in (prior_output + output)
                            if item.get('type') == 'function_call_output'
                        }
                        responses_api_tool_calls = []
                        for item in output:
                            if (
                                item.get('type') == 'function_call'
                                and item.get('call_id') not in handled_call_ids
                                and not item.get('hermes_display_only')
                            ):
                                arguments = item.get('arguments', '{}')
                                responses_api_tool_calls.append(
                                    {
                                        'id': item.get('call_id', ''),
                                        'index': len(responses_api_tool_calls),
                                        'function': {
                                            'name': item.get('name', ''),
                                            'arguments': (
                                                arguments if isinstance(arguments, str) else json.dumps(arguments)
                                            ),
                                        },
                                    }
                                )
                        if responses_api_tool_calls:
                            tool_calls.append(_split_tool_calls(responses_api_tool_calls))

                try:
                    await stream_body_handler(response, form_data)
                finally:
                    if response.background:
                        await response.background()

                tool_call_retries = 0
                tool_call_sources = []  # Track citation sources from tool results
                all_tool_call_sources = []  # Accumulated sources across all iterations
                user_message = get_last_user_message(form_data['messages'])

                # Check if citations are enabled for this model
                citations_enabled = (model.get('info', {}).get('meta', {}).get('capabilities') or {}).get(
                    'citations', True
                )

                # Use the pre-RAG system content captured before the
                # initial file-source injection in process_chat_payload.
                # This ensures restore truly undoes the RAG template.
                original_system_content = metadata.get('system_prompt')
                if original_system_content is None:
                    original_system_message = get_system_message(form_data['messages'])
                    original_system_content = (
                        get_content_from_message(original_system_message) if original_system_message else None
                    )

                while len(tool_calls) > 0 and tool_call_retries < CHAT_RESPONSE_MAX_TOOL_CALL_RETRIES:
                    tool_call_retries += 1

                    response_tool_calls = tool_calls.pop(0)
                    response_tool_calls = _skip_hermes_display_tool_calls(response_tool_calls, output)
                    if not response_tool_calls:
                        continue

                    # Append function_call items for each tool call
                    # (Responses API already has them from streaming, so skip duplicates)
                    existing_call_ids = {item.get('call_id') for item in output if item.get('type') == 'function_call'}
                    for tc in response_tool_calls:
                        call_id = tc.get('id', '')
                        if call_id not in existing_call_ids:
                            func = tc.get('function', {})
                            output.append(
                                {
                                    'type': 'function_call',
                                    'id': call_id or output_id('fc'),
                                    'call_id': call_id,
                                    'name': func.get('name', ''),
                                    'arguments': func.get('arguments', '{}'),
                                    'status': 'in_progress',
                                }
                            )

                    await event_emitter(
                        {
                            'type': 'chat:completion',
                            'data': {
                                'content': serialize_output(full_output()),
                                'output': full_output(),
                            },
                        }
                    )

                    tools = metadata.get('tools', {})

                    results = []

                    for tool_call in response_tool_calls:
                        tool_call_id = tool_call.get('id', '')
                        tool_function_name = tool_call.get('function', {}).get('name', '')
                        tool_args = tool_call.get('function', {}).get('arguments', '{}')

                        tool_function_params = {}
                        if tool_args and tool_args.strip():
                            try:
                                # json.loads cannot be used because some models do not produce valid JSON
                                tool_function_params = ast.literal_eval(tool_args)
                            except Exception as e:
                                log.debug(e)
                                # Fallback to JSON parsing
                                try:
                                    tool_function_params = json.loads(tool_args)
                                except Exception as e:
                                    log.error(f'Error parsing tool call arguments: {tool_args}')
                                    results.append(
                                        {
                                            'tool_call_id': tool_call_id,
                                            'content': f'Error: Tool call arguments could not be parsed. The model generated malformed or incomplete JSON for `{tool_function_name}`. Please try again.',
                                        }
                                    )
                                    continue

                        # Ensure arguments are valid JSON for downstream LLM integrations
                        log.debug(f'Parsed args from {tool_args} to {tool_function_params}')
                        tool_call.setdefault('function', {})['arguments'] = json.dumps(tool_function_params)

                        tool_result = None
                        tool = None
                        tool_type = None
                        direct_tool = False

                        if tool_function_name in tools:
                            tool = tools[tool_function_name]
                            spec = tool.get('spec', {})

                            tool_type = tool.get('type', '')
                            direct_tool = tool.get('direct', False)

                            try:
                                allowed_params = spec.get('parameters', {}).get('properties', {}).keys()

                                tool_function_params = {
                                    k: v for k, v in tool_function_params.items() if k in allowed_params
                                }

                                if direct_tool:
                                    tool_result = await event_caller(
                                        {
                                            'type': 'execute:tool',
                                            'data': {
                                                'id': str(uuid4()),
                                                'name': tool_function_name,
                                                'params': tool_function_params,
                                                'server': tool.get('server', {}),
                                                'session_id': metadata.get('session_id', None),
                                            },
                                        }
                                    )

                                else:
                                    tool_function = await get_updated_tool_function(
                                        function=tool['callable'],
                                        extra_params={
                                            '__messages__': form_data.get('messages', []),
                                            '__files__': metadata.get('files', []),
                                        },
                                    )

                                    tool_result = await tool_function(**tool_function_params)

                            except Exception as e:
                                tool_result = str(e)

                        tool_result, tool_result_files, tool_result_embeds = await process_tool_result(
                            request,
                            tool_function_name,
                            tool_result,
                            tool_type,
                            direct_tool,
                            metadata,
                            user,
                        )

                        await terminal_event_handler(
                            tool_function_name,
                            tool_function_params,
                            tool_result,
                            event_emitter,
                        )

                        # Extract citation sources from tool results
                        if (
                            citations_enabled
                            and tool_function_name
                            in [
                                'search_web',
                                'fetch_url',
                                'view_file',
                                'view_knowledge_file',
                                'query_knowledge_files',
                            ]
                            and tool_result
                        ):
                            try:
                                citation_sources = get_citation_source_from_tool_result(
                                    tool_name=tool_function_name,
                                    tool_params=tool_function_params,
                                    tool_result=tool_result,
                                    tool_id=tool.get('tool_id', '') if tool else '',
                                )
                                tool_call_sources.extend(citation_sources)
                            except Exception as e:
                                log.exception(f'Error extracting citation source: {e}')

                        results.append(
                            {
                                'tool_call_id': tool_call_id,
                                'content': str(tool_result) if tool_result else '',
                                **({'files': tool_result_files} if tool_result_files else {}),
                                **({'embeds': tool_result_embeds} if tool_result_embeds else {}),
                            }
                        )

                    # Update function_call statuses and append function_call_output items
                    for tc in response_tool_calls:
                        call_id = tc.get('id', '')
                        # Mark function_call as completed
                        for item in output:
                            if item.get('type') == 'function_call' and item.get('call_id') == call_id:
                                item['status'] = 'completed'
                                # Update arguments with parsed/sanitized version
                                item['arguments'] = tc.get('function', {}).get('arguments', '{}')
                                break

                    for result in results:
                        output_parts = [{'type': 'input_text', 'text': result.get('content', '')}]

                        # Separate image data URIs (for LLM via input_image) from
                        # other files (for frontend display via files attribute).
                        display_files = []
                        for file_item in result.get('files', []):
                            if file_item.get('type') == 'image' and file_item.get('url', '').startswith('data:'):
                                # LLM-only: add as input_image part (invisible to serialize_output)
                                output_parts.append({'type': 'input_image', 'image_url': file_item['url']})
                            else:
                                # Frontend display (MCP images, audio, etc.)
                                display_files.append(file_item)

                        output.append(
                            {
                                'type': 'function_call_output',
                                'id': output_id('fco'),
                                'call_id': result.get('tool_call_id', ''),
                                'output': output_parts,
                                'status': 'completed',
                                **({'files': display_files} if display_files else {}),
                                **({'embeds': result.get('embeds')} if result.get('embeds') else {}),
                            }
                        )

                    # Append a new empty message item for the next response
                    output.append(
                        {
                            'type': 'message',
                            'id': output_id('msg'),
                            'status': 'in_progress',
                            'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': ''}],
                        }
                    )

                    # Emit citation sources to the frontend for display
                    if citations_enabled:
                        for source in tool_call_sources:
                            await event_emitter({'type': 'source', 'data': source})

                        # Apply tool source context to messages for the model.
                        # Restoring to pre-RAG original prevents duplicating
                        # the RAG template across file and tool sources.
                        all_tool_call_sources.extend(tool_call_sources)
                        if all_tool_call_sources and user_message:
                            # Restore pre-RAG message state before re-applying
                            # to prevent RAG template duplication.
                            original_user_message = metadata.get('user_prompt') or user_message
                            set_last_user_message_content(
                                original_user_message,
                                form_data['messages'],
                            )
                            replace_system_message_content(
                                original_system_content or '',
                                form_data['messages'],
                            )

                            # Build context: file sources with content,
                            # tool sources as citation markers only.
                            source_ids = {}
                            source_context = get_source_context(
                                metadata.get('sources', []), source_ids
                            ) + get_source_context(
                                all_tool_call_sources,
                                source_ids,
                                include_content=False,
                            )
                            source_context = source_context.strip()
                            if source_context:
                                rag_content = rag_template(
                                    request.app.state.config.RAG_TEMPLATE,
                                    source_context,
                                    user_message,
                                )
                                if RAG_SYSTEM_CONTEXT:
                                    form_data['messages'] = add_or_update_system_message(
                                        rag_content,
                                        form_data['messages'],
                                        append=True,
                                    )
                                else:
                                    form_data['messages'] = add_or_update_user_message(
                                        rag_content,
                                        form_data['messages'],
                                        append=False,
                                    )
                        tool_call_sources.clear()

                    # Strip input_image parts (large base64 data URIs) from the
                    # output sent to the frontend — they're only for LLM consumption
                    # via convert_output_to_messages.
                    frontend_output = []
                    for item in output:
                        if item.get('type') == 'function_call_output':
                            parts = item.get('output', [])
                            if any(p.get('type') == 'input_image' for p in parts):
                                item = {**item, 'output': [p for p in parts if p.get('type') != 'input_image']}
                        frontend_output.append(item)

                    await event_emitter(
                        {
                            'type': 'chat:completion',
                            'data': {
                                'content': serialize_output(output),
                                'output': frontend_output,
                            },
                        }
                    )

                    try:
                        new_form_data = {
                            **form_data,
                            'model': model_id,
                            'stream': True,
                            'metadata': metadata,
                        }

                        if ENABLE_RESPONSES_API_STATEFUL and last_response_id:
                            system_message = get_system_message(form_data['messages'])
                            new_form_data['messages'] = (
                                [system_message] if system_message else []
                            ) + convert_output_to_messages(output, raw=True)
                            new_form_data['previous_response_id'] = last_response_id
                        else:
                            tool_messages = convert_output_to_messages(output, raw=True)

                            # Chat Completions providers don't support multimodal
                            # tool messages.  Extract images into a user message.
                            image_urls = []
                            for message in tool_messages:
                                if message.get('role') == 'tool' and isinstance(message.get('content'), list):
                                    text_parts = []
                                    for part in message['content']:
                                        if part.get('type') == 'input_text':
                                            text_parts.append(part.get('text', ''))
                                        elif part.get('type') == 'input_image':
                                            image_urls.append(part.get('image_url', ''))
                                    message['content'] = ''.join(text_parts)

                            new_form_data['messages'] = [
                                *form_data['messages'],
                                *tool_messages,
                            ]

                            if image_urls:
                                new_form_data['messages'].append(
                                    {
                                        'role': 'user',
                                        'content': [
                                            {
                                                'type': 'text',
                                                'text': 'Here are the images from the tool results above. Please analyze them.',
                                            },
                                            *[{'type': 'image_url', 'image_url': {'url': url}} for url in image_urls],
                                        ],
                                    }
                                )

                        res = await generate_chat_completion(
                            request,
                            new_form_data,
                            user,
                            bypass_system_prompt=True,
                        )

                        if isinstance(res, StreamingResponse):
                            # Save accumulated output and start fresh.
                            # Responses API output_index values are relative
                            # to the current response — a clean output list
                            # keeps indices aligned. The display prefix
                            # ensures the UI shows tool history during
                            # streaming.
                            prior_output = list(output)
                            # Trim the trailing empty placeholder message
                            # so it doesn't persist as a ghost item once
                            # the new stream produces real content.
                            if (
                                prior_output
                                and prior_output[-1].get('type') == 'message'
                                and prior_output[-1].get('status') == 'in_progress'
                            ):
                                msg_parts = prior_output[-1].get('content', [])
                                if not msg_parts or (len(msg_parts) == 1 and not msg_parts[0].get('text', '').strip()):
                                    prior_output.pop()
                            output = []
                            await stream_body_handler(res, new_form_data)
                            output[:0] = prior_output
                            prior_output = []
                        else:
                            break
                    except Exception as e:
                        log.debug(e)
                        break

                if DETECT_CODE_INTERPRETER:
                    MAX_RETRIES = 5
                    retries = 0

                    while output and output[-1].get('type') == 'open_webui:code_interpreter' and retries < MAX_RETRIES:
                        await event_emitter(
                            {
                                'type': 'chat:completion',
                                'data': {
                                    'content': serialize_output(output),
                                    'output': output,
                                },
                            }
                        )

                        retries += 1
                        log.debug(f'Attempt count: {retries}')

                        ci_item = output[-1]
                        ci_output = ''
                        try:
                            if ci_item.get('attributes', {}).get('type') == 'code':
                                code = ci_item.get('code', '')
                                # Sanitize code (strips ANSI codes and markdown fences)
                                code = sanitize_code(code)

                                if CODE_INTERPRETER_BLOCKED_MODULES:
                                    blocking_code = textwrap.dedent(
                                        f"""
                                        import builtins
    
                                        BLOCKED_MODULES = {CODE_INTERPRETER_BLOCKED_MODULES}
    
                                        _real_import = builtins.__import__
                                        async def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
                                            if name.split('.')[0] in BLOCKED_MODULES:
                                                importer_name = globals.get('__name__') if globals else None
                                                if importer_name == '__main__':
                                                    raise ImportError(
                                                        f"Direct import of module {{name}} is restricted."
                                                    )
                                            return _real_import(name, globals, locals, fromlist, level)
    
                                        builtins.__import__ = restricted_import
                                    """
                                    )
                                    code = blocking_code + '\n' + code

                                if request.app.state.config.CODE_INTERPRETER_ENGINE == 'jupyter':
                                    ci_output = await execute_code_jupyter(
                                        request.app.state.config.CODE_INTERPRETER_JUPYTER_URL,
                                        code,
                                        (
                                            request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_TOKEN
                                            if request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH == 'token'
                                            else None
                                        ),
                                        (
                                            request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD
                                            if request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH == 'password'
                                            else None
                                        ),
                                        request.app.state.config.CODE_INTERPRETER_JUPYTER_TIMEOUT,
                                    )
                                else:
                                    ci_output = {'stdout': 'Code interpreter engine not configured.'}

                                log.debug(f'Code interpreter output: {ci_output}')

                                if isinstance(ci_output, dict):
                                    stdout = ci_output.get('stdout', '')

                                    if isinstance(stdout, str):
                                        stdoutLines = stdout.split('\n')
                                        for idx, line in enumerate(stdoutLines):
                                            if re.match(r'data:image/\w+;base64', line):
                                                image_url = await get_image_url_from_base64(
                                                    request,
                                                    line,
                                                    metadata,
                                                    user,
                                                )
                                                if image_url:
                                                    stdoutLines[idx] = f'![Output Image]({image_url})'

                                        ci_output['stdout'] = '\n'.join(stdoutLines)

                                    result = ci_output.get('result', '')

                                    if isinstance(result, str):
                                        resultLines = result.split('\n')
                                        for idx, line in enumerate(resultLines):
                                            if re.match(r'data:image/\w+;base64', line):
                                                image_url = await get_image_url_from_base64(
                                                    request,
                                                    line,
                                                    metadata,
                                                    user,
                                                )
                                                resultLines[idx] = f'![Output Image]({image_url})'
                                        ci_output['result'] = '\n'.join(resultLines)
                        except Exception as e:
                            ci_output = str(e)

                        ci_item['output'] = ci_output
                        ci_item['status'] = 'completed'

                        output.append(
                            {
                                'type': 'message',
                                'id': output_id('msg'),
                                'status': 'in_progress',
                                'role': 'assistant',
                                'content': [{'type': 'output_text', 'text': ''}],
                            }
                        )

                        await event_emitter(
                            {
                                'type': 'chat:completion',
                                'data': {
                                    'content': serialize_output(output),
                                    'output': output,
                                },
                            }
                        )

                        try:
                            new_form_data = {
                                **form_data,
                                'model': model_id,
                                'stream': True,
                                'metadata': metadata,
                                'messages': [
                                    *form_data['messages'],
                                    *convert_output_to_messages(output, raw=True),
                                ],
                            }

                            res = await generate_chat_completion(
                                request,
                                new_form_data,
                                user,
                                bypass_system_prompt=True,
                            )

                            if isinstance(res, StreamingResponse):
                                await stream_body_handler(res, new_form_data)
                            else:
                                break
                        except Exception as e:
                            log.debug(e)
                            break

                # Mark all in-progress items as completed
                for item in output:
                    if item.get('status') == 'in_progress':
                        item['status'] = 'completed'

                title = await Chats.get_chat_title_by_id(metadata['chat_id'])
                data = {
                    'done': True,
                    'content': serialize_output(output),
                    'output': output,
                    'title': title,
                    **({'usage': usage} if usage else {}),
                }

                if not ENABLE_REALTIME_CHAT_SAVE:
                    # Save message in the database
                    await Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata['chat_id'],
                        metadata['message_id'],
                        {
                            'done': True,
                            'content': serialize_output(output),
                            'output': output,
                            **({'usage': usage} if usage else {}),
                        },
                    )
                elif usage:
                    await Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata['chat_id'],
                        metadata['message_id'],
                        {'done': True, 'usage': usage},
                    )
                else:
                    await Chats.upsert_message_to_chat_by_id_and_message_id(
                        metadata['chat_id'],
                        metadata['message_id'],
                        {'done': True},
                    )

                # Send a webhook notification if the user is not active
                if request.app.state.config.ENABLE_USER_WEBHOOKS and not await Users.is_user_active(user.id):
                    webhook_url = await Users.get_user_webhook_url_by_id(user.id)
                    if webhook_url:
                        await post_webhook(
                            request.app.state.WEBUI_NAME,
                            webhook_url,
                            f'{content}\n\n{title} - {request.app.state.config.WEBUI_URL}/c/{metadata["chat_id"]}',
                            {
                                'action': 'chat',
                                'message': content,
                                'title': title,
                                'url': f'{request.app.state.config.WEBUI_URL}/c/{metadata["chat_id"]}',
                            },
                        )

                await event_emitter(
                    {
                        'type': 'chat:completion',
                        'data': data,
                    }
                )

                await background_tasks_handler(ctx)
                ctx['assistant_message'] = {
                    'content': serialize_output(output),
                    'output': output,
                    **({'usage': usage} if usage else {}),
                }
                await outlet_filter_handler(ctx)
            except asyncio.CancelledError:
                log.warning('Task was cancelled!')

                # Close the response body iterator to trigger cleanup
                # in stream_wrapper's finally block and release the
                # upstream connection.  Without this, the async
                # generator is orphaned and may spin in anyio internals.
                if hasattr(response, 'body_iterator') and hasattr(response.body_iterator, 'aclose'):
                    try:
                        await asyncio.shield(response.body_iterator.aclose())
                    except (asyncio.CancelledError, Exception):
                        pass

                async def save_cancelled_state():
                    await event_emitter({'type': 'chat:tasks:cancel'})
                    if not ENABLE_REALTIME_CHAT_SAVE:
                        await Chats.upsert_message_to_chat_by_id_and_message_id(
                            metadata['chat_id'],
                            metadata['message_id'],
                            {
                                'done': True,
                                'content': serialize_output(output),
                                'output': output,
                            },
                        )
                    else:
                        await Chats.upsert_message_to_chat_by_id_and_message_id(
                            metadata['chat_id'],
                            metadata['message_id'],
                            {'done': True},
                        )

                try:
                    await asyncio.shield(save_cancelled_state())
                except (asyncio.CancelledError, Exception):
                    pass
                raise  # re-raise CancelledError for proper propagation

            if response.background is not None:
                await response.background()

        return await response_handler(response, events)

    else:
        # Fallback to the original response
        async def stream_wrapper(original_generator, events):
            def wrap_item(item):
                return f'data: {item}\n\n'

            for event in events:
                event, _ = await process_filter_functions(
                    request=request,
                    filter_functions=filter_functions,
                    filter_type='stream',
                    form_data=event,
                    extra_params=extra_params,
                )

                if event:
                    yield wrap_item(json.dumps(event))

            async for data in original_generator:
                data, _ = await process_filter_functions(
                    request=request,
                    filter_functions=filter_functions,
                    filter_type='stream',
                    form_data=data,
                    extra_params=extra_params,
                )

                if data:
                    yield data

        return StreamingResponse(
            stream_wrapper(response.body_iterator, events),
            headers=dict(response.headers),
            background=response.background,
        )


async def process_chat_response(response, ctx):
    # Non-streaming response
    if not isinstance(response, StreamingResponse):
        return await non_streaming_chat_response_handler(response, ctx)

    # Non standard response
    if not any(
        content_type in response.headers['Content-Type']
        for content_type in ['text/event-stream', 'application/x-ndjson']
    ):
        return response

    # Streaming response
    return await streaming_chat_response_handler(response, ctx)
