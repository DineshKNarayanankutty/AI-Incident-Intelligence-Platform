"""Small application metrics abstraction."""
from __future__ import annotations

from dataclasses import dataclass, field
from time import monotonic


@dataclass
class Metrics:
    requests: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    prompt_calls: int = 0
    prompt_failures: int = 0
    _started: dict[str, float] = field(default_factory=dict)

    def start(self, operation_id: str) -> None:
        self._started[operation_id] = monotonic()

    def finish(self, operation_id: str, failed: bool = False) -> float:
        elapsed = (monotonic() - self._started.pop(operation_id, monotonic())) * 1000
        self.requests += 1
        self.total_latency_ms += elapsed
        self.failures += int(failed)
        return elapsed

    @property
    def average_latency_ms(self) -> float:
        return self.total_latency_ms / self.requests if self.requests else 0.0
