import logging
import copy
import io
import uuid
import asyncio
from fastapi import APIRouter, Depends, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field
import aiohttp

from typing import Optional
from urllib.parse import urlparse

from open_webui.env import AIOHTTP_CLIENT_SESSION_SSL, AIOHTTP_CLIENT_TIMEOUT
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.config import get_config, save_config, async_save_config
from open_webui.config import BannerModel
from open_webui.storage.provider import get_storage_provider

from open_webui.utils.tools import (
    get_tool_server_data,
    get_tool_server_url,
    set_tool_servers,
    set_terminal_servers,
)
from open_webui.utils.mcp.client import MCPClient
from open_webui.models.oauth_sessions import OAuthSessions


from open_webui.utils.oauth import (
    get_discovery_urls,
    get_oauth_client_info_with_dynamic_client_registration,
    get_oauth_client_info_with_static_credentials,
    encrypt_data,
    decrypt_data,
    resolve_oauth_client_info,
    OAuthClientInformationFull,
)
from mcp.shared.auth import OAuthMetadata

router = APIRouter()

log = logging.getLogger(__name__)


############################
# ImportConfig
# Thy configuration come, thy settings be done,
# in production as it is in development.
############################


class ImportConfigForm(BaseModel):
    config: dict


@router.post('/import', response_model=dict)
async def import_config(form_data: ImportConfigForm, user=Depends(get_admin_user)):
    await async_save_config(form_data.config)
    return get_config()


############################
# ExportConfig
############################


@router.get('/export', response_model=dict)
async def export_config(user=Depends(get_admin_user)):
    return get_config()


############################
# Connections Config
############################


class ConnectionsConfigForm(BaseModel):
    ENABLE_BASE_MODELS_CACHE: bool


@router.get('/connections', response_model=ConnectionsConfigForm)
async def get_connections_config(request: Request, user=Depends(get_admin_user)):
    return {
        'ENABLE_BASE_MODELS_CACHE': request.app.state.config.ENABLE_BASE_MODELS_CACHE,
    }


############################
# Storage Config
############################


class StorageConfigResponse(BaseModel):
    provider: str
    endpoint_url: str = ''
    bucket_name: str = ''
    region_name: str = ''
    addressing_style: str = ''
    key_prefix: str = ''
    public_base_url: str = ''
    access_key_configured: bool = False
    secret_key_configured: bool = False


class StorageConfigForm(BaseModel):
    provider: str
    endpoint_url: str = ''
    bucket_name: str = ''
    region_name: str = ''
    access_key_id: Optional[str] = None
    secret_access_key: Optional[str] = None
    addressing_style: str = ''
    key_prefix: str = ''
    public_base_url: str = ''


def _storage_config_response(config: dict) -> StorageConfigResponse:
    return StorageConfigResponse(
        provider=config.get('provider') or 'local',
        endpoint_url=config.get('endpoint_url') or '',
        bucket_name=config.get('bucket_name') or '',
        region_name=config.get('region_name') or '',
        addressing_style=config.get('addressing_style') or '',
        key_prefix=config.get('key_prefix') or '',
        public_base_url=config.get('public_base_url') or '',
        access_key_configured=bool(config.get('access_key_id')),
        secret_key_configured=bool(config.get('secret_access_key')),
    )


