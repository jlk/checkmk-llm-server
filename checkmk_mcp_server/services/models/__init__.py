"""Pydantic models for service layer responses."""

from .hosts import (
    HostInfo,
    HostListResult,
    HostCreateResult,
    HostUpdateResult,
    HostDeleteResult,
)
from .services import (
    ServiceInfo,
    ServiceListResult,
    ServiceStatusResult,
    ServiceAcknowledgeResult,
    ServiceDowntimeResult,
)
from .status import HealthDashboard, ProblemSummary, ServiceState, HostStatus
from .historical import (
    HistoricalDataPoint,
    HistoricalDataResult,
    HistoricalDataRequest,
    HistoricalDataServiceResult,
)

__all__ = [
    # Host models
    "HostInfo",
    "HostListResult",
    "HostCreateResult",
    "HostUpdateResult",
    "HostDeleteResult",
    # Service models
    "ServiceInfo",
    "ServiceListResult",
    "ServiceStatusResult",
    "ServiceAcknowledgeResult",
    "ServiceDowntimeResult",
    # Status models
    "HealthDashboard",
    "ProblemSummary",
    "ServiceState",
    "HostStatus",
    # Historical data models
    "HistoricalDataPoint",
    "HistoricalDataResult",
    "HistoricalDataRequest",
    "HistoricalDataServiceResult",
]
