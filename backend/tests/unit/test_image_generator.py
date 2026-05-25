"""image_generator.build_* 프롬프트 조합 검증."""

from __future__ import annotations

from backend.src.services.image_generator import (
    _extract_replicate_https_url,
    build_npc_avatar_prompt,
)


class _FakeWorldRow:
    """build_npc_avatar_prompt 에 넘기는 최소 스텁."""

    def __init__(
        self,
        *,
        name: str = "테스트 월드",
        world_data: dict | None = None,
    ) -> None:
        self.name = name
        self.world_data = world_data or {}


def test_extract_replicate_https_url_list_of_dict() -> None:
    assert _extract_replicate_https_url([{"url": "https://cdn.example/a.webp"}]) == "https://cdn.example/a.webp"


def test_extract_replicate_https_url_nested() -> None:
    assert _extract_replicate_https_url({"output": [{"uri": "https://b.example/x.png"}]}) == "https://b.example/x.png"


def test_build_npc_avatar_prompt_prefers_appearance_for_ai() -> None:
    w = _FakeWorldRow(world_data={"description": "캠퍼스."})
    npc = {
        "name": "민지",
        "role": "선배",
        "appearance_for_ai": "실버 단발, 둥근 안경, 크림색 니트.",
        "personality": "내성적",  # 있어도 전용 필드가 우선이면 생략됨
        "location": "도서관",
    }
    p = build_npc_avatar_prompt(w, npc)
    assert "Visual appearance for portrait" in p
    assert "실버 단발" in p
    assert "Often seen at" not in p
    assert "내성적" not in p


def test_build_npc_avatar_prompt_fallback_personality_without_portrait_field() -> None:
    w = _FakeWorldRow()
    npc = {"name": "A", "role": "B", "personality": "활발함", "location": "정문"}
    p = build_npc_avatar_prompt(w, npc)
    assert "Personality: 활발함" in p
    assert "Often seen at" not in p
