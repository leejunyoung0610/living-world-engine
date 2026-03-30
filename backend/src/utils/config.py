"""
설정 관리 모듈

환경 변수를 로드하고 앱 전체에서 사용할 설정을 관리합니다.
"""

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
WORLDS_DIR = BACKEND_ROOT / "src" / "worlds"
SAVES_DIR = PROJECT_ROOT / "saves"
# 장기기억 파일 — CWD와 무관하게 항상 프로젝트 루트 기준 (play_game --reset 과 동일 경로)
MEMORIES_JSON_PATH = PROJECT_ROOT / "data" / "memories.json"

# Anthropic 공식 모델 ID (향후 스위칭 로직에서도 재사용)
CLAUDE_MODEL_HAIKU_45 = "claude-haiku-4-5-20251001"
CLAUDE_MODEL_SONNET_45 = "claude-sonnet-4-5-20250929"

# .env 에 짧게 쓸 때 → 전체 ID로 치환 (나중에 모델 스위치 알고리즘과 호환)
LLM_MODEL_ALIASES: dict[str, str] = {
    "haiku": CLAUDE_MODEL_HAIKU_45,
    "hikaru": CLAUDE_MODEL_HAIKU_45,  # 히카루 = Haiku 테스트용 별칭
    "sonnet": CLAUDE_MODEL_SONNET_45,
    "sonnet45": CLAUDE_MODEL_SONNET_45,
    "haiku45": CLAUDE_MODEL_HAIKU_45,
}


class Settings(BaseSettings):
    """앱 설정"""

    model_config = {
        "env_file": str(PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }

    # API
    anthropic_api_key: str = ""

    # 서버
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # 게임
    default_world: str = "arcane_academy"
    max_turns_per_session: int = 100
    # 기본: Sonnet 4.5. (선택) .env 에서만 Haiku 등 다른 ID 지정 가능 — 단가는 UsageTracker가 모델명으로 구분
    llm_model: str = CLAUDE_MODEL_SONNET_45
    # 출력 상한 — 낮출수록 비용↓ (툴 JSON+대사 동시 응답 고려, 너무 낮으면 잘림)
    llm_max_tokens: int = 768

    @field_validator("llm_model", mode="before")
    @classmethod
    def resolve_llm_model(cls, v: object) -> object:
        if not isinstance(v, str):
            return v
        key = v.strip().lower()
        return LLM_MODEL_ALIASES.get(key, v.strip())


def get_settings() -> Settings:
    """설정 싱글톤 반환"""
    return Settings()
