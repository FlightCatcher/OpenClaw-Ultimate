from __future__ import annotations

import json
import statistics
import tempfile
from pathlib import Path
from time import perf_counter

from openclaw_ultimate.core.messages import Message
from openclaw_ultimate.core.runtime import RuntimeResult
from openclaw_ultimate.planner import (
    PlanStep,
    RuleBasedVerifier,
    SQLitePlanStore,
    TaskPlan,
)


def _milliseconds(samples: list[float]) -> dict[str, float]:
    return {
        "mean_ms": round(statistics.fmean(samples) * 1000, 3),
        "p95_ms": round(sorted(samples)[int(len(samples) * 0.95) - 1] * 1000, 3),
        "max_ms": round(max(samples) * 1000, 3),
    }


def main() -> None:
    iterations = 100
    save_samples: list[float] = []
    read_samples: list[float] = []
    verify_samples: list[float] = []

    with tempfile.TemporaryDirectory(prefix="vela-benchmark-") as temporary:
        store = SQLitePlanStore(Path(temporary) / "plans.db")
        verifier = RuleBasedVerifier()

        for index in range(iterations):
            step = PlanStep(
                id=f"step-{index}",
                title="Benchmark",
                description="Measure deterministic local operations.",
            )
            plan = TaskPlan.create(goal=f"Benchmark plan {index}", steps=(step,))

            started = perf_counter()
            store.save(plan)
            save_samples.append(perf_counter() - started)

            started = perf_counter()
            store.get(plan.id)
            read_samples.append(perf_counter() - started)

            started = perf_counter()
            verifier.verify(
                plan=plan,
                step=step,
                runtime_result=RuntimeResult(
                    output="completed",
                    messages=(Message.assistant("completed"),),
                    steps=1,
                ),
            )
            verify_samples.append(perf_counter() - started)

    print(
        json.dumps(
            {
                "benchmark": "vela-foundation",
                "version": "1.0.2",
                "iterations": iterations,
                "plan_save": _milliseconds(save_samples),
                "plan_read": _milliseconds(read_samples),
                "verification": _milliseconds(verify_samples),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
