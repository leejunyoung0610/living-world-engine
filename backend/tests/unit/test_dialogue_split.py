"""dialogue_split 유닛 테스트."""

from backend.src.engine.dialogue_split import (
    compact_assistant_segments,
    split_assistant_into_segments,
)


def test_single_npc_block() -> None:
    text = "벨라 (웃으며) 오늘 날씨 좋네."
    segs = split_assistant_into_segments(text, ["벨라", "루아"])
    assert len(segs) == 1
    assert segs[0]["speaker"] == "벨라"
    assert "오늘" in segs[0]["text"]


def test_two_npcs_blank_line() -> None:
    text = "벨라 (끄덕이며) 그래.\n\n루아 (한숨) 나는 모르겠어."
    segs = split_assistant_into_segments(text, ["벨라", "루아"])
    assert len(segs) == 2
    assert segs[0]["speaker"] == "벨라"
    assert segs[1]["speaker"] == "루아"


def test_longer_name_first_match() -> None:
    text = "김벨라 (인사) 안녕\n\n벨라 (웃음) 하하"
    segs = split_assistant_into_segments(text, ["벨라", "김벨라"])
    assert segs[0]["speaker"] == "김벨라"


def test_no_npc_names_one_blob() -> None:
    segs = split_assistant_into_segments("그냥 텍스트", [])
    assert len(segs) == 1
    assert segs[0]["speaker"] == "응답"


def test_many_narration_blocks_merged_to_one() -> None:
    parts = [f"장면 묘사 {i}" for i in range(15)]
    text = "\n\n".join(parts)
    segs = split_assistant_into_segments(text, ["김아현"])
    assert len(segs) == 1
    assert segs[0]["speaker"] == "내레이션"
    assert "장면 묘사 0" in segs[0]["text"]
    assert "장면 묘사 14" in segs[0]["text"]


def test_interleaved_narration_collapsed() -> None:
    text = (
        "김아현 (웃으며) 안녕\n\n"
        "바다 냄새가 난다.\n\n"
        "이준영 (고개 끄덕) 그래\n\n"
        "파도 소리.\n\n"
        "김아현 (미소) 좋지?"
    )
    segs = split_assistant_into_segments(text, ["김아현", "이준영"])
    narr_count = sum(1 for s in segs if s["speaker"] == "내레이션")
    assert narr_count == 1
    assert len(segs) <= 6


def test_compact_preserves_npc_blocks() -> None:
    raw = [
        {"speaker": "벨라", "text": "안녕"},
        {"speaker": "내레이션", "text": "a"},
        {"speaker": "내레이션", "text": "b"},
        {"speaker": "루아", "text": "응"},
    ]
    out = compact_assistant_segments(raw)
    assert [s["speaker"] for s in out] == ["벨라", "내레이션", "루아"]
    assert "a" in out[1]["text"] and "b" in out[1]["text"]
