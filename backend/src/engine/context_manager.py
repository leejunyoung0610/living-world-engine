from __future__ import annotations

from typing import List, Dict

from ..utils.logger import get_logger

logger = get_logger(__name__)


class ContextManager:
    """3-Layer Memory Architecture - Context Window 최적화
    
    Layer 1 (Immediate): 최근 4턴 - 즉각적인 대화 흐름
    Layer 2 (NPC Relationship): 중기 범위(최근 30턴)에서 NPC별 샘플링 - 관계 맥락
    Layer 3 (Critical Events): LongTermMemory가 담당 - 중요 사건 기억
    """

    MAX_CONTEXT_TOKENS = 2000  # 보수적 설정
    KEEP_RECENT_TURNS = 4      # Layer 1: 최근 4턴 무조건 유지
    NPC_SAMPLING_WINDOW = 30   # Layer 2: 최근 30턴 범위에서 샘플링
    NPC_RECENT_TURNS = 2       # Layer 2: NPC별 최근 2턴씩 (3→2 최적화)

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
        """3-Layer Context 구성
        
        Layer 1: 최근 4턴 무조건 유지 (즉각 흐름)
        Layer 2: 중기 범위(최근 30턴)에서 NPC별 샘플링 (관계 맥락)
        Layer 3: LongTermMemory가 System Prompt에 제공 (중요 사건)
        """
        if not full_history:
            return []

        # Layer 1: 최근 4턴 무조건 유지
        recent_messages = self._keep_recent(full_history, self.KEEP_RECENT_TURNS)
        
        # Layer 2: 중기 범위에서 NPC별 샘플링
        sampling_window_start = max(
            0, 
            len(full_history) - len(recent_messages) - self.NPC_SAMPLING_WINDOW * 2
        )
        sampling_window = full_history[sampling_window_start:-len(recent_messages)]
        
        npc_sampled = self._sample_by_npc(sampling_window, self.NPC_RECENT_TURNS)
        
        # 조합 (시간 순서 유지됨)
        optimized = npc_sampled + recent_messages
        
        # 토큰 확인
        total_tokens = self._count_tokens(optimized)
        
        # 초과 시 NPC당 턴 수 줄이기
        if total_tokens > max_tokens:
            logger.warning(f"Token budget exceeded ({total_tokens} > {max_tokens}), reducing NPC turns")
            npc_sampled = self._sample_by_npc(sampling_window, 2)  # 3턴 → 2턴
            optimized = npc_sampled + recent_messages
            total_tokens = self._count_tokens(optimized)
        
        logger.info(
            f"Context: Layer1({len(recent_messages)}) + Layer2({len(npc_sampled)}) = {len(optimized)} ({total_tokens} tokens)"
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
            if npc == 'other':
                # 환경/독백은 최근 2개만
                selected.extend(msgs[-2:] if len(msgs) > 2 else msgs)
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
