"""Which specialist actually did the work in this run.

In PROCESS_MODE=hierarchical the manager executes every task and is *asked* to delegate,
but nothing forces it: in the first runs the Research Director wrote the strategy itself,
because the Strategy Analyst has no tools that would have made delegation necessary.
Specialists record each finished execution here (see crew.TrackedAgent), so a guardrail can
check that the owner of a task really produced it, and use the specialist's own answer.

One crew runs per process (see docs/DECISIONS.md), so a module-level registry is safe.
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_outputs: dict[str, list[str]] = {}


def reset() -> None:
    with _lock:
        _outputs.clear()


def record(key: str, output: Any) -> None:
    if not key:
        return
    with _lock:
        _outputs.setdefault(key, []).append(str(output))


def outputs(key: str) -> list[str]:
    with _lock:
        return list(_outputs.get(key, []))
