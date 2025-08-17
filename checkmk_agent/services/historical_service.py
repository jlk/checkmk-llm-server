"""Historical data service with scraper factory pattern integration."""

import logging
import re
from datetime import datetime
from typing import List, Tuple, Union, Optional, Dict, Any
from dataclasses import asdict

from ..config import AppConfig, CheckmkConfig
from ..async_api_client import AsyncCheckmkClient
from .base import BaseService, ServiceResult
from .cache import CachingService
from .models.historical import (
    HistoricalDataPoint,
    HistoricalDataResult,
    HistoricalDataRequest,
    HistoricalDataServiceResult
)

# Import request context utilities with fallback
try:
    from ..utils.request_context import (
        get_request_id,
        ensure_request_id,
        with_request_id,
    )
except ImportError:
    # Fallback for cases where request tracking is not available
    def get_request_id() -> Optional[str]:
        return None

    def ensure_request_id() -> str:
        return "req_unknown"

    def with_request_id(request_id: Optional[str] = None):
        def decorator(func):
            return func
        return decorator


class HistoricalDataService(BaseService):
    """Service for retrieving historical data using scraper factory pattern.
    
    This service manages historical data retrieval by creating fresh scraper
    instances per request to ensure clean state and proper resource management.
    It provides data parsing capabilities to handle mixed output from scrapers.
    """

    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig):
        """Initialize the historical data service.
        
        Args:
            checkmk_client: Async Checkmk API client
            config: Application configuration containing historical data settings
        """
        super().__init__(checkmk_client, config)
        self.logger = logging.getLogger(__name__)
        
        # Extract historical data configuration with defaults
        historical_config = getattr(config, 'historical_data', {})
        if isinstance(historical_config, dict):
            self.source = historical_config.get('source', 'scraper')
            self.cache_ttl = historical_config.get('cache_ttl', 60)
            self.scraper_timeout = historical_config.get('scraper_timeout', 30)
        else:
            # Handle case where historical_data is a Pydantic model
            self.source = getattr(historical_config, 'source', 'scraper')
            self.cache_ttl = getattr(historical_config, 'cache_ttl', 60)
            self.scraper_timeout = getattr(historical_config, 'scraper_timeout', 30)
        
        self.logger.debug(f"Initialized historical data service with source: {self.source}")

    def _create_scraper_instance(self) -> "CheckmkHistoricalScraper":
        """Create a fresh scraper instance using factory pattern.
        
        This method implements the factory pattern by creating a new scraper
        instance for each request, ensuring clean state and proper isolation.
        
        Returns:
            Fresh CheckmkHistoricalScraper instance
            
        Raises:
            ImportError: If CheckmkHistoricalScraper cannot be imported
            ValueError: If CheckmkConfig cannot be created
        """
        try:
            # Import the scraper class dynamically to avoid circular imports
            from checkmk_scraper import CheckmkHistoricalScraper
            
            # Create CheckmkConfig from AppConfig
            checkmk_config = self.config.checkmk
            
            # Create fresh scraper instance
            scraper = CheckmkHistoricalScraper(checkmk_config)
            
            self.logger.debug(f"Created fresh scraper instance for server: {checkmk_config.server_url}")
            return scraper
            
        except ImportError as e:
            error_msg = f"Failed to import CheckmkHistoricalScraper: {e}"
            self.logger.error(error_msg)
            raise ImportError(error_msg) from e
        except Exception as e:
            error_msg = f"Failed to create scraper instance: {e}"
            self.logger.error(error_msg)
            raise ValueError(error_msg) from e

    def _is_timestamp(self, value: str) -> bool:
        """Detect if a string value is a timestamp.
        
        This method checks if a string matches common timestamp patterns
        used in Checkmk historical data, including ISO format and Unix timestamps.
        It also validates that the timestamp is actually parseable.
        
        Args:
            value: String value to check
            
        Returns:
            True if value appears to be a timestamp and is parseable
        """
        if not isinstance(value, str):
            return False
        
        # Check ISO 8601 timestamp format (2025-01-15T10:30:00)
        iso_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?$'
        if re.match(iso_pattern, value):
            # Try to parse to validate it's a real date
            try:
                datetime.fromisoformat(value.replace('Z', '+00:00'))
                return True
            except ValueError:
                return False
        
        # Check Unix timestamp (numeric string)
        if value.isdigit() and len(value) >= 9:  # Unix timestamps are typically 10+ digits
            try:
                timestamp = int(value)
                
                # Handle both seconds and milliseconds timestamps
                if len(value) >= 12:  # Millisecond timestamp
                    timestamp = timestamp // 1000  # Convert to seconds
                
                # Unix timestamps should be positive and reasonable (1970 to ~2038)
                if 0 < timestamp < 2**31:  # Until year 2038
                    datetime.fromtimestamp(timestamp)
                    return True
            except (ValueError, OSError, OverflowError):
                pass
            return False
        
        # Check date-only format (2025-01-15)
        date_pattern = r'^\d{4}-\d{2}-\d{2}$'
        if re.match(date_pattern, value):
            # Try to parse to validate it's a real date
            try:
                datetime.strptime(value, '%Y-%m-%d')
                return True
            except ValueError:
                return False
        
        # Check time-only format (10:30:00)
        time_pattern = r'^\d{2}:\d{2}:\d{2}$'
        if re.match(time_pattern, value):
            # Try to parse to validate it's a real time
            try:
                # Parse as time and check ranges
                parts = value.split(':')
                hour, minute, second = int(parts[0]), int(parts[1]), int(parts[2])
                if 0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59:
                    return True
            except (ValueError, IndexError):
                pass
            return False
        
        return False

    def _is_summary_stat(self, value: str) -> bool:
        """Detect if a string value is a summary statistic.
        
        This method checks if a string matches common summary statistic
        names used in monitoring data.
        
        Args:
            value: String value to check
            
        Returns:
            True if value appears to be a summary statistic name
        """
        if not isinstance(value, str):
            return False
        
        # Common summary statistic names (case-insensitive)
        summary_stats = {
            'min', 'max', 'avg', 'average', 'mean', 'median', 'mode',
            'std', 'stddev', 'stdev', 'variance', 'var',
            'sum', 'total', 'count', 'last', 'first',
            'p50', 'p90', 'p95', 'p99',  # Percentiles
            'q1', 'q2', 'q3',  # Quartiles
            'range', 'iqr'  # Range and interquartile range
        }
        
        return value.lower() in summary_stats

    def _parse_scraper_output(
        self, 
        scraper_data: List[Tuple[str, Union[float, str]]], 
        host_name: str, 
        service_name: str,
        period: str
    ) -> HistoricalDataResult:
        """Parse scraper output into structured historical data result.
        
        This method processes the raw output from CheckmkHistoricalScraper,
        separating time-series data points from summary statistics and
        handling timestamp parsing.
        
        Args:
            scraper_data: Raw output from CheckmkHistoricalScraper
            host_name: Host name for context
            service_name: Service name for context  
            period: Time period for context
            
        Returns:
            Structured historical data result
            
        Raises:
            ValueError: If data parsing fails
        """
        request_id = ensure_request_id()
        self.logger.debug(f"[{request_id}] Parsing {len(scraper_data)} data points from scraper")
        
        data_points = []
        summary_stats = {}
        parse_errors = []
        
        for i, (timestamp_str, value) in enumerate(scraper_data):
            try:
                # Check if this is a summary statistic
                if self._is_summary_stat(timestamp_str):
                    # This is a summary stat where timestamp_str is the stat name
                    if isinstance(value, (int, float)):
                        summary_stats[timestamp_str] = float(value)
                        self.logger.debug(f"[{request_id}] Found summary stat: {timestamp_str} = {value}")
                    continue
                
                # Check if this is a timestamp
                if self._is_timestamp(timestamp_str):
                    # Parse timestamp
                    try:
                        # Try ISO format first
                        if 'T' in timestamp_str:
                            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                        # Try Unix timestamp
                        elif timestamp_str.isdigit():
                            timestamp = datetime.fromtimestamp(int(timestamp_str))
                        # Try date-only format
                        elif re.match(r'^\d{4}-\d{2}-\d{2}$', timestamp_str):
                            timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d')
                        else:
                            # Skip if we can't parse the timestamp
                            self.logger.warning(f"[{request_id}] Could not parse timestamp: {timestamp_str}")
                            continue
                        
                        # Create data point
                        # Infer metric name from service name (LLM can enhance this)
                        metric_name = service_name.lower().replace(' ', '_')
                        
                        # Try to extract unit from value if it's a string
                        unit = None
                        numeric_value = value
                        if isinstance(value, str):
                            # Try to extract numeric value and unit
                            value_match = re.search(r'([\d.]+)\s*([a-zA-Z°%]+)?', str(value))
                            if value_match:
                                numeric_value = float(value_match.group(1))
                                unit = value_match.group(2)
                            else:
                                # Keep as string if not numeric
                                numeric_value = value
                        
                        data_point = HistoricalDataPoint(
                            timestamp=timestamp,
                            value=numeric_value,
                            metric_name=metric_name,
                            unit=unit
                        )
                        data_points.append(data_point)
                        
                    except Exception as e:
                        error_msg = f"Error parsing data point {i}: {e}"
                        parse_errors.append(error_msg)
                        self.logger.warning(f"[{request_id}] {error_msg}")
                        continue
                else:
                    # Skip non-timestamp, non-summary entries
                    self.logger.debug(f"[{request_id}] Skipping non-timestamp entry: {timestamp_str}")
                    continue
                    
            except Exception as e:
                error_msg = f"Error processing scraper data point {i}: {e}"
                parse_errors.append(error_msg)
                self.logger.warning(f"[{request_id}] {error_msg}")
                continue
        
        # Create metadata
        metadata = {
            "source": "scraper",
            "time_range": period,
            "host_name": host_name,
            "service_name": service_name,
            "parse_errors": parse_errors,
            "raw_data_count": len(scraper_data),
            "parsed_data_points": len(data_points),
            "parsed_summary_stats": len(summary_stats),
            "request_id": request_id,
        }
        
        self.logger.info(
            f"[{request_id}] Parsed {len(data_points)} data points and "
            f"{len(summary_stats)} summary stats from {len(scraper_data)} raw entries"
        )
        
        return HistoricalDataResult(
            data_points=data_points,
            summary_stats=summary_stats,
            metadata=metadata,
            source="scraper"
        )

    @with_request_id()
    async def get_historical_data(
        self, 
        request: HistoricalDataRequest
    ) -> HistoricalDataServiceResult:
        """Retrieve historical data for a host/service using scraper.
        
        This method implements the main interface for historical data retrieval,
        using the factory pattern to create fresh scraper instances and
        parsing the output into structured data.
        
        Args:
            request: Historical data request parameters
            
        Returns:
            Service result containing historical data or error information
        """
        request_id = ensure_request_id()
        start_time = datetime.now()
        
        self.logger.info(
            f"[{request_id}] Getting historical data for {request.host_name}/"
            f"{request.service_name} (period: {request.period})"
        )
        
        try:
            # Create fresh scraper instance using factory pattern
            scraper = self._create_scraper_instance()
            
            # Scrape historical data
            self.logger.debug(f"[{request_id}] Scraping data with period: {request.period}")
            raw_data = scraper.scrape_historical_data(
                period=request.period,
                host=request.host_name,
                service=request.service_name
            )
            
            self.logger.debug(f"[{request_id}] Received {len(raw_data)} raw data points from scraper")
            
            # Parse scraper output into structured format
            historical_result = self._parse_scraper_output(
                raw_data, 
                request.host_name, 
                request.service_name, 
                request.period
            )
            
            execution_time = (datetime.now() - start_time).total_seconds() * 1000
            
            # Add execution time to metadata
            historical_result.metadata["execution_time_ms"] = execution_time
            
            self.logger.info(
                f"[{request_id}] Successfully retrieved historical data in {execution_time:.2f}ms "
                f"({len(historical_result.data_points)} data points, "
                f"{len(historical_result.summary_stats)} summary stats)"
            )
            
            return HistoricalDataServiceResult.success_result(
                data=historical_result,
                metadata={"execution_time_ms": execution_time},
                request_id=request_id
            )
            
        except ImportError as e:
            error_msg = f"Scraper not available: {e}"
            self.logger.error(f"[{request_id}] {error_msg}")
            
            return HistoricalDataServiceResult.error_result(
                error=error_msg,
                metadata={"error_type": "import_error"},
                request_id=request_id
            )
            
        except Exception as e:
            # Check if this is a ScrapingError and pass it through with additional context
            try:
                from checkmk_scraper import ScrapingError
                if isinstance(e, ScrapingError):
                    error_msg = f"Scraping failed: {e}"
                    self.logger.error(f"[{request_id}] {error_msg}")
                    
                    return HistoricalDataServiceResult.error_result(
                        error=error_msg,
                        metadata={
                            "error_type": "scraping_error",
                            "original_error": str(e),
                            "error_class": "ScrapingError"
                        },
                        request_id=request_id
                    )
            except ImportError:
                # ScrapingError not available, fall through to generic handling
                pass
            
            error_msg = f"Failed to retrieve historical data: {e}"
            self.logger.error(f"[{request_id}] {error_msg}")
            
            return HistoricalDataServiceResult.error_result(
                error=error_msg,
                metadata={"error_type": "scraper_error"},
                request_id=request_id
            )

    async def get_available_metrics(
        self, 
        host_name: str, 
        service_name: str
    ) -> ServiceResult[List[str]]:
        """Get list of available metrics for a host/service.
        
        This is a placeholder for future implementation when multiple
        metrics per service are supported.
        
        Args:
            host_name: Host name
            service_name: Service name
            
        Returns:
            List of available metric names
        """
        request_id = ensure_request_id()
        
        # For now, return the service name as the only available metric
        # This can be enhanced later to query actual available metrics
        metric_name = service_name.lower().replace(' ', '_')
        
        self.logger.debug(
            f"[{request_id}] Returning default metric for {host_name}/{service_name}: {metric_name}"
        )
        
        return ServiceResult.success_result(
            data=[metric_name],
            metadata={"host_name": host_name, "service_name": service_name},
            request_id=request_id
        )


