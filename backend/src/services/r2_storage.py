"""Cloudflare R2 (S3 호환) — Replicate 결과물을 버킷에 옮겨 영구 공개 URL로 바꿉니다."""

from __future__ import annotations

import logging
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import boto3
from botocore.config import Config as BotoCoreConfig
from botocore.exceptions import BotoCoreError, ClientError

from ..utils.config import Settings

logger = logging.getLogger(__name__)

# Replicate 결과 다운로드 상한 — 악/abuse 및 실수 완충.
_MAX_DOWNLOAD_BYTES = 35 * 1024 * 1024
_DOWNLOAD_TIMEOUT_SEC = 120


def _r2_fully_configured(settings: Settings) -> bool:
    return bool(
        (settings.r2_account_id or "").strip()
        and (settings.r2_access_key or "").strip()
        and (settings.r2_secret_key or "").strip()
        and (settings.r2_bucket or "").strip()
        and (settings.r2_public_url or "").strip()
    )


def _download_https(url: str) -> bytes:
    u = url.strip()
    if not u.startswith("https://"):
        raise ValueError("Only HTTPS URLs are supported for mirror download")
    req = Request(
        u,
        headers={
            "User-Agent": "LivingWorldEngine-cover-mirror/1.0",
        },
        method="GET",
    )
    try:
        with urlopen(req, timeout=_DOWNLOAD_TIMEOUT_SEC) as resp:
            chunks: list[bytes] = []
            total = 0
            while True:
                part = resp.read(min(65536, _MAX_DOWNLOAD_BYTES - total + 1))
                if not part:
                    break
                total += len(part)
                if total > _MAX_DOWNLOAD_BYTES:
                    raise ValueError("Downloaded image exceeds size limit")
                chunks.append(part)
    except HTTPError as e:
        raise RuntimeError(f"Image download HTTP {e.code}") from e
    except URLError as e:
        raise RuntimeError(f"Image download failed: {e.reason!r}") from e
    return b"".join(chunks)


def _s3_client(settings: Settings):
    account_id = settings.r2_account_id.strip()
    return boto3.client(
        "s3",
        endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key.strip(),
        aws_secret_access_key=settings.r2_secret_key.strip(),
        region_name="auto",
        config=BotoCoreConfig(signature_version="s3v4"),
    )


def mirror_https_asset_to_permanent_url(
    transient_https_url: str,
    *,
    object_key: str,
    settings: Settings,
    content_type: str = "image/webp",
) -> str:
    """R2 미설정 시 원본 URL. ``object_key`` 는 버킷 루트 기준 슬래시 안 붙임."""
    if not _r2_fully_configured(settings):
        return transient_https_url.strip()

    key = object_key.strip().lstrip("/")
    data = _download_https(transient_https_url)
    if not data:
        raise RuntimeError("Downloaded empty image")

    bucket = settings.r2_bucket.strip()
    try:
        client = _s3_client(settings)
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
        )
    except (ClientError, BotoCoreError) as e:
        logger.exception("R2 put_object failed")
        raise RuntimeError(f"R2 upload failed: {e}") from e

    base = settings.r2_public_url.strip().rstrip("/")
    return f"{base}/{key}"


def mirror_generated_cover_to_permanent_url(
    transient_https_url: str,
    *,
    world_id: uuid.UUID,
    settings: Settings,
    object_suffix: str = ".webp",
) -> str:
    key = f"covers/{world_id}/{uuid.uuid4().hex}{object_suffix}"
    return mirror_https_asset_to_permanent_url(
        transient_https_url,
        object_key=key,
        settings=settings,
    )


def mirror_npc_avatar_to_permanent_url(
    transient_https_url: str,
    *,
    world_id: uuid.UUID,
    npc_key_slug: str,
    settings: Settings,
    object_suffix: str = ".webp",
) -> str:
    key = f"avatars/{world_id}/{npc_key_slug}/{uuid.uuid4().hex}{object_suffix}"
    return mirror_https_asset_to_permanent_url(
        transient_https_url,
        object_key=key,
        settings=settings,
    )
