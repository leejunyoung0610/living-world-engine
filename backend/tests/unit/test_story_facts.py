"""story_facts — 확정 플래그·화자 필터."""

from backend.src.engine.story_facts import (
    active_flags,
    build_canon_state_lines,
    is_invalid_speaker_label,
    normalize_flag_key,
    normalize_flag_value,
)


def test_normalize_flag_key() -> None:
    assert normalize_flag_key("Debt-Paid") == "debt_paid"
    assert normalize_flag_key("!@#") is None
    assert normalize_flag_key("") is None


def test_normalize_flag_value() -> None:
    assert normalize_flag_value(True) is True
    assert normalize_flag_value(False) is False
    assert normalize_flag_value("  인천 원룸 ") == "인천 원룸"
    assert normalize_flag_value("") is None


def test_active_flags_skips_falsey() -> None:
    flags = active_flags({
        "flags": {
            "debt_paid": True,
            "warned": False,
            "loc": "집",
            "bad-key": "x",
        }
    })
    keys = [k for k, _ in flags]
    assert "debt_paid" in keys
    assert "loc" in keys
    assert "warned" not in keys
    assert "bad-key" not in keys


def test_build_canon_state_lines_contradiction_warning() -> None:
    lines = build_canon_state_lines({"flags": {"debt_paid": True}}, day=10)
    text = "\n".join(lines)
    assert "10일차" in text
    assert "debt_paid" in text
    assert "모순 금지" in text


def test_is_invalid_speaker_label() -> None:
    assert is_invalid_speaker_label("플랍")
    assert is_invalid_speaker_label("팟: 1200")
    assert is_invalid_speaker_label("Q♦ J♥")
    assert not is_invalid_speaker_label("이준영")
    assert not is_invalid_speaker_label("내레이션")