class CachedHistoricalDataService(CachingService, HistoricalDataService):
    """Cached version of HistoricalDataService with configurable TTL.
    
    This service provides caching for historical data retrieval operations
    using the existing cache infrastructure. It follows the same pattern
    as CachedHostService for consistency.
    """
    
    def __init__(self, checkmk_client: AsyncCheckmkClient, config: AppConfig, cache_ttl: int = None):
        """Initialize the cached historical data service.
        
        Args:
            checkmk_client: Async Checkmk API client
            config: Application configuration
            cache_ttl: Cache TTL in seconds (defaults to historical_data.cache_ttl from config)
        """
        # Get cache TTL from config or use provided value
        if cache_ttl is None:
            historical_config = getattr(config, 'historical_data', {})
            if isinstance(historical_config, dict):
                cache_ttl = historical_config.get('cache_ttl', 60)
            else:
                cache_ttl = getattr(historical_config, 'cache_ttl', 60)
        
        # Initialize with caching capabilities
        super().__init__(checkmk_client, config, cache_ttl=cache_ttl, cache_size=1000)
        
        self.logger.debug(f"Initialized cached historical data service with TTL: {cache_ttl}s")

    @property
    def cached(self):
        """Access the decorator as a property to use instance cache."""
        return super().cached

    async def get_historical_data(
        self, 
        request: HistoricalDataRequest
    ) -> HistoricalDataServiceResult:
        """Retrieve historical data with caching.
        
        This method wraps the parent get_historical_data method with caching
        using the configured TTL. Cache keys are based on the request parameters
        to ensure proper cache isolation.
        
        Args:
            request: Historical data request parameters
            
        Returns:
            Service result containing historical data or error information
        """
        
        @self.cached(ttl=self.cache_ttl, key_prefix="historical_data")
        async def _cached_get_historical_data(request: HistoricalDataRequest):
            # Call parent implementation
            return await super(CachedHistoricalDataService, self).get_historical_data(request)
        
        return await _cached_get_historical_data(request)

    async def get_available_metrics(
        self, 
        host_name: str, 
        service_name: str
    ) -> ServiceResult[List[str]]:
        """Get list of available metrics with caching.
        
        Args:
            host_name: Host name
            service_name: Service name
            
        Returns:
            List of available metric names
        """
        
        @self.cached(ttl=300, key_prefix="available_metrics")  # Cache metrics for 5 minutes
        async def _cached_get_available_metrics(host_name: str, service_name: str):
            # Call parent implementation
            return await super(CachedHistoricalDataService, self).get_available_metrics(host_name, service_name)
        
        return await _cached_get_available_metrics(host_name, service_name)