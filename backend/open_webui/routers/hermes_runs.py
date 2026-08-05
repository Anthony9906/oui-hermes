import logging
from typing import Literal

import aiohttp
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL
from open_webui.models.chats import Chats
from open_webui.utils.auth import get_verified_user
from open_webui.utils.hermes_runs import (
    APPROVAL_CHOICES,
    hermes_run_approval_error,
    hermes_run_approval_is_gone,
    hermes_run_registry,
)
from open_webui.utils.session_pool import cleanup_response, get_session


log = logging.getLogger(__name__)
router = APIRouter()


class HermesApprovalResponseForm(BaseModel):
    chat_id: str
    approval_request_id: str
    choice: Literal['once', 'session', 'deny']


@router.get('/approvals')
async def list_pending_approvals(chat_id: str, user=Depends(get_verified_user)):
    chat = await Chats.get_chat_by_id_and_user_id(chat_id, user.id)
    if not chat:
        raise HTTPException(status_code=404, detail='Chat not found.')

    approvals = await hermes_run_registry.list_pending(user.id, chat_id)
    return {'items': approvals}


@router.post('/runs/{run_id}/approval')
async def respond_to_approval(
    run_id: str,
    form_data: HermesApprovalResponseForm,
    user=Depends(get_verified_user),
):
    if form_data.choice not in APPROVAL_CHOICES:
        raise HTTPException(status_code=400, detail='Invalid approval choice.')

    chat = await Chats.get_chat_by_id_and_user_id(form_data.chat_id, user.id)
    if not chat:
        raise HTTPException(status_code=404, detail='Chat not found.')

    try:
        run, approval = await hermes_run_registry.claim_approval(
            run_id,
            form_data.approval_request_id,
            user.id,
            form_data.chat_id,
            form_data.choice,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail='Agent task not found for this chat.')
    except RuntimeError as exc:
        code = str(exc)
        if code == 'approval_not_at_queue_head':
            raise HTTPException(status_code=409, detail='Another approval must be answered first.')
        raise HTTPException(status_code=409, detail='Approval is no longer pending.')

    if approval.status in {'approved', 'denied'}:
        return {
            'run_id': run_id,
            'approval_request_id': approval.id,
            'choice': approval.selected_choice,
            'status': approval.status,
            'idempotent': True,
        }

    response = None
    try:
        session = await get_session()
        response = await session.request(
            method='POST',
            url=f'{run.base_url}/runs/{run_id}/approval',
            json={'choice': form_data.choice, 'resolve_all': False},
            headers=run.headers,
            cookies=run.cookies,
            ssl=AIOHTTP_CLIENT_SESSION_SSL,
            timeout=aiohttp.ClientTimeout(total=30),
        )
        try:
            response_data = await response.json()
        except Exception:
            response_data = {'error': {'message': await response.text()}}

        if response.status >= 400:
            message, _ = hermes_run_approval_error(response_data)
            approval_is_gone = hermes_run_approval_is_gone(response.status, response_data)
            if approval_is_gone:
                await hermes_run_registry.expire_approvals(run_id)
            else:
                await hermes_run_registry.release_approval(run_id, approval.id)
            raise HTTPException(
                status_code=410 if approval_is_gone else response.status,
                detail=message or 'Agent rejected the approval response.',
            )

        await hermes_run_registry.finish_approval(run_id, approval.id, form_data.choice)
        return {
            'run_id': run_id,
            'approval_request_id': approval.id,
            'choice': form_data.choice,
            'status': 'denied' if form_data.choice == 'deny' else 'approved',
            'resolved': response_data.get('resolved') if isinstance(response_data, dict) else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        await hermes_run_registry.release_approval(run_id, approval.id)
        log.exception('Failed to respond to Hermes approval for run %s', run_id)
        raise HTTPException(status_code=502, detail=f'Failed to reach Agent: {exc}')
    finally:
        if response is not None:
            await cleanup_response(response)
