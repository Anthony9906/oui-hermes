import os
import shutil
import json
import logging
import mimetypes
import re
from abc import ABC, abstractmethod
from typing import Any, BinaryIO, Tuple, Dict

from open_webui.config import (
    S3_ACCESS_KEY_ID,
    S3_BUCKET_NAME,
    S3_ENDPOINT_URL,
    S3_KEY_PREFIX,
    S3_PUBLIC_BASE_URL,
    S3_REGION_NAME,
    S3_SECRET_ACCESS_KEY,
    S3_USE_ACCELERATE_ENDPOINT,
    S3_ADDRESSING_STYLE,
    S3_ENABLE_TAGGING,
    GCS_BUCKET_NAME,
    GOOGLE_APPLICATION_CREDENTIALS_JSON,
    AZURE_STORAGE_ENDPOINT,
    AZURE_STORAGE_CONTAINER_NAME,
    AZURE_STORAGE_KEY,
    STORAGE_PROVIDER,
    UPLOAD_DIR,
)
from open_webui.constants import ERROR_MESSAGES

log = logging.getLogger(__name__)


class StorageProvider(ABC):
    @abstractmethod
    def get_file(self, file_path: str) -> str:
        pass

    @abstractmethod
    def upload_file(self, file: BinaryIO, filename: str, tags: Dict[str, str]) -> Tuple[bytes, str]:
        pass

    @abstractmethod
    def delete_all_files(self) -> None:
        pass

    @abstractmethod
    def delete_file(self, file_path: str) -> None:
        pass


class LocalStorageProvider(StorageProvider):
    @staticmethod
    def upload_file(file: BinaryIO, filename: str, tags: Dict[str, str]) -> Tuple[bytes, str]:
        contents = file.read()
        if not contents:
            raise ValueError(ERROR_MESSAGES.EMPTY_CONTENT)

        normalized_filename = os.path.normpath(filename).lstrip(os.sep)
        if normalized_filename == '..' or normalized_filename.startswith(f'..{os.sep}'):
            raise ValueError('Invalid upload filename')

        file_path = os.path.abspath(os.path.join(UPLOAD_DIR, normalized_filename))
        upload_dir = os.path.abspath(UPLOAD_DIR)
        if os.path.commonpath([upload_dir, file_path]) != upload_dir:
            raise ValueError('Invalid upload filename')

        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'wb') as f:
            f.write(contents)
        return contents, file_path

    @staticmethod
    def get_file(file_path: str) -> str:
        """Handles downloading of the file from local storage."""
        return file_path

    @staticmethod
    def delete_file(file_path: str) -> None:
        """Handles deletion of the file from local storage."""
        upload_dir = os.path.abspath(UPLOAD_DIR)
        candidate = os.path.abspath(file_path)
        if os.path.commonpath([upload_dir, candidate]) != upload_dir:
            candidate = os.path.join(upload_dir, os.path.basename(file_path))
        file_path = candidate
        if os.path.isfile(file_path):
            os.remove(file_path)
        else:
            log.warning(f'File {file_path} not found in local storage.')

    @staticmethod
    def delete_all_files() -> None:
        """Handles deletion of all files from local storage."""
        if os.path.exists(UPLOAD_DIR):
            for filename in os.listdir(UPLOAD_DIR):
                file_path = os.path.join(UPLOAD_DIR, filename)
                try:
                    if os.path.isfile(file_path) or os.path.islink(file_path):
                        os.unlink(file_path)  # Remove the file or link
                    elif os.path.isdir(file_path):
                        shutil.rmtree(file_path)  # Remove the directory
                except Exception as e:
                    log.exception(f'Failed to delete {file_path}. Reason: {e}')
        else:
            log.warning(f'Directory {UPLOAD_DIR} not found in local storage.')


