"""Thread-safe runtime metrics used by the incident API."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
from typing import Any


@dataclass
class Metrics:
    """Small in-process metrics store for health/debug visibility.

    Azure Monitor/OpenTelemetry is the durable telemetry backend in Azure.
    These counters intentionally remain lightweight and contain no payload data.
    When an OpenTelemetry metrics provider is active, the same operation-level
    counters and latency are exported as custom Azure Monitor metrics.
    """

    requests: int = 0
    failures: int = 0
    total_latency_ms: float = 0.0
    prompt_calls: int = 0
    prompt_failures: int = 0
    operation_requests: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    operation_failures: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    operation_latency_ms: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    _started: dict[str, float] = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock, repr=False)
    _otel_initialized: bool = field(default=False, init=False, repr=False)
    _otel_request_counter: Any = field(default=None, init=False, repr=False)
    _otel_failure_counter: Any = field(default=None, init=False, repr=False)
    _otel_latency_histogram: Any = field(default=None, init=False, repr=False)

    def _ensure_otel_metrics(self) -> None:
        """Create custom OTel instruments once, when an SDK provider is available."""
        if self._otel_initialized:
            return

        try:
            from opentelemetry import metrics as otel_metrics

            meter = otel_metrics.get_meter("ai-incident-intelligence.runtime")
            self._otel_request_counter = meter.create_counter(
                "incident.operation.requests",
                description="Incident API operation requests.",
                unit="1",
            )
            self._otel_failure_counter = meter.create_counter(
                "incident.operation.failures",
                description="Incident API operation failures.",
                unit="1",
            )
            self._otel_latency_histogram = meter.create_histogram(
                "incident.operation.duration",
                description="Incident API operation latency.",
                unit="ms",
            )
        except Exception:
            # Local/test environments may have only the OpenTelemetry API or a
            # no-op provider. Runtime counters must continue to work regardless.
            self._otel_request_counter = None
            self._otel_failure_counter = None
            self._otel_latency_histogram = None

        self._otel_initialized = True

    def _record_otel(self, operation: str, latency_ms: float, failed: bool) -> None:
        self._ensure_otel_metrics()
        attributes = {"operation": operation}
        try:
            if self._otel_request_counter is not None:
                self._otel_request_counter.add(1, attributes)
            if failed and self._otel_failure_counter is not None:
                self._otel_failure_counter.add(1, attributes)
            if self._otel_latency_histogram is not None:
                self._otel_latency_histogram.record(latency_ms, attributes)
        except Exception:
            # Never let telemetry break inference or analysis requests.
            return

    def start(self, operation_id: str) -> None:
        with self._lock:
            self._started[operation_id] = monotonic()

    def finish(
        self,
        operation_id: str,
        failed: bool = False,
        operation: str = "request",
    ) -> float:
        with self._lock:
            started = self._started.pop(operation_id, monotonic())
            elapsed = (monotonic() - started) * 1000
            self.requests += 1
            self.total_latency_ms += elapsed
            self.failures += int(failed)
            self.operation_requests[operation] += 1
            self.operation_latency_ms[operation] += elapsed
            self.operation_failures[operation] += int(failed)
            self._record_otel(operation, elapsed, failed)
            return elapsed

    def record(self, operation: str, latency_ms: float, failed: bool = False) -> None:
        with self._lock:
            self.requests += 1
            self.total_latency_ms += latency_ms
            self.failures += int(failed)
            self.operation_requests[operation] += 1
            self.operation_latency_ms[operation] += latency_ms
            self.operation_failures[operation] += int(failed)
            if operation == "foundry.analyze":
                self.prompt_calls += 1
                self.prompt_failures += int(failed)
            self._record_otel(operation, latency_ms, failed)

    @property
    def average_latency_ms(self) -> float:
        with self._lock:
            return self.total_latency_ms / self.requests if self.requests else 0.0

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            operations = {}
            for name, count in self.operation_requests.items():
                total = self.operation_latency_ms[name]
                operations[name] = {
                    "requests": count,
                    "failures": self.operation_failures[name],
                    "average_latency_ms": round(total / count, 2) if count else 0.0,
                }

            return {
                "requests": self.requests,
                "failures": self.failures,
                "average_latency_ms": round(
                    self.total_latency_ms / self.requests, 2
                ) if self.requests else 0.0,
                "prompt_calls": self.prompt_calls,
                "prompt_failures": self.prompt_failures,
                "operations": operations,
            }


runtime_metrics = Metrics()
