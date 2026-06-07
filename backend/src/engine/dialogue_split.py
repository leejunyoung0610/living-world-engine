"""LLM NPC 응답을 UI용 화자 블록으로 나눔 — 멘트(대사) 단위 카드."""

from __future__ import annotations

import re

from .story_facts import is_invalid_speaker_label

MAX_DISPLAY_SEGMENTS = 5
MAX_NARRATION_BLOCKS = 1

_HR_LINE = re.compile(r"^---+\s*$|^\*{3}\s*$|^_{3,}\s*$")
_DIALOGUE_START = re.compile(r'^["\'…「]|^\.\.\.')
_ACTION_START = re.compile(r"^\([^)]*\)")
_SPEAKER_HEADER = re.compile(
    r"^\*{0,2}([^*\n]{2,40}?)\*{0,2}\s*(?:\([^)]+\)|[:：])"
)


def normalize_assistant_text(text: str) -> str:
    """`---` 구분선 제거, 과도한 빈 줄 축소."""
    t = (text or "").strip()
    if not t:
        return ""
    t = re.sub(r"\n\s*---+\s*\n", "\n\n", t)
    t = re.sub(r"(?:^\s*---+\s*\n|\n\s*---+\s*$)", "", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def compact_assistant_segments(
    segments: list[dict[str, str]],
    *,
    max_total: int = MAX_DISPLAY_SEGMENTS,
    max_narration_blocks: int = MAX_NARRATION_BLOCKS,
) -> list[dict[str, str]]:
    """내레이션만 합치고, NPC 멘트 카드는 유지. 상한 초과 시 뒤쪽부터 합침."""
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

    if len(merged) <= max_total:
        return merged

    narr_only = [s for s in merged if s.get("speaker") == "내레이션"]
    npc_only = [s for s in merged if s.get("speaker") != "내레이션"]
    narr_slot = 1 if narr_only else 0
    keep_npcs = max(1, max_total - narr_slot)

    if len(npc_only) <= keep_npcs:
        return (npc_only + narr_only)[:max_total]

    kept = npc_only[: keep_npcs - 1]
    overflow = npc_only[keep_npcs - 1 :]
    overflow_text = "\n\n".join(s["text"] for s in overflow)
    kept.append({"speaker": overflow[0]["speaker"], "text": overflow_text})
    if narr_only:
        kept.append({"speaker": "내레이션", "text": narr_only[0]["text"]})
    return kept[:max_total]


def _speaker_header_name(line: str) -> str | None:
    """`이름 (행동)` / `**이름** (행동)` / `이름:` 형태에서 이름 추출."""
    stripped = line.lstrip()
    if not stripped or _is_dialogue_line(stripped):
        return None
    clean = stripped.replace("**", "").strip()
    m = _SPEAKER_HEADER.match(clean) or _SPEAKER_HEADER.match(stripped)
    if m:
        cand = m.group(1).strip()
        if cand and not _is_dialogue_line(cand):
            return cand
    bold = re.match(r"^\*\*([^*]+)\*\*", stripped)
    if bold:
        cand = bold.group(1).strip()
        if cand:
            rest = stripped[bold.end() :].strip()
            if not rest or rest[0] == "(":
                return cand
    return None


def _resolve_speaker_label(label: str, names: list[str]) -> str:
    for name in names:
        if label == name or label.startswith(name) or name.startswith(label):
            return name
    return label


def _is_player_speaker(label: str, player_name: str | None) -> bool:
    if not player_name or not label:
        return False
    p = player_name.strip()
    n = label.strip()
    return n == p or n.startswith(p) or p.startswith(n)


def _filter_speaker(
    label: str, names: list[str], *, player_name: str | None = None
) -> str | None:
    """NPC 카드 화자로 쓸 수 있으면 정규화된 이름, 아니면 None."""
    resolved = _resolve_speaker_label(label, names)
    if _is_player_speaker(resolved, player_name) or _is_player_speaker(label, player_name):
        return None
    if is_invalid_speaker_label(resolved):
        return None
    return resolved


def _discover_speaker_names(
    text: str, known: list[str], *, player_name: str | None = None
) -> list[str]:
    found: set[str] = set()
    for n in known:
        if n and _filter_speaker(str(n), known, player_name=player_name):
            found.add(_resolve_speaker_label(str(n), known))
    for line in text.split("\n"):
        cand = _speaker_header_name(line.strip())
        if cand:
            acc = _filter_speaker(cand, list(found) + known, player_name=player_name)
            if acc:
                found.add(acc)
    return sorted(found, key=len, reverse=True)


def _preprocess_speaker_line_breaks(text: str, names: list[str]) -> str:
    """빈 줄 없이 `이름 (행동)` 만 줄바꿈된 LLM 출력도 블록 경계로 삼음."""
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if out and stripped and _speaker_header_name(stripped):
            if out[-1].strip():
                out.append("")
        out.append(line)
    return "\n".join(out)


def _speaker_for_first_line(
    first_line: str, names: list[str], *, player_name: str | None = None
) -> str | None:
    stripped = first_line.lstrip()
    header = _speaker_header_name(stripped)
    if header:
        return _filter_speaker(header, names, player_name=player_name)
    bold = re.match(r"^\*\*([^*]+)\*\*", stripped)
    if bold:
        label = bold.group(1).strip()
        return _filter_speaker(label, names, player_name=player_name)
    for name in names:
        if stripped.startswith(name):
            rest = stripped[len(name) :]
            if not rest or rest[0] in " \t(":
                return _filter_speaker(name, names, player_name=player_name)
    return None


def _speaker_for_block(
    block: str, names: list[str], *, player_name: str | None = None
) -> str | None:
    first = block.split("\n", 1)[0]
    return _speaker_for_first_line(first, names, player_name=player_name)


def _first_line(block: str) -> str:
    return block.strip().split("\n", 1)[0].strip()


def _is_dialogue_line(line: str) -> bool:
    return bool(_DIALOGUE_START.match(line))


def _is_action_line(line: str) -> bool:
    return bool(_ACTION_START.match(line))


def _block_has_dialogue(block: str) -> bool:
    for line in block.split("\n"):
        if _is_dialogue_line(line.strip()):
            return True
    return False


def _strip_npc_prefix(line: str, names: list[str]) -> str:
    stripped = line.lstrip()
    bold = re.match(r"^\*\*([^*]+)\*\*", stripped)
    if bold:
        return re.sub(r"^\*\*[^*]+\*\*", "", stripped).strip()
    for name in names:
        if stripped.startswith(name):
            return stripped[len(name) :].strip()
    return stripped


def _is_npc_header_only(block: str, names: list[str]) -> bool:
    """`**이름** (행동)` 만 있고 대사가 없을 때만 True."""
    if _speaker_for_block(block, names) is None:
        return False
    if _block_has_dialogue(block):
        return False
    lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
    if len(lines) != 1:
        return False
    rest = _strip_npc_prefix(lines[0], names)
    rest = re.sub(r"^\([^)]*\)", "", rest).strip()
    return not rest


def _append_narration(out: list[dict[str, str]], block: str) -> None:
    if out and out[-1].get("speaker") == "내레이션":
        out[-1]["text"] = out[-1]["text"] + "\n\n" + block
    else:
        out.append({"speaker": "내레이션", "text": block})


def _split_by_utterances(
    blocks: list[str],
    names: list[str],
    *,
    player_name: str | None = None,
) -> list[dict[str, str]]:
    """멘트(따옴표 대사)마다 카드 1개. 직전 (행동)·NPC 헤더는 해당 멘트에 붙임."""
    out: list[dict[str, str]] = []
    active_npc: str | None = None
    pending_prefix = ""

    def flush_prefix_to_last() -> None:
        nonlocal pending_prefix
        if not pending_prefix:
            return
        if out and out[-1]["speaker"] != "내레이션":
            out[-1]["text"] = out[-1]["text"] + "\n\n" + pending_prefix
        elif active_npc:
            out.append({"speaker": active_npc, "text": pending_prefix})
        else:
            out.append({"speaker": "내레이션", "text": pending_prefix})
        pending_prefix = ""

    for block in blocks:
        if not block or _HR_LINE.match(block):
            continue

        first = _first_line(block)
        header_name = _speaker_header_name(first)
        if header_name and _filter_speaker(header_name, names, player_name=player_name) is None:
            flush_prefix_to_last()
            active_npc = None
            _append_narration(out, block)
            continue

        named = _speaker_for_block(block, names, player_name=player_name)

        if named:
            active_npc = named
            if _is_npc_header_only(block, names):
                pending_prefix = (
                    f"{pending_prefix}\n\n{block}" if pending_prefix else block
                )
                continue
            text = f"{pending_prefix}\n\n{block}" if pending_prefix else block
            out.append({"speaker": named, "text": text})
            pending_prefix = ""
            continue

        if _is_action_line(first) and not _block_has_dialogue(block):
            pending_prefix = (
                f"{pending_prefix}\n\n{block}" if pending_prefix else block
            )
            continue

        if _is_dialogue_line(first) or _block_has_dialogue(block):
            speaker = active_npc or "내레이션"
            text = f"{pending_prefix}\n\n{block}" if pending_prefix else block
            out.append({"speaker": speaker, "text": text})
            pending_prefix = ""
            continue

        flush_prefix_to_last()
        active_npc = None
        _append_narration(out, block)

    flush_prefix_to_last()
    return out


def split_assistant_into_segments(
    text: str,
    npc_names: list[str],
    *,
    player_name: str | None = None,
) -> list[dict[str, str]]:
    """`text`를 멘트 단위 화자 블록으로 분리."""
    text = normalize_assistant_text(text)
    if not text:
        return []

    known = [str(n).strip() for n in npc_names if n and str(n).strip()]
    names = _discover_speaker_names(text, known, player_name=player_name)
    if not names:
        return [{"speaker": "응답", "text": text}]

    text = _preprocess_speaker_line_breaks(text, names)
    raw_blocks = re.split(r"\n\s*\n+", text)
    blocks = [b.strip() for b in raw_blocks if b.strip() and not _HR_LINE.match(b.strip())]

    utterances = _split_by_utterances(blocks, names, player_name=player_name)
    return compact_assistant_segments(utterances)
