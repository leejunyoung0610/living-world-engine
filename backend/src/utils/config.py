"""
설정 관리 모듈

환경 변수를 로드하고 앱 전체에서 사용할 설정을 관리합니다.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


# 프로젝트 루트 경로
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
WORLDS_DIR = BACKEND_ROOT / "src" / "worlds"
SAVES_DIR = PROJECT_ROOT / "saves"


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
    llm_model: str = "claude-sonnet-4-5-20250929"
    llm_max_tokens: int = 2000


def get_settings() -> Settings:
    """설정 싱글톤 반환"""
    return Settings()
