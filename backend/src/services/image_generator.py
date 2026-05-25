"""Replicate 기반 이미지 생성 — 월드 커버(Phase 1), NPC 초상(Phase 2)."""

from __future__ import annotations

import re
from typing import Any, cast

import replicate
from replicate.exceptions import ReplicateError

from ..utils.config import Settings


# 키워드 기반 프롬프트에 붙이는 고정 지시 (텍스트·로고 제외 등)
_COVER_SUFFIX_EN = (
    "Cinematic atmospheric key art for an interactive story scene, wide composition, "
    "cohesive lighting and color grade, high detail, painterly digital illustration. "
    "No text, no logos, no watermarks, no speech bubbles, no UI."
)

_NPC_AVATAR_SUFFIX_EN = (
    "Portrait, head-and-shoulders crop, expressive character focused illustration — "
    "visual novel roster art style with smooth shading. Soft neutral backdrop. "
    "Single centered subject. No frame, no text, no logos, no watermark, no UI."
)


def build_world_cover_prompt(w: Any) -> str:
    """월드 DB row → 영어 중심 Flux 프롬프트."""
    wd = w.world_data if isinstance(w.world_data, dict) else {}
    hooks: list[str] = []
    name = getattr(w, "name", None)
    if isinstance(name, str) and name.strip():
        hooks.append(f"Setting title: {name.strip()}.")
    desc = wd.get("description")
    if isinstance(desc, str) and desc.strip():
        hooks.append(f"Summary: {desc.strip()[:400]}.")
    raw_ws = wd.get("world_setting")
    if isinstance(raw_ws, str) and raw_ws.strip():
        hooks.append(f"World tone: {raw_ws.strip()[:500]}.")
    elif isinstance(raw_ws, list):
        parts = [str(x).strip() for x in raw_ws if isinstance(x, str) and str(x).strip()]
        if parts:
            hooks.append(f"World tone: {' '.join(parts)[:500]}.")
    wt = wd.get("time")
    if isinstance(wt, str) and wt.strip():
        hooks.append(f"When: {wt.strip()}.")
    raw_genres = getattr(w, "genres", None)
    if isinstance(raw_genres, list):
        gparts = [str(x).strip() for x in raw_genres if isinstance(x, str) and str(x).strip()]
        if gparts:
            hooks.append(f"Genres / mood tags: {', '.join(gparts[:8])}.")
    core = " ".join(hooks) if hooks else "Original interactive fiction world scene."
    prompt = f"{core} {_COVER_SUFFIX_EN}"
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return prompt[:3500]


def build_npc_avatar_prompt(w: Any, npc: dict[str, Any]) -> str:
    """월드·NPC dict → 1:1 초상용 영어 프롬프트."""
    wd = w.world_data if isinstance(w.world_data, dict) else {}
    bits: list[str] = []
    wname = getattr(w, "name", None)
    if isinstance(wname, str) and wname.strip():
        bits.append(f"Story world: {wname.strip()}.")
    desc = wd.get("description")
    if isinstance(desc, str) and desc.strip():
        bits.append(f"World logline: {desc.strip()[:240]}.")

    n = npc.get("name")
    if isinstance(n, str) and n.strip():
        bits.append(f"Character name: {n.strip()}.")
    role = npc.get("role")
    if isinstance(role, str) and role.strip():
        bits.append(f"Role: {role.strip()}.")

    portrait_visual = npc.get("appearance_for_ai")
    if isinstance(portrait_visual, str) and portrait_visual.strip():
        bits.append(f"Visual appearance for portrait (author intent): {portrait_visual.strip()[:800]}.")
    else:
        for key in ("personality", "background", "appearance", "description"):
            v = npc.get(key)
            if isinstance(v, str) and v.strip():
                bits.append(f"{key.capitalize()}: {v.strip()[:400]}.")
                break

    core = " ".join(bits) if bits else "Original interactive fiction character."
    prompt = f"{core} {_NPC_AVATAR_SUFFIX_EN}"
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return prompt[:3500]


def _extract_replicate_https_url(out: Any) -> str | None:
    """Replicate `client.run` 반환 타입 차이 대응 — str / list 중첩 / dict(url) / 객체 .url 등."""
    if out is None:
        return None
    if isinstance(out, str):
        u = out.strip()
        return u if u.startswith("https://") else None
    if isinstance(out, (list, tuple)):
        for item in out:
            got = _extract_replicate_https_url(item)
            if got:
                return got
        return None
    if isinstance(out, dict):
        for k in ("url", "uri"):
            v = out.get(k)
            if isinstance(v, str) and v.strip().startswith("https://"):
                return v.strip()
        for k in ("output", "outputs", "image", "images"):
            got = _extract_replicate_https_url(out.get(k))
            if got:
                return got
        return None
    url_attr = getattr(out, "url", None)
    if isinstance(url_attr, str) and url_attr.strip().startswith("https://"):
        return url_attr.strip()
    return None


