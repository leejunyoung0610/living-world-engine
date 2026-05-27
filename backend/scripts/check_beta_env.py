#!/usr/bin/env python3
"""베타 배포 전 환경 변수 점검 — 값은 출력하지 않고 상태만 표시.

사용 (프로젝트 루트):
  poetry run python backend/scripts/check_beta_env.py
  poetry run python backend/scripts/check_beta_env.py --strict   # 권장·R2까지 필수
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.src.utils.config import get_settings

DEV_JWT = "dev-only-change-me-32bytes-min!!"


def _status_set(label: str, ok: bool, note: str = "") -> tuple[str, bool]:
    mark = "OK" if ok else "MISSING"
    extra = f" ({note})" if note else ""
    return f"  [{mark}] {label}{extra}", ok


def _check_str(name: str, val: str, *, min_len: int = 1) -> tuple[bool, str]:
    s = (val or "").strip()
    if len(s) < min_len:
        return False, "MISSING"
    return True, "set"


def main() -> int:
    parser = argparse.ArgumentParser(description="Beta deployment env checklist")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="R2·Sentry·비용 방어·가입 게이트까지 필수로 검사",
    )
    args = parser.parse_args()
    s = get_settings()
    failures = 0
    lines: list[str] = ["=== Beta env check (values hidden) ==="]

    checks: list[tuple[str, bool, str]] = []

    ok, _ = _check_str("DATABASE_URL", s.database_url)
    checks.append(("DATABASE_URL", ok, ""))

    jwt_ok = bool(s.jwt_secret and s.jwt_secret != DEV_JWT and len(s.jwt_secret) >= 32)
    checks.append(
        (
            "JWT_SECRET",
            jwt_ok,
            "≥32 chars, not dev default" if not jwt_ok else "",
        )
    )

    ok, _ = _check_str("ANTHROPIC_API_KEY", s.anthropic_api_key, min_len=20)
    checks.append(("ANTHROPIC_API_KEY", ok, ""))

    checks.append(("LLM_MODEL", bool(s.llm_model.strip()), ""))
    checks.append(("ENABLE_SINGLE_PASS", s.enable_single_pass, ""))

    ok, _ = _check_str("REPLICATE_API_TOKEN", s.replicate_api_token, min_len=8)
    checks.append(("REPLICATE_API_TOKEN", ok, ""))

    r2_keys = (
        s.r2_account_id,
        s.r2_access_key,
        s.r2_secret_key,
        s.r2_bucket,
        s.r2_public_url,
    )
    r2_all = all(bool(x.strip()) for x in r2_keys)
    r2_any = any(bool(x.strip()) for x in r2_keys)
    if r2_any and not r2_all:
        checks.append(("R2_* (all five)", False, "partial — set all or none"))
    else:
        checks.append(("R2_* (all five)", r2_all or not args.strict, "optional" if not args.strict else ""))

    checks.append(("DEBUG=false", not s.debug, f"current debug={s.debug}"))
    cors_ok = bool(s.cors_origins.strip()) and "*" not in s.cors_origins
    checks.append(("CORS_ORIGINS (no *)", cors_ok, ""))

    checks.append(("RATE_LIMITING_ENABLED", s.rate_limiting_enabled, ""))

    if args.strict:
        checks.append(("SENTRY_DSN", bool(s.sentry_dsn.strip()), ""))
        checks.append(("STRUCTURED_LOGGING", s.structured_logging, ""))
        checks.append(("ENFORCE_PLATFORM_TURN_QUOTA", s.enforce_platform_turn_quota, ""))
        checks.append(
            (
                "PLATFORM_DAILY_TURN_LIMIT",
                s.platform_daily_turn_limit is not None and s.platform_daily_turn_limit >= 1,
                "",
            )
        )
        checks.append(
            (
                "PLATFORM_DAILY_COST_ALERT_THRESHOLD_USD",
                s.platform_daily_cost_alert_threshold_usd is not None,
                "",
            )
        )
        checks.append(
            ("PLATFORM_COST_ALERT_WEBHOOK_URL", bool(s.platform_cost_alert_webhook_url.strip()), "")
        )
        checks.append(
            (
                "IMAGE_GEN_DAILY_BUDGET_USD",
                s.image_gen_daily_budget_usd is not None and s.image_gen_daily_budget_usd > 0,
                "",
            )
        )
        checks.append(("REQUIRE_INVITE_CODE_FOR_SIGNUP", s.require_invite_code_for_signup, ""))
        checks.append(
            ("MAX_TOTAL_USERS", s.max_total_users is not None and s.max_total_users >= 1, "")
        )

    if s.kakao_login_enabled:
        ok_id, _ = _check_str("KAKAO_CLIENT_ID", s.kakao_client_id)
        checks.append(("KAKAO_CLIENT_ID", ok_id, "KAKAO_LOGIN_ENABLED=true"))
    else:
        checks.append(("KAKAO (disabled)", True, "KAKAO_LOGIN_ENABLED=false"))

    for label, ok, note in checks:
        line, _ = _status_set(label, ok, note)
        lines.append(line)
        if not ok:
            failures += 1

    lines.append("")
    if failures:
        lines.append(f"FAIL: {failures} check(s). See docs/BETA_DEPLOYMENT_CHECKLIST.md §2")
        lines.append("  Production template: .env.production.example")
    else:
        lines.append("PASS: all checked variables OK for this mode.")
    print("\n".join(lines))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
