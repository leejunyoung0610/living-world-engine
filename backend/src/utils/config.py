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

    # API — 플랫폼 단일 Anthropic 키(모든 유저 LLM 호출)
    anthropic_api_key: str = ""

    # 서버
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True
    # CORS — 콤마 구분 (Vite 기본 http://localhost:5173)
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # JWT (프로덕션에서는 JWT_SECRET 필수 변경)
    jwt_secret: str = "dev-only-change-me-32bytes-min!!"  # ≥32바이트 권장 (HS256)
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7  # 7일

    # PostgreSQL (로컬: .env.example 참고). 비우면 API DB 접속 시 오류 — 테스트는 SQLite 오버라이드
    database_url: str = ""
    # UGC 월드 수 상한 (정책·플랜과 맞출 것)
    max_worlds_per_user: int = 3
    # 가입 게이트 (Epic C) — True면 유효한 DB 초대 코드 없이는 signup 불가
    require_invite_code_for_signup: bool = False
    # 전체 가입자 상한 — None 이면 미적용. 정책 상한(예: 100)은 UGC_MVP_PLAN 참고
    max_total_users: int | None = None

    # 플랫폼 키 일일 턴 쿼터 (Epic D) — UTC 자정 리셋.
    enforce_platform_turn_quota: bool = False
    platform_daily_turn_limit: int | None = None  # 예: 20. None 이거나 1 미만이면 enforce 시에도 실질 미적용

    # 레이트 리밋 (Epic F, slowapi) — `backend/tests/conftest.py` 가 테스트에서 끔.
    rate_limiting_enabled: bool = True

    # --- Kakao OAuth ---
    #: 비활성 시 라우트 자체가 404. 키만 채우고 ``KAKAO_LOGIN_ENABLED=true`` 로 켠다.
    kakao_login_enabled: bool = False
    kakao_client_id: str = ""
    #: 카카오 콘솔 「보안」에서 발급. 비워두면 token 교환 시 secret 미전송 (콘솔에서 「사용 안 함」이어야 동작).
    kakao_client_secret: str = ""
    #: 카카오 콘솔에 등록한 Redirect URI 와 **글자 단위로 동일**해야 함.
    kakao_redirect_uri: str = ""
    #: 콜백 후 토큰을 들고 돌아올 프론트 콜백 URL. 비우면 ``/oauth/callback`` 로 폴백.
    kakao_post_login_redirect: str = ""

    # 관측 (Epic H) — Sentry DSN 비우면 비활성. 구조화 로그는 JSON 한 줄(요청 id·경로·상태 등).
    sentry_dsn: str = ""
    sentry_environment: str | None = None
    sentry_traces_sample_rate: float = 0.0
    structured_logging: bool = False

    # 비용 알림·긴급 셧다운 (Epic E) — 플랫폼 턴 비용은 `UsageTracker` 단가로 일별 누적.
    emergency_shutdown: bool = False
    platform_daily_cost_alert_threshold_usd: float | None = None  # 예: 50.0 — None 이면 알림 없음
    platform_cost_alert_webhook_url: str = ""  # Slack Incoming Webhook 등 JSON `{"text":...}` 수신 URL

    # 게임
    default_world: str = "arcane_academy"
    max_turns_per_session: int = 100
    # 기본: Sonnet 4.5. (선택) .env 에서만 Haiku 등 다른 ID 지정 가능 — 단가는 UsageTracker가 모델명으로 구분
    llm_model: str = CLAUDE_MODEL_SONNET_45
    # 출력 상한 — 낮출수록 비용↓ (툴 JSON+대사 동시 응답 고려, 너무 낮으면 잘림)
    llm_max_tokens: int = 768
    # True: 1차 응답에 NPC 텍스트+tool_use가 같이 오면 2차 API 호출 생략 (game_loop → ClaudeClient)
    enable_single_pass: bool = True
    # 장기기억: 전체 개수가 max_total 초과 시 가장 오래된 저중요도 묶음을 태그 요약 1건으로 접음
    ltm_compact_max_total: int = 200
    ltm_compact_min_batch: int = 10
    ltm_compact_importance_below: int = 50

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
