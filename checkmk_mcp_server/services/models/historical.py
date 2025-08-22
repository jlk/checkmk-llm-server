"""Pydantic models for historical data operations."""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
from dataclasses import dataclass


@dataclass
class HistoricalDataPoint:
    """Represents a single historical data point with timestamp and value.
    
    This class represents a single point in a time series, containing both
    the timestamp when the measurement was taken and the value that was measured.
    The metric_name and unit fields provide context for the LLM to understand
    what the data represents.
    """
    
    timestamp: datetime
    value: Union[float, str]
    metric_name: str  # LLM can infer from context
    unit: Optional[str] = None  # LLM can infer from context

    def __post_init__(self):
        """Validate data point after initialization."""
        if not isinstance(self.timestamp, datetime):
            raise ValueError(f"timestamp must be datetime, got {type(self.timestamp)}")
        
        if not isinstance(self.value, (int, float, str)):
            raise ValueError(f"value must be numeric or string, got {type(self.value)}")
        
        if not self.metric_name or not isinstance(self.metric_name, str):
            raise ValueError("metric_name must be a non-empty string")


@dataclass
class HistoricalDataResult:
    """Complete result of historical data retrieval operation.
    
    This class contains all the data extracted from a historical data source,
    including individual time-series points, summary statistics, and metadata
    about the data source and retrieval operation.
    """
    
    data_points: List[HistoricalDataPoint]
    summary_stats: Dict[str, float]  # Preserve original names (min/avg/std/etc.)
    metadata: Dict[str, Any]  # source, time_range, etc.
    source: str  # "rest_api", "scraper", "event_console"

    def __post_init__(self):
        """Validate historical data result after initialization."""
        if not isinstance(self.data_points, list):
            raise ValueError("data_points must be a list")
        
        for point in self.data_points:
            if not isinstance(point, HistoricalDataPoint):
                raise ValueError("All data_points must be HistoricalDataPoint instances")
        
        if not isinstance(self.summary_stats, dict):
            raise ValueError("summary_stats must be a dictionary")
        
        if not isinstance(self.metadata, dict):
            raise ValueError("metadata must be a dictionary")
        
        if not self.source or not isinstance(self.source, str):
            raise ValueError("source must be a non-empty string")
        
        # Validate that source is from known sources
        valid_sources = ["rest_api", "scraper", "event_console"]
        if self.source not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}, got '{self.source}'")


class HistoricalDataRequest(BaseModel):
    """Request model for historical data retrieval."""
    
    host_name: str = Field(description="Host name to retrieve data for")
    service_name: str = Field(description="Service name to retrieve data for") 
    period: str = Field(
        default="4h", 
        description="Time period (4h, 25h, 8d, etc.)"
    )
    metric_name: Optional[str] = Field(
        None, 
        description="Specific metric name to retrieve"
    )
    source: Optional[str] = Field(
        None,
        description="Data source preference (rest_api, scraper, event_console)"
    )
    
    model_config = {"str_strip_whitespace": True}

    @field_validator("host_name", "service_name")
    @classmethod
    def validate_required_strings(cls, v: str) -> str:
        """Validate required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()

    @field_validator("period")
    @classmethod
    def validate_period(cls, v: str) -> str:
        """Validate time period format."""
        if not v:
            raise ValueError("period cannot be empty")
        
        # Basic validation - should end with h, d, w, m, or y
        valid_suffixes = ['h', 'd', 'w', 'm', 'y']
        if not any(v.lower().endswith(suffix) for suffix in valid_suffixes):
            raise ValueError(f"period must end with one of {valid_suffixes}")
        
        return v

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: Optional[str]) -> Optional[str]:
        """Validate data source if provided."""
        if v is None:
            return v
        
        valid_sources = ["rest_api", "scraper", "event_console"]
        if v not in valid_sources:
            raise ValueError(f"source must be one of {valid_sources}")
        
        return v


class HistoricalDataServiceResult(BaseModel):
    """Service layer result wrapper for historical data operations."""
    
    success: bool = Field(description="Whether the operation was successful")
    data: Optional[HistoricalDataResult] = Field(
        None, 
        description="Historical data result if successful"
    )
    error: Optional[str] = Field(
        None, 
        description="Error message if operation failed"
    )
    warnings: List[str] = Field(
        default_factory=list, 
        description="Any warnings during operation"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, 
        description="Additional metadata about the operation"
    )
    
    # Timing information
    execution_time_ms: Optional[float] = Field(
        None, 
        description="Operation execution time in milliseconds"
    )
    timestamp: datetime = Field(
        default_factory=datetime.now, 
        description="When operation was performed"
    )
    
    # Request tracking information
    request_id: Optional[str] = Field(
        None, 
        description="Request ID for tracing this operation"
    )
    
    @classmethod
    def success_result(
        cls,
        data: HistoricalDataResult,
        warnings: List[str] = None,
        metadata: Dict[str, Any] = None,
        request_id: Optional[str] = None,
    ) -> "HistoricalDataServiceResult":
        """Create a successful result."""
        return cls(
            success=True,
            data=data,
            warnings=warnings or [],
            metadata=metadata or {},
            request_id=request_id,
        )

    @classmethod
    def error_result(
        cls,
        error: str,
        warnings: List[str] = None,
        metadata: Dict[str, Any] = None,
        request_id: Optional[str] = None,
    ) -> "HistoricalDataServiceResult":
        """Create an error result."""
        return cls(
            success=False,
            error=error,
            warnings=warnings or [],
            metadata=metadata or {},
            request_id=request_id,
        )