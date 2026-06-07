"""
pytest 설정 및 공통 픽스쳐
"""

from pathlib import Path

import pytest

from backend.src.engine.state import WorldState
from backend.src.engine.memory import KeywordMemorySearch
from backend.src.engine.validator import StateChangeValidator


# 테스트용 경로
TEST_DIR = Path(__file__).parent
PROJECT_ROOT = TEST_DIR.parent.parent
WORLDS_DIR = PROJECT_ROOT / "backend" / "src" / "worlds"


@pytest.fixture
def world_state() -> WorldState:
    """기본 WorldState 픽스쳐"""
    state = WorldState()
    state.world = {
        "id": "test-world",
        "time": "Day 1",
    }
    state.player = {
        "name": "TestPlayer",
        "class": "정크",
        "stats": {"hp": 24, "mana": 10, "focus": 4},
        "flags": {"junk": True},
        "relationships": {
            "elena": {"affection": 50, "trust": 30},
            "bella": {"affection": 40, "trust": 20},
        },
    }
    state.npcs = [
        {
            "id": "elena",
            "name": "엘레나",
            "role": "2학년 수석",
            "location": "결투장",
            "relationship_stats": {"affection": True, "trust": True},
        },
        {
            "id": "bella",
            "name": "벨라",
            "role": "귀족 정크",
            "location": "기숙사",
            "relationship_stats": {"affection": True, "trust": True},
        },
        {
            "id": "lua",
            "name": "루아",
            "role": "정령마법 천재",
            "location": "정령정원",
        },
    ]
    return state


@pytest.fixture
def memory_search() -> KeywordMemorySearch:
    """기본 KeywordMemorySearch 픽스쳐"""
    mem = KeywordMemorySearch()
    mem.add_memory("엘레나와 결투장에서 처음 만났다", emotion="surprise", importance=7)
    mem.add_memory("벨라에게 도서관에서 도움을 줬다", emotion="joy", importance=6)
    mem.add_memory("루아와 정령정원에서 산책했다", emotion="joy", importance=5)
    return mem


@pytest.fixture
def validator(world_state: WorldState) -> StateChangeValidator:
    """기본 Validator 픽스쳐"""
    v = StateChangeValidator()
    v.set_valid_characters(world_state.get_all_character_names())
    return v


@pytest.fixture
def arcane_academy_path() -> Path:
    """아케인 아카데미 세계관 경로"""
    return WORLDS_DIR / "arcane_academy"

def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow API tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "rate_limit: slowapi 한도 검증 (기본은 비활성)")


@pytest.fixture(autouse=True)
def _disable_rate_limits_for_unit_tests(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch):
    """Epic F slowapi — 기본적으로 환경으로 끔 (`create_app` 이 설정을 반영). `@pytest.mark.rate_limit` 이면 유지.

    로컬 `.env`에 ``REQUIRE_INVITE_CODE_FOR_SIGNUP=true``가 있어도 유닛에서 빈 초대로 가입 가능하도록 끔
    (초대 필수 자체를 검증하는 테스트는 같은 monkeypatch로 다시 켠다).
    """
    monkeypatch.setenv("REQUIRE_INVITE_CODE_FOR_SIGNUP", "false")
    if request.node.get_closest_marker("rate_limit"):
        yield
    else:
        monkeypatch.setenv("RATE_LIMITING_ENABLED", "false")
        yield