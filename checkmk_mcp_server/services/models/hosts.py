"""Pydantic models for host operations."""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class HostState(str, Enum):
    """Host state enumeration."""

    UP = "UP"
    DOWN = "DOWN"
    UNREACHABLE = "UNREACHABLE"
    PENDING = "PENDING"


class HostInfo(BaseModel):
    """Information about a single host."""

    name: str = Field(description="Host name")
    folder: str = Field(description="Checkmk folder path")
    ip_address: Optional[str] = Field(None, description="IP address")
    attributes: Dict[str, Any] = Field(
        default_factory=dict, description="Host attributes"
    )
    labels: Dict[str, str] = Field(default_factory=dict, description="Host labels")

    # Status information (when available)
    state: Optional[HostState] = Field(None, description="Current host state")
    state_type: Optional[str] = Field(None, description="State type (hard/soft)")
    last_check: Optional[datetime] = Field(None, description="Last check time")
    last_state_change: Optional[datetime] = Field(None, description="Last state change")
    plugin_output: Optional[str] = Field(None, description="Plugin output")
    performance_data: Optional[str] = Field(None, description="Performance data")
    acknowledged: bool = Field(False, description="Whether host is acknowledged")
    in_downtime: bool = Field(False, description="Whether host is in downtime")

    class Config:
        use_enum_values = True


class HostListResult(BaseModel):
    """Result of listing hosts."""

    hosts: List[HostInfo] = Field(description="List of hosts")
    total_count: int = Field(description="Total number of hosts found")
    search_applied: Optional[str] = Field(None, description="Search pattern applied")
    folder_filter: Optional[str] = Field(None, description="Folder filter applied")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )

    # Summary statistics
    stats: Dict[str, int] = Field(
        default_factory=dict, description="Host state statistics"
    )


class HostCreateResult(BaseModel):
    """Result of creating a host."""

    host: HostInfo = Field(description="Created host information")
    success: bool = Field(description="Whether creation was successful")
    message: str = Field(description="Success or error message")
    warnings: List[str] = Field(
        default_factory=list, description="Any warnings during creation"
    )
    etag: Optional[str] = Field(None, description="ETag for the created host")


class HostUpdateResult(BaseModel):
    """Result of updating a host."""

    host: HostInfo = Field(description="Updated host information")
    success: bool = Field(description="Whether update was successful")
    message: str = Field(description="Success or error message")
    warnings: List[str] = Field(
        default_factory=list, description="Any warnings during update"
    )
    changes_made: List[str] = Field(
        default_factory=list, description="List of changes made"
    )
    etag: Optional[str] = Field(None, description="New ETag for the host")


class HostDeleteResult(BaseModel):
    """Result of deleting a host."""

    host_name: str = Field(description="Name of deleted host")
    success: bool = Field(description="Whether deletion was successful")
    message: str = Field(description="Success or error message")
    warnings: List[str] = Field(
        default_factory=list, description="Any warnings during deletion"
    )


class HostBulkCreateResult(BaseModel):
    """Result of bulk creating hosts."""

    created_hosts: List[HostInfo] = Field(description="Successfully created hosts")
    failed_hosts: List[Dict[str, str]] = Field(
        default_factory=list, description="Failed host creations with errors"
    )
    success_count: int = Field(description="Number of successfully created hosts")
    failure_count: int = Field(description="Number of failed host creations")
    total_requested: int = Field(
        description="Total number of hosts requested to create"
    )
    warnings: List[str] = Field(default_factory=list, description="General warnings")


class HostBulkDeleteResult(BaseModel):
    """Result of bulk deleting hosts."""

    deleted_hosts: List[str] = Field(description="Names of successfully deleted hosts")
    failed_hosts: List[Dict[str, str]] = Field(
        default_factory=list, description="Failed host deletions with errors"
    )
    success_count: int = Field(description="Number of successfully deleted hosts")
    failure_count: int = Field(description="Number of failed host deletions")
    total_requested: int = Field(
        description="Total number of hosts requested to delete"
    )
    warnings: List[str] = Field(default_factory=list, description="General warnings")
