"""Pydantic models for status monitoring and health dashboards."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
from .hosts import HostState
from .services import ServiceState


class ProblemSeverity(str, Enum):
    """Problem severity levels."""

    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"


class ProblemCategory(str, Enum):
    """Problem categorization."""

    PERFORMANCE = "performance"
    CONNECTIVITY = "connectivity"
    DISK = "disk"
    MEMORY = "memory"
    NETWORK = "network"
    MONITORING = "monitoring"
    OTHER = "other"


class ServiceProblem(BaseModel):
    """Information about a service problem."""

    host_name: str = Field(description="Host name")
    service_name: str = Field(description="Service name")
    state: ServiceState = Field(description="Current service state")
    severity: ProblemSeverity = Field(description="Problem severity")
    category: ProblemCategory = Field(description="Problem category")

    # Problem details
    plugin_output: str = Field(description="Service check output")
    duration: str = Field(description="How long service has been in this state")
    last_state_change: datetime = Field(description="When state changed")

    # Problem management
    acknowledged: bool = Field(False, description="Whether problem is acknowledged")
    in_downtime: bool = Field(False, description="Whether service is in downtime")

    # Urgency scoring
    urgency_score: int = Field(description="Urgency score (0-100)")
    business_impact: str = Field(description="Business impact assessment")

    class Config:
        use_enum_values = True


class HostStatus(BaseModel):
    """Host status summary."""

    name: str = Field(description="Host name")
    state: HostState = Field(description="Host state")
    total_services: int = Field(description="Total number of services")
    ok_services: int = Field(description="Number of OK services")
    warning_services: int = Field(description="Number of warning services")
    critical_services: int = Field(description="Number of critical services")
    unknown_services: int = Field(description="Number of unknown services")

    # Health metrics
    health_percentage: float = Field(description="Overall health percentage")
    health_grade: str = Field(description="Health grade (A+ to F)")

    # Problem summary
    urgent_problems: int = Field(description="Number of urgent problems")
    acknowledged_problems: int = Field(description="Number of acknowledged problems")

    class Config:
        use_enum_values = True


class ProblemSummary(BaseModel):
    """Summary of system problems."""

    total_problems: int = Field(description="Total number of problems")
    critical_problems: int = Field(description="Number of critical problems")
    warning_problems: int = Field(description="Number of warning problems")
    unknown_problems: int = Field(description="Number of unknown problems")

    # Problem breakdown
    unacknowledged_problems: int = Field(description="Unacknowledged problems")
    urgent_problems: int = Field(
        description="Urgent problems requiring immediate attention"
    )

    # Categorization
    problems_by_category: Dict[str, int] = Field(
        default_factory=dict, description="Problems by category"
    )
    problems_by_host: Dict[str, int] = Field(
        default_factory=dict, description="Problems by host"
    )

    # Recent trends
    new_problems_last_hour: int = Field(description="New problems in last hour")
    resolved_problems_last_hour: int = Field(
        description="Resolved problems in last hour"
    )


class HealthDashboard(BaseModel):
    """Comprehensive health dashboard."""

    # Overall metrics
    overall_health_percentage: float = Field(
        description="Overall system health percentage"
    )
    overall_health_grade: str = Field(description="Overall health grade (A+ to F)")
    total_hosts: int = Field(description="Total number of hosts")
    total_services: int = Field(description="Total number of services")

    # Service state distribution
    service_states: Dict[str, int] = Field(description="Service state counts")
    host_states: Dict[str, int] = Field(description="Host state counts")

    # Problem analysis
    problem_summary: ProblemSummary = Field(description="Problem summary")
    critical_problems: List[ServiceProblem] = Field(
        description="Critical service problems"
    )
    urgent_problems: List[ServiceProblem] = Field(
        description="Urgent problems needing attention"
    )

    # Host status
    host_statuses: List[HostStatus] = Field(description="Individual host statuses")
    worst_performing_hosts: List[HostStatus] = Field(
        description="Hosts with lowest health scores"
    )

    # Trends and insights
    health_trend: str = Field(description="Health trend (improving/stable/degrading)")
    recommendations: List[str] = Field(
        default_factory=list, description="Maintenance recommendations"
    )
    alerts: List[str] = Field(default_factory=list, description="Important alerts")

    # Metadata
    last_updated: datetime = Field(description="When dashboard was last updated")
    data_freshness: str = Field(description="How fresh the data is")


class StatusFilterOptions(BaseModel):
    """Options for filtering status queries."""

    host_filter: Optional[str] = Field(None, description="Host name pattern filter")
    service_filter: Optional[str] = Field(
        None, description="Service name pattern filter"
    )
    state_filter: Optional[List[ServiceState]] = Field(
        None, description="Service states to include"
    )
    severity_filter: Optional[List[ProblemSeverity]] = Field(
        None, description="Problem severities to include"
    )
    category_filter: Optional[List[ProblemCategory]] = Field(
        None, description="Problem categories to include"
    )

    # Time-based filters
    problems_since: Optional[datetime] = Field(
        None, description="Only show problems since this time"
    )
    acknowledged_filter: Optional[bool] = Field(
        None, description="Filter by acknowledgement status"
    )
    downtime_filter: Optional[bool] = Field(
        None, description="Filter by downtime status"
    )

    # Sorting and limiting
    sort_by: str = Field(default="urgency", description="Sort criteria")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")
    limit: Optional[int] = Field(None, description="Maximum number of results")


class StatusQueryResult(BaseModel):
    """Result of a status query."""

    success: bool = Field(description="Whether query was successful")
    message: str = Field(description="Success or error message")

    # Results
    problems: List[ServiceProblem] = Field(description="Matching service problems")
    host_statuses: List[HostStatus] = Field(description="Matching host statuses")

    # Query metadata
    filter_applied: StatusFilterOptions = Field(description="Filters that were applied")
    total_matches: int = Field(description="Total number of matches before limiting")
    query_time: datetime = Field(description="When query was executed")
    execution_time_ms: float = Field(description="Query execution time in milliseconds")
