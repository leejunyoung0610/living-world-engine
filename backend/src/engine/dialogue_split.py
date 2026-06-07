"""LLM NPC 응답을 UI용 화자 블록으로 나눔 (프롬프트: 빈 줄로 화자 블록 구분)."""

from __future__ import annotations

import re

# UI 카드 상한 — LLM이 프롬프트를 어겨도 내레이션 남발을 완화
MAX_DISPLAY_SEGMENTS = 6
MAX_NARRATION_BLOCKS = 1


def compact_assistant_segments(
    segments: list[dict[str, str]],
    *,
    max_total: int = MAX_DISPLAY_SEGMENTS,
    max_narration_blocks: int = MAX_NARRATION_BLOCKS,
) -> list[dict[str, str]]:
    """연속·분산 내레이션 블록을 합치고, 화면 카드 수를 상한 이내로 줄인다."""
    if not segments:
        return []

    merged: list[dict[str, str]] = []
    for seg in segments:
        speaker = seg.get("speaker", "")
        text = str(seg.get("text", "")).strip()
        if not text:
            continue
        if (
            merged
            and speaker == "내레이션"
            and merged[-1].get("speaker") == "내레이션"
        ):
            merged[-1]["text"] = merged[-1]["text"] + "\n\n" + text
        else:
            merged.append({"speaker": speaker, "text": text})

    narr_indices = [i for i, s in enumerate(merged) if s.get("speaker") == "내레이션"]
    if len(narr_indices) > max_narration_blocks:
        all_narr = "\n\n".join(merged[i]["text"] for i in narr_indices)
        out: list[dict[str, str]] = []
        inserted = False
        for i, seg in enumerate(merged):
            if seg.get("speaker") == "내레이션":
                if not inserted and i == narr_indices[0]:
                    out.append({"speaker": "내레이션", "text": all_narr})
                    inserted = True
                continue
            out.append(seg)
        merged = out

    if len(merged) > max_total:
        narr_only = [s for s in merged if s.get("speaker") == "내레이션"]
        npc_only = [s for s in merged if s.get("speaker") != "내레이션"]
        keep_npcs = npc_only[: max_total - (1 if narr_only else 0)]
        if narr_only:
            merged = keep_npcs + [{"speaker": "내레이션", "text": narr_only[0]["text"]}]
        else:
            merged = keep_npcs[:max_total]

    return merged


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

    # NPC·내레이션 블록은 빈 줄 단위 그대로 유지 (합치지 않음)
    return segments