class S3StorageProvider(StorageProvider):
    def __init__(self, config: dict[str, Any] | None = None):
        import boto3
        from botocore.config import Config

        storage_config = config or {}
        region_name = storage_config.get('region_name') or S3_REGION_NAME
        endpoint_url = storage_config.get('endpoint_url') or S3_ENDPOINT_URL
        access_key_id = storage_config.get('access_key_id') or S3_ACCESS_KEY_ID
        secret_access_key = storage_config.get('secret_access_key') or S3_SECRET_ACCESS_KEY
        addressing_style = storage_config.get('addressing_style') or S3_ADDRESSING_STYLE

        config = Config(
            s3={
                'use_accelerate_endpoint': S3_USE_ACCELERATE_ENDPOINT,
                'addressing_style': addressing_style,
            },
            # KIT change - see https://github.com/boto/boto3/issues/4400#issuecomment-2600742103∆
            request_checksum_calculation='when_required',
            response_checksum_validation='when_required',
        )

        # If access key and secret are provided, use them for authentication
        if access_key_id and secret_access_key:
            self.s3_client = boto3.client(
                's3',
                region_name=region_name,
                endpoint_url=endpoint_url,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                config=config,
            )
        else:
            # If no explicit credentials are provided, fall back to default AWS credentials
            # This supports workload identity (IAM roles for EC2, EKS, etc.)
            self.s3_client = boto3.client(
                's3',
                region_name=region_name,
                endpoint_url=endpoint_url,
                config=config,
            )

        self.bucket_name = storage_config.get('bucket_name') or S3_BUCKET_NAME
        self.key_prefix = storage_config.get('key_prefix') or S3_KEY_PREFIX or ''
        public_base_url = storage_config.get('public_base_url') or S3_PUBLIC_BASE_URL
        self.public_base_url = public_base_url.rstrip('/') if public_base_url else None

    @staticmethod
    def sanitize_tag_value(s: str) -> str:
        """Only include S3 allowed characters."""
        return re.sub(r'[^a-zA-Z0-9 äöüÄÖÜß\+\-=\._:/@]', '', s)

    @staticmethod
    def get_content_type(filename: str) -> str | None:
        extension = os.path.splitext(filename)[1].lower()
        if extension in {'.md', '.markdown'}:
            return 'text/markdown'

        content_type, _ = mimetypes.guess_type(filename)
        return content_type

    def upload_file(self, file: BinaryIO, filename: str, tags: Dict[str, str]) -> Tuple[bytes, str]:
        """Handles uploading of the file to S3 storage."""
        contents, file_path = LocalStorageProvider.upload_file(file, filename, tags)
        s3_key = os.path.join(self.key_prefix, filename)
        try:
            extra_args = {}
            content_type = self.get_content_type(filename)
            if content_type:
                extra_args['ContentType'] = content_type

            self.s3_client.upload_file(file_path, self.bucket_name, s3_key, ExtraArgs=extra_args or None)
            if S3_ENABLE_TAGGING and tags:
                sanitized_tags = {self.sanitize_tag_value(k): self.sanitize_tag_value(v) for k, v in tags.items()}
                tagging = {'TagSet': [{'Key': k, 'Value': v} for k, v in sanitized_tags.items()]}
                self.s3_client.put_object_tagging(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Tagging=tagging,
                )
            return (
                contents,
                f's3://{self.bucket_name}/{s3_key}',
            )
        except Exception as e:
            raise RuntimeError(f'Error uploading file to S3: {e}')

    def get_file(self, file_path: str) -> str:
        """Handles downloading of the file from S3 storage."""
        try:
            s3_key = self._extract_s3_key(file_path)
            local_file_path = self._get_local_file_path(s3_key)
            self.s3_client.download_file(self.bucket_name, s3_key, local_file_path)
            return local_file_path
        except Exception as e:
            raise RuntimeError(f'Error downloading file from S3: {e}')

    def delete_file(self, file_path: str) -> None:
        """Handles deletion of the file from S3 storage."""
        try:
            s3_key = self._extract_s3_key(file_path)
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
        except Exception as e:
            raise RuntimeError(f'Error deleting file from S3: {e}')

        # Always delete from local storage
        LocalStorageProvider.delete_file(file_path)

    def delete_all_files(self) -> None:
        """Handles deletion of all files from S3 storage."""
        try:
            response = self.s3_client.list_objects_v2(Bucket=self.bucket_name)
            if 'Contents' in response:
                for content in response['Contents']:
                    # Skip objects that were not uploaded from open-webui in the first place
                    if not content['Key'].startswith(self.key_prefix):
                        continue

                    self.s3_client.delete_object(Bucket=self.bucket_name, Key=content['Key'])
        except Exception as e:
            raise RuntimeError(f'Error deleting all files from S3: {e}')

        # Always delete from local storage
        LocalStorageProvider.delete_all_files()

    # The s3 key is the name assigned to an object. It excludes the bucket name, but includes the internal path and the file name.
    def _extract_s3_key(self, full_file_path: str) -> str:
        return '/'.join(full_file_path.split('//')[1].split('/')[1:])

    def _get_local_file_path(self, s3_key: str) -> str:
        return os.path.join(UPLOAD_DIR, s3_key.split('/')[-1])

    def get_public_url(self, full_file_path: str) -> str | None:
        if not self.public_base_url:
            return None
        s3_key = self._extract_s3_key(full_file_path)
        return f'{self.public_base_url}/{s3_key}'


