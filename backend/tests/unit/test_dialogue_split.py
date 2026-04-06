"""dialogue_split 유닛 테스트."""

from backend.src.engine.dialogue_split import split_assistant_into_segments


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
