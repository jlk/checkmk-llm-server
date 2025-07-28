"""Base service class with common patterns and error handling."""

import logging
from typing import TypeVar, Generic, Optional, List, Dict, Any, Callable, Awaitable
from pydantic import BaseModel, Field
from datetime import datetime
import asyncio
from functools import wraps

from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkAPIError
from ..config import AppConfig

T = TypeVar('T')


class ServiceResult(BaseModel, Generic[T]):
    """Standard service result wrapper for all operations."""
    model_config = {"arbitrary_types_allowed": True}
    
    success: bool = Field(description="Whether the operation was successful")
    data: Optional[T] = Field(None, description="Operation result data")
    error: Optional[str] = Field(None, description="Error message if operation failed")
    warnings: List[str] = Field(default_factory=list, description="Any warnings during operation")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    # Timing information
    execution_time_ms: Optional[float] = Field(None, description="Operation execution time in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.now, description="When operation was performed")
    
    @classmethod
    def success_result(cls, data: T, warnings: List[str] = None, metadata: Dict[str, Any] = None) -> 'ServiceResult[T]':
        """Create a successful result."""
        return cls(
            success=True,
            data=data,
            warnings=warnings or [],
            metadata=metadata or {}
        )
    
    @classmethod
    def error_result(cls, error: str, warnings: List[str] = None, metadata: Dict[str, Any] = None) -> 'ServiceResult[T]':
        """Create an error result."""
        return cls(
            success=False,
            error=error,
            warnings=warnings or [],
            metadata=metadata or {}
        )


class BaseService:
    """Base service class with common patterns and error handling."""
    
    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        self.checkmk = checkmk_client
        self.config = config
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def _execute_with_error_handling(
        self, 
        operation: Callable[[], Awaitable[T]], 
        operation_name: str = "operation"
    ) -> ServiceResult[T]:
        """
        Execute an operation with standardized error handling and timing.
        
        Args:
            operation: Async function to execute
            operation_name: Name of operation for logging
            
        Returns:
            ServiceResult with success/error information
        """
        start_time = datetime.now()
        
        try:
            self.logger.debug(f"Starting {operation_name}")
            result = await operation()
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            self.logger.debug(f"Completed {operation_name} in {execution_time:.2f}ms")
            
            return ServiceResult.success_result(
                data=result,
                metadata={"execution_time_ms": execution_time}
            )
            
        except CheckmkAPIError as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = f"Checkmk API error in {operation_name}: {e}"
            self.logger.error(error_msg)
            
            return ServiceResult.error_result(
                error=error_msg,
                metadata={
                    "execution_time_ms": execution_time,
                    "error_type": "checkmk_api_error",
                    "original_error": str(e)
                }
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            error_msg = f"Internal error in {operation_name}: {e}"
            self.logger.exception(error_msg)
            
            return ServiceResult.error_result(
                error=error_msg,
                metadata={
                    "execution_time_ms": execution_time,
                    "error_type": "internal_error",
                    "original_error": str(e)
                }
            )
    
    def _apply_text_filter(self, items: List[Any], text: str, fields: List[str]) -> List[Any]:
        """
        Apply text-based filtering to a list of items.
        
        Args:
            items: List of items to filter
            text: Text to search for
            fields: List of field names to search in
            
        Returns:
            Filtered list of items
        """
        if not text:
            return items
        
        text_lower = text.lower()
        filtered_items = []
        
        for item in items:
            for field in fields:
                if hasattr(item, field):
                    field_value = getattr(item, field)
                    if field_value and text_lower in str(field_value).lower():
                        filtered_items.append(item)
                        break
                elif isinstance(item, dict) and field in item:
                    field_value = item[field]
                    if field_value and text_lower in str(field_value).lower():
                        filtered_items.append(item)
                        break
        
        return filtered_items
    
    def _apply_pagination(self, items: List[T], offset: int = 0, limit: Optional[int] = None) -> List[T]:
        """
        Apply pagination to a list of items.
        
        Args:
            items: List of items to paginate
            offset: Starting index
            limit: Maximum number of items to return
            
        Returns:
            Paginated list of items
        """
        if offset < 0:
            offset = 0
        
        if limit is None:
            return items[offset:]
        
        if limit <= 0:
            return []
        
        return items[offset:offset + limit]
    
    def _calculate_health_percentage(self, ok_count: int, total_count: int) -> float:
        """Calculate health percentage."""
        if total_count == 0:
            return 100.0
        return round((ok_count / total_count) * 100, 1)
    
    def _get_health_grade(self, health_percentage: float) -> str:
        """Convert health percentage to letter grade."""
        if health_percentage >= 98:
            return "A+"
        elif health_percentage >= 95:
            return "A"
        elif health_percentage >= 90:
            return "A-"
        elif health_percentage >= 85:
            return "B+"
        elif health_percentage >= 80:
            return "B"
        elif health_percentage >= 75:
            return "B-"
        elif health_percentage >= 70:
            return "C+"
        elif health_percentage >= 65:
            return "C"
        elif health_percentage >= 60:
            return "C-"
        elif health_percentage >= 55:
            return "D+"
        elif health_percentage >= 50:
            return "D"
        elif health_percentage >= 45:
            return "D-"
        else:
            return "F"
    
    async def _execute_batch_operation(
        self,
        items: List[Any],
        operation: Callable[[Any], Awaitable[Any]],
        batch_size: int = 10,
        operation_name: str = "batch_operation"
    ) -> List[ServiceResult]:
        """
        Execute a batch operation with concurrency control.
        
        Args:
            items: List of items to process
            operation: Async function to apply to each item
            batch_size: Number of concurrent operations
            operation_name: Name for logging
            
        Returns:
            List of ServiceResult objects
        """
        results = []
        
        # Process items in batches to control concurrency
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            self.logger.debug(f"Processing batch {i//batch_size + 1} of {operation_name} ({len(batch)} items)")
            
            # Execute batch concurrently
            batch_tasks = [
                self._execute_with_error_handling(
                    lambda item=item: operation(item),
                    f"{operation_name}_item_{i + j}"
                )
                for j, item in enumerate(batch)
            ]
            
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Handle any exceptions that occurred
            for j, result in enumerate(batch_results):
                if isinstance(result, Exception):
                    error_result = ServiceResult.error_result(
                        error=f"Exception in {operation_name}: {result}"
                    )
                    results.append(error_result)
                else:
                    results.append(result)
        
        return results
    
    def _validate_required_params(self, params: Dict[str, Any], required: List[str]) -> List[str]:
        """
        Validate that required parameters are provided.
        
        Args:
            params: Parameter dictionary
            required: List of required parameter names
            
        Returns:
            List of validation error messages
        """
        errors = []
        for param in required:
            if param not in params or params[param] is None:
                errors.append(f"Missing required parameter: {param}")
            elif isinstance(params[param], str) and not params[param].strip():
                errors.append(f"Empty value for required parameter: {param}")
        
        return errors