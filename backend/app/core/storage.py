"""Object-storage client behind a thin abstraction.

Uses the S3 API (boto3) so the same code targets MinIO locally and Azure Blob
(via S3-compatible gateway) or AWS S3 in other environments
(per docs/10_integrations_and_interoperability.md and docs/18_technical_decisions.md).
"""

from functools import lru_cache

import boto3
from botocore.client import Config

from app.core.config import settings


@lru_cache
def get_s3_client():
    """Return a cached boto3 S3 client pointed at the configured endpoint."""
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )
