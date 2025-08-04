"""Streaming support for large dataset operations."""

import asyncio
import logging
from typing import AsyncIterator, Dict, Any, List, Optional, TypeVar, Generic
from datetime import datetime

from pydantic import BaseModel, Field

from .base import BaseService, ServiceResult
from .models.hosts import HostInfo
from .models.services import ServiceInfo, ServiceState


T = TypeVar("T")


class StreamBatch(BaseModel, Generic[T]):
    """A batch of items in a stream."""

    items: List[T]
    batch_number: int
    total_batches: Optional[int] = None
    timestamp: datetime = Field(default_factory=datetime.now)
    has_more: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class StreamingMixin:
    """Mixin to add streaming capabilities to services."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.default_batch_size = 100
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def _stream_paginated_data(
        self, fetch_function, batch_size: Optional[int] = None, **fetch_kwargs
    ) -> AsyncIterator[StreamBatch]:
        """
        Generic streaming implementation for paginated data.

        Args:
            fetch_function: Async function to fetch data (must support limit/offset)
            batch_size: Number of items per batch
            **fetch_kwargs: Additional arguments for fetch function

        Yields:
            StreamBatch objects containing data
        """
        batch_size = batch_size or self.default_batch_size
        offset = 0
        batch_number = 0
        total_count = None

        while True:
            try:
                # Fetch batch
                result = await fetch_function(
                    limit=batch_size, offset=offset, **fetch_kwargs
                )

                # Extract items based on result type
                if hasattr(result, "items"):
                    items = result.items
                elif hasattr(result, "data") and isinstance(result.data, list):
                    items = result.data
                elif isinstance(result, list):
                    items = result
                else:
                    self.logger.warning(f"Unexpected result type: {type(result)}")
                    break

                # Get total count if available
                if hasattr(result, "total_count") and total_count is None:
                    total_count = result.total_count
                    total_batches = (total_count + batch_size - 1) // batch_size
                else:
                    total_batches = None

                # Check if we have items
                if not items:
                    break

                # Yield batch
                has_more = len(items) == batch_size
                yield StreamBatch(
                    items=items,
                    batch_number=batch_number,
                    total_batches=total_batches,
                    has_more=has_more,
                    metadata={
                        "offset": offset,
                        "batch_size": batch_size,
                        "items_in_batch": len(items),
                        "total_count": total_count,
                    },
                )

                # Check if done
                if not has_more:
                    break

                # Prepare for next batch
                offset += len(items)
                batch_number += 1

                # Small delay to prevent overwhelming the API
                await asyncio.sleep(0.1)

            except Exception as e:
                self.logger.error(f"Error in streaming batch {batch_number}: {e}")
                yield StreamBatch(
                    items=[],
                    batch_number=batch_number,
                    has_more=False,
                    metadata={"error": str(e)},
                )
                break

    async def _process_stream_with_callback(
        self, stream: AsyncIterator[StreamBatch], callback, max_concurrent: int = 5
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Process a stream with a callback function.

        Args:
            stream: The async iterator of batches
            callback: Async function to process each item
            max_concurrent: Maximum concurrent callback executions

        Returns:
            ServiceResult with processing statistics
        """
        processed_count = 0
        error_count = 0
        errors = []
        start_time = datetime.now()

        # Semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_item(item):
            async with semaphore:
                try:
                    await callback(item)
                    return True, None
                except Exception as e:
                    return False, str(e)

        try:
            async for batch in stream:
                if batch.metadata.get("error"):
                    errors.append(
                        f"Batch {batch.batch_number}: {batch.metadata['error']}"
                    )
                    continue

                # Process items in batch concurrently
                tasks = [process_item(item) for item in batch.items]
                results = await asyncio.gather(*tasks)

                # Count successes and failures
                for success, error in results:
                    if success:
                        processed_count += 1
                    else:
                        error_count += 1
                        if error:
                            errors.append(error)

                # Log progress
                if batch.batch_number % 10 == 0:
                    self.logger.info(
                        f"Processed batch {batch.batch_number}: "
                        f"{processed_count} successful, {error_count} errors"
                    )

            duration = (datetime.now() - start_time).total_seconds()

            return ServiceResult(
                success=True,
                data={
                    "processed_count": processed_count,
                    "error_count": error_count,
                    "duration_seconds": duration,
                    "items_per_second": (
                        processed_count / duration if duration > 0 else 0
                    ),
                },
                warnings=errors[:10] if errors else [],  # Limit error list
            )

        except Exception as e:
            self.logger.exception("Error in stream processing")
            return ServiceResult(
                success=False,
                error=f"Stream processing failed: {str(e)}",
                data={"processed_count": processed_count, "error_count": error_count},
            )


