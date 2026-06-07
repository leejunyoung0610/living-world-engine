"""확정 스토리 사실(Canon) — 모든 월드 공통.

``player.flags`` = 코드·이벤트·LLM 툴이 확정한 「지금 진실」.
세계관 초기 설정·옛 대화보다 우선하며, LLM이 번복하면 안 됨.
"""

from __future__ import annotations

import re
from typing import Any

FLAG_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
MAX_FLAG_CHANGES_PER_TURN = 3
MAX_FLAG_VALUE_STR_LEN = 120
MIN_FLAG_REASON_LEN = 4
MAX_FLAGS_IN_PROMPT = 24

# split/UI — 화자로 쓰이면 안 되는 패턴 (포커·내레이션 잔해)
_INVALID_SPEAKER_MARKERS = (
    "팟:",
    "플랍",
    "턴:",
    "턴 ",
    "리버",
    "보드",
    "차례",
    "카톡",
    "문자",
    "위치:",
    "핸드",
    "♠",
    "♥",
    "♦",
    "♣",
    " — ",
)


def normalize_flag_key(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    key = re.sub(r"[^a-z0-9_]", "", key)
    if not key or not FLAG_KEY_PATTERN.match(key):
        return None
    return key


def normalize_flag_value(raw: object) -> bool | str | int | float | None:
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, int) and not isinstance(raw, bool):
        return raw
    if isinstance(raw, float) and raw == raw:
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return None
        return s[:MAX_FLAG_VALUE_STR_LEN]
    return None


def is_truthy_flag_value(val: object) -> bool:
    if val is False or val is None or val == "" or val == 0:
        return False
    return True


def format_flag_line(key: str, val: object) -> str:
    if val is True:
        return f"- 확정: {key}"
    if isinstance(val, str):
        return f"- 확정: {key} = {val}"
    return f"- 확정: {key} = {val!r}"


def active_flags(player: dict[str, object]) -> list[tuple[str, object]]:
    flags = player.get("flags")
    if not isinstance(flags, dict):
        return []
    out: list[tuple[str, object]] = []
    for key in sorted(flags.keys(), key=str):
        nk = normalize_flag_key(key)
        if not nk:
            continue
        val = flags[key]
        if not is_truthy_flag_value(val):
            continue
        norm_val = normalize_flag_value(val)
        if norm_val is None and val is not True:
            continue
        out.append((nk, norm_val if norm_val is not None else True))
    return out[:MAX_FLAGS_IN_PROMPT]


def build_canon_state_lines(player: dict[str, object], day: int) -> list[str]:
    """State 블록 본문 — 일차 + 확정 플래그 + 모순 금지."""
    lines = ["## 지금 사실 (저장된 사실 — 세계관 초기 설정·옛 대화보다 우선)"]
    lines.append(f"- 진행: {day}일차")
    flags = active_flags(player)
    if flags:
        for key, val in flags:
            lines.append(format_flag_line(key, val))
        lines.append(
            "- **모순 금지**: 위 확정 사실과 반대되는 상황·대사를 쓰지 마세요. "
            "예: `debt_paid`가 있으면 「빚 갚아야 한다」「대부에게 연락」 같은 **이전 미완 서사**를 다시 시작하지 마세요."
        )
    else:
        lines.append("- (아직 확정 플래그 없음 — 중요한 사건이 확정되면 `flag_changes`로 기록)")
    lines.append("")
    lines.append(
        "우선순위: 이 블록(확정 플래그·일차) > 최근 대화 > 단기기억·중요기억 > 세계관 배경."
    )
    lines.append(
        "관계 톤은 아래 「관계 수치」·대화·기억을 종합하세요. "
        "수치만으로 연인·사귐을 단정하지 마세요 — 확정은 플래그·대화로만."
    )
    return lines


def is_invalid_speaker_label(name: str) -> bool:
    """내레이션·포커 잔해를 화자 카드로 쓰지 않기."""
    if not name or not name.strip():
        return True
    n = name.strip()
    if n in ("내레이션", "응답", "모르는 번호"):
        return False
    if any(m in n for m in _INVALID_SPEAKER_MARKERS):
        return True
    if re.search(r"[♠♥♦♣]", n):
        return True
    if re.match(r"^\d", n):
        return True
    if len(n) > 36:
        return True
    return False
