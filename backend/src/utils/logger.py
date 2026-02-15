"""
로깅 유틸리티

앱 전체에서 사용할 로거를 설정합니다.
"""

import logging
import sys


def setup_logger(name: str = "living_world", level: int = logging.DEBUG) -> logging.Logger:
    """로거 생성 및 설정"""
    logger = logging.getLogger(name)

    if not logger.handlers:
        logger.setLevel(level)

        # 콘솔 핸들러
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)

        # 포맷
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def get_logger(name: str = "living_world", level: int = logging.DEBUG) -> logging.Logger:
    """설정된 로거를 반환하는 편의 함수"""
    return setup_logger(name=name, level=level)


# 기본 로거
logger = setup_logger()
