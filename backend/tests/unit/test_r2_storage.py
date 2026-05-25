"""R2 미러링 — 설정·다운로드·업로드 경로."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from urllib.error import URLError

from backend.src.services.r2_storage import (
    mirror_generated_cover_to_permanent_url,
    mirror_npc_avatar_to_permanent_url,
)
from backend.src.utils.config import Settings


class _FakeHttpBody:
    def __init__(self, data: bytes) -> None:
        self._buf = data

    def read(self, n: int = -1) -> bytes:
        if not self._buf:
            return b""
        if n is None or n < 0:
            out, self._buf = self._buf, b""
            return out
        out, self._buf = self._buf[:n], self._buf[n:]
        return out

    def __enter__(self) -> _FakeHttpBody:
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _r2_settings() -> Settings:
    return Settings().model_copy(
        update={
            "r2_account_id": "testacct",
            "r2_access_key": "access",
            "r2_secret_key": "secret",
            "r2_bucket": "my-bucket",
            "r2_public_url": "https://cdn.example.com",
        }
    )


def test_mirror_returns_original_when_r2_incomplete() -> None:
    s = Settings().model_copy(update={"r2_account_id": "only"})
    url = "https://replicate.delivery/x.webp"
    out = mirror_generated_cover_to_permanent_url(
        url,
        world_id=uuid.uuid4(),
        settings=s,
    )
    assert out == url


def test_mirror_rejects_non_https_source() -> None:
    s = _r2_settings()
    with pytest.raises(ValueError, match="HTTPS"):
        mirror_generated_cover_to_permanent_url(
            "http://insecure/x.webp",
            world_id=uuid.uuid4(),
            settings=s,
        )


def test_mirror_uploads_builds_public_url() -> None:
    wid = uuid.uuid4()
    s = _r2_settings()
    src = "https://replicate.delivery/p/t.webp"
    body = b"fake-webp-bytes"

    mock_s3 = MagicMock()
    with (
        patch(
            "backend.src.services.r2_storage.urlopen",
            return_value=_FakeHttpBody(body),
        ),
        patch("backend.src.services.r2_storage.boto3.client", return_value=mock_s3),
    ):
        out = mirror_generated_cover_to_permanent_url(
            src,
            world_id=wid,
            settings=s,
        )

    assert out.startswith("https://cdn.example.com/covers/")
    assert f"/{wid}/" in out
    assert out.endswith(".webp")
    mock_s3.put_object.assert_called_once()
    kwargs = mock_s3.put_object.call_args.kwargs
    assert kwargs["Bucket"] == "my-bucket"
    assert kwargs["Body"] == body
    assert kwargs["ContentType"] == "image/webp"


def test_mirror_download_error_surfaces() -> None:
    s = _r2_settings()
    with (
        patch(
            "backend.src.services.r2_storage.urlopen",
            side_effect=URLError("boom"),
        ),
        pytest.raises(RuntimeError, match="download failed"),
    ):
        mirror_generated_cover_to_permanent_url(
            "https://ok/x.webp",
            world_id=uuid.uuid4(),
            settings=s,
        )


def test_mirror_npc_avatar_key_layout() -> None:
    wid = uuid.uuid4()
    s = _r2_settings()
    body = b"x"
    mock_s3 = MagicMock()
    with (
        patch("backend.src.services.r2_storage.urlopen", return_value=_FakeHttpBody(body)),
        patch("backend.src.services.r2_storage.boto3.client", return_value=mock_s3),
    ):
        out = mirror_npc_avatar_to_permanent_url(
            "https://replicate.example/o.webp",
            world_id=wid,
            npc_key_slug="kim_sunbae",
            settings=s,
        )
    assert "/avatars/" in out
    assert f"/{wid}/kim_sunbae/" in out
