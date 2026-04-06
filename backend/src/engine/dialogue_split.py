"""LLM NPC 응답을 UI용 화자 블록으로 나눔 (프롬프트: 빈 줄로 화자 블록 구분)."""

from __future__ import annotations

import re


def split_assistant_into_segments(text: str, npc_names: list[str]) -> list[dict[str, str]]:
    """`text`를 화자별 블록으로 분리. `npc_names`는 길이 내림차순으로 매칭."""
    text = (text or "").strip()
    if not text:
        return []

    names = sorted({str(n).strip() for n in npc_names if n and str(n).strip()}, key=len, reverse=True)
    if not names:
        return [{"speaker": "응답", "text": text}]

    raw_blocks = re.split(r"\n\s*\n+", text)
    blocks = [b.strip() for b in raw_blocks if b.strip()]

    def speaker_for_first_line(first_line: str) -> str | None:
        stripped = first_line.lstrip()
        for name in names:
            if stripped.startswith(name):
                rest = stripped[len(name) :]
                if not rest or rest[0] in " \t(":
                    return name
        return None

    segments: list[dict[str, str]] = []
    for block in blocks:
        first = block.split("\n", 1)[0]
        sp = speaker_for_first_line(first)
        if sp:
            segments.append({"speaker": sp, "text": block})
        else:
            segments.append({"speaker": "내레이션", "text": block})

    return segments
