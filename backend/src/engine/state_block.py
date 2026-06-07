"""동적 프롬프트용 State 층 — ``story_facts`` 확정 사실 (모든 월드 공통)."""

from __future__ import annotations

from .story_facts import build_canon_state_lines


def build_state_block(
    player: dict[str, object],
    day: int,
) -> str:
    return "\n".join(build_canon_state_lines(player, day))
