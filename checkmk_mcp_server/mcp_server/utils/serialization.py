"""
JSON Serialization Utilities

This module provides utilities for safely serializing objects to JSON,
with special handling for datetime objects, Decimal values, Enums,
and Pydantic models.

Extracted from the monolithic server.py during Phase 1 refactoring.
"""

import json
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Any


class MCPJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime, Decimal, and Enum objects."""

    def default(self, obj: Any) -> Any:
        """
        Convert non-serializable objects to JSON-serializable format.
        
        Args:
            obj: Object to serialize
            
        Returns:
            JSON-serializable representation of the object
            
        Raises:
            TypeError: If object cannot be serialized
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, date):
            return obj.isoformat()
        elif isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, "model_dump"):
            return obj.model_dump()
        elif hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


def safe_json_dumps(obj: Any) -> str:
    """
    Safely serialize object to JSON, handling datetime and other non-serializable types.
    
    This function provides a fallback mechanism for serialization failures,
    ensuring that some representation is always returned even if the primary
    serialization attempt fails.
    
    Args:
        obj: Object to serialize to JSON
        
    Returns:
        JSON string representation of the object
        
    Example:
        >>> safe_json_dumps({"timestamp": datetime.now(), "value": 42})
        '{"timestamp": "2025-08-19T10:30:00.123456", "value": 42}'
    """
    try:
        return json.dumps(obj, cls=MCPJSONEncoder, ensure_ascii=False)
    except Exception as e:
        # Fallback: convert to string representation
        return json.dumps(
            {"error": f"Serialization failed: {str(e)}", "data": str(obj)}
        )