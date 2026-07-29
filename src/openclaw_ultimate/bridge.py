from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import asdict
from typing import Any

from openclaw_ultimate.app import build_default_agent
from openclaw_ultimate.branding import PRODUCT_NAME, VERSION
from openclaw_ultimate.config import Settings, load_settings
from openclaw_ultimate.governance import SQLiteGovernanceStore
from openclaw_ultimate.planner import (
    ErrorContext,
    PlanExecutor,
    ReflectionEngine,
    SQLitePlanStore,
    StepStatus,
    StructuredPlanner,
)
from openclaw_ultimate.rag import (
    SQLiteKnowledgeStore,
    build_knowledge_base,
)

MAX_REQUEST_BYTES = 1_000_000


async def handle_request(
    payload: dict[str, Any],
    *,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """执行 OpenClaw 插件发来的单个结构化 VELA 请求。"""

    action = _required_text(payload, "action")
    current_settings = (settings or load_settings()).model_copy(
        update={
            # OpenClaw 调 VELA 时禁止 VELA 再委托回 OpenClaw，避免递归。
            "openclaw_enabled": False,
        }
    )
    store = SQLitePlanStore(current_settings.planner_db_path)

    if action == "knowledge_status":
        stats = SQLiteKnowledgeStore(current_settings.knowledge_db_path).stats()
        return _success(
            action,
            {
                "root": str(current_settings.knowledge_root),
                "database": str(current_settings.knowledge_db_path),
                "documents": stats.document_count,
                "chunks": stats.chunk_count,
                "last_indexed_at": stats.last_indexed_at,
            },
        )

    if action == "knowledge_search":
        query = _required_text(payload, "query")
        limit = _optional_limit(
            payload.get("limit"),
            default=current_settings.knowledge_search_limit,
        )
        knowledge = build_knowledge_base(current_settings)
        hits = await knowledge.search(
            query,
            limit=limit,
            minimum_score=(current_settings.knowledge_minimum_score),
        )
        return _success(
            action,
            {
                "query": query,
                "results": [
                    {
                        "score": hit.score,
                        "citation": hit.chunk.citation,
                        "content": hit.chunk.content,
                    }
                    for hit in hits
                ],
            },
        )

    if action == "status":
        plans = store.list(limit=200)
        return _success(
            action,
            {
                "service": PRODUCT_NAME,
                "version": VERSION,
                "planner_database": str(current_settings.planner_db_path),
                "plan_count": len(plans),
                "openclaw_recursion_guard": True,
            },
        )

    if action == "plan_show":
        plan = store.get(_required_text(payload, "plan_id"))
        return _success(
            action,
            _serialize_plan_bundle(
                store,
                plan.id,
            ),
        )

    if action == "plan_create":
        goal = _required_text(payload, "goal")
        agent = build_default_agent(current_settings)
        planner = StructuredPlanner(
            agent.model,
            max_steps=current_settings.planner_max_steps,
        )
        plan = await planner.create_plan(
            goal,
            tools=agent.tools.definitions(),
        )
        store.save(plan)
        return _success(
            action,
            _serialize_plan(plan),
        )

    if action == "plan_run":
        plan_id = _required_text(payload, "plan_id")
        plan = store.get(plan_id)
        agent = build_default_agent(current_settings)
        result = await PlanExecutor(
            control_store=SQLiteGovernanceStore(current_settings.governance_db_path)
        ).execute(
            plan=plan,
            agent=agent,
            store=store,
        )
        return _success(
            action,
            {
                "plan": _serialize_plan(result.plan),
                "completed_step_ids": list(result.completed_step_ids),
                "failed_step_id": result.failed_step_id,
                "interrupted_reason": result.interrupted_reason,
            },
        )

    if action == "plan_reflect":
        plan_id = _required_text(payload, "plan_id")
        plan = store.get(plan_id)
        failed_steps = tuple(step for step in plan.steps if step.status == StepStatus.FAILED)
        reflections = []

        for step in failed_steps:
            reflection = ReflectionEngine().reflect(
                plan=plan,
                failed_step=step,
                error_context=ErrorContext(
                    error_type=(step.error or "UnknownError").split(":", 1)[0],
                    error_message=step.error or "Unknown error",
                    tool_name=step.tool_hint,
                    input_summary=step.description,
                ),
            )
            store.save_reflection(reflection)
            reflections.append(asdict(reflection))

        return _success(
            action,
            {
                "plan_id": plan.id,
                "reflections": reflections,
                "reflection_count": len(reflections),
            },
        )

    raise ValueError(f"Unsupported bridge action: {action}")


def _serialize_plan_bundle(
    store: SQLitePlanStore,
    plan_id: str,
) -> dict[str, Any]:
    plan = store.get(plan_id)
    return {
        "plan": _serialize_plan(plan),
        "reflections": [asdict(item) for item in store.list_reflections(plan_id=plan_id)],
        "retry_attempts": [
            asdict(item) for item in store.list_retry_attempts_for_plan(plan_id=plan_id)
        ],
        "revisions": [asdict(item) for item in store.list_revisions(plan_id=plan_id)],
        "verifications": [asdict(item) for item in store.list_verifications(plan_id=plan_id)],
    }


def _serialize_plan(
    plan: Any,
) -> dict[str, Any]:
    return asdict(plan)


def _success(
    action: str,
    data: Any,
) -> dict[str, Any]:
    return {
        "ok": True,
        "action": action,
        "data": data,
    }


def _required_text(
    payload: dict[str, Any],
    key: str,
) -> str:
    value = payload.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Bridge field '{key}' must be non-empty text.")

    return value.strip()


def _optional_limit(
    value: Any,
    *,
    default: int,
) -> int:
    selected = default if value is None else value

    if not isinstance(selected, int) or not 1 <= selected <= 20:
        raise ValueError("Bridge field 'limit' must be between 1 and 20.")

    return selected


def _read_request() -> dict[str, Any]:
    raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)

    if len(raw) > MAX_REQUEST_BYTES:
        raise ValueError("Bridge request exceeds the 1 MB limit.")

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Bridge request must be valid UTF-8 JSON.") from exc

    if not isinstance(payload, dict):
        raise TypeError("Bridge request root must be an object.")

    return payload


def main() -> None:
    try:
        response = asyncio.run(handle_request(_read_request()))
        exit_code = 0
    except Exception as exc:  # noqa: BLE001 - process boundary returns structured errors
        response = {
            "ok": False,
            "error": {
                "type": type(exc).__name__,
                "message": str(exc),
            },
        }
        exit_code = 1

    sys.stdout.write(
        json.dumps(
            response,
            ensure_ascii=False,
            default=str,
        )
    )
    sys.stdout.write("\n")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