def _merge_storage_config(current: dict, form_data: StorageConfigForm) -> dict:
    provider = (form_data.provider or '').strip().lower()
    if provider not in {'r2', 's3'}:
        raise HTTPException(status_code=400, detail='Storage provider must be r2 or s3.')

    next_config = {
        'provider': provider,
        'endpoint_url': form_data.endpoint_url.strip(),
        'bucket_name': form_data.bucket_name.strip(),
        'region_name': form_data.region_name.strip(),
        'access_key_id': (
            form_data.access_key_id.strip()
            if form_data.access_key_id is not None and form_data.access_key_id.strip()
            else current.get('access_key_id', '')
        ),
        'secret_access_key': (
            form_data.secret_access_key.strip()
            if form_data.secret_access_key is not None and form_data.secret_access_key.strip()
            else current.get('secret_access_key', '')
        ),
        'addressing_style': form_data.addressing_style.strip(),
        'key_prefix': form_data.key_prefix.strip().strip('/'),
        'public_base_url': form_data.public_base_url.strip().rstrip('/'),
    }

    required = {
        'endpoint_url': 'Endpoint URL is required.',
        'bucket_name': 'Bucket name is required.',
        'access_key_id': 'Access key is required.',
        'secret_access_key': 'Secret key is required.',
        'public_base_url': 'Public base URL is required.',
    }
    for field, message in required.items():
        if not next_config.get(field):
            raise HTTPException(status_code=400, detail=message)

    if not next_config['public_base_url'].startswith(('http://', 'https://')):
        raise HTTPException(status_code=400, detail='Public base URL must start with http:// or https://.')

    return next_config


async def _verify_public_url_accessible(public_url: str) -> None:
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout, trust_env=True) as session:
        async with session.head(public_url, ssl=AIOHTTP_CLIENT_SESSION_SSL) as response:
            if response.status < 400:
                return
            if response.status != 405:
                raise HTTPException(
                    status_code=400,
                    detail=f'Public URL is not accessible: HTTP {response.status}.',
                )

        async with session.get(
            public_url,
            headers={'Range': 'bytes=0-0'},
            ssl=AIOHTTP_CLIENT_SESSION_SSL,
        ) as response:
            if response.status < 400:
                return
            raise HTTPException(
                status_code=400,
                detail=f'Public URL is not accessible: HTTP {response.status}.',
            )


@router.get('/storage', response_model=StorageConfigResponse)
async def get_storage_config(request: Request, user=Depends(get_admin_user)):
    return _storage_config_response(request.app.state.config.STORAGE_CONFIG or {})


@router.post('/storage', response_model=StorageConfigResponse)
async def set_storage_config(request: Request, form_data: StorageConfigForm, user=Depends(get_admin_user)):
    current = request.app.state.config.STORAGE_CONFIG or {}
    next_config = _merge_storage_config(current, form_data)
    request.app.state.config.STORAGE_CONFIG = next_config
    return _storage_config_response(next_config)


@router.post('/storage/verify')
async def verify_storage_config(request: Request, form_data: StorageConfigForm, user=Depends(get_admin_user)):
    current = request.app.state.config.STORAGE_CONFIG or {}
    next_config = _merge_storage_config(current, form_data)
    storage = get_storage_provider(next_config['provider'], next_config)
    filename = f'open-webui-storage-verify-{uuid.uuid4().hex}.txt'
    storage_path = None
    public_url = None

    try:
        _, storage_path = await asyncio.to_thread(
            storage.upload_file,
            io.BytesIO(b'open-webui storage verification'),
            filename,
            {'OpenWebUI-Storage-Verify': 'true'},
        )
        public_url = storage.get_public_url(storage_path)
        if not public_url:
            raise HTTPException(status_code=400, detail='Public URL could not be generated.')

        if not urlparse(public_url).path.lower().endswith('.txt'):
            raise HTTPException(status_code=400, detail='Public URL must preserve the filename extension.')

        await _verify_public_url_accessible(public_url)

        return {'status': True, 'public_url': public_url}
    finally:
        if storage_path:
            try:
                await asyncio.to_thread(storage.delete_file, storage_path)
            except Exception as e:
                log.debug(f'Failed to delete storage verification object: {e}')


@router.post('/connections', response_model=ConnectionsConfigForm)
async def set_connections_config(
    request: Request,
    form_data: ConnectionsConfigForm,
    user=Depends(get_admin_user),
):
    request.app.state.config.ENABLE_BASE_MODELS_CACHE = form_data.ENABLE_BASE_MODELS_CACHE

    return {
        'ENABLE_BASE_MODELS_CACHE': request.app.state.config.ENABLE_BASE_MODELS_CACHE,
    }


