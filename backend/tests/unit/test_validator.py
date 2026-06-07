"""
StateChangeValidator 유닛 테스트
"""


from backend.src.engine.validator import StateChangeValidator


class TestStateChangeValidator:
    """StateChangeValidator 클래스 테스트"""

    def test_valid_change(self, validator: StateChangeValidator) -> None:
        """유효한 상태 변경"""
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "affection", "change": 2, "reason": "선물을 받아 기뻐했다"},
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

    def test_disgust_and_wrath_stats_accepted(self, validator: StateChangeValidator) -> None:
        """혐오·살의 관계 스탯 허용"""
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "disgust", "change": 2, "reason": "거짓말을 들었다"},
                {"character": "엘레나", "stat": "wrath", "change": 2, "reason": "위협을 느꼈다"},
            ],
        }
        result = validator.validate(changes)
        assert len(result["relationship_changes"]) == 2
        assert result["relationship_changes"][0]["stat"] == "disgust"
        assert result["relationship_changes"][1]["stat"] == "wrath"

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
        """변화량 제한 (±3)"""
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "affection", "change": 50, "reason": "큰 갈등 후 화해"},
                {"character": "벨라", "stat": "trust", "change": -30, "reason": "거짓말이 들통났다"},
            ],
        }
        result = validator.validate(changes)
        assert len(result["relationship_changes"]) == 1
        assert result["relationship_changes"][0]["change"] == 3

    def test_relationship_requires_reason(self, validator: StateChangeValidator) -> None:
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "affection", "change": 2},
            ],
        }
        result = validator.validate(changes)
        assert len(result.get("relationship_changes", [])) == 0

    def test_relationship_sum_cap(self, validator: StateChangeValidator) -> None:
        changes = {
            "relationship_changes": [
                {"character": "엘레나", "stat": "affection", "change": 3, "reason": "깊은 신뢰 형성"},
                {"character": "벨라", "stat": "trust", "change": 3, "reason": "함께 연습했다"},
            ],
        }
        result = validator.validate(changes)
        total = sum(abs(x["change"]) for x in result["relationship_changes"])
        assert total <= 5

    def test_npc_memory_updates(self, validator: StateChangeValidator) -> None:
        changes = {
            "npc_memory_updates": [
                {"character": "엘레나", "summary": "플레이어가 비밀을 털어놓았다"},
                {"character": "엘레나", "summary": "중복은 무시"},
            ],
        }
        result = validator.validate(changes)
        assert len(result["npc_memory_updates"]) == 1

    def test_resource_stat_change_valid(self, validator: StateChangeValidator) -> None:
        validator.set_valid_resource_stats(["rap", "producing"])
        changes = {
            "resource_stat_changes": [
                {"key": "rap", "change": 4, "reason": "연습"},
                {"key": "invalid", "change": 2},
            ],
        }
        result = validator.validate(changes)
        assert len(result["resource_stat_changes"]) == 1
        assert result["resource_stat_changes"][0]["key"] == "rap"
        assert result["resource_stat_changes"][0]["change"] == 4

    def test_resource_stat_change_clamped(self, validator: StateChangeValidator) -> None:
        validator.set_valid_resource_stats(["skill"])
        changes = {"resource_stat_changes": [{"key": "skill", "change": 99}]}
        result = validator.validate(changes)
        assert result["resource_stat_changes"][0]["change"] == 5

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

    def test_flag_changes_valid(self, validator: StateChangeValidator) -> None:
        changes = {
            "flag_changes": [
                {"key": "debt_paid", "value": True, "reason": "대부에게 1000만 상환 완료"},
                {"key": "Debt-Paid", "value": True, "reason": "중복 키 무시"},
                {"key": "!@#", "value": True, "reason": "잘못된 키"},
            ],
        }
        result = validator.validate(changes)
        assert len(result["flag_changes"]) == 1
        assert result["flag_changes"][0]["key"] == "debt_paid"
        assert result["flag_changes"][0]["value"] is True

    def test_flag_changes_requires_reason(self, validator: StateChangeValidator) -> None:
        changes = {"flag_changes": [{"key": "debt_paid", "value": True, "reason": "짧"}]}
        result = validator.validate(changes)
        assert len(result.get("flag_changes", [])) == 0

    def test_flag_changes_max_three(self, validator: StateChangeValidator) -> None:
        changes = {
            "flag_changes": [
                {"key": f"f{i}", "value": True, "reason": f"사유 {i}"}
                for i in range(5)
            ],
        }
        result = validator.validate(changes)
        assert len(result["flag_changes"]) == 3

    def test_empty_changes(self, validator: StateChangeValidator) -> None:
        """빈 변경 사항"""
        result = validator.validate({})
        assert result == {}

    def test_no_valid_characters_allows_all(self) -> None:
        """유효 캐릭터 목록이 비어있으면 모두 허용"""
        v = StateChangeValidator(valid_characters=[])
        changes = {
            "relationship_changes": [
                {"character": "아무나", "stat": "affection", "change": 2, "reason": "친절한 대화"},
            ],
        }
        result = v.validate(changes)
        assert len(result["relationship_changes"]) == 1
        assert result["relationship_changes"][0]["change"] == 2
