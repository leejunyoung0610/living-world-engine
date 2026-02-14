"""
StateChangeValidator 유닛 테스트
"""

import pytest

from backend.src.engine.validator import StateChangeValidator


class TestStateChangeValidator:
    """StateChangeValidator 클래스 테스트"""

    def test_valid_change(self, validator: StateChangeValidator) -> None:
        """유효한 상태 변경"""
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "affection", "change": 5, "reason": "선물"},
            ],
            "new_memories": [
                {"content": "꽃을 선물했다", "emotion": "joy", "importance": 7},
            ],
        }
        result = validator.validate(changes)
        assert len(result["relationship_changes"]) == 1
        assert len(result["new_memories"]) == 1

    def test_invalid_character_rejected(self, validator: StateChangeValidator) -> None:
        """존재하지 않는 캐릭터 변경 거부"""
        changes = {
            "relationship_changes": [
                {"character": "없는캐릭터", "stat": "affection", "change": 10},
            ],
        }
        result = validator.validate(changes)
        assert len(result["relationship_changes"]) == 0

    def test_invalid_stat_rejected(self, validator: StateChangeValidator) -> None:
        """유효하지 않은 스탯 거부"""
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "invalid_stat", "change": 5},
            ],
        }
        result = validator.validate(changes)
        assert len(result["relationship_changes"]) == 0

    def test_change_clamping(self, validator: StateChangeValidator) -> None:
        """변화량 제한 (-10 ~ +10)"""
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "affection", "change": 50},
                {"character": "벨라", "stat": "trust", "change": -30},
            ],
        }
        result = validator.validate(changes)
        assert result["relationship_changes"][0]["change"] == 10  # 50 → 10
        assert result["relationship_changes"][1]["change"] == -10  # -30 → -10

    def test_empty_memory_rejected(self, validator: StateChangeValidator) -> None:
        """빈 기억 거부"""
        changes = {
            "new_memories": [
                {"content": "", "emotion": "joy", "importance": 5},
                {"content": "a", "emotion": "joy", "importance": 5},  # 너무 짧음
            ],
        }
        result = validator.validate(changes)
        assert len(result["new_memories"]) == 0

    def test_importance_clamping(self, validator: StateChangeValidator) -> None:
        """중요도 1-10 범위 제한"""
        changes = {
            "new_memories": [
                {"content": "높은 중요도 기억", "emotion": "joy", "importance": 99},
                {"content": "낮은 중요도 기억", "emotion": "neutral", "importance": -5},
            ],
        }
        result = validator.validate(changes)
        assert result["new_memories"][0]["importance"] == 10
        assert result["new_memories"][1]["importance"] == 1

    def test_invalid_emotion_defaults_to_neutral(self, validator: StateChangeValidator) -> None:
        """유효하지 않은 감정 → neutral로 대체"""
        changes = {
            "new_memories": [
                {"content": "기억 내용 테스트", "emotion": "invalid_emotion", "importance": 5},
            ],
        }
        result = validator.validate(changes)
        assert result["new_memories"][0]["emotion"] == "neutral"

    def test_empty_changes(self, validator: StateChangeValidator) -> None:
        """빈 변경 사항"""
        result = validator.validate({})
        assert result == {}

    def test_no_valid_characters_allows_all(self) -> None:
        """유효 캐릭터 목록이 비어있으면 모두 허용"""
        v = StateChangeValidator(valid_characters=[])
        changes = {
            "relationship_changes": [
                {"character": "아무나", "stat": "affection", "change": 5},
            ],
        }
        result = v.validate(changes)
        assert len(result["relationship_changes"]) == 1
