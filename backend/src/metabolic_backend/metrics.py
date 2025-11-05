"\"\"\"Lightweight latency metrics recorder for SLA monitoring.\"\"\""

from __future__ import annotations

import threading
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict


@dataclass
class LatencyStats:
    count: int = 0
    total: float = 0.0
    max_value: float = 0.0

    def record(self, value: float) -> None:
        self.count += 1
        self.total += value
        if value > self.max_value:
            self.max_value = value

    def summary(self) -> Dict[str, float]:
        avg = self.total / self.count if self.count else 0.0
        return {"count": self.count, "avg_ms": avg * 1000.0, "max_ms": self.max_value * 1000.0}


class LatencyMonitor:
    def __init__(self) -> None:
        self._stats: Dict[str, LatencyStats] = defaultdict(LatencyStats)
        self._lock = threading.Lock()

    def record(self, stage: str, duration: float) -> None:
        with self._lock:
            self._stats[stage].record(duration)

    def snapshot(self) -> Dict[str, Dict[str, float]]:
        with self._lock:
            return {stage: stats.summary() for stage, stats in self._stats.items()}


monitor = LatencyMonitor()


def record_latency(stage: str, duration: float) -> None:
    monitor.record(stage, duration)


def latency_summary() -> Dict[str, Dict[str, float]]:
    return monitor.snapshot()

