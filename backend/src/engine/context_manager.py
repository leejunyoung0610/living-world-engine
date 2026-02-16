from __future__ import annotations

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class ContextManager:
    """Context Window 최적화"""

    MAX_CONTEXT_TOKENS = 3000
    KEEP_RECENT_TURNS = 10

    def build_context(
        self,
        user_input: str,
        full_history: List[Dict[str, str]],
        max_tokens: int = MAX_CONTEXT_TOKENS,
    ) -> List[Dict[str, str]]:
        if not full_history:
            return []

        recent_messages = self._keep_recent(full_history, self.KEEP_RECENT_TURNS)
        recent_tokens = self._count_tokens(recent_messages)
        remaining_tokens = max_tokens - recent_tokens

        if remaining_tokens <= 0:
            logger.warning("Recent history exceeds token budget")
            return recent_messages

        old_messages = full_history[:-len(recent_messages)] if len(full_history) > len(recent_messages) else []
        sampled = self._sample_important(old_messages, user_input, remaining_tokens)

        optimized = sampled + recent_messages
        total_tokens = self._count_tokens(optimized)
        logger.info(
            f"Context optimized from {len(full_history)} → {len(optimized)} messages ({total_tokens} tokens)"
        )
        return optimized

    def _keep_recent(self, history: List[Dict[str, str]], n_turns: int) -> List[Dict[str, str]]:
        n_messages = n_turns * 2
        return history[-n_messages:] if len(history) > n_messages else history.copy()

    def _sample_important(
        self,
        old_messages: List[Dict[str, str]],
        current_input: str,
        token_budget: int,
    ) -> List[Dict[str, str]]:
        if not old_messages or token_budget <= 0:
            return []

        scored = []
        for msg in old_messages:
            score = self._calculate_importance(msg, current_input)
            if score > 0:
                scored.append((msg, score))

        scored.sort(key=lambda x: x[1], reverse=True)

        selected = []
        used_tokens = 0
        for msg, _ in scored:
            msg_tokens = self._count_tokens([msg])
            if used_tokens + msg_tokens <= token_budget:
                selected.append(msg)
                used_tokens += msg_tokens
            else:
                break

        selected.sort(key=lambda x: old_messages.index(x))
        logger.debug(f"Sampled {len(selected)}/{len(old_messages)} important messages ({used_tokens} tokens)")
        return selected

    def _calculate_importance(self, message: Dict[str, str], current_input: str) -> float:
        score = 0.0
        content = message.get("content", "")

        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    score += 5.0
                    break

        if isinstance(content, str):
            current_lower = current_input.lower()
            content_lower = content.lower()
            npcs = ["루아", "lua", "벨라", "bella", "엘레나", "elena", "록산느", "roxanne"]
            for npc in npcs:
                if npc in current_lower and npc in content_lower:
                    score += 2.0
                    break

            keywords = [kw for kw in current_lower.split() if len(kw) > 2]
            for kw in keywords:
                if kw in content_lower:
                    score += 0.5

            length_score = min(len(content) / 200, 2.0)
            score += length_score

        return score

    def _count_tokens(self, messages: List[Dict[str, str]]) -> int:
        total_chars = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict):
                        total_chars += len(str(block))
        return total_chars // 4
