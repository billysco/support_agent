"""
Log event generator with background threading for monitoring simulation.
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
    
    DB_QUERIES = [
        "SELECT * FROM users WHERE id = ?",
        "UPDATE orders SET status = ? WHERE id = ?",
        "INSERT INTO audit_log VALUES (?, ?, ?)",
        "SELECT COUNT(*) FROM products WHERE category = ?",
        "DELETE FROM sessions WHERE expires_at < ?"
    ]
    
    JS_ERRORS = [
        "TypeError: Cannot read property 'data' of undefined",
        "ReferenceError: fetchUser is not defined",
        "NetworkError: Failed to fetch",
        "ChunkLoadError: Loading chunk 3 failed",
        "SecurityError: Blocked a frame with origin"
    ]
    
    CUSTOMER_IDS = [f"cust_{i:05d}" for i in range(1, 101)]
    
    def __init__(self, event_interval: float = 2.0):
        """
        Initialize the event generator.
        
        Args:
            event_interval: Time between events in seconds (default 2.0 for ~30/min)
        """
        self._event_interval = event_interval
        self._running = False
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._events: deque[LogEvent] = deque(maxlen=500)
        self._anomaly_mode = False
        self._anomaly_service: Optional[str] = None
        self._anomaly_count = 0
    
    def start(self):
        """Start the event generator thread."""
        with self._lock:
            if self._running:
                return
            
            self._running = True
            self._thread = threading.Thread(target=self._generate_events, daemon=True)
            self._thread.start()
    
    def stop(self):
        """Stop the event generator thread gracefully."""
        with self._lock:
            if not self._running:
                return
            
            self._running = False
        
        if self._thread:
            self._thread.join(timeout=5.0)
            self._thread = None
    
    def is_running(self) -> bool:
        """Check if generator is running."""
        with self._lock:
            return self._running
    
    def get_events(self, limit: Optional[int] = None) -> list[LogEvent]:
        """
        Get recent events from the buffer.
        
        Args:
            limit: Maximum number of events to return (default all)
            
        Returns:
            List of events sorted by timestamp descending
        """
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
    
    def _generate_events(self):
        """Background thread that generates events continuously."""
        while True:
            with self._lock:
                if not self._running:
                    break
            
            event = self._create_event()
            
            with self._lock:
                self._events.append(event)
            
            time.sleep(self._event_interval)
    
    def _create_event(self) -> LogEvent:
        """Create a single log event."""
        is_anomalous = random.random() < 0.15
        
        if is_anomalous:
            if not self._anomaly_mode or random.random() < 0.3:
                self._anomaly_mode = True
                self._anomaly_service = random.choice(self.SERVICES[random.choice(list(EventType))])
                self._anomaly_count = 0
        
        if self._anomaly_mode:
            self._anomaly_count += 1
            if self._anomaly_count >= 5:
                self._anomaly_mode = False
                self._anomaly_service = None
                self._anomaly_count = 0
        
        event_type = random.choice(list(EventType))
        
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
        service_name = self._anomaly_service if self._anomaly_mode and anomalous else random.choice(self.SERVICES[EventType.api])
        endpoint = random.choice(self.API_ENDPOINTS)
        
        if anomalous:
            latency = random.uniform(500, 800)
            status_code = random.choice([500, 503, 429, 500, 500])
            severity = "error"
        else:
            latency = random.uniform(50, 450)
            status_code = random.choice([200, 200, 200, 200, 201, 400, 404])
            severity = "info" if status_code < 400 else "warning"
        
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
                "request_size_kb": round(random.uniform(0.5, 50), 2)
            }
        )
    
    def _create_database_event(self, anomalous: bool) -> LogEvent:
        """Create a database log event."""
        service_name = self._anomaly_service if self._anomaly_mode and anomalous else random.choice(self.SERVICES[EventType.database])
        query = random.choice(self.DB_QUERIES)
        
        if anomalous:
            query_time = random.uniform(300, 500)
            severity = "error"
            pool_utilization = random.uniform(45, 50)
        else:
            query_time = random.uniform(10, 250)
            severity = "info"
            pool_utilization = random.uniform(5, 40)
        
        return LogEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.database,
            service_name=service_name,
            region=random.choice(self.REGIONS),
            customer_id=random.choice(self.CUSTOMER_IDS) if random.random() < 0.3 else None,
            severity=severity,
            message=f"Query executed: {query[:50]}...",
            metrics={
                "query_time_ms": round(query_time, 2),
                "rows_affected": random.randint(0, 1000),
                "connection_pool_size": int(pool_utilization)
            }
        )
    
    def _create_frontend_event(self, anomalous: bool) -> LogEvent:
        """Create a frontend log event."""
        service_name = self._anomaly_service if self._anomaly_mode and anomalous else random.choice(self.SERVICES[EventType.frontend])
        
        if anomalous:
            load_time = random.uniform(5000, 8000)
            severity = "error"
            has_js_error = random.random() < 0.6
        else:
            load_time = random.uniform(500, 4500)
            severity = "info"
            has_js_error = random.random() < 0.05
        
        if has_js_error:
            error_msg = random.choice(self.JS_ERRORS)
            message = f"Page load error: {error_msg}"
        else:
            message = f"Page loaded successfully"
        
        return LogEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.frontend,
            service_name=service_name,
            region=random.choice(self.REGIONS),
            customer_id=random.choice(self.CUSTOMER_IDS) if random.random() < 0.8 else None,
            severity=severity,
            message=message,
            metrics={
                "load_time_ms": round(load_time, 2),
                "bundle_size_kb": round(random.uniform(200, 800), 2),
                "resources_loaded": random.randint(10, 50)
            }
        )
    
    def _create_infrastructure_event(self, anomalous: bool) -> LogEvent:
        """Create an infrastructure log event."""
        service_name = self._anomaly_service if self._anomaly_mode and anomalous else random.choice(self.SERVICES[EventType.infrastructure])
        
        if anomalous:
            cpu = random.uniform(90, 95)
            memory = random.uniform(95, 98)
            severity = "critical"
        else:
            cpu = random.uniform(20, 85)
            memory = random.uniform(40, 90)
            severity = "info"
        
        return LogEvent(
            event_id=str(uuid.uuid4()),
            timestamp=datetime.now(),
            event_type=EventType.infrastructure,
            service_name=service_name,
            region=random.choice(self.REGIONS),
            customer_id=None,
            severity=severity,
            message=f"Resource utilization report",
            metrics={
                "cpu_percent": round(cpu, 2),
                "memory_percent": round(memory, 2),
                "disk_io_mbps": round(random.uniform(10, 500), 2),
                "network_io_mbps": round(random.uniform(50, 1000), 2)
            }
        )
