from __future__ import annotations

from typing import List, Dict

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager:
    """3-Layer Memory Architecture - Context Window 최적화

    Layer 1 (Immediate): 최근 N턴(KEEP_RECENT_TURNS) — 유저·NPC 대화 전문
    Layer 2 (NPC Relationship): 중기 샘플링 (기본 비활성 — 유저 발언 누락 방지)
    Layer 3 (Critical Events): LongTermMemory + NPC 단기기억 + 시스템 프롬프트
    """

    # Phase 2 튜닝 (2026-06): 5턴 verbatim + 단기기억/LTM 보완. 턴당 +~2–3원 예상.
    MAX_CONTEXT_TOKENS = 2200
    KEEP_RECENT_TURNS = 7      # Layer 1: 최근 7턴 (유저 발언 6~7턴 전까지 verbatim)
    MAX_STORED_TURNS = 30      # 세션 conversation_history 보존 (메시지 2N개)
    NPC_SAMPLING_WINDOW = 20   # Layer 2: 샘플링 윈도(턴 단위 ×2는 build에서 처리)
    NPC_RECENT_TURNS = 0       # Layer 2 비활성 (NPC명 없는 유저 발언 탈락 방지)
    OTHER_CAP = 4              # Layer 2 사용 시 other(유저 단독 발언) 상한

    def __init__(self):
        self.npc_names = []  # 동적으로 설정됨
    
    def set_npc_names(self, npc_names: List[str]) -> None:
        """세계관 로딩 시 NPC 이름 설정"""
        self.npc_names = [name.lower() for name in npc_names]
        logger.info(f"ContextManager: NPC {len(npc_names)}명 등록 - {', '.join(npc_names)}")

    def build_context(
        self,
        user_input: str,
        full_history: List[Dict[str, str]],
        max_tokens: int = MAX_CONTEXT_TOKENS,
    ) -> List[Dict[str, str]]:
        """3-Layer Context 구성.

        Layer 1·2는 본 클래스. Layer 3는 LongTermMemory + 시스템 프롬프트.
        """
        if not full_history:
            return []

        # Layer 1: 최근 N턴
        recent_messages = self._keep_recent(full_history, self.KEEP_RECENT_TURNS)

        # Layer 2: 중기 범위에서 NPC별 샘플링
        sampling_window_start = max(
            0,
            len(full_history) - len(recent_messages) - self.NPC_SAMPLING_WINDOW * 2,
        )
        sampling_window = full_history[sampling_window_start : -len(recent_messages)]

        layer2_turns = self.NPC_RECENT_TURNS
        npc_sampled = (
            self._sample_by_npc(sampling_window, layer2_turns)
            if sampling_window and layer2_turns > 0
            else []
        )
        optimized = npc_sampled + recent_messages
        total_tokens = self._count_tokens(optimized)

        # 예산 초과 → Layer2부터 턴 수 단계적 감소
        while total_tokens > max_tokens and layer2_turns > 0:
            logger.warning(
                "Token budget exceeded (%s > %s), Layer2 turns %s → %s",
                total_tokens,
                max_tokens,
                layer2_turns,
                layer2_turns - 1,
            )
            layer2_turns -= 1
            npc_sampled = (
                self._sample_by_npc(sampling_window, layer2_turns)
                if sampling_window and layer2_turns > 0
                else []
            )
            optimized = npc_sampled + recent_messages
            total_tokens = self._count_tokens(optimized)

        # 여전히 초과 → Layer 1(최근 턴)만 줄임 (최소 1턴 = 2메시지)
        keep = self.KEEP_RECENT_TURNS
        while total_tokens > max_tokens and keep > 1:
            logger.warning(
                "Token budget exceeded (%s > %s), Layer1 turns %s → %s",
                total_tokens,
                max_tokens,
                keep,
                keep - 1,
            )
            keep -= 1
            recent_messages = self._keep_recent(full_history, keep)
            optimized = npc_sampled + recent_messages
            total_tokens = self._count_tokens(optimized)

        logger.info(
            "Context: Layer1(%s) + Layer2(%s) = %s msgs (~%s tok est.)",
            len(recent_messages),
            len(npc_sampled),
            len(optimized),
            total_tokens,
        )
        return optimized

    def _keep_recent(self, history: List[Dict[str, str]], n_turns: int) -> List[Dict[str, str]]:
        """최근 N턴 유지 (Layer 1)"""
        n_messages = n_turns * 2
        return history[-n_messages:] if len(history) > n_messages else history.copy()

    def _sample_by_npc(
        self,
        messages: List[Dict[str, str]],
        n_turns_per_npc: int,
    ) -> List[Dict[str, str]]:
        """NPC별로 최근 N턴씩 샘플링 (Layer 2)
        
        목적: 각 NPC와의 관계 맥락 유지
        """
        if not messages:
            return []
        
        # NPC별로 메시지 분류
        npc_messages = {npc: [] for npc in self.npc_names}
        npc_messages['other'] = []  # NPC 없는 메시지 (환경/독백)
        
        for msg in messages:
            content = str(msg.get("content", "")).lower()
            found_npc = False
            
            # NPC 이름으로 분류
            for npc in self.npc_names:
                if npc in content:
                    npc_messages[npc].append(msg)
                    found_npc = True
                    break
            
            if not found_npc:
                npc_messages['other'].append(msg)
        
        # 각 NPC별 최근 N턴 선택
        selected = []
        for npc, msgs in npc_messages.items():
            if npc == "other":
                cap = self.OTHER_CAP
                selected.extend(msgs[-cap:] if len(msgs) > cap else msgs)
            else:
                # NPC별 최근 N턴 (2N messages)
                n_messages = n_turns_per_npc * 2
                selected.extend(msgs[-n_messages:] if len(msgs) > n_messages else msgs)
        
        # 시간 순 정렬
        selected.sort(key=lambda x: messages.index(x))
        
        logger.debug(f"NPC sampling: {len(messages)} → {len(selected)} messages")
        return selected


    def _count_tokens(self, messages: List[Dict[str, str]]) -> int:
        """토큰 수 추정 (한글 보정 강화)"""
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        block_str = str(block)
                        # Tool use JSON은 토큰 소비가 많음
                        total_chars += int(len(block_str) * 1.5)
        
        # 한글 보정: 1 token ≈ 1.2 chars
        # (chars / 2는 과소평가, chars / 1.2가 더 정확)
        return int(total_chars / 1.2)
