import base64
import os
import random
from pathlib import Path

import uvicorn

KEY_FILE = Path.cwd() / '.webui_secret_key'


def version_callback(value: bool) -> None:
    if value:
        from open_webui.env import VERSION

        print(f'Open WebUI version: {VERSION}')
        raise SystemExit(0)


def main(
    version: bool | None = None,
):
    version_callback(bool(version))


def serve(
    host: str = '0.0.0.0',
    port: int = 8080,
):
    os.environ['FROM_INIT_PY'] = 'true'
    if os.getenv('WEBUI_SECRET_KEY') is None:
        print('Loading WEBUI_SECRET_KEY from file, not provided as an environment variable.')
        if not KEY_FILE.exists():
            print(f'Generating a new secret key and saving it to {KEY_FILE}')
            KEY_FILE.write_bytes(base64.b64encode(random.randbytes(12)))
        print(f'Loading WEBUI_SECRET_KEY from {KEY_FILE}')
        os.environ['WEBUI_SECRET_KEY'] = KEY_FILE.read_text()

    if os.getenv('USE_CUDA_DOCKER', 'false') == 'true':
        print('CUDA is enabled, appending LD_LIBRARY_PATH to include torch/cudnn & cublas libraries.')
        LD_LIBRARY_PATH = os.getenv('LD_LIBRARY_PATH', '').split(':')
        os.environ['LD_LIBRARY_PATH'] = ':'.join(
            LD_LIBRARY_PATH
            + [
                '/usr/local/lib/python3.11/site-packages/torch/lib',
                '/usr/local/lib/python3.11/site-packages/nvidia/cudnn/lib',
            ]
        )
        try:
            import torch

            assert torch.cuda.is_available(), 'CUDA not available'
            print('CUDA seems to be working')
        except Exception as e:
            print(
                'Error when testing CUDA but USE_CUDA_DOCKER is true. '
                'Resetting USE_CUDA_DOCKER to false and removing '
                f'LD_LIBRARY_PATH modifications: {e}'
            )
            os.environ['USE_CUDA_DOCKER'] = 'false'
            os.environ['LD_LIBRARY_PATH'] = ':'.join(LD_LIBRARY_PATH)

    import open_webui.main  # noqa: F401
    from open_webui.env import UVICORN_WORKERS  # Import the workers setting

    uvicorn.run(
        'open_webui.main:app',
        host=host,
        port=port,
        forwarded_allow_ips='*',
        workers=UVICORN_WORKERS,
    )


def dev(
    host: str = '0.0.0.0',
    port: int = 8080,
    reload: bool = True,
):
    uvicorn.run(
        'open_webui.main:app',
        host=host,
        port=port,
        reload=reload,
        forwarded_allow_ips='*',
    )


if __name__ == '__main__':
    app()
