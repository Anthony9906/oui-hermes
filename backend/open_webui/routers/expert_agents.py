import logging

import aiohttp
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from open_webui.config import HERMES_API_BASE_URL
from open_webui.utils.auth import get_verified_user

log = logging.getLogger(__name__)

router = APIRouter()


class ExpertAgentItem(BaseModel):
    skill_name: str
    description: str = ''


class ExpertAgentListResponse(BaseModel):
    items: list[ExpertAgentItem]


@router.get('', response_model=ExpertAgentListResponse)
@router.get('/', response_model=ExpertAgentListResponse)
async def get_expert_agents(user=Depends(get_verified_user)):
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(f'{HERMES_API_BASE_URL}/skills') as response:
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