class OAuthClientRegistrationForm(BaseModel):
    url: str
    client_id: str
    client_name: Optional[str] = None
    client_secret: Optional[str] = None


@router.post('/oauth/clients/register')
async def register_oauth_client(
    request: Request,
    form_data: OAuthClientRegistrationForm,
    type: Optional[str] = None,
    user=Depends(get_admin_user),
):
    try:
        oauth_client_id = form_data.client_id
        if type:
            oauth_client_id = f'{type}:{form_data.client_id}'

        if form_data.client_secret:
            # Static credentials: skip dynamic registration, build from provided credentials
            oauth_client_info = await get_oauth_client_info_with_static_credentials(
                request,
                oauth_client_id,
                form_data.url,
                oauth_client_id=form_data.client_id,
                oauth_client_secret=form_data.client_secret,
            )
        else:
            oauth_client_info = await get_oauth_client_info_with_dynamic_client_registration(
                request, oauth_client_id, form_data.url
            )
        return {
            'status': True,
            'oauth_client_info': encrypt_data(oauth_client_info.model_dump(mode='json')),
        }
    except Exception as e:
        log.debug(f'Failed to register OAuth client: {e}')
        raise HTTPException(
            status_code=400,
            detail=f'Failed to register OAuth client',
        )


############################
# ToolServers Config
############################


class ToolServerConnection(BaseModel):
    url: str
    path: str
    type: Optional[str] = 'openapi'  # openapi, mcp
    auth_type: Optional[str]
    headers: Optional[dict | str] = None
    key: Optional[str]
    config: Optional[dict]

    model_config = ConfigDict(extra='allow')


class ToolServersConfigForm(BaseModel):
    TOOL_SERVER_CONNECTIONS: list[ToolServerConnection]


@router.get('/tool_servers', response_model=ToolServersConfigForm)
async def get_tool_servers_config(request: Request, user=Depends(get_admin_user)):
    return {
        'TOOL_SERVER_CONNECTIONS': request.app.state.config.TOOL_SERVER_CONNECTIONS,
    }


@router.post('/tool_servers', response_model=ToolServersConfigForm)
async def set_tool_servers_config(
    request: Request,
    form_data: ToolServersConfigForm,
    user=Depends(get_admin_user),
):
    for connection in request.app.state.config.TOOL_SERVER_CONNECTIONS:
        server_type = connection.get('type', 'openapi')
        auth_type = connection.get('auth_type', 'none')

        if auth_type in ('oauth_2.1', 'oauth_2.1_static'):
            # Remove existing OAuth clients for tool servers
            server_id = connection.get('info', {}).get('id')
            client_key = f'{server_type}:{server_id}'

            try:
                request.app.state.oauth_client_manager.remove_client(client_key)
            except Exception:
                pass

    # Set new tool server connections
    request.app.state.config.TOOL_SERVER_CONNECTIONS = [
        connection.model_dump() for connection in form_data.TOOL_SERVER_CONNECTIONS
    ]

    await set_tool_servers(request)

    for connection in request.app.state.config.TOOL_SERVER_CONNECTIONS:
        server_type = connection.get('type', 'openapi')
        if server_type == 'mcp':
            server_id = connection.get('info', {}).get('id')
            auth_type = connection.get('auth_type', 'none')

            if auth_type in ('oauth_2.1', 'oauth_2.1_static') and server_id:
                try:
                    oauth_client_info = resolve_oauth_client_info(connection)
                    request.app.state.oauth_client_manager.add_client(
                        f'{server_type}:{server_id}',
                        OAuthClientInformationFull(**oauth_client_info),
                    )
                except Exception as e:
                    log.debug(f'Failed to add OAuth client for MCP tool server: {e}')
                    continue

    return {
        'TOOL_SERVER_CONNECTIONS': request.app.state.config.TOOL_SERVER_CONNECTIONS,
    }


