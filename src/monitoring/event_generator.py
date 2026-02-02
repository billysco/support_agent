"""
Log event generator with deterministic demo mode for monitoring simulation.
"""

import random
import time
import threading
from collections import deque
from datetime import datetime
from typing import Optional, Callable
import uuid

from .schemas import LogEvent, EventType


class LogEventGenerator:
    """Generates realistic log events for monitoring simulation."""

    REGIONS = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "ap-northeast-1"]
    SERVICES = {
        EventType.api: ["auth-api", "user-api", "payment-api", "product-api", "search-api"],
        EventType.database: ["postgres-primary", "postgres-replica", "redis-cache", "mongo-db"],
        EventType.frontend: ["web-app", "mobile-app", "admin-dashboard"],
        EventType.infrastructure: ["k8s-cluster", "load-balancer", "cdn", "storage"]
    }

    API_ENDPOINTS = [
        "/api/v1/users",
        "/api/v1/auth/login",
        "/api/v1/products",
        "/api/v1/orders",
        "/api/v1/payments",
        "/api/v1/search"
    ]

    CUSTOMER_IDS = [f"cust_{i:05d}" for i in range(1, 101)]

    def __init__(self, event_interval: float = 2.0, demo_mode: bool = True):
        """
        Initialize the event generator.

        Args:
            event_interval: Time between events in seconds
            demo_mode: If True, generates deterministic 10-event sequence
        """
        self._event_interval = event_interval
        self._demo_mode = demo_mode
        self._running = False
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._events: deque[LogEvent] = deque(maxlen=500)
        self._event_count = 0
        self._max_events = 10 if demo_mode else None

        # Demo mode: pre-generated critical event and callback for synchronization
        self._critical_event: Optional[LogEvent] = None
        self._ai_ready_event = threading.Event()
        self._on_complete_callback: Optional[Callable] = None

    def set_critical_event(self, event: LogEvent):
        """Set the pre-generated critical event for demo mode."""
        self._critical_event = event

    def set_ai_ready(self):
        """Signal that AI processing is complete for the critical event."""
        self._ai_ready_event.set()

    def set_on_complete(self, callback: Callable):
        """Set callback to run when demo completes."""
        self._on_complete_callback = callback

    def get_critical_event(self) -> Optional[LogEvent]:
        """Get the critical event for pre-processing."""
        return self._critical_event

    def start(self):
        """Start the event generator thread."""
        with self._lock:
            if self._running:
                return

            self._running = True
            self._stop_event.clear()
            self._ai_ready_event.clear()
            self._event_count = 0
            self._thread = threading.Thread(target=self._generate_events, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop the event generator thread gracefully."""
        with self._lock:
            if not self._running:
                return

            self._running = False
            self._stop_event.set()
            self._ai_ready_event.set()  # Unblock if waiting

        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def is_running(self) -> bool:
        """Check if generator is running."""
        with self._lock:
            return self._running

    def get_events(self, limit: Optional[int] = None) -> list[LogEvent]:
        """Get recent events from the buffer."""
        with self._lock:
            events = list(self._events)

        events.sort(key=lambda e: e.timestamp, reverse=True)

        if limit:
            events = events[:limit]

        return events

    def clear_events(self):
        """Clear the event buffer."""
        with self._lock:
            self._events.clear()
            self._event_count = 0

    def _generate_events(self):
        """Background thread that generates events."""
        print(f"[Generator] Started in {'demo' if self._demo_mode else 'continuous'} mode")

        while True:
            with self._lock:
                if not self._running:
                    break

            # Check if we've hit max events in demo mode
            if self._demo_mode and self._max_events and self._event_count >= self._max_events:
                print(f"[Generator] Demo complete - {self._event_count} events generated")
                with self._lock:
                    self._running = False
                if self._on_complete_callback:
                    self._on_complete_callback()
                break

            # For event 4 (index 3), wait for AI to be ready first
            if self._demo_mode and self._event_count == 3:
                print(f"[Generator] Waiting for AI to be ready before critical event...")
                self._ai_ready_event.wait()
                if not self._running:
                    break
                print(f"[Generator] AI ready, showing critical event")

            event = self._create_demo_event() if self._demo_mode else self._create_random_event()

            with self._lock:
                self._events.append(event)
                self._event_count += 1
                print(f"[Generator] Event {self._event_count}: {event.service_name} (critical={event.critical})")

            # Wait for next interval
            if self._stop_event.wait(timeout=self._event_interval):
                break

        print(f"[Generator] Stopped")

    def _create_demo_event(self) -> LogEvent:
        """Create deterministic demo event based on sequence position."""
        # Event 4 (index 3) is the critical one - use pre-generated event
        if self._event_count == 3 and self._critical_event:
            # Update timestamp to NOW so it appears in correct order
            self._critical_event.timestamp = datetime.now()
            return self._critical_event

        # Events 1-3: normal events, Events 5-10: mix of normal
        is_critical = False
        event_type = random.choice([EventType.api, EventType.database, EventType.frontend])

        if event_type == EventType.api:
            return self._create_api_event(anomalous=is_critical)
        elif event_type == EventType.database:
            return self._create_database_event(anomalous=is_critical)
        else:
            return self._create_frontend_event(anomalous=is_critical)

    def _create_random_event(self) -> LogEvent:
        """Create a random event (non-demo mode)."""
        event_type = random.choice(list(EventType))
        is_anomalous = random.random() < 0.15

        if event_type == EventType.api:
            return self._create_api_event(is_anomalous)
        elif event_type == EventType.database:
            return self._create_database_event(is_anomalous)
        elif event_type == EventType.frontend:
            return self._create_frontend_event(is_anomalous)
        else:
            return self._create_infrastructure_event(is_anomalous)

    def _create_api_event(self, anomalous: bool) -> LogEvent:
        """Create an API log event."""
        service_name = random.choice(self.SERVICES[EventType.api])
        endpoint = random.choice(self.API_ENDPOINTS)

        if anomalous:
            latency = random.uniform(550, 800)
            status_code = random.choice([500, 503, 429])
            severity = "error"
        else:
            latency = random.uniform(50, 200)
            status_code = random.choice([200, 200, 200, 201])
            severity = "info"

        return LogEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.api,
            service_name=service_name,
            region=random.choice(self.REGIONS),
            customer_id=random.choice(self.CUSTOMER_IDS) if random.random() < 0.7 else None,
            severity=severity,
            message=f"{endpoint} - {status_code}",
            metrics={
                "latency_ms": round(latency, 2),
                "status_code": status_code,
                "request_size_kb": round(random.uniform(0.5, 10), 2)
            }
        )

    def _create_database_event(self, anomalous: bool) -> LogEvent:
        """Create a database log event."""
        service_name = random.choice(self.SERVICES[EventType.database])

        if anomalous:
            query_time = random.uniform(350, 500)
            severity = "error"
        else:
            query_time = random.uniform(10, 100)
            severity = "info"

        return LogEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.database,
            service_name=service_name,
            region=random.choice(self.REGIONS),
            customer_id=random.choice(self.CUSTOMER_IDS) if random.random() < 0.3 else None,
            severity=severity,
            message=f"Query executed: SELECT * FROM users...",
            metrics={
                "query_time_ms": round(query_time, 2),
                "rows_affected": random.randint(0, 100),
                "connection_pool_size": random.randint(5, 20)
            }
        )

    def _create_frontend_event(self, anomalous: bool) -> LogEvent:
        """Create a frontend log event."""
        service_name = random.choice(self.SERVICES[EventType.frontend])

        if anomalous:
            load_time = random.uniform(5500, 8000)
            severity = "error"
        else:
            load_time = random.uniform(500, 2000)
            severity = "info"

        return LogEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.frontend,
            service_name=service_name,
            region=random.choice(self.REGIONS),
            customer_id=random.choice(self.CUSTOMER_IDS) if random.random() < 0.8 else None,
            severity=severity,
            message="Page loaded successfully" if not anomalous else "Page load error: timeout",
            metrics={
                "load_time_ms": round(load_time, 2),
                "bundle_size_kb": round(random.uniform(200, 400), 2),
                "resources_loaded": random.randint(10, 30)
            }
        )

    def _create_infrastructure_event(self, anomalous: bool) -> LogEvent:
        """Create an infrastructure log event."""
        service_name = random.choice(self.SERVICES[EventType.infrastructure])

        if anomalous:
            cpu = random.uniform(92, 98)
            memory = random.uniform(95, 99)
            severity = "critical"
        else:
            cpu = random.uniform(20, 60)
            memory = random.uniform(40, 70)
            severity = "info"

        return LogEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.infrastructure,
            service_name=service_name,
            region=random.choice(self.REGIONS),
            customer_id=None,
            severity=severity,
            message="Resource utilization report",
            metrics={
                "cpu_percent": round(cpu, 2),
                "memory_percent": round(memory, 2),
                "disk_io_mbps": round(random.uniform(10, 100), 2),
                "network_io_mbps": round(random.uniform(50, 200), 2)
            }
        )


def create_critical_api_event() -> LogEvent:
    """Create a predetermined critical API event for demo mode."""
    return LogEvent(
        event_id=str(uuid.uuid4()),
        timestamp=datetime.now(),
        event_type=EventType.api,
        service_name="payment-api",
        region="us-east-1",
        customer_id="cust_00042",
        severity="error",
        message="/api/v1/payments - 500",
        metrics={
            "latency_ms": 752.34,
            "status_code": 500,
            "request_size_kb": 2.4
        },
        flagged=True,
        critical=True
    )
