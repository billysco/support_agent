"""
Threshold monitoring and anomaly detection for log events.
"""

from collections import deque
from typing import Optional
from pydantic import BaseModel
from .schemas import LogEvent, EventType


class ThresholdResult(BaseModel):
    """Result of threshold checking for a log event."""
    flagged: bool
    critical: bool
    threshold_exceeded: Optional[str] = None
    actual_value: Optional[float] = None
    threshold_value: Optional[float] = None
    baseline_value: Optional[float] = None


class RollingBaseline:
    """Tracks rolling baseline for a service metric."""
    
    def __init__(self, max_size: int = 100):
        self.values = deque(maxlen=max_size)
        self.consecutive_violations = 0
    
    def add_value(self, value: float):
        """Add a value to the baseline."""
        self.values.append(value)
    
    def get_average(self) -> Optional[float]:
        """Calculate average of baseline values."""
        if not self.values:
            return None
        return sum(self.values) / len(self.values)


class ThresholdChecker:
    """Monitors events against thresholds and flags anomalies."""
    
    THRESHOLDS = {
        EventType.api: {
            "latency_ms": 500.0,
            "error_rate": 5.0
        },
        EventType.database: {
            "query_time_ms": 300.0
        },
        EventType.frontend: {
            "load_time_ms": 5000.0
        },
        EventType.infrastructure: {
            "cpu_percent": 90.0,
            "memory_percent": 95.0
        }
    }
    
    def __init__(self):
        self._baselines: dict[str, dict[str, RollingBaseline]] = {}
    
    def check_event(self, event: LogEvent) -> ThresholdResult:
        """
        Check if event exceeds thresholds and flag accordingly.
        
        Args:
            event: The log event to check
            
        Returns:
            ThresholdResult with flagging decision and details
        """
        service_key = f"{event.service_name}:{event.event_type.value}"
        
        if service_key not in self._baselines:
            self._baselines[service_key] = {}
        
        thresholds = self.THRESHOLDS.get(event.event_type, {})
        result = ThresholdResult(flagged=False, critical=False)
        
        for metric_name, threshold_value in thresholds.items():
            if metric_name not in event.metrics:
                continue
            
            actual_value = event.metrics[metric_name]
            
            if metric_name not in self._baselines[service_key]:
                self._baselines[service_key][metric_name] = RollingBaseline()
            
            baseline = self._baselines[service_key][metric_name]
            baseline_avg = baseline.get_average()
            
            if actual_value > threshold_value:
                result.flagged = True
                result.threshold_exceeded = metric_name
                result.actual_value = actual_value
                result.threshold_value = threshold_value
                result.baseline_value = baseline_avg
                
                baseline.consecutive_violations += 1
                
                if baseline.consecutive_violations >= 3:
                    result.critical = True
                
                break
            else:
                baseline.consecutive_violations = 0
            
            baseline.add_value(actual_value)
        
        return result