class TerminalServerConnection(BaseModel):
    id: Optional[str] = ''
    name: Optional[str] = ''

    enabled: Optional[bool] = True

    url: str
    path: Optional[str] = '/openapi.json'

    key: Optional[str] = ''
    auth_type: Optional[str] = 'bearer'

    config: Optional[dict] = None

    # Orchestrator policy fields
    server_type: Optional[str] = None  # "orchestrator", "terminal"
    policy_id: Optional[str] = None
    policy: Optional[dict] = None  # cached policy data

    model_config = ConfigDict(extra='allow')


class TerminalServersConfigForm(BaseModel):
    TERMINAL_SERVER_CONNECTIONS: list[TerminalServerConnection]


@router.get('/terminal_servers')
async def get_terminal_servers_config(request: Request, user=Depends(get_admin_user)):
    return {
        'TERMINAL_SERVER_CONNECTIONS': request.app.state.config.TERMINAL_SERVER_CONNECTIONS,
    }


@router.post('/terminal_servers')
async def set_terminal_servers_config(
    request: Request,
    form_data: TerminalServersConfigForm,
    user=Depends(get_admin_user),
):
    request.app.state.config.TERMINAL_SERVER_CONNECTIONS = [
        connection.model_dump() for connection in form_data.TERMINAL_SERVER_CONNECTIONS
    ]

    await set_terminal_servers(request)

    return {
        'TERMINAL_SERVER_CONNECTIONS': request.app.state.config.TERMINAL_SERVER_CONNECTIONS,
    }


@router.post('/terminal_servers/verify')
async def verify_terminal_server_connection(
    request: Request, form_data: TerminalServerConnection, user=Depends(get_admin_user)
):
    """
    Verify the connection to a terminal server by detecting its type.

    Tries GET {url}/api/v1/policies (orchestrator) then GET {url}/api/config
    (plain terminal).  Returns ``{status: true, type: "orchestrator"|"terminal"}``.
    """
    base_url = (form_data.url or '').rstrip('/')
    if not base_url:
        raise HTTPException(status_code=400, detail='Terminal server URL is required')

    headers = {}
    if form_data.auth_type == 'bearer' and form_data.key:
        headers['Authorization'] = f'Bearer {form_data.key}'

    try:
        async with aiohttp.ClientSession(
            trust_env=True,
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
        ) as session:
            # Orchestrators expose a policies API; plain terminals don't.
            try:
                async with session.get(
                    f'{base_url}/api/v1/policies', headers=headers, ssl=AIOHTTP_CLIENT_SESSION_SSL
                ) as resp:
                    if resp.ok:
                        return {'status': True, 'type': 'orchestrator'}
            except Exception:
                pass

            # Fall back to open-terminal config endpoint.
            try:
                async with session.get(
                    f'{base_url}/api/config', headers=headers, ssl=AIOHTTP_CLIENT_SESSION_SSL
                ) as resp:
                    if resp.ok:
                        return {'status': True, 'type': 'terminal'}
            except Exception:
                pass

    except Exception as e:
        log.debug(f'Failed to connect to the terminal server: {e}')

    raise HTTPException(status_code=400, detail='Failed to connect to the terminal server')


class TerminalServerPolicyForm(BaseModel):
    url: str
    key: Optional[str] = ''
    auth_type: Optional[str] = 'bearer'
    policy_id: str
    policy_data: dict


