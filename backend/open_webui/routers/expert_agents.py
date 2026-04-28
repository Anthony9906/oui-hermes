import logging
from typing import Any
from urllib.parse import quote

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from open_webui.config import HERMES_API_BASE_URL, HERMES_API_KEY
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


class ExpertAgentItem(BaseModel):
    skill_name: str
    description: str = ''


class ExpertAgentListResponse(BaseModel):
    items: list[ExpertAgentItem]


class ExpertAgentDetailResponse(BaseModel):
    name: str
    description: str = ''
    content: str
    path: str | None = None
    tags: list[str] = Field(default_factory=list)
    related_skills: list[str] = Field(default_factory=list)
    linked_files: dict[str, list[str]] | None = None
    readiness_status: str | None = None
    setup_needed: bool | None = None
    setup_note: str | None = None
    metadata: dict[str, Any] | None = None


@router.get('', response_model=ExpertAgentListResponse)
@router.get('/', response_model=ExpertAgentListResponse)
async def get_expert_agents(user=Depends(get_verified_user)):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            headers = {}
            if HERMES_API_KEY:
                headers['Authorization'] = f'Bearer {HERMES_API_KEY}'

            async with session.get(f'{HERMES_API_BASE_URL}/skills', headers=headers) as response:
                if response.status >= 400:
                    body = await response.text()
                    log.warning('Failed to load Hermes skills: status=%s body=%s', response.status, body)
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail='Failed to load Hermes skills',
                    )

                data = await response.json()

        items = []
        for item in data.get('items', []):
            skill_name = item.get('skill_name', '')
            if not skill_name:
                continue

            items.append(
                ExpertAgentItem(
                    skill_name=skill_name,
                    description=item.get('description', '') or '',
                )
            )

        return ExpertAgentListResponse(items=items)
    except HTTPException:
        raise
    except Exception as e:
        log.exception('Failed to load Hermes skills: %s', e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Failed to load Hermes skills',
        )


@router.get('/{skill_name:path}', response_model=ExpertAgentDetailResponse)
async def get_expert_agent_detail(skill_name: str, user=Depends(get_verified_user)):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            headers = {}
            if HERMES_API_KEY:
                headers['Authorization'] = f'Bearer {HERMES_API_KEY}'

            encoded_skill_name = quote(skill_name, safe='')
            async with session.get(
                f'{HERMES_API_BASE_URL}/skills/{encoded_skill_name}', headers=headers
            ) as response:
                if response.status == 404:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail='Expert skill not found',
                    )
                if response.status >= 400:
                    body = await response.text()
                    log.warning(
                        'Failed to load Hermes skill detail: status=%s body=%s',
                        response.status,
                        body,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail='Failed to load Hermes skill detail',
                    )

                data = await response.json()

        return ExpertAgentDetailResponse(
            name=data.get('name') or skill_name,
            description=data.get('description') or '',
            content=data.get('content') or '',
            path=data.get('path'),
            tags=data.get('tags') or [],
            related_skills=data.get('related_skills') or [],
            linked_files=data.get('linked_files'),
            readiness_status=data.get('readiness_status'),
            setup_needed=data.get('setup_needed'),
            setup_note=data.get('setup_note'),
            metadata=data.get('metadata'),
        )
    except HTTPException:
        raise
    except Exception as e:
        log.exception('Failed to load Hermes skill detail: %s', e)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail='Failed to load Hermes skill detail',
        )
