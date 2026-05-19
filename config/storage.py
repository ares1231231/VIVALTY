"""Media storage backends: local filesystem (dev) or S3-compatible (R2 / AWS)."""

from __future__ import annotations

import os


def use_s3_media() -> bool:
    """True when object storage env vars are set (Cloudflare R2 or AWS S3)."""
    return bool(os.getenv("AWS_STORAGE_BUCKET_NAME", "").strip())


def configure_media_storage() -> dict:
    """Return Django STORAGES['default'] config and optional MEDIA_URL override."""
    if not use_s3_media():
        return {
            "default": {
                "BACKEND": "django.core.files.storage.FileSystemStorage",
            },
            "media_url": None,
        }

    custom_domain = os.getenv("AWS_S3_CUSTOM_DOMAIN", "").strip()
    media_url = None
    if custom_domain:
        media_url = f"https://{custom_domain.rstrip('/')}/"

    return {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": os.getenv("AWS_ACCESS_KEY_ID", ""),
                "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY", ""),
                "bucket_name": os.getenv("AWS_STORAGE_BUCKET_NAME", ""),
                "endpoint_url": os.getenv("AWS_S3_ENDPOINT_URL") or None,
                "region_name": os.getenv("AWS_S3_REGION_NAME", "auto"),
                "custom_domain": custom_domain or None,
                "default_acl": None,
                "querystring_auth": False,
                "file_overwrite": False,
                "object_parameters": {"CacheControl": "max-age=86400"},
            },
        },
        "media_url": media_url,
    }