@router.post('/terminal_servers/policy')
async def put_terminal_server_policy(
    request: Request, form_data: TerminalServerPolicyForm, user=Depends(get_admin_user)
):
    """
    Proxy a policy PUT to an orchestrator terminal server.
    """
    base_url = (form_data.url or '').rstrip('/')
    if not base_url:
        raise HTTPException(status_code=400, detail='Terminal server URL is required')

    headers = {'Content-Type': 'application/json'}
    if form_data.auth_type == 'bearer' and form_data.key:
        headers['Authorization'] = f'Bearer {form_data.key}'

    try:
        async with aiohttp.ClientSession(
            trust_env=True,
            timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
        ) as session:
            policy_url = f'{base_url}/api/v1/policies/{form_data.policy_id}'
            async with session.put(
                policy_url, headers=headers, json=form_data.policy_data, ssl=AIOHTTP_CLIENT_SESSION_SSL
            ) as resp:
                if resp.ok:
                    return await resp.json()
                detail = await resp.text()
                raise HTTPException(status_code=resp.status, detail=detail)
    except HTTPException:
        raise
    except Exception as e:
        log.debug(f'Failed to save policy to terminal server: {e}')
        raise HTTPException(status_code=400, detail='Failed to save policy to terminal server')


@router.post('/tool_servers/verify')
async def verify_tool_servers_config(request: Request, form_data: ToolServerConnection, user=Depends(get_admin_user)):
    """
    Verify the connection to the tool server.
    """
    try:
        if form_data.type == 'mcp':
            if form_data.auth_type in ('oauth_2.1', 'oauth_2.1_static'):
                discovery_urls = await get_discovery_urls(form_data.url)
                for discovery_url in discovery_urls:
                    log.debug(f'Trying to fetch OAuth 2.1 discovery document from {discovery_url}')
                    async with aiohttp.ClientSession(
                        trust_env=True,
                        timeout=aiohttp.ClientTimeout(total=AIOHTTP_CLIENT_TIMEOUT),
                    ) as session:
                        async with session.get(
                            discovery_url, ssl=AIOHTTP_CLIENT_SESSION_SSL
                        ) as oauth_server_metadata_response:
                            if oauth_server_metadata_response.status == 200:
                                try:
                                    oauth_server_metadata = OAuthMetadata.model_validate(
                                        await oauth_server_metadata_response.json()
                                    )
                                    return {
                                        'status': True,
                                        'oauth_server_metadata': oauth_server_metadata.model_dump(mode='json'),
                                    }
                                except Exception as e:
                                    log.info(f'Failed to parse OAuth 2.1 discovery document: {e}')
                                    raise HTTPException(
                                        status_code=400,
                                        detail=f'Failed to parse OAuth 2.1 discovery document from {discovery_url}',
                                    )

                raise HTTPException(
                    status_code=400,
                    detail=f'Failed to fetch OAuth 2.1 discovery document from {discovery_urls}',
                )
            else:
                try:
                    client = MCPClient()
                    headers = None

                    token = None
                    if form_data.auth_type == 'bearer':
                        token = form_data.key
                    elif form_data.auth_type == 'session':
                        token = request.state.token.credentials
                    elif form_data.auth_type == 'system_oauth':
                        oauth_token = None
                        try:
                            if request.cookies.get('oauth_session_id', None):
                                oauth_token = await request.app.state.oauth_manager.get_oauth_token(
                                    user.id,
                                    request.cookies.get('oauth_session_id', None),
                                )

                                if oauth_token:
                                    token = oauth_token.get('access_token', '')
                        except Exception as e:
                            pass
                    if token:
                        headers = {'Authorization': f'Bearer {token}'}

                    if form_data.headers and isinstance(form_data.headers, dict):
                        if headers is None:
                            headers = {}
                        headers.update(form_data.headers)

                    await client.connect(form_data.url, headers=headers)
                    specs = await client.list_tool_specs()
                    return {
                        'status': True,
                        'specs': specs,
                    }
                except Exception as e:
                    log.debug(f'Failed to create MCP client: {e}')
                    raise HTTPException(
                        status_code=400,
                        detail=f'Failed to create MCP client',
                    )
                finally:
                    if client:
                        await client.disconnect()
        else:  # openapi
            token = None
            headers = None
            if form_data.auth_type == 'bearer':
                token = form_data.key
            elif form_data.auth_type == 'session':
                token = request.state.token.credentials
            elif form_data.auth_type == 'system_oauth':
                try:
                    if request.cookies.get('oauth_session_id', None):
                        oauth_token = await request.app.state.oauth_manager.get_oauth_token(
                            user.id,
                            request.cookies.get('oauth_session_id', None),
                        )

                        if oauth_token:
                            token = oauth_token.get('access_token', '')

                except Exception as e:
                    pass

            if token:
                headers = {'Authorization': f'Bearer {token}'}

            if form_data.headers and isinstance(form_data.headers, dict):
                if headers is None:
                    headers = {}
                headers.update(form_data.headers)

            url = get_tool_server_url(form_data.url, form_data.path)
            return await get_tool_server_data(url, headers=headers)
    except HTTPException as e:
        raise e
    except Exception as e:
        log.debug(f'Failed to connect to the tool server: {e}')
        raise HTTPException(
            status_code=400,
            detail=f'Failed to connect to the tool server',
        )


