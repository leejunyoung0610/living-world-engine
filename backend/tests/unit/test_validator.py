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


class TestValidatorTypeGuards:
    """LLM 툴 입력이 스키마와 다른 타입일 때 — 예외 없이 강제 변환하거나 해당 항목만 버린다."""

    @staticmethod
    def _memory(importance: object, **extra: object) -> dict:
        return {"new_memories": [{"content": "중요한 사건", "emotion": "joy", "importance": importance, **extra}]}

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("7", 7),  # 기존: min(10, "7") → TypeError 로 턴 전체가 500
            (" 8 ", 8),
            ("9.6", 9),
            (7.9, 7),
            ("15", 10),
            ("-3", 1),
        ],
    )
    def test_numeric_importance_is_coerced(
        self, validator: StateChangeValidator, raw: object, expected: int
    ) -> None:
        result = validator.validate(self._memory(raw))
        assert result["new_memories"][0]["importance"] == expected

    @pytest.mark.parametrize("raw", ["높음", "", None, True, [7], {"v": 7}, float("nan")])
    def test_non_numeric_importance_falls_back_to_default(
        self, validator: StateChangeValidator, raw: object
    ) -> None:
        result = validator.validate(self._memory(raw))
        assert result["new_memories"][0]["importance"] == 5

    def test_memory_without_importance_defaults_to_5(self, validator: StateChangeValidator) -> None:
        result = validator.validate({"new_memories": [{"content": "중요도 없음", "emotion": "joy"}]})
        assert result["new_memories"][0]["importance"] == 5

    def test_malformed_memory_items_are_dropped(self, validator: StateChangeValidator) -> None:
        changes = {
            "new_memories": [
                "그냥 문자열",
                ["리스트"],
                {"content": 12345, "emotion": "joy", "importance": 5},
                {"content": "정상 기억", "emotion": ["joy"], "importance": 5},
            ]
        }
        result = validator.validate(changes)
        assert result["new_memories"] == [
            {"content": "정상 기억", "emotion": "neutral", "importance": 5}
        ]

    @pytest.mark.parametrize("raw", ["기억", {"content": "x"}, 3, None])
    def test_non_list_arrays_are_ignored(self, validator: StateChangeValidator, raw: object) -> None:
        result = validator.validate(
            {"new_memories": raw, "resource_stat_changes": raw, "relationship_changes": raw}
        )
        assert result == {
            "new_memories": [],
            "resource_stat_changes": [],
            "relationship_changes": [],
        }

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("3", 3), ("-2", -2), (2.9, 2), ("99", 5)],
    )
    def test_resource_change_numeric_coercion(
        self, validator: StateChangeValidator, raw: object, expected: int
    ) -> None:
        validator.set_valid_resource_stats(["skill"])
        result = validator.validate({"resource_stat_changes": [{"key": "skill", "change": raw}]})
        assert result["resource_stat_changes"][0]["change"] == expected

    @pytest.mark.parametrize("raw", ["많이", True, None, [1], float("inf"), float("nan")])
    def test_resource_change_non_numeric_rejected(
        self, validator: StateChangeValidator, raw: object
    ) -> None:
        validator.set_valid_resource_stats(["skill"])
        result = validator.validate({"resource_stat_changes": [{"key": "skill", "change": raw}]})
        assert result["resource_stat_changes"] == []

    def test_resource_items_with_bad_shape_dropped(self, validator: StateChangeValidator) -> None:
        changes = {
            "resource_stat_changes": [
                "skill",
                {"key": ["skill"], "change": 2},
                {"key": "skill", "change": 2, "show_card": "false"},
            ]
        }
        result = validator.validate(changes)
        assert result["resource_stat_changes"] == [
            {"key": "skill", "change": 2, "reason": "", "show_card": False}
        ]

    def test_relationship_items_with_bad_shape_dropped(self, validator: StateChangeValidator) -> None:
        changes = {
            "relationship_changes": [
                "엘레나 호감 +2",
                {"character": "엘레나", "stat": "affection", "change": "2", "reason": "도움을 줌"},
            ]
        }
        result = validator.validate(changes)
        assert result["relationship_changes"] == [
            {"character": "엘레나", "stat": "affection", "change": 2, "reason": "도움을 줌"}
        ]

    @pytest.mark.parametrize(
        "bad",
        [
            {"stat": ["affection"]},  # unhashable — set 조회에서 TypeError 나던 경우
            {"character": ["엘레나"]},
            {"change": "많이"},
            {"change": True},
            {"reason": {"text": "도움을 줌"}},
        ],
    )
    def test_relationship_bad_field_types_rejected(
        self, validator: StateChangeValidator, bad: dict
    ) -> None:
        item = {"character": "엘레나", "stat": "affection", "change": 2, "reason": "도움을 줌", **bad}
        result = validator.validate({"relationship_changes": [item]})
        assert result["relationship_changes"] == []

    @pytest.mark.parametrize("raw", [None, "변경", ["a"], 3])
    def test_non_dict_changes_return_empty(self, validator: StateChangeValidator, raw: object) -> None:
        assert validator.validate(raw) == {}  # type: ignore[arg-type]
