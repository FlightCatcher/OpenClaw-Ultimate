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
