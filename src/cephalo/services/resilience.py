"""
Cephalo Resilience Layer (resilience.py)
========================================
Inspired by Situation Monitor (hipcityreg/situation-monitor).

Provides:
1. Three-State CircuitBreaker (CLOSED, OPEN, HALF_OPEN): Prevents cascading failures and
   wasteful network hangs when external APIs or search endpoints are throttled.
2. In-Flight RequestDeduplicator: Collapses simultaneous duplicate requests into a shared Future.
3. Stale-While-Revalidate (SWR) Local Cache: Returns cached data immediately to keep UI/agent
   responsive while revalidating in the background.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, Optional, TypeVar

logger = logging.getLogger("cephalo.resilience")

T = TypeVar("T")


class CircuitState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    """Three-state circuit breaker pattern for external HTTP/search services."""

    def __init__(self, service_id: str, failure_threshold: int = 3, reset_timeout: float = 60.0):
        self.service_id = service_id
        self.failure_threshold = failure_threshold
        self.reset_timeout = reset_timeout
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.last_failure_time: Optional[float] = None
        self._lock = threading.Lock()

    def can_request(self) -> bool:
        """Checks if a request is permitted to proceed."""
        with self._lock:
            now = time.time()
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.OPEN:
                if self.last_failure_time and (now - self.last_failure_time) >= self.reset_timeout:
                    self.state = CircuitState.HALF_OPEN
                    logger.info("[CircuitBreaker] %s: OPEN -> HALF_OPEN (probing)", self.service_id)
                    return True
                return False
            if self.state == CircuitState.HALF_OPEN:
                return True
            return False

    def record_success(self) -> None:
        """Records a successful operation; recovers from HALF_OPEN to CLOSED."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                logger.info("[CircuitBreaker] %s: HALF_OPEN -> CLOSED (recovered)", self.service_id)
            self.failures = 0

    def record_failure(self) -> None:
        """Records a failed operation; trips circuit to OPEN if threshold exceeded."""
        with self._lock:
            self.failures += 1
            self.last_failure_time = time.time()
            if self.state == CircuitState.HALF_OPEN or self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    "[CircuitBreaker] %s tripped to OPEN (%d failures)",
                    self.service_id,
                    self.failures,
                )


class RequestDeduplicator:
    """Collapses identical concurrent requests into a single in-flight execution."""

    def __init__(self):
        self._in_flight: Dict[str, threading.Event] = {}
        self._results: Dict[str, Any] = {}
        self._errors: Dict[str, Exception] = {}
        self._lock = threading.Lock()

    def dedupe(self, key: str, fetch_fn: Callable[[], T], timeout: float = 20.0) -> T:
        with self._lock:
            if key in self._in_flight:
                event = self._in_flight[key]
                first_caller = False
            else:
                event = threading.Event()
                self._in_flight[key] = event
                first_caller = True

        if not first_caller:
            event.wait(timeout=timeout)
            if key in self._errors:
                raise self._errors[key]
            return self._results.get(key)

        try:
            result = fetch_fn()
            self._results[key] = result
            return result
        except Exception as e:
            self._errors[key] = e
            raise
        finally:
            with self._lock:
                event.set()
                self._in_flight.pop(key, None)
