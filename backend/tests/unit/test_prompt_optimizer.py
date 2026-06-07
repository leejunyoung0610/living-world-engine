
from backend.src.engine.prompt_optimizer import SystemPromptOptimizer


def test_prompt_length():
    """프롬프트 길이가 목표 범위 안인지"""
    optimizer = SystemPromptOptimizer()

    world = {"name": "Test World"}
    player = {"turn": 1, "location": "test_area"}
    npcs = [
        {
            "id": "npc1",
            "name": "Test NPC",
            "role": "Tester",
            "location": "test_area",
            "persona": {"traits": ["friendly", "helpful", "test"]},
        }
    ]
    memories = [{"content": "Test memory", "importance": 7}]

    prompt = optimizer.build_optimized_prompt(
        world=world,
        player=player,
        npcs=npcs,
        memories=memories,
    )

    # 공통 코어만 (Sonnet 경로) — 슬림 유지
    assert len(prompt) < 3700, f"Prompt too long: {len(prompt)} chars"
    assert "[Haiku·경량 모델 전용" not in prompt


def test_no_haiku_supplement_in_prompt():
    """Sonnet 단일 경로 — Haiku 전용 접두 없음"""
    optimizer = SystemPromptOptimizer()
    prompt = optimizer.build_optimized_prompt(
        world={"name": "Test World"},
        player={"turn": 1, "name": "P", "location": "x"},
        npcs=[],
        memories=[],
    )
    assert "[Haiku·경량 모델 전용" not in prompt
    assert "너는 Test World" in prompt
    assert len(prompt) < 4500


def test_dialogue_npc_cap_truncates_npc_list_without_mention_or_history():
    """지목·히스토리 없을 때 프로필에 대화 상한만큼만 넣음 (전원 주입 방지)."""
    optimizer = SystemPromptOptimizer()

    npcs = [
        {"id": "npc1", "name": "Alpha", "location": "area1", "role": "R", "persona": {"traits": []}},
        {"id": "npc2", "name": "Beta", "location": "area2", "role": "R", "persona": {"traits": []}},
        {"id": "npc3", "name": "Gamma", "location": "area2", "role": "R", "persona": {"traits": []}},
    ]

    prompt = optimizer.build_optimized_prompt(
        world={
            "name": "Test",
            "world_variables": {"dialogue_npc_cap": 2},
        },
        player={"turn": 1, "location": "area1"},
        npcs=npcs,
        memories=[],
        user_message="",
        recent_conversation=[],
    )

    assert "Alpha" in prompt
    assert "Beta" in prompt
    assert "Gamma" not in prompt


def test_dialogue_user_message_mentions_select_npc_even_if_late():
    """플레이어 메시지에 이름 문자열 포함 시 해당 NPC가 우선 선택됨."""
    optimizer = SystemPromptOptimizer()

    npcs = [
        {"id": "npc1", "name": "Here", "location": "area1", "role": "R", "persona": {"traits": []}},
        {"id": "npc2", "name": "There", "location": "area2", "role": "R", "persona": {"traits": []}},
    ]

    prompt = optimizer.build_optimized_prompt(
        world={"name": "Test", "world_variables": {"dialogue_npc_cap": 2}},
        player={"turn": 1},
        npcs=npcs,
        memories=[],
        user_message="There에게 물어보자",
        recent_conversation=[],
    )

    assert "Here" in prompt
    assert "There" in prompt


def test_dialogue_recent_assistant_speakers_prioritized():
    """직전 assistant 발화에 등장한 화자 이름이 선택에 반영됨."""
    optimizer = SystemPromptOptimizer()
    npcs = [
        {"id": "n0", "name": "NPC0", "role": "R", "persona": {"traits": []}},
        {"id": "n1", "name": "NPC1", "role": "R", "persona": {"traits": []}},
        {"id": "n2", "name": "NPC2", "role": "R", "persona": {"traits": []}},
    ]
    prompt = optimizer.build_optimized_prompt(
        world={"name": "W", "world_variables": {"dialogue_npc_cap": 2}},
        player={"name": "P"},
        npcs=npcs,
        memories=[],
        user_message="",
        recent_conversation=[
            {
                "role": "assistant",
                "content": "NPC2 (고개를 끄덕이며) 응.",
            }
        ],
    )
    assert "NPC2" in prompt
    assert "NPC0" in prompt
    assert "NPC1" not in prompt


def test_build_system_blocks_split_for_cache():
    """static / dynamic 분리 — dynamic에만 상황·NPC·기억"""
    optimizer = SystemPromptOptimizer()
    memories = [{"content": "Secret", "importance": 8}]
    npcs = [
        {
            "id": "n1",
            "name": "OnlyHere",
            "location": "A",
            "role": "R",
            "persona": {"traits": ["t"]},
        }
    ]
    static, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"turn": 2, "name": "P", "location": "A"},
        npcs=npcs,
        memories=memories,
    )
    assert "## 현재 상황" in dynamic
    assert "OnlyHere" in dynamic
    assert "Secret" in dynamic
    assert "## 현재 상황" not in static
    assert "OnlyHere" not in static
    assert "## Tool (update_game_state)" in static
    assert "## 응답 규칙" in static
    assert "NPC가 바뀔 때만" in static
    assert "`---`" in static
    assert "npc_memory_updates" in static
    assert "이번 턴 출력 제한" in dynamic