############################
# CodeInterpreterConfig
############################
class CodeInterpreterConfigForm(BaseModel):
    ENABLE_CODE_EXECUTION: bool
    CODE_EXECUTION_ENGINE: str
    CODE_EXECUTION_JUPYTER_URL: Optional[str]
    CODE_EXECUTION_JUPYTER_AUTH: Optional[str]
    CODE_EXECUTION_JUPYTER_AUTH_TOKEN: Optional[str]
    CODE_EXECUTION_JUPYTER_AUTH_PASSWORD: Optional[str]
    CODE_EXECUTION_JUPYTER_TIMEOUT: Optional[int]
    ENABLE_CODE_INTERPRETER: bool
    CODE_INTERPRETER_ENGINE: str
    CODE_INTERPRETER_PROMPT_TEMPLATE: Optional[str]
    CODE_INTERPRETER_JUPYTER_URL: Optional[str]
    CODE_INTERPRETER_JUPYTER_AUTH: Optional[str]
    CODE_INTERPRETER_JUPYTER_AUTH_TOKEN: Optional[str]
    CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD: Optional[str]
    CODE_INTERPRETER_JUPYTER_TIMEOUT: Optional[int]


@router.get('/code_execution', response_model=CodeInterpreterConfigForm)
async def get_code_execution_config(request: Request, user=Depends(get_admin_user)):
    return {
        'ENABLE_CODE_EXECUTION': request.app.state.config.ENABLE_CODE_EXECUTION,
        'CODE_EXECUTION_ENGINE': request.app.state.config.CODE_EXECUTION_ENGINE,
        'CODE_EXECUTION_JUPYTER_URL': request.app.state.config.CODE_EXECUTION_JUPYTER_URL,
        'CODE_EXECUTION_JUPYTER_AUTH': request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH,
        'CODE_EXECUTION_JUPYTER_AUTH_TOKEN': request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_TOKEN,
        'CODE_EXECUTION_JUPYTER_AUTH_PASSWORD': request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_PASSWORD,
        'CODE_EXECUTION_JUPYTER_TIMEOUT': request.app.state.config.CODE_EXECUTION_JUPYTER_TIMEOUT,
        'ENABLE_CODE_INTERPRETER': request.app.state.config.ENABLE_CODE_INTERPRETER,
        'CODE_INTERPRETER_ENGINE': request.app.state.config.CODE_INTERPRETER_ENGINE,
        'CODE_INTERPRETER_PROMPT_TEMPLATE': request.app.state.config.CODE_INTERPRETER_PROMPT_TEMPLATE,
        'CODE_INTERPRETER_JUPYTER_URL': request.app.state.config.CODE_INTERPRETER_JUPYTER_URL,
        'CODE_INTERPRETER_JUPYTER_AUTH': request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH,
        'CODE_INTERPRETER_JUPYTER_AUTH_TOKEN': request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_TOKEN,
        'CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD': request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD,
        'CODE_INTERPRETER_JUPYTER_TIMEOUT': request.app.state.config.CODE_INTERPRETER_JUPYTER_TIMEOUT,
    }


