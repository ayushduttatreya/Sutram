# services/memory-service/app/compression/archiver.py
"""S3 archival for compressed memory items."""
from __future__ import annotations
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import boto3

from app.settings import get_settings


class Archiver:
    def __init__(self) -> None:
        settings = get_settings()
        kwargs: dict[str, Any] = {"region_name": settings.s3_region}
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        self._s3 = boto3.client("s3", **kwargs)
        self._bucket = settings.s3_bucket
        self._prefix = settings.s3_prefix

    def archive_items(
        self,
        tenant_id: uuid.UUID,
        summary_id: uuid.UUID,
        items: list[dict],
    ) -> str:
        """Write compressed items to S3. Returns S3 key."""
        now = datetime.now(timezone.utc)
        key = f"{self._prefix}/{tenant_id}/{now.year}/{now.month:02d}/{summary_id}.json"
        body = json.dumps({
            "summary_id": str(summary_id),
            "tenant_id": str(tenant_id),
            "archived_at": now.isoformat(),
            "items": items,
        }).encode()
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=body)
        return key
