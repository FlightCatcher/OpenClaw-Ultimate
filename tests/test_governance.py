from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest

from openclaw_ultimate.governance import (
    ConfirmationRequired,
    ConfirmationStatus,
    PlanControlState,
    RiskLevel,
    SQLiteGovernanceStore,
)
from openclaw_ultimate.memory import SQLiteMemoryStore


def test_confirmation_is_single_use(tmp_path) -> None:
    store = SQLiteGovernanceStore(tmp_path / "governance.db")

    with pytest.raises(ConfirmationRequired) as required:
        store.require_confirmation(
            action="memory.delete",
            description="Delete memory",
            risk=RiskLevel.HIGH,
            resource_id="memory-1",
        )

    confirmation = store.resolve_confirmation(
        required.value.request.confirmation_id,
        approve=True,
    )
    assert confirmation.status == ConfirmationStatus.APPROVED

    store.require_confirmation(
        action="memory.delete",
        description="Delete memory",
        risk=RiskLevel.HIGH,
        resource_id="memory-1",
    )

    consumed = store.list_confirmations(limit=10)[0]
    assert consumed.status == ConfirmationStatus.CONSUMED

    with pytest.raises(ConfirmationRequired):
        store.require_confirmation(
            action="memory.delete",
            description="Delete memory",
            risk=RiskLevel.HIGH,
            resource_id="memory-1",
        )


def test_audit_and_plan_controls_are_persisted(tmp_path) -> None:
    path = tmp_path / "governance.db"
    store = SQLiteGovernanceStore(path)
    store.audit(category="test", action="verify", outcome="ok")
    store.set_plan_control("plan-1", PlanControlState.PAUSE)

    reloaded = SQLiteGovernanceStore(path)

    assert reloaded.list_audit()[0].action == "control.set"
    assert reloaded.plan_control_state("plan-1") == PlanControlState.PAUSE
    assert reloaded.schema_versions() == (1,)


def test_concurrent_stores_serialize_governance_writes(tmp_path) -> None:
    db_path = tmp_path / "governance.db"
    stores = (SQLiteGovernanceStore(db_path), SQLiteGovernanceStore(db_path))

    def write_event(index: int) -> str:
        return (
            stores[index % 2]
            .audit(
                category="concurrency",
                action=f"event-{index}",
                outcome="ok",
            )
            .event_id
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        event_ids = tuple(executor.map(write_event, range(40)))

    assert len(set(event_ids)) == 40
    assert len(stores[0].list_audit(limit=100)) == 40


def test_memory_governance_archives_expired_records(tmp_path) -> None:
    store = SQLiteMemoryStore(tmp_path / "memory.db")
    expired = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    record = store.add(
        content="temporary",
        embedding=(1.0, 0.0),
        memory_type="project",
        importance=0.8,
        sensitivity="private",
        expires_at=expired,
    )

    assert store.list() == ()
    assert store.prune_expired() == 1
    archived = store.get(record.id)
    assert archived.archived is True
    assert archived.memory_type == "project"
    assert archived.importance == 0.8
    assert archived.sensitivity == "private"