@router.post('/code_execution', response_model=CodeInterpreterConfigForm)
async def set_code_execution_config(
    request: Request, form_data: CodeInterpreterConfigForm, user=Depends(get_admin_user)
):
    request.app.state.config.ENABLE_CODE_EXECUTION = form_data.ENABLE_CODE_EXECUTION

    request.app.state.config.CODE_EXECUTION_ENGINE = form_data.CODE_EXECUTION_ENGINE
    request.app.state.config.CODE_EXECUTION_JUPYTER_URL = form_data.CODE_EXECUTION_JUPYTER_URL
    request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH = form_data.CODE_EXECUTION_JUPYTER_AUTH
    request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_TOKEN = form_data.CODE_EXECUTION_JUPYTER_AUTH_TOKEN
    request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_PASSWORD = form_data.CODE_EXECUTION_JUPYTER_AUTH_PASSWORD
    request.app.state.config.CODE_EXECUTION_JUPYTER_TIMEOUT = form_data.CODE_EXECUTION_JUPYTER_TIMEOUT

    request.app.state.config.ENABLE_CODE_INTERPRETER = form_data.ENABLE_CODE_INTERPRETER
    request.app.state.config.CODE_INTERPRETER_ENGINE = form_data.CODE_INTERPRETER_ENGINE
    request.app.state.config.CODE_INTERPRETER_PROMPT_TEMPLATE = form_data.CODE_INTERPRETER_PROMPT_TEMPLATE

    request.app.state.config.CODE_INTERPRETER_JUPYTER_URL = form_data.CODE_INTERPRETER_JUPYTER_URL

    request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH = form_data.CODE_INTERPRETER_JUPYTER_AUTH

    request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_TOKEN = form_data.CODE_INTERPRETER_JUPYTER_AUTH_TOKEN
    request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD = form_data.CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD
    request.app.state.config.CODE_INTERPRETER_JUPYTER_TIMEOUT = form_data.CODE_INTERPRETER_JUPYTER_TIMEOUT

    return {
        'ENABLE_CODE_EXECUTION': request.app.state.config.ENABLE_CODE_EXECUTION,
        'CODE_EXECUTION_ENGINE': request.app.state.config.CODE_EXECUTION_ENGINE,
        'CODE_EXECUTION_JUPYTER_URL': request.app.state.config.CODE_EXECUTION_JUPYTER_URL,
        'CODE_EXECUTION_JUPYTER_AUTH': request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH,
        'CODE_EXECUTION_JUPYTER_AUTH_TOKEN': request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_TOKEN,
        'CODE_EXECUTION_JUPYTER_AUTH_PASSWORD': request.app.state.config.CODE_EXECUTION_JUPYTER_AUTH_PASSWORD,
        'CODE_EXECUTION_JUPYTER_TIMEOUT': request.app.state.config.CODE_EXECUTION_JUPYTER_TIMEOUT,
        'ENABLE_CODE_INTERPRETER': request.app.state.config.ENABLE_CODE_INTERPRETER,
        'CODE_INTERPRETER_ENGINE': request.app.state.config.CODE_INTERPRETER_ENGINE,
        'CODE_INTERPRETER_PROMPT_TEMPLATE': request.app.state.config.CODE_INTERPRETER_PROMPT_TEMPLATE,
        'CODE_INTERPRETER_JUPYTER_URL': request.app.state.config.CODE_INTERPRETER_JUPYTER_URL,
        'CODE_INTERPRETER_JUPYTER_AUTH': request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH,
        'CODE_INTERPRETER_JUPYTER_AUTH_TOKEN': request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_TOKEN,
        'CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD': request.app.state.config.CODE_INTERPRETER_JUPYTER_AUTH_PASSWORD,
        'CODE_INTERPRETER_JUPYTER_TIMEOUT': request.app.state.config.CODE_INTERPRETER_JUPYTER_TIMEOUT,
    }


