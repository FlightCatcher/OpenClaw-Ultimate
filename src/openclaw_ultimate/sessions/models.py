from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionRecord:
    """一个持久化会话的基本信息。"""

    id: str
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


@dataclass(frozen=True, slots=True)
class SessionSummaryRecord:
    """持久化的滚动会话摘要。"""

    session_id: str
    summary: str
    covered_message_count: int
    updated_at: str