def _npc_avatar_replicate_input(*, prompt: str, model_id: str, settings: Settings) -> dict[str, Any]:
    m = model_id.lower()
    if "sdxl" in m:
        px = max(768, min(1024, int(settings.image_npc_avatar_pixels)))
        return {"prompt": prompt, "width": px, "height": px}
    if "flux-schnell" in m:
        return {"prompt": prompt, "aspect_ratio": "1:1"}
    inp: dict[str, Any] = {"prompt": prompt, "aspect_ratio": "1:1"}
    if "flux" in m:
        q = max(1, min(100, int(settings.image_npc_avatar_output_quality)))
        inp["output_quality"] = q
        inp["output_format"] = "webp"
    return inp


def _raise_replicate_friendly(exc: ReplicateError, *, fallback: str) -> None:
    """Replicate API 오류 → RuntimeError 로 통일 worlds 라우트가 detail 로 전달."""
    if exc.status == 402:
        raise RuntimeError(
            "Replicate 계정 크레딧이 부족합니다. "
            "https://replicate.com/account/billing 에서 충전한 뒤 몇 분 기다렸다가 다시 시도해 주세요."
        ) from exc
    blob_l = f"{exc.title or ''} {exc.detail or ''}".lower()
    if exc.status == 429 or "throttl" in blob_l or "rate limit" in blob_l:
        raise RuntimeError(
            "Replicate 쪽 요청 속도 제한(Throttling)에 걸렸습니다. 잔여 크레딧이 적으면 분당 허용 횟수가 크게 줄고, "
            "연속 요청 시 몇 초~수십 초 간격을 두어야 할 수 있습니다. "
            "잠시 후 한 번만 다시 시도하거나 크레딧을 충전(https://replicate.com/account/billing)해 속도 한도 완화를 노려 보세요."
        ) from exc
    summary = (exc.title or exc.detail or "").strip()
    if summary:
        raise RuntimeError(f"이미지 provider(Replicate) 오류 ({summary})") from exc
    raise RuntimeError(fallback) from exc


def generate_world_cover_image_url(*, prompt: str, settings: Settings) -> str:
    """Replicate Flux — HTTPS URL 한 개 반환."""
    token = (settings.replicate_api_token or "").strip()
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN is not set")
    model = (settings.image_model_cover or "").strip() or "black-forest-labs/flux-1.1-pro"
    aspect = (settings.image_cover_aspect_ratio or "16:9").strip()
    quality = max(1, min(100, int(settings.image_cover_output_quality)))
    client = replicate.Client(api_token=token)
    try:
        out = client.run(
            cast(Any, model),
            input={
                "prompt": prompt,
                "aspect_ratio": aspect,
                "output_quality": quality,
                "output_format": "webp",
            },
        )
    except ReplicateError as exc:
        _raise_replicate_friendly(exc, fallback="커버 이미지 생성 요청(Replicate)이 실패했습니다.")
    url = _extract_replicate_https_url(out)
    if not url:
        raise RuntimeError(f"Unexpected Replicate output type: {type(out)!r}")
    return url


def generate_npc_avatar_image_url(*, prompt: str, settings: Settings) -> str:
    """저렴 플루즈/SDXL 등 — 정사각형 초상, HTTPS 한 개 반환."""
    token = (settings.replicate_api_token or "").strip()
    if not token:
        raise RuntimeError("REPLICATE_API_TOKEN is not set")
    model = (settings.image_model_npc_avatar or "").strip() or "black-forest-labs/flux-schnell"
    client = replicate.Client(api_token=token)
    inp = _npc_avatar_replicate_input(prompt=prompt, model_id=model, settings=settings)
    try:
        out = client.run(cast(Any, model), input=inp)
    except ReplicateError as exc:
        _raise_replicate_friendly(exc, fallback="NPC 초상 이미지 생성 요청(Replicate)이 실패했습니다.")
    url = _extract_replicate_https_url(out)
    if not url:
        raise RuntimeError(f"Unexpected Replicate output type: {type(out)!r}")
    return url