############################
# SetDefaultModels
############################
class ModelsConfigForm(BaseModel):
    DEFAULT_MODELS: Optional[str]
    DEFAULT_PINNED_MODELS: Optional[str]
    MODEL_ORDER_LIST: Optional[list[str]]
    DEFAULT_MODEL_METADATA: Optional[dict] = None
    DEFAULT_MODEL_PARAMS: Optional[dict] = None


@router.get('/models/defaults')
async def get_models_defaults(request: Request, user=Depends(get_verified_user)):
    return {
        'DEFAULT_MODEL_METADATA': request.app.state.config.DEFAULT_MODEL_METADATA,
    }


@router.get('/models', response_model=ModelsConfigForm)
async def get_models_config(request: Request, user=Depends(get_admin_user)):
    return {
        'DEFAULT_MODELS': request.app.state.config.DEFAULT_MODELS,
        'DEFAULT_PINNED_MODELS': request.app.state.config.DEFAULT_PINNED_MODELS,
        'MODEL_ORDER_LIST': request.app.state.config.MODEL_ORDER_LIST,
        'DEFAULT_MODEL_METADATA': request.app.state.config.DEFAULT_MODEL_METADATA,
        'DEFAULT_MODEL_PARAMS': request.app.state.config.DEFAULT_MODEL_PARAMS,
    }


@router.post('/models', response_model=ModelsConfigForm)
async def set_models_config(request: Request, form_data: ModelsConfigForm, user=Depends(get_admin_user)):
    request.app.state.config.DEFAULT_MODELS = form_data.DEFAULT_MODELS
    request.app.state.config.DEFAULT_PINNED_MODELS = form_data.DEFAULT_PINNED_MODELS
    request.app.state.config.MODEL_ORDER_LIST = form_data.MODEL_ORDER_LIST
    request.app.state.config.DEFAULT_MODEL_METADATA = form_data.DEFAULT_MODEL_METADATA
    request.app.state.config.DEFAULT_MODEL_PARAMS = form_data.DEFAULT_MODEL_PARAMS
    return {
        'DEFAULT_MODELS': request.app.state.config.DEFAULT_MODELS,
        'DEFAULT_PINNED_MODELS': request.app.state.config.DEFAULT_PINNED_MODELS,
        'MODEL_ORDER_LIST': request.app.state.config.MODEL_ORDER_LIST,
        'DEFAULT_MODEL_METADATA': request.app.state.config.DEFAULT_MODEL_METADATA,
        'DEFAULT_MODEL_PARAMS': request.app.state.config.DEFAULT_MODEL_PARAMS,
    }


class PromptSuggestionLocale(BaseModel):
    title: list[str] = Field(default_factory=list)
    content: str = ''


class PromptSuggestion(BaseModel):
    id: Optional[str] = None
    title: list[str]
    content: str
    locales: Optional[dict[str, PromptSuggestionLocale]] = None


class SetDefaultSuggestionsForm(BaseModel):
    suggestions: list[PromptSuggestion]


@router.post('/suggestions', response_model=list[PromptSuggestion])
async def set_default_suggestions(
    request: Request,
    form_data: SetDefaultSuggestionsForm,
    user=Depends(get_admin_user),
):
    data = form_data.model_dump()
    request.app.state.config.DEFAULT_PROMPT_SUGGESTIONS = data['suggestions']
    return request.app.state.config.DEFAULT_PROMPT_SUGGESTIONS


############################
# SetBanners
############################


class SetBannersForm(BaseModel):
    banners: list[BannerModel]


@router.post('/banners', response_model=list[BannerModel])
async def set_banners(
    request: Request,
    form_data: SetBannersForm,
    user=Depends(get_admin_user),
):
    data = form_data.model_dump()
    request.app.state.config.BANNERS = data['banners']
    return request.app.state.config.BANNERS


@router.get('/banners', response_model=list[BannerModel])
async def get_banners(
    request: Request,
    user=Depends(get_verified_user),
):
    return request.app.state.config.BANNERS
