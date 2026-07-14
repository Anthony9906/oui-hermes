from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, AsyncIterator
from uuid import uuid4

import aiohttp
from fastapi import HTTPException
from starlette.responses import StreamingResponse

from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL
from open_webui.utils.session_pool import cleanup_response, get_session


log = logging.getLogger(__name__)

APPROVAL_CHOICES = frozenset({'once', 'session', 'always', 'deny'})
TERMINAL_RUN_STATUSES = frozenset({'completed', 'failed', 'cancelled'})
REQUIRED_RUN_FEATURES = frozenset(
    {
        'run_submission',
        'run_events_sse',
        'run_approval_response',
        'approval_events',
        'run_tool_arguments',
        'run_tool_results',
    }
)
_capability_cache: dict[str, tuple[float, bool]] = {}
_capability_lock = asyncio.Lock()


def hermes_run_approvals_enabled() -> bool:
    return os.environ.get('HERMES_RUN_APPROVALS_ENABLED', 'false').strip().lower() in {
        '1',
        'true',
        'yes',
        'on',
    }


def _runs_url(base_url: str) -> str:
    return f'{base_url.rstrip("/")}/runs'


def hermes_run_capabilities_satisfied(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    features = payload.get('features')
    return isinstance(features, dict) and all(features.get(name) is True for name in REQUIRED_RUN_FEATURES)


async def is_hermes_runs_capable(
    base_url: str,
    headers: dict[str, str],
    cookies: dict[str, str],
) -> bool:
    cache_key = base_url.rstrip('/')
    now = time.time()
    async with _capability_lock:
        cached = _capability_cache.get(cache_key)
        if cached and cached[0] > now:
            return cached[1]

    response = None
    capable = False
    try:
        session = await get_session()
        response = await session.request(
            method='GET',
            url=f'{cache_key}/capabilities',
            headers=headers,
            cookies=cookies,
            ssl=AIOHTTP_CLIENT_SESSION_SSL,
            timeout=aiohttp.ClientTimeout(total=10),
        )
        if response.status == 200:
            capable = hermes_run_capabilities_satisfied(await response.json())
    except Exception as exc:
        log.debug('Hermes Runs capability probe failed for %s: %s', cache_key, exc)
    finally:
        if response is not None:
            await cleanup_response(response)

    async with _capability_lock:
        _capability_cache[cache_key] = (now + (300 if capable else 30), capable)
    return capable


def _sse(data: dict[str, Any], event: str | None = None) -> bytes:
    prefix = f'event: {event}\n' if event else ''
    return f'{prefix}data: {json.dumps(data, ensure_ascii=False)}\n\n'.encode()


def _message_content(payload: dict[str, Any]) -> Any:
    messages = payload.get('messages') or []
    for message in reversed(messages):
        if isinstance(message, dict) and message.get('role') == 'user':
            return message.get('content', '')
    return ''


@dataclass
class PendingApproval:
    id: str
    command: str
    description: str
    pattern_key: str
    pattern_keys: list[str]
    choices: list[str]
    sequence: int
    requested_at: float
    status: str = 'pending'
    selected_choice: str | None = None
    responded_at: float | None = None

    def public_dict(self, run: 'HermesRun') -> dict[str, Any]:
        return {
            'approval_request_id': self.id,
            'run_id': run.run_id,
            'chat_id': run.chat_id,
            'message_id': run.message_id,
            'command': self.command,
            'description': self.description,
            'pattern_key': self.pattern_key,
            'pattern_keys': self.pattern_keys,
            'choices': self.choices,
            'sequence': self.sequence,
            'status': self.status,
            'selected_choice': self.selected_choice,
            'requested_at': self.requested_at,
            'responded_at': self.responded_at,
        }


@dataclass
class HermesRun:
    run_id: str
    chat_id: str
    message_id: str
    user_id: str
    model_id: str
    base_url: str
    headers: dict[str, str]
    cookies: dict[str, str]
    session_id: str
    status: str = 'running'
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    approvals: list[PendingApproval] = field(default_factory=list)


class HermesRunRegistry:
    """Process-local routing and approval state for active Hermes runs.

    Hermes currently keeps active run queues in process memory too. Keeping the
    upstream credentials here avoids putting connection secrets in browser events,
    while chat ownership is re-checked on every approval response.
    """

    def __init__(self) -> None:
        self._runs: dict[str, HermesRun] = {}
        self._lock = asyncio.Lock()

    async def register(self, run: HermesRun) -> None:
        async with self._lock:
            cutoff = time.time() - 3600
            self._runs = {
                run_id: existing
                for run_id, existing in self._runs.items()
                if existing.status not in TERMINAL_RUN_STATUSES or existing.updated_at >= cutoff
            }
            self._runs[run.run_id] = run

    async def get(self, run_id: str) -> HermesRun | None:
        async with self._lock:
            return self._runs.get(run_id)

    async def set_status(self, run_id: str, status: str) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if run:
                run.status = status
                run.updated_at = time.time()

    async def add_approval(self, run_id: str, data: dict[str, Any]) -> tuple[HermesRun, PendingApproval]:
        async with self._lock:
            run = self._runs.get(run_id)
            if not run:
                raise KeyError(run_id)

            approval = PendingApproval(
                id=f'hap_{uuid4().hex}',
                command=str(data.get('command') or ''),
                description=str(data.get('description') or ''),
                pattern_key=str(data.get('pattern_key') or ''),
                pattern_keys=[str(value) for value in data.get('pattern_keys') or []],
                choices=[
                    str(value)
                    for value in data.get('choices') or ['once', 'session', 'always', 'deny']
                    if str(value) in APPROVAL_CHOICES
                ],
                sequence=len(run.approvals) + 1,
                requested_at=float(data.get('timestamp') or time.time()),
            )
            run.approvals.append(approval)
            run.status = 'waiting_for_approval'
            run.updated_at = time.time()
            return run, approval

    async def list_pending(self, user_id: str, chat_id: str) -> list[dict[str, Any]]:
        async with self._lock:
            pending = []
            for run in self._runs.values():
                if run.user_id != user_id or run.chat_id != chat_id:
                    continue
                pending.extend(
                    approval.public_dict(run)
                    for approval in run.approvals
                    if approval.status in {'pending', 'responding'}
                )
            return sorted(pending, key=lambda item: (item['requested_at'], item['sequence']))

    async def claim_approval(
        self,
        run_id: str,
        approval_id: str,
        user_id: str,
        chat_id: str,
        choice: str,
    ) -> tuple[HermesRun, PendingApproval]:
        async with self._lock:
            run = self._runs.get(run_id)
            if not run or run.user_id != user_id or run.chat_id != chat_id:
                raise LookupError(run_id)

            pending = [approval for approval in run.approvals if approval.status == 'pending']
            if not pending:
                existing = next((approval for approval in run.approvals if approval.id == approval_id), None)
                if existing and existing.status in {'approved', 'denied'}:
                    return run, existing
                raise RuntimeError('approval_not_pending')

            approval = pending[0]
            if approval.id != approval_id:
                raise RuntimeError('approval_not_at_queue_head')

            approval.status = 'responding'
            approval.selected_choice = choice
            run.updated_at = time.time()
            return run, approval

    async def finish_approval(self, run_id: str, approval_id: str, choice: str) -> PendingApproval | None:
        async with self._lock:
            run = self._runs.get(run_id)
            if not run:
                return None
            approval = next((item for item in run.approvals if item.id == approval_id), None)
            if not approval:
                return None
            approval.status = 'denied' if choice == 'deny' else 'approved'
            approval.selected_choice = choice
            approval.responded_at = time.time()
            run.status = 'running'
            run.updated_at = time.time()
            return approval

    async def release_approval(self, run_id: str, approval_id: str) -> None:
        async with self._lock:
            run = self._runs.get(run_id)
            if not run:
                return
            approval = next((item for item in run.approvals if item.id == approval_id), None)
            if approval and approval.status == 'responding':
                approval.status = 'pending'
                approval.selected_choice = None
                run.updated_at = time.time()


hermes_run_registry = HermesRunRegistry()


async def create_hermes_run_response(
    *,
    payload: dict[str, Any],
    metadata: dict[str, Any],
    user_id: str,
    base_url: str,
    headers: dict[str, str],
    cookies: dict[str, str],
) -> StreamingResponse:
    chat_id = str(metadata.get('chat_id') or '')
    message_id = str(metadata.get('message_id') or '')
    if not chat_id or not message_id:
        raise HTTPException(status_code=400, detail='Hermes Runs require chat_id and message_id.')

    model_id = str(payload.get('model') or '')
    run_payload = {
        'model': model_id,
        'session_id': chat_id,
        'input': _message_content(payload),
    }

    session = await get_session()
    start_response = await session.request(
        method='POST',
        url=_runs_url(base_url),
        json=run_payload,
        headers=headers,
        cookies=cookies,
        ssl=AIOHTTP_CLIENT_SESSION_SSL,
        timeout=aiohttp.ClientTimeout(total=30),
    )
    try:
        start_data = await start_response.json()
    except Exception:
        start_data = {'error': {'message': await start_response.text()}}
    finally:
        await cleanup_response(start_response)

    if start_response.status >= 400:
        message = (
            (start_data.get('error') or {}).get('message')
            if isinstance(start_data, dict)
            else str(start_data)
        )
        raise HTTPException(status_code=start_response.status, detail=message or 'Failed to start Hermes run.')

    run_id = str(start_data.get('run_id') or '')
    if not run_id:
        raise HTTPException(status_code=502, detail='Hermes did not return a run_id.')

    run = HermesRun(
        run_id=run_id,
        chat_id=chat_id,
        message_id=message_id,
        user_id=user_id,
        model_id=model_id,
        base_url=base_url.rstrip('/'),
        headers=dict(headers),
        cookies=dict(cookies),
        session_id=chat_id,
    )
    await hermes_run_registry.register(run)

    completion_id = f'chatcmpl-{run_id}'

    async def event_stream() -> AsyncIterator[bytes]:
        events_response = None
        saw_delta = False
        tool_calls: dict[str, deque[str]] = defaultdict(deque)
        try:
            events_response = await session.request(
                method='GET',
                url=f'{_runs_url(base_url)}/{run_id}/events',
                headers=headers,
                cookies=cookies,
                ssl=AIOHTTP_CLIENT_SESSION_SSL,
                timeout=aiohttp.ClientTimeout(total=None, sock_read=90),
            )
            if events_response.status >= 400:
                error_text = await events_response.text()
                yield _sse({'error': {'message': error_text or 'Failed to subscribe to Hermes run.'}})
                return

            async for raw_line in events_response.content:
                line = raw_line.decode('utf-8', 'replace').strip()
                if not line or line.startswith(':') or not line.startswith('data:'):
                    continue
                raw_data = line[len('data:') :].strip()
                try:
                    event = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue

                event_type = str(event.get('event') or '')
                if event_type == 'message.delta':
                    delta = str(event.get('delta') or '')
                    if delta:
                        saw_delta = True
                        yield _sse(
                            {
                                'id': completion_id,
                                'object': 'chat.completion.chunk',
                                'model': model_id,
                                'choices': [{'index': 0, 'delta': {'content': delta}, 'finish_reason': None}],
                            }
                        )
                    continue

                if event_type == 'reasoning.available':
                    yield _sse(
                        {
                            'id': completion_id,
                            'object': 'chat.completion.chunk',
                            'model': model_id,
                            'choices': [
                                {
                                    'index': 0,
                                    'delta': {'reasoning_content': str(event.get('text') or '')},
                                    'finish_reason': None,
                                }
                            ],
                        }
                    )
                    continue

                if event_type == 'tool.started':
                    tool_name = str(event.get('tool') or event.get('tool_name') or 'tool')
                    call_id = str(event.get('tool_call_id') or event.get('toolCallId') or f'call_{uuid4().hex}')
                    tool_calls[tool_name].append(call_id)
                    yield _sse(
                        {
                            'event': 'hermes.tool.progress',
                            'run_id': run_id,
                            'tool': tool_name,
                            'toolCallId': call_id,
                            'status': 'running',
                            'label': str(event.get('preview') or tool_name),
                            'args': event.get('args') or {},
                        },
                        event='hermes.tool.progress',
                    )
                    continue

                if event_type in {'tool.completed', 'tool.failed'}:
                    tool_name = str(event.get('tool') or event.get('tool_name') or 'tool')
                    call_id = str(event.get('tool_call_id') or event.get('toolCallId') or '')
                    if not call_id and tool_calls[tool_name]:
                        call_id = tool_calls[tool_name].popleft()
                    yield _sse(
                        {
                            'event': 'hermes.tool.progress',
                            'run_id': run_id,
                            'tool': tool_name,
                            'toolCallId': call_id or f'call_{uuid4().hex}',
                            'status': 'failed' if event_type == 'tool.failed' or event.get('error') else 'completed',
                            'args': event.get('args') or {},
                            'result': event.get('result'),
                        },
                        event='hermes.tool.progress',
                    )
                    continue

                if event_type == 'approval.request':
                    registered_run, approval = await hermes_run_registry.add_approval(run_id, event)
                    yield _sse(
                        approval.public_dict(registered_run),
                        event='hermes.approval.request',
                    )
                    continue

                if event_type == 'approval.responded':
                    yield _sse(
                        {
                            'run_id': run_id,
                            'choice': event.get('choice'),
                            'resolved': event.get('resolved'),
                        },
                        event='hermes.approval.responded',
                    )
                    continue

                if event_type == 'run.completed':
                    output = str(event.get('output') or '')
                    if output and not saw_delta:
                        yield _sse(
                            {
                                'id': completion_id,
                                'object': 'chat.completion.chunk',
                                'model': model_id,
                                'choices': [{'index': 0, 'delta': {'content': output}, 'finish_reason': None}],
                            }
                        )
                    yield _sse(
                        {
                            'id': completion_id,
                            'object': 'chat.completion.chunk',
                            'model': model_id,
                            'choices': [{'index': 0, 'delta': {}, 'finish_reason': 'stop'}],
                            'usage': event.get('usage') or {},
                        }
                    )
                    await hermes_run_registry.set_status(run_id, 'completed')
                    yield b'data: [DONE]\n\n'
                    return

                if event_type in {'run.failed', 'run.cancelled'}:
                    status = 'failed' if event_type == 'run.failed' else 'cancelled'
                    await hermes_run_registry.set_status(run_id, status)
                    yield _sse({'error': {'message': str(event.get('error') or status)}})
                    yield b'data: [DONE]\n\n'
                    return
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.exception('Hermes run stream failed for %s', run_id)
            await hermes_run_registry.set_status(run_id, 'failed')
            yield _sse({'error': {'message': str(exc)}})
        finally:
            if events_response is not None:
                await cleanup_response(events_response)

    return StreamingResponse(
        event_stream(),
        media_type='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
            'X-Hermes-Run-Id': run_id,
        },
    )
