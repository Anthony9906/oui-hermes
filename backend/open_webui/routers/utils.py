import black
import aiohttp
import logging
import markdown
import os
import re
from urllib.parse import parse_qs, urlparse

from open_webui.models.chats import ChatTitleMessagesForm
from open_webui.config import (
    DATA_DIR,
    ENABLE_ADMIN_EXPORT,
    HERMES_API_BASE_URL,
    HERMES_API_KEY,
    S3_PUBLIC_BASE_URL,
)
from open_webui.constants import ERROR_MESSAGES
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel
from starlette.responses import FileResponse


from open_webui.utils.misc import get_gravatar_url
from open_webui.utils.pdf_generator import PDFGenerator
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.utils.code_interpreter import execute_code_jupyter

log = logging.getLogger(__name__)

router = APIRouter()

LOCAL_ARTIFACT_BASE_URL = os.environ.get('LOCAL_ARTIFACT_BASE_URL', 'http://localhost:8787').rstrip('/')
LOCAL_ARTIFACT_ID_RE = re.compile(r'^[A-Za-z0-9_-]+$')
LOCAL_ARTIFACT_PATH_RE = re.compile(r'^/(?:v|api/artifacts)/([A-Za-z0-9_-]+)/?$')
LOCAL_ARTIFACT_HOST_ALIASES = {'localhost', '127.0.0.1', '::1'}
MINIO_ARTIFACT_VIEWER_PATH = '/artifact-viewer/index.html'


class AguiApprovalForm(BaseModel):
    run_id: str
    choice: str
    resolve_all: bool = False


def _is_allowed_local_artifact_url(url: str) -> tuple[str, str]:
    parsed = urlparse(url)
    base = urlparse(LOCAL_ARTIFACT_BASE_URL)

    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        raise HTTPException(status_code=400, detail='invalid_artifact_url')

    base_host = (base.hostname or '').lower()
    request_host = parsed.hostname.lower()
    base_port = base.port
    request_port = parsed.port

    if base_host in LOCAL_ARTIFACT_HOST_ALIASES:
        host_allowed = request_host in LOCAL_ARTIFACT_HOST_ALIASES
    else:
        host_allowed = request_host == base_host

    if not host_allowed or request_port != base_port:
        raise HTTPException(status_code=400, detail='artifact_host_not_allowed')

    match = LOCAL_ARTIFACT_PATH_RE.match(parsed.path)
    artifact_id = match.group(1) if match else ''
    if not artifact_id or not LOCAL_ARTIFACT_ID_RE.match(artifact_id):
        raise HTTPException(status_code=400, detail='invalid_artifact_id')

    origin = f'{parsed.scheme}://{parsed.netloc}'
    return origin, artifact_id


def _is_allowed_s3_public_url(url: str) -> bool:
    if not S3_PUBLIC_BASE_URL:
        return False

    parsed = urlparse(url)
    base = urlparse(S3_PUBLIC_BASE_URL.rstrip('/'))

    if parsed.scheme not in {'http', 'https'} or not parsed.hostname:
        return False

    if parsed.scheme != base.scheme:
        return False

    if parsed.hostname.lower() != (base.hostname or '').lower() or parsed.port != base.port:
        return False

    base_path = base.path.rstrip('/')
    return parsed.path == base_path or parsed.path.startswith(f'{base_path}/')


def _get_allowed_minio_metadata_url(url: str) -> tuple[str, str]:
    if not _is_allowed_s3_public_url(url):
        raise HTTPException(status_code=400, detail='artifact_host_not_allowed')

    parsed = urlparse(url)

    if parsed.path.endswith(MINIO_ARTIFACT_VIEWER_PATH):
        artifact_values = parse_qs(parsed.query).get('artifact') or []
        payload_url = artifact_values[0] if artifact_values else ''
        payload = urlparse(payload_url)
        if (
            not payload_url
            or not _is_allowed_s3_public_url(payload_url)
            or payload.path.endswith(MINIO_ARTIFACT_VIEWER_PATH)
            or not payload.path.lower().endswith('.json')
        ):
            raise HTTPException(status_code=400, detail='invalid_artifact_payload_url')

        return payload_url, 'json'

    if parsed.path.lower().endswith('.json'):
        return url, 'json'

    if parsed.path.lower().endswith('.html'):
        return url, 'html'

    raise HTTPException(status_code=400, detail='invalid_artifact_payload_url')


@router.get('/gravatar')
async def get_gravatar(email: str, user=Depends(get_verified_user)):
    return get_gravatar_url(email)