def test_dynamic_includes_player_stats_not_static():
    """플레이어 스텟은 dynamic(캐시 비대상)에만 포함"""
    optimizer = SystemPromptOptimizer()
    static, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"name": "P", "location": "A", "stats": {"fatigue": 3}},
        npcs=[],
        memories=[],
        turn=2,
        day=1,
    )
    assert "fatigue" in dynamic
    assert "fatigue" not in static


def test_static_includes_world_setting_and_one_line_summary():
    """세계관·한 줄 요약은 static(프롬프트 캐시 후보)에 포함"""
    optimizer = SystemPromptOptimizer()
    static, dynamic = optimizer.build_system_blocks(
        world={
            "name": "W",
            "description": "목록용 한줄",
            "world_setting": "긴\n설명",
        },
        player={"name": "P", "location": "A"},
        npcs=[],
        memories=[],
    )
    assert "## 세계 한 줄 요약" in static
    assert "목록용 한줄" in static
    assert "## 세계관 설정" in static
    assert "긴" in static
    assert "## 세계 한 줄 요약" not in dynamic


def test_only_important_memories():
    """중요 기억만 포함되는지"""
    optimizer = SystemPromptOptimizer()

    memories = [
        {"content": "Low importance", "importance": 3},
        {"content": "High importance", "importance": 8},
    ]

    prompt = optimizer.build_optimized_prompt(
        world={"name": "Test"},
        player={"turn": 1, "location": "area1"},
        npcs=[],
        memories=memories,
    )

    assert "High importance" in prompt
    assert "Low importance" not in prompt


def test_dynamic_includes_relationship_stats_for_llm():
    """관계 수치는 dynamic에 포함 — 클로드가 현재값을 본다."""
    optimizer = SystemPromptOptimizer()
    npcs = [
        {
            "id": "kim",
            "name": "김선배",
            "role": "선배",
            "relationship_stats": {"affection": 40, "trust": 30},
        }
    ]
    player = {
        "name": "P",
        "relationships": {"kim": {"affection": 55, "trust": 30}},
    }
    _, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player=player,
        npcs=npcs,
        memories=[],
    )
    assert "## 관계 수치" in dynamic
    assert "호감(affection): 55/100" in dynamic
    assert "신뢰(trust): 30/100" in dynamic


def test_static_forbids_player_npc_blocks_and_flag_changes_guide():
    optimizer = SystemPromptOptimizer()
    static, _ = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"name": "조현용"},
        npcs=[],
        memories=[],
    )
    assert "플레이어(조현용) NPC 블록 절대 금지" in static
    assert "flag_changes" in static
    assert "debt_paid" in static
    assert "모순" in static


def test_static_forbids_npc_group_chat_and_solo_scene_rules():
    optimizer = SystemPromptOptimizer()
    static, _ = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"name": "P"},
        npcs=[],
        memories=[],
    )
    assert "NPC끼리 대화 연속 금지" in static
    assert "따라 말하기" in static or "echo" in static
    assert "혼자·이별·귀가" in static


def test_static_forbids_relationship_numbers_in_user_dialogue():
    optimizer = SystemPromptOptimizer()
    static, _ = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"name": "P"},
        npcs=[],
        memories=[],
    )
    assert "유저에게 보이는 대사에 관계 수치" in static


def test_compact_npc_includes_major_background_and_speech_style_alias():
    optimizer = SystemPromptOptimizer()
    npcs = [
        {
            "id": "d1",
            "name": "Dancer",
            "role": "후배",
            "major": "무용과",
            "personality": "열정적",
            "background": "발레 전공",
            "speech_style": "존댓말, 밝음",
        }
    ]
    _, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"name": "P"},
        npcs=npcs,
        memories=[],
    )
    assert "무용과" in dynamic
    assert "배경: 발레 전공" in dynamic
    assert "말투: 존댓말, 밝음" in dynamic


def test_pending_event_hints_injected_into_dynamic_block():
    optimizer = SystemPromptOptimizer()
    _, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"name": "P", "stats": {}, "relationships": {}},
        npcs=[],
        memories=[],
        pending_event_hints=["아현을 떠올리며 멜로디가 흘렀다."],
    )
    assert "## 방금 일어난 일 (지난 턴)" in dynamic
    assert "아현을 떠올리며 멜로디가 흘렀다." in dynamic
    assert "자연스럽게 인지" in dynamic


def test_npc_short_term_block_in_dynamic():
    optimizer = SystemPromptOptimizer()
    _, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"name": "P", "stats": {}, "relationships": {}},
        npcs=[],
        memories=[],
        npc_short_term_block="### 아현\n- [턴 2] 비밀을 들려줬다",
    )
    assert "## NPC 단기기억" in dynamic
    assert "비밀을 들려줬다" in dynamic


def test_empty_pending_event_hints_omits_block():
    optimizer = SystemPromptOptimizer()
    _, dynamic = optimizer.build_system_blocks(
        world={"name": "W"},
        player={"name": "P", "stats": {}, "relationships": {}},
        npcs=[],
        memories=[],
        pending_event_hints=[],
    )
    assert "## 방금 일어난 일" not in dynamic
