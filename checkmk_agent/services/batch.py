"""Batch operations support for efficient bulk processing."""

import asyncio
import logging
from typing import List, Dict, Any, TypeVar, Generic, Callable, Optional, Union, Tuple
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from .base import ServiceResult


T = TypeVar('T')
R = TypeVar('R')


class BatchItemStatus(str, Enum):
    """Status of a batch item."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class BatchItem(BaseModel, Generic[T, R]):
    """A single item in a batch operation."""
    id: str
    data: T
    status: BatchItemStatus = BatchItemStatus.PENDING
    result: Optional[R] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def mark_processing(self):
        """Mark item as being processed."""
        self.status = BatchItemStatus.PROCESSING
        self.started_at = datetime.now()
    
    def mark_success(self, result: R):
        """Mark item as successfully processed."""
        self.status = BatchItemStatus.SUCCESS
        self.result = result
        self.completed_at = datetime.now()
    
    def mark_failed(self, error: str):
        """Mark item as failed."""
        self.status = BatchItemStatus.FAILED
        self.error = error
        self.completed_at = datetime.now()
    
    def mark_skipped(self, reason: str):
        """Mark item as skipped."""
        self.status = BatchItemStatus.SKIPPED
        self.error = reason
        self.completed_at = datetime.now()
    
    @property
    def processing_time(self) -> Optional[float]:
        """Get processing time in seconds."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class BatchProgress(BaseModel):
    """Progress tracking for batch operations."""
    total_items: int
    pending: int = 0
    processing: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: datetime = Field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    
    @property
    def completed(self) -> int:
        """Get total completed items."""
        return self.success + self.failed + self.skipped
    
    @property
    def progress_percent(self) -> float:
        """Get progress percentage."""
        return (self.completed / self.total_items * 100) if self.total_items > 0 else 0
    
    @property
    def duration(self) -> Optional[float]:
        """Get duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()
    
    @property
    def items_per_second(self) -> float:
        """Calculate processing rate."""
        duration = self.duration
        return self.completed / duration if duration and duration > 0 else 0
    
    @property
    def estimated_remaining(self) -> Optional[float]:
        """Estimate remaining time in seconds."""
        rate = self.items_per_second
        if rate > 0:
            remaining_items = self.total_items - self.completed
            return remaining_items / rate
        return None


class BatchResult(BaseModel, Generic[T, R]):
    """Result of a batch operation."""
    batch_id: str
    items: List[BatchItem[T, R]]
    progress: BatchProgress
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def get_successful_items(self) -> List[BatchItem[T, R]]:
        """Get all successful items."""
        return [item for item in self.items if item.status == BatchItemStatus.SUCCESS]
    
    def get_failed_items(self) -> List[BatchItem[T, R]]:
        """Get all failed items."""
        return [item for item in self.items if item.status == BatchItemStatus.FAILED]
    
    def get_results(self) -> List[R]:
        """Get all successful results."""
        return [item.result for item in self.items 
                if item.status == BatchItemStatus.SUCCESS and item.result is not None]


class BatchProcessor:
    """Generic batch processor with rate limiting and error handling."""
    
    def __init__(
        self,
        max_concurrent: int = 10,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        rate_limit: Optional[int] = None
    ):
        """
        Initialize batch processor.
        
        Args:
            max_concurrent: Maximum concurrent operations
            max_retries: Maximum retry attempts per item
            retry_delay: Delay between retries (seconds)
            rate_limit: Maximum operations per second (None for unlimited)
        """
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.rate_limit = rate_limit
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._rate_limiter = asyncio.Semaphore(rate_limit) if rate_limit else None
        self._last_operation_time = 0
        self.logger = logging.getLogger(__name__)
    
    async def _rate_limit(self):
        """Apply rate limiting if configured."""
        if self.rate_limit:
            # Calculate minimum time between operations
            min_interval = 1.0 / self.rate_limit
            
            # Wait if necessary
            current_time = asyncio.get_event_loop().time()
            time_since_last = current_time - self._last_operation_time
            if time_since_last < min_interval:
                await asyncio.sleep(min_interval - time_since_last)
            
            self._last_operation_time = asyncio.get_event_loop().time()
    
    async def process_batch(
        self,
        items: List[T],
        operation: Callable[[T], R],
        batch_id: Optional[str] = None,
        progress_callback: Optional[Callable[[BatchProgress], None]] = None,
        validate_item: Optional[Callable[[T], Tuple[bool, Optional[str]]]] = None
    ) -> BatchResult[T, R]:
        """
        Process a batch of items.
        
        Args:
            items: List of items to process
            operation: Async function to process each item
            batch_id: Optional batch identifier
            progress_callback: Optional callback for progress updates
            validate_item: Optional validation function (returns valid, error_msg)
            
        Returns:
            BatchResult with all items and their results
        """
        batch_id = batch_id or f"batch_{datetime.now().timestamp()}"
        
        # Create batch items
        batch_items = [
            BatchItem(
                id=f"{batch_id}_{i}",
                data=item
            )
            for i, item in enumerate(items)
        ]
        
        # Initialize progress
        progress = BatchProgress(total_items=len(items), pending=len(items))
        
        # Process items
        async def process_item(batch_item: BatchItem[T, R]):
            async with self._semaphore:
                try:
                    # Update progress
                    progress.pending -= 1
                    progress.processing += 1
                    if progress_callback:
                        await progress_callback(progress)
                    
                    # Validate item if validator provided
                    if validate_item:
                        valid, error_msg = await validate_item(batch_item.data)
                        if not valid:
                            batch_item.mark_skipped(error_msg or "Validation failed")
                            progress.processing -= 1
                            progress.skipped += 1
                            return
                    
                    # Apply rate limiting
                    await self._rate_limit()
                    
                    # Process with retries
                    batch_item.mark_processing()
                    
                    for attempt in range(self.max_retries):
                        try:
                            result = await operation(batch_item.data)
                            batch_item.mark_success(result)
                            progress.processing -= 1
                            progress.success += 1
                            return
                            
                        except Exception as e:
                            batch_item.retry_count = attempt + 1
                            if attempt < self.max_retries - 1:
                                self.logger.warning(
                                    f"Retry {attempt + 1}/{self.max_retries} for item {batch_item.id}: {e}"
                                )
                                await asyncio.sleep(self.retry_delay * (attempt + 1))
                            else:
                                batch_item.mark_failed(str(e))
                                progress.processing -= 1
                                progress.failed += 1
                                self.logger.error(f"Failed item {batch_item.id} after {self.max_retries} attempts: {e}")
                                
                except Exception as e:
                    # Unexpected error in processing logic
                    batch_item.mark_failed(f"Processing error: {str(e)}")
                    progress.processing -= 1
                    progress.failed += 1
                    self.logger.exception(f"Unexpected error processing item {batch_item.id}")
                
                finally:
                    if progress_callback:
                        await progress_callback(progress)
        
        # Process all items concurrently
        start_time = datetime.now()
        await asyncio.gather(*[process_item(item) for item in batch_items], return_exceptions=True)
        
        # Finalize progress
        progress.end_time = datetime.now()
        
        # Create result
        result = BatchResult(
            batch_id=batch_id,
            items=batch_items,
            progress=progress,
            metadata={
                'start_time': start_time.isoformat(),
                'end_time': progress.end_time.isoformat(),
                'duration_seconds': progress.duration,
                'items_per_second': progress.items_per_second
            }
        )
        
        self.logger.info(
            f"Batch {batch_id} completed: "
            f"{progress.success} success, {progress.failed} failed, "
            f"{progress.skipped} skipped in {progress.duration:.2f}s"
        )
        
        return result


class BatchOperationsMixin:
    """Mixin to add batch operation capabilities to services."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.batch_processor = BatchProcessor()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    async def batch_create(
        self,
        items: List[Dict[str, Any]],
        resource_type: str,
        create_function: Callable,
        validate_function: Optional[Callable] = None,
        progress_callback: Optional[Callable] = None
    ) -> ServiceResult[BatchResult]:
        """
        Generic batch create operation.
        
        Args:
            items: List of items to create
            resource_type: Type of resource (for logging)
            create_function: Function to create single item
            validate_function: Optional validation function
            progress_callback: Optional progress callback
            
        Returns:
            ServiceResult containing BatchResult
        """
        try:
            self.logger.info(f"Starting batch create for {len(items)} {resource_type}s")
            
            result = await self.batch_processor.process_batch(
                items=items,
                operation=create_function,
                batch_id=f"create_{resource_type}_{datetime.now().timestamp()}",
                progress_callback=progress_callback,
                validate_item=validate_function
            )
            
            return ServiceResult(
                success=True,
                data=result,
                warnings=[item.error for item in result.get_failed_items()]
            )
            
        except Exception as e:
            self.logger.exception(f"Batch create failed for {resource_type}")
            return ServiceResult(
                success=False,
                error=f"Batch operation failed: {str(e)}"
            )
    
    async def batch_update(
        self,
        updates: List[Tuple[str, Dict[str, Any]]],  # (id, update_data)
        resource_type: str,
        update_function: Callable,
        progress_callback: Optional[Callable] = None
    ) -> ServiceResult[BatchResult]:
        """
        Generic batch update operation.
        
        Args:
            updates: List of (id, update_data) tuples
            resource_type: Type of resource
            update_function: Function to update single item
            progress_callback: Optional progress callback
            
        Returns:
            ServiceResult containing BatchResult
        """
        try:
            self.logger.info(f"Starting batch update for {len(updates)} {resource_type}s")
            
            # Create wrapper to unpack tuple
            async def update_wrapper(item: Tuple[str, Dict[str, Any]]):
                resource_id, update_data = item
                return await update_function(resource_id, **update_data)
            
            result = await self.batch_processor.process_batch(
                items=updates,
                operation=update_wrapper,
                batch_id=f"update_{resource_type}_{datetime.now().timestamp()}",
                progress_callback=progress_callback
            )
            
            return ServiceResult(
                success=True,
                data=result,
                warnings=[item.error for item in result.get_failed_items()]
            )
            
        except Exception as e:
            self.logger.exception(f"Batch update failed for {resource_type}")
            return ServiceResult(
                success=False,
                error=f"Batch operation failed: {str(e)}"
            )