@router.get('/artifacts/title')
async def get_artifact_title(url: str, user=Depends(get_verified_user)):
    artifact_id = ''

    if _is_allowed_s3_public_url(url):
        metadata_url, metadata_kind = _get_allowed_minio_metadata_url(url)
    else:
        origin, artifact_id = _is_allowed_local_artifact_url(url)
        metadata_url = f'{origin}/api/artifacts/{artifact_id}'
        metadata_kind = 'json'

    try:
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.get(metadata_url) as response:
                if response.status == 404:
                    raise HTTPException(status_code=404, detail='artifact_not_found')
                if response.status == 410:
                    raise HTTPException(status_code=410, detail='artifact_expired')
                if response.status >= 400:
                    raise HTTPException(status_code=502, detail='artifact_metadata_unavailable')

                if metadata_kind == 'html':
                    text = await response.text()
                    match = re.search(r'<title[^>]*>([\s\S]*?)</title>', text, re.IGNORECASE)
                    title = re.sub(r'\s+', ' ', match.group(1)).strip() if match else ''
                    return {'id': artifact_id, 'title': title}

                payload = await response.json()
    except HTTPException:
        raise
    except Exception as e:
        log.debug(f'Failed to fetch artifact metadata from {metadata_url}: {e}')
        raise HTTPException(status_code=502, detail='artifact_metadata_unavailable')

    title = payload.get('artifact', {}).get('title') or payload.get('title')
    return {'id': artifact_id, 'title': title if isinstance(title, str) else ''}


@router.post('/agui/approval')
async def resolve_agui_approval(form_data: AguiApprovalForm, user=Depends(get_verified_user)):
    run_id = (form_data.run_id or '').strip()
    choice = (form_data.choice or '').strip().lower()

    if not run_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='missing_run_id')

    if choice not in {'once', 'session', 'always', 'deny'}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='invalid_approval_choice')

    headers = {'Content-Type': 'application/json'}
    if HERMES_API_KEY:
        headers['Authorization'] = f'Bearer {HERMES_API_KEY}'

    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
            async with session.post(
                f'{HERMES_API_BASE_URL}/v1/runs/{run_id}/approval',
                headers=headers,
                json={
                    'choice': choice,
                    'resolve_all': bool(form_data.resolve_all),
                },
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400:
                    raise HTTPException(status_code=response.status, detail=payload)
                return payload
    except HTTPException:
        raise
    except Exception as e:
        log.exception('Failed to resolve AG-UI approval')
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))


class CodeForm(BaseModel):
    code: str


@router.post('/code/format')
async def format_code(form_data: CodeForm, user=Depends(get_admin_user)):
    try:
        formatted_code = black.format_str(form_data.code, mode=black.Mode())
        return {'code': formatted_code}
    except black.NothingChanged:
        return {'code': form_data.code}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post('/code/execute')
async def execute_code(request: Request, form_data: CodeForm, user=Depends(get_verified_user)):
    if not request.app.state.config.ENABLE_CODE_EXECUTION:
        raise HTTPException(
            status_code=403,
            detail=ERROR_MESSAGES.FEATURE_DISABLED('Code execution'),
        )

    if request.app.state.config.CODE_EXECUTION_ENGINE == 'jupyter':
        output = await execute_code_jupyter(
            request.app.state.config.CODE_EXECUTION_JUPYTER_URL,
            form_data.code,
            (
                request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_TOKEN
                if request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH == 'token'
                else None
            ),
            (
                request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_PASSWORD
                if request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH == 'password'
                else None
            ),
            request.app.state.config.CODE_EXECUTION_JUPYTER_TIMEOUT,
        )

        return output
    else:
        raise HTTPException(
            status_code=400,
            detail=ERROR_MESSAGES.DEFAULT('Code execution engine not supported'),
        )


class MarkdownForm(BaseModel):
    md: str


@router.post('/markdown')
async def get_html_from_markdown(form_data: MarkdownForm, user=Depends(get_verified_user)):
    return {'html': markdown.markdown(form_data.md)}


class ChatForm(BaseModel):
    title: str
    messages: list[dict]


@router.post('/pdf')
async def download_chat_as_pdf(form_data: ChatTitleMessagesForm, user=Depends(get_verified_user)):
    try:
        pdf_bytes = PDFGenerator(form_data).generate_chat_pdf()

        return Response(
            content=pdf_bytes,
            media_type='application/pdf',
            headers={'Content-Disposition': 'attachment;filename=chat.pdf'},
        )
    except Exception as e:
        log.exception(f'Error generating PDF: {e}')
        raise HTTPException(status_code=400, detail=str(e))


@router.get('/db/download')
async def download_db(user=Depends(get_admin_user)):
    if not ENABLE_ADMIN_EXPORT:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=ERROR_MESSAGES.ACCESS_PROHIBITED,
        )
    from open_webui.internal.db import engine

    if engine.name != 'sqlite':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=ERROR_MESSAGES.DB_NOT_SQLITE,
        )
    return FileResponse(
        engine.url.database,
        media_type='application/octet-stream',
        filename='webui.db',
    )
