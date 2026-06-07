"""dialogue_split 유닛 테스트."""

from backend.src.engine.dialogue_split import (
    compact_assistant_segments,
    normalize_assistant_text,
    split_assistant_into_segments,
)


def test_single_npc_block() -> None:
    text = "벨라 (웃으며) 오늘 날씨 좋네."
    segs = split_assistant_into_segments(text, ["벨라", "루아"])
    assert len(segs) == 1
    assert segs[0]["speaker"] == "벨라"


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


def test_many_narration_blocks_merge_to_one_card() -> None:
    parts = [f"장면 묘사 {i}" for i in range(5)]
    text = "\n\n".join(parts)
    segs = split_assistant_into_segments(text, ["김아현"])
    assert len(segs) == 1
    assert segs[0]["speaker"] == "내레이션"


def test_interleaved_npcs_stay_separate() -> None:
    text = (
        "김아현 (웃으며) 안녕\n\n"
        "바다 냄새가 난다.\n\n"
        "이준영 (고개 끄덕) 그래\n\n"
        "파도 소리.\n\n"
        "김아현 (미소) 좋지?"
    )
    segs = split_assistant_into_segments(text, ["김아현", "이준영"])
    speakers = [s["speaker"] for s in segs]
    assert "김아현" in speakers
    assert "이준영" in speakers
    assert len(segs) <= 5


def test_utterance_split_per_quote_line() -> None:
    text = (
        "**김아현** (픽 웃으며)\n\n"
        '"술도 안 마셨는데 무슨 취해."\n\n'
        "(침대 모서리에 조심스럽게 앉으며)\n\n"
        '"오빠가 일 뺐다고? 진짜?"\n\n'
        "---\n\n"
        "**김아현** (이불 덮으며)\n\n"
        '"...미친놜."'
    )
    segs = split_assistant_into_segments(text, ["김아현"])
    assert len(segs) == 3
    assert all(s["speaker"] == "김아현" for s in segs)
    assert "술도 안 마셨는데" in segs[0]["text"]
    assert "침대 모서리" in segs[1]["text"]
    assert "오빠가 일 뺐다고" in segs[1]["text"]
    assert "이불 덮으며" in segs[2]["text"]
    assert "미친놜" in segs[2]["text"]


def test_session_like_response_capped_at_five() -> None:
    text = (
        "**김아현** (픽 웃으며)\n\n"
        '"술도 안 마셨는데 무슨 취해."\n\n'
        "(침대 모서리에 조심스럽게 앉으며)\n\n"
        '"오빠가 일 뺐다고? 진짜?"\n\n'
        "(놀란 표정)\n\n"
        '"야, 성민근."\n\n'
        "**김아현** (이불 덮으며)\n\n"
        '"...고마워."\n\n'
        "그녀의 숨소리가 가까이 들린다."
    )
    segs = split_assistant_into_segments(text, ["김아현"])
    assert len(segs) <= 5
    assert segs[0]["speaker"] == "김아현"
    assert any(s["speaker"] == "내레이션" for s in segs)


def test_normalize_strips_horizontal_rules() -> None:
    assert "---" not in normalize_assistant_text("a\n\n---\n\nb")
    assert normalize_assistant_text("a\n\n---\n\nb") == "a\n\nb"


def test_discovers_speaker_not_in_npc_list() -> None:
    text = "조현용 (카드를 밀며) 올인이다.\n\n이민수 (웃으며) 콜."
    segs = split_assistant_into_segments(text, [])
    assert len(segs) == 2
    assert segs[0]["speaker"] == "조현용"
    assert segs[1]["speaker"] == "이민수"


def test_player_name_not_npc_card() -> None:
    text = "조현용 (카드를 밀며) 올인이다.\n\n이민수 (웃으며) 콜."
    segs = split_assistant_into_segments(text, ["이민수"], player_name="조현용")
    assert all(s["speaker"] != "조현용" for s in segs)
    assert any(s["speaker"] == "이민수" for s in segs)


def test_invalid_poker_label_becomes_narration() -> None:
    text = "플랍 (턴 2)\n\nQ♦ J♥ 보드가 펼쳐진다.\n\n이준영 (웃으며) 콜."
    segs = split_assistant_into_segments(text, ["이준영"])
    assert all(s["speaker"] != "플랍" for s in segs)
    assert all("♦" not in s["speaker"] for s in segs)
    assert segs[-1]["speaker"] == "이준영"


def test_single_newline_between_speakers_splits() -> None:
    text = "조현용 (딜러) \"올인.\"\n이민수 (옆에서) \"콜.\""
    segs = split_assistant_into_segments(text, ["이민수"], player_name="조현용")
    assert all(s["speaker"] != "조현용" for s in segs)
    assert segs[-1]["speaker"] == "이민수"


def test_compact_preserves_npc_utterance_cards() -> None:
    raw = [
        {"speaker": "벨라", "text": "안녕"},
        {"speaker": "벨라", "text": "또 말함"},
        {"speaker": "내레이션", "text": "a"},
        {"speaker": "내레이션", "text": "b"},
        {"speaker": "루아", "text": "응"},
    ]
    out = compact_assistant_segments(raw)
    assert [s["speaker"] for s in out] == ["벨라", "벨라", "내레이션", "루아"]
    assert "a" in out[2]["text"] and "b" in out[2]["text"]
