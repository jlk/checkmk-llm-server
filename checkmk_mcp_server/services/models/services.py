"""Pydantic models for service operations."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class ServiceState(str, Enum):
    """Service state enumeration."""

    OK = "OK"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    UNKNOWN = "UNKNOWN"


class ServiceInfo(BaseModel):
    """Information about a single service."""

    host_name: str = Field(description="Host name this service belongs to")
    service_name: str = Field(description="Service display name")
    state: ServiceState = Field(description="Current service state")
    state_type: str = Field(description="State type (hard/soft)")

    # Status details
    plugin_output: str = Field(description="Service check output")
    long_plugin_output: Optional[str] = Field(
        None, description="Extended service output"
    )
    performance_data: Optional[str] = Field(None, description="Performance metrics")

    # Timing information
    last_check: datetime = Field(description="Last check time")
    last_state_change: datetime = Field(description="Last state change")
    last_ok: Optional[datetime] = Field(None, description="Last time service was OK")
    next_check: Optional[datetime] = Field(None, description="Next scheduled check")

    # Problem management
    acknowledged: bool = Field(
        False, description="Whether service problem is acknowledged"
    )
    acknowledgement_author: Optional[str] = Field(
        None, description="Who acknowledged the problem"
    )
    acknowledgement_comment: Optional[str] = Field(
        None, description="Acknowledgement comment"
    )
    acknowledgement_time: Optional[datetime] = Field(
        None, description="When problem was acknowledged"
    )

    # Downtime information
    in_downtime: bool = Field(
        False, description="Whether service is in scheduled downtime"
    )
    downtime_start: Optional[datetime] = Field(None, description="Downtime start time")
    downtime_end: Optional[datetime] = Field(None, description="Downtime end time")
    downtime_comment: Optional[str] = Field(None, description="Downtime comment")

    # Check configuration
    check_command: Optional[str] = Field(None, description="Check command used")
    check_interval: Optional[int] = Field(None, description="Check interval in seconds")
    retry_interval: Optional[int] = Field(None, description="Retry interval in seconds")
    max_check_attempts: Optional[int] = Field(
        None, description="Maximum check attempts"
    )
    current_attempt: Optional[int] = Field(None, description="Current check attempt")

    # Service configuration
    notifications_enabled: bool = Field(
        True, description="Whether notifications are enabled"
    )
    active_checks_enabled: bool = Field(
        True, description="Whether active checks are enabled"
    )
    passive_checks_enabled: bool = Field(
        True, description="Whether passive checks are enabled"
    )

    class Config:
        use_enum_values = True


class ServiceListResult(BaseModel):
    """Result of listing services."""

    services: List[ServiceInfo] = Field(description="List of services")
    total_count: int = Field(description="Total number of services found")
    host_filter: Optional[str] = Field(None, description="Host filter applied")
    state_filter: Optional[ServiceState] = Field(
        None, description="State filter applied"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    # Summary statistics
    stats: Dict[str, int] = Field(
        default_factory=dict, description="Service state statistics"
    )


class ServiceStatusResult(BaseModel):
    """Result of getting detailed service status."""

    service: ServiceInfo = Field(description="Detailed service information")
    success: bool = Field(description="Whether status retrieval was successful")
    message: str = Field(description="Success or error message")

    # Additional context
    related_services: List[ServiceInfo] = Field(
        default_factory=list, description="Related services on same host"
    )
    host_status: Optional[str] = Field(None, description="Host status summary")


class ServiceAcknowledgeResult(BaseModel):
    """Result of acknowledging a service problem."""

    host_name: str = Field(description="Host name")
    service_name: str = Field(description="Service name")
    success: bool = Field(description="Whether acknowledgement was successful")
    message: str = Field(description="Success or error message")
    comment: str = Field(description="Acknowledgement comment")
    author: str = Field(description="Who made the acknowledgement")
    sticky: bool = Field(description="Whether acknowledgement is sticky")
    notify: bool = Field(description="Whether notification was sent")
    persistent: bool = Field(
        description="Whether acknowledgement persists across restarts"
    )
    acknowledgement_time: datetime = Field(description="When acknowledgement was made")


class ServiceDowntimeResult(BaseModel):
    """Result of creating service downtime."""

    host_name: str = Field(description="Host name")
    service_name: str = Field(description="Service name")
    success: bool = Field(description="Whether downtime creation was successful")
    message: str = Field(description="Success or error message")
    downtime_id: Optional[str] = Field(None, description="Downtime ID if successful")

    # Downtime details
    start_time: datetime = Field(description="Downtime start time")
    end_time: datetime = Field(description="Downtime end time")
    duration_hours: float = Field(description="Downtime duration in hours")
    comment: str = Field(description="Downtime comment")
    author: str = Field(description="Who created the downtime")
    fixed: bool = Field(description="Whether downtime has fixed duration")


class ServiceDiscoveryResult(BaseModel):
    """Result of service discovery operation."""

    host_name: str = Field(description="Host name where discovery was performed")
    success: bool = Field(description="Whether discovery was successful")
    message: str = Field(description="Success or error message")

    # Discovery results
    new_services: List[str] = Field(
        default_factory=list, description="Newly discovered services"
    )
    removed_services: List[str] = Field(
        default_factory=list, description="Services that vanished"
    )
    changed_services: List[str] = Field(
        default_factory=list, description="Services with changed parameters"
    )
    unchanged_services: List[str] = Field(
        default_factory=list, description="Unchanged services"
    )

    # Summary counts
    new_count: int = Field(description="Number of new services")
    removed_count: int = Field(description="Number of removed services")
    changed_count: int = Field(description="Number of changed services")
    unchanged_count: int = Field(description="Number of unchanged services")

    # Discovery metadata
    discovery_mode: str = Field(description="Discovery mode used")
    discovery_time: datetime = Field(description="When discovery was performed")


class ServiceParameterResult(BaseModel):
    """Result of service parameter operations."""

    host_name: str = Field(description="Host name")
    service_name: str = Field(description="Service name")
    success: bool = Field(description="Whether operation was successful")
    message: str = Field(description="Success or error message")

    # Parameter details
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Service parameters"
    )
    rule_id: Optional[str] = Field(
        None, description="Rule ID if parameter rule was created or updated"
    )
    ruleset: Optional[str] = Field(None, description="Ruleset name")
    effective_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Effective parameters after change"
    )

    # Operation details
    was_updated: bool = Field(
        default=False,
        description="Whether an existing rule was updated (True) or new rule created (False)",
    )

    # Change tracking
    changes_made: List[str] = Field(
        default_factory=list, description="List of parameter changes"
    )
    warnings: List[str] = Field(default_factory=list, description="Any warnings")