class StreamingHostService(StreamingMixin, BaseService):
    """Host service with streaming capabilities."""

    async def list_hosts_streamed(
        self,
        batch_size: int = 100,
        search: Optional[str] = None,
        folder: Optional[str] = None,
    ) -> AsyncIterator[StreamBatch[HostInfo]]:
        """
        Stream hosts in batches.

        Args:
            batch_size: Number of hosts per batch
            search: Optional search filter
            folder: Optional folder filter

        Yields:
            StreamBatch[HostInfo] objects
        """

        # Define fetch function for hosts
        async def fetch_hosts(limit: int, offset: int):
            result = await self.checkmk.list_hosts(
                search=search, folder=folder, limit=limit, offset=offset
            )
            # Convert to HostInfo models
            hosts = []
            for host_data in result.get("value", []):
                host_info = HostInfo(
                    name=host_data.get("id", ""),
                    folder=host_data.get("folder", "/"),
                    attributes=host_data.get("attributes", {}),
                    is_cluster=host_data.get("is_cluster", False),
                )
                hosts.append(host_info)

            return type(
                "Result", (), {"items": hosts, "total_count": result.get("total_count")}
            )()

        # Stream the data
        async for batch in self._stream_paginated_data(
            fetch_hosts, batch_size=batch_size
        ):
            yield batch


class StreamingServiceService(StreamingMixin, BaseService):
    """Service operations with streaming capabilities."""

    async def list_all_services_streamed(
        self,
        batch_size: int = 200,
        state_filter: Optional[List[str]] = None,
        host_filter: Optional[str] = None,
    ) -> AsyncIterator[StreamBatch[ServiceInfo]]:
        """
        Stream all services in batches.

        Args:
            batch_size: Number of services per batch
            state_filter: Optional state filter
            host_filter: Optional host pattern filter

        Yields:
            StreamBatch[ServiceInfo] objects
        """
        # For services, we might need to stream by host first
        # then services per host
        batch_number = 0
        all_services = []

        # Get hosts to iterate through
        hosts_result = await self.checkmk.list_hosts(search=host_filter)
        hosts = hosts_result.get("value", [])

        for i, host in enumerate(hosts):
            host_name = host.get("id")
            if not host_name:
                continue

            # Get services for this host
            services_result = await self.checkmk.list_host_services(host_name)
            services_data = services_result.get("value", [])

            # Convert to ServiceInfo models
            for svc_data in services_data:
                # Convert numeric state to ServiceState enum
                state_num = svc_data.get("state", 0)
                state_map = {
                    0: ServiceState.OK,
                    1: ServiceState.WARNING,
                    2: ServiceState.CRITICAL,
                    3: ServiceState.UNKNOWN,
                }
                state = state_map.get(state_num, ServiceState.UNKNOWN)

                # Provide required fields with defaults
                from datetime import datetime

                now = datetime.now()

                service_info = ServiceInfo(
                    host_name=host_name,
                    service_name=svc_data.get("description", ""),
                    state=state,
                    state_type=svc_data.get("state_type", "hard"),
                    plugin_output=svc_data.get("plugin_output", ""),
                    last_check=svc_data.get("last_check", now),
                    last_state_change=svc_data.get("last_state_change", now),
                )

                # Apply state filter if needed
                if state_filter and service_info.state not in state_filter:
                    continue

                all_services.append(service_info)

                # Yield batch when full
                if len(all_services) >= batch_size:
                    yield StreamBatch(
                        items=all_services[:batch_size],
                        batch_number=batch_number,
                        has_more=i < len(hosts) - 1,
                        metadata={
                            "current_host": host_name,
                            "hosts_processed": i + 1,
                            "total_hosts": len(hosts),
                        },
                    )
                    all_services = all_services[batch_size:]
                    batch_number += 1

                    # Small delay between batches
                    await asyncio.sleep(0.1)

        # Yield remaining services
        if all_services:
            yield StreamBatch(
                items=all_services,
                batch_number=batch_number,
                has_more=False,
                metadata={"hosts_processed": len(hosts), "total_hosts": len(hosts)},
            )
