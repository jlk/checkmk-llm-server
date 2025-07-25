"""Base formatter class for data presentation."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List
from datetime import datetime


class BaseFormatter(ABC):
    """Base class for all data formatters."""
    
    def __init__(self):
        self.timestamp_format = "%Y-%m-%d %H:%M:%S"
    
    @abstractmethod
    def format_host_list(self, data: Dict[str, Any]) -> str:
        """Format host list data."""
        pass
    
    @abstractmethod
    def format_service_list(self, data: Dict[str, Any]) -> str:
        """Format service list data."""
        pass
    
    @abstractmethod
    def format_health_dashboard(self, data: Dict[str, Any]) -> str:
        """Format health dashboard data."""
        pass
    
    @abstractmethod
    def format_service_status(self, data: Dict[str, Any]) -> str:
        """Format detailed service status."""
        pass
    
    @abstractmethod
    def format_error(self, error: str, context: str = "") -> str:
        """Format error message."""
        pass
    
    def format_timestamp(self, timestamp: datetime) -> str:
        """Format timestamp consistently."""
        if isinstance(timestamp, datetime):
            return timestamp.strftime(self.timestamp_format)
        return str(timestamp)
    
    def format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        elif seconds < 86400:
            hours = seconds / 3600
            return f"{hours:.1f}h"
        else:
            days = seconds / 86400
            return f"{days:.1f}d"
    
    def format_percentage(self, value: float, decimals: int = 1) -> str:
        """Format percentage value."""
        return f"{value:.{decimals}f}%"
    
    def format_file_size(self, bytes_value: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes_value < 1024.0:
                return f"{bytes_value:.1f} {unit}"
            bytes_value /= 1024.0
        return f"{bytes_value:.1f} PB"
    
    def truncate_text(self, text: str, max_length: int, suffix: str = "...") -> str:
        """Truncate text to maximum length."""
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    
    def format_list_summary(self, items: List[Any], item_name: str = "item") -> str:
        """Format a summary of list items."""
        count = len(items)
        if count == 0:
            return f"No {item_name}s found"
        elif count == 1:
            return f"Found 1 {item_name}"
        else:
            return f"Found {count} {item_name}s"