class GCSStorageProvider(StorageProvider):
    def __init__(self):
        from google.cloud import storage

        self.bucket_name = GCS_BUCKET_NAME

        if GOOGLE_APPLICATION_CREDENTIALS_JSON:
            self.gcs_client = storage.Client.from_service_account_info(
                info=json.loads(GOOGLE_APPLICATION_CREDENTIALS_JSON)
            )
        else:
            # if no credentials json is provided, credentials will be picked up from the environment
            # if running on local environment, credentials would be user credentials
            # if running on a Compute Engine instance, credentials would be from Google Metadata server
            self.gcs_client = storage.Client()
        self.bucket = self.gcs_client.bucket(GCS_BUCKET_NAME)

    def upload_file(self, file: BinaryIO, filename: str, tags: Dict[str, str]) -> Tuple[bytes, str]:
        """Handles uploading of the file to GCS storage."""
        contents, file_path = LocalStorageProvider.upload_file(file, filename, tags)
        try:
            blob = self.bucket.blob(filename)
            blob.upload_from_filename(file_path)
            return contents, 'gs://' + self.bucket_name + '/' + filename
        except Exception as e:
            raise RuntimeError(f'Error uploading file to GCS: {e}')

    def get_file(self, file_path: str) -> str:
        """Handles downloading of the file from GCS storage."""
        try:
            filename = file_path.removeprefix('gs://').split('/')[1]
            local_file_path = os.path.join(UPLOAD_DIR, filename)
            blob = self.bucket.get_blob(filename)
            blob.download_to_filename(local_file_path)

            return local_file_path
        except Exception as e:
            raise RuntimeError(f'Error downloading file from GCS: {e}')

    def delete_file(self, file_path: str) -> None:
        """Handles deletion of the file from GCS storage."""
        try:
            filename = file_path.removeprefix('gs://').split('/')[1]
            blob = self.bucket.get_blob(filename)
            blob.delete()
        except Exception as e:
            raise RuntimeError(f'Error deleting file from GCS: {e}')

        # Always delete from local storage
        LocalStorageProvider.delete_file(file_path)

    def delete_all_files(self) -> None:
        """Handles deletion of all files from GCS storage."""
        try:
            blobs = self.bucket.list_blobs()

            for blob in blobs:
                blob.delete()

        except Exception as e:
            raise RuntimeError(f'Error deleting all files from GCS: {e}')

        # Always delete from local storage
        LocalStorageProvider.delete_all_files()


class AzureStorageProvider(StorageProvider):
    def __init__(self):
        from azure.identity import DefaultAzureCredential
        from azure.storage.blob import BlobServiceClient

        self.endpoint = AZURE_STORAGE_ENDPOINT
        self.container_name = AZURE_STORAGE_CONTAINER_NAME
        storage_key = AZURE_STORAGE_KEY

        if storage_key:
            # Configure using the Azure Storage Account Endpoint and Key
            self.blob_service_client = BlobServiceClient(account_url=self.endpoint, credential=storage_key)
        else:
            # Configure using the Azure Storage Account Endpoint and DefaultAzureCredential
            # If the key is not configured, then the DefaultAzureCredential will be used to support Managed Identity authentication
            self.blob_service_client = BlobServiceClient(account_url=self.endpoint, credential=DefaultAzureCredential())
        self.container_client = self.blob_service_client.get_container_client(self.container_name)

    def upload_file(self, file: BinaryIO, filename: str, tags: Dict[str, str]) -> Tuple[bytes, str]:
        """Handles uploading of the file to Azure Blob Storage."""
        contents, file_path = LocalStorageProvider.upload_file(file, filename, tags)
        try:
            blob_client = self.container_client.get_blob_client(filename)
            blob_client.upload_blob(contents, overwrite=True)
            return contents, f'{self.endpoint}/{self.container_name}/{filename}'
        except Exception as e:
            raise RuntimeError(f'Error uploading file to Azure Blob Storage: {e}')

    def get_file(self, file_path: str) -> str:
        """Handles downloading of the file from Azure Blob Storage."""
        try:
            filename = file_path.split('/')[-1]
            local_file_path = os.path.join(UPLOAD_DIR, filename)
            blob_client = self.container_client.get_blob_client(filename)
            with open(local_file_path, 'wb') as download_file:
                download_file.write(blob_client.download_blob().readall())
            return local_file_path
        except Exception as e:
            raise RuntimeError(f'Error downloading file from Azure Blob Storage: {e}')

    def delete_file(self, file_path: str) -> None:
        """Handles deletion of the file from Azure Blob Storage."""
        try:
            filename = file_path.split('/')[-1]
            blob_client = self.container_client.get_blob_client(filename)
            blob_client.delete_blob()
        except Exception as e:
            raise RuntimeError(f'Error deleting file from Azure Blob Storage: {e}')

        # Always delete from local storage
        LocalStorageProvider.delete_file(file_path)

    def delete_all_files(self) -> None:
        """Handles deletion of all files from Azure Blob Storage."""
        try:
            blobs = self.container_client.list_blobs()
            for blob in blobs:
                self.container_client.delete_blob(blob.name)
        except Exception as e:
            raise RuntimeError(f'Error deleting all files from Azure Blob Storage: {e}')

        # Always delete from local storage
        LocalStorageProvider.delete_all_files()


def _normalize_storage_config(config: dict[str, Any] | None = None) -> dict[str, Any]:
    config = config or {}
    provider = config.get('provider') or STORAGE_PROVIDER
    return {
        'provider': provider,
        'endpoint_url': config.get('endpoint_url') or S3_ENDPOINT_URL,
        'bucket_name': config.get('bucket_name') or S3_BUCKET_NAME,
        'region_name': config.get('region_name') or S3_REGION_NAME,
        'access_key_id': config.get('access_key_id') or S3_ACCESS_KEY_ID,
        'secret_access_key': config.get('secret_access_key') or S3_SECRET_ACCESS_KEY,
        'addressing_style': config.get('addressing_style') or S3_ADDRESSING_STYLE,
        'key_prefix': config.get('key_prefix') or S3_KEY_PREFIX or '',
        'public_base_url': config.get('public_base_url') or S3_PUBLIC_BASE_URL,
    }


def get_storage_config_from_app_config(app_config) -> dict[str, Any]:
    try:
        return _normalize_storage_config(getattr(app_config, 'STORAGE_CONFIG', None))
    except Exception:
        return _normalize_storage_config()


def get_storage_provider(storage_provider: str, config: dict[str, Any] | None = None):
    config = _normalize_storage_config(config)
    if storage_provider == 'local':
        Storage = LocalStorageProvider()
    elif storage_provider in ('s3', 'r2'):
        Storage = S3StorageProvider(config)
    elif storage_provider == 'gcs':
        Storage = GCSStorageProvider()
    elif storage_provider == 'azure':
        Storage = AzureStorageProvider()
    else:
        raise RuntimeError(f'Unsupported storage provider: {storage_provider}')
    return Storage


def get_storage_provider_from_app_config(app_config):
    config = get_storage_config_from_app_config(app_config)
    return get_storage_provider(config.get('provider') or STORAGE_PROVIDER, config)


def get_storage_provider_for_path(file_path: str, config: dict[str, Any] | None = None):
    config = _normalize_storage_config(config)
    if isinstance(file_path, str) and file_path.startswith('s3://'):
        return get_storage_provider('r2' if config.get('provider') == 'r2' else 's3', config)
    if isinstance(file_path, str) and file_path.startswith('gs://'):
        return get_storage_provider('gcs')
    if isinstance(file_path, str) and file_path.startswith(('http://', 'https://')) and STORAGE_PROVIDER == 'azure':
        return get_storage_provider('azure')
    return Storage


def get_storage_provider_for_path_from_app_config(file_path: str, app_config):
    return get_storage_provider_for_path(file_path, get_storage_config_from_app_config(app_config))


def get_public_url_for_path(file_path: str, config: dict[str, Any] | None = None) -> str | None:
    storage = get_storage_provider_for_path(file_path, config)
    get_public_url = getattr(storage, 'get_public_url', None)
    if callable(get_public_url):
        return get_public_url(file_path)
    return None


def get_public_url_for_path_from_app_config(file_path: str, app_config) -> str | None:
    return get_public_url_for_path(file_path, get_storage_config_from_app_config(app_config))


Storage = get_storage_provider(STORAGE_PROVIDER)
