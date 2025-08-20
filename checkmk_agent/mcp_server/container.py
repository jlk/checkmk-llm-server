"""Dependency injection container for MCP server.

This module provides a service container for managing dependencies and
service lifecycle in the MCP server architecture.
"""

import logging
from typing import Dict, Any, Optional, TypeVar, Type

from ..config import AppConfig
from ..async_api_client import AsyncCheckmkClient
from ..api_client import CheckmkClient
from ..services import HostService, StatusService, ServiceService, ParameterService
from ..services.event_service import EventService
from ..services.metrics_service import MetricsService
from ..services.bi_service import BIService
from ..services.historical_service import HistoricalDataService, CachedHistoricalDataService
from ..services.streaming import StreamingHostService, StreamingServiceService
from ..services.cache import CachedHostService
from ..services.batch import BatchProcessor

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceContainer:
    """
    Dependency injection container for managing service instances.
    
    This container manages the lifecycle of all services and provides
    clean dependency injection for the MCP server components.
    """
    
    def __init__(self, config: AppConfig):
        """Initialize the service container.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self._services: Dict[str, Any] = {}
        self._initialized = False
        
    async def initialize(self) -> None:
        """Initialize all services in proper dependency order."""
        if self._initialized:
            return
            
        try:
            # Initialize the core API client
            sync_client = CheckmkClient(self.config.checkmk)
            async_client = AsyncCheckmkClient(sync_client)
            self._services['async_client'] = async_client
            self._services['sync_client'] = sync_client
            
            # Initialize core services
            self._services['host_service'] = HostService(async_client, self.config)
            self._services['status_service'] = StatusService(async_client, self.config)
            self._services['service_service'] = ServiceService(async_client, self.config)
            self._services['parameter_service'] = ParameterService(async_client, self.config)
            self._services['event_service'] = EventService(async_client, self.config)
            self._services['metrics_service'] = MetricsService(async_client, self.config)
            self._services['bi_service'] = BIService(async_client, self.config)
            self._services['historical_service'] = CachedHistoricalDataService(async_client, self.config)
            
            # Initialize enhanced services
            self._services['streaming_host_service'] = StreamingHostService(async_client, self.config)
            self._services['streaming_service_service'] = StreamingServiceService(async_client, self.config)
            self._services['cached_host_service'] = CachedHostService(async_client, self.config)
            # Initialize batch processor with configuration parameters
            batch_config = getattr(self.config, 'batch', None)
            if batch_config:
                self._services['batch_processor'] = BatchProcessor(
                    max_concurrent=getattr(batch_config, 'max_concurrent', 5),
                    max_retries=getattr(batch_config, 'max_retries', 3),
                    retry_delay=getattr(batch_config, 'retry_delay', 1.0),
                    rate_limit=getattr(batch_config, 'rate_limit', None)
                )
            else:
                self._services['batch_processor'] = BatchProcessor()
            
            self._initialized = True
            logger.info(f"Service container initialized with {len(self._services)} services")
            
        except Exception as e:
            logger.exception("Failed to initialize service container")
            raise RuntimeError(f"Service container initialization failed: {str(e)}")
    
    def get_service(self, service_name: str, service_type: Optional[Type[T]] = None) -> T:
        """Get a service instance by name.
        
        Args:
            service_name: Name of the service to retrieve
            service_type: Optional type hint for return value
            
        Returns:
            Service instance
            
        Raises:
            KeyError: If service is not found
            RuntimeError: If container is not initialized
        """
        if not self._initialized:
            raise RuntimeError("Service container not initialized. Call initialize() first.")
            
        if service_name not in self._services:
            raise KeyError(f"Service '{service_name}' not found in container")
            
        return self._services[service_name]
    
    def has_service(self, service_name: str) -> bool:
        """Check if a service is registered.
        
        Args:
            service_name: Name of the service to check
            
        Returns:
            True if service is registered, False otherwise
        """
        return service_name in self._services
    
    def get_all_services(self) -> Dict[str, Any]:
        """Get all registered services.
        
        Returns:
            Dictionary of service name to service instance
        """
        return self._services.copy()
    
    def is_initialized(self) -> bool:
        """Check if the container has been initialized.
        
        Returns:
            True if initialized, False otherwise
        """
        return self._initialized
    
    async def shutdown(self) -> None:
        """Shutdown the service container and cleanup resources."""
        try:
            # Cleanup services that need explicit shutdown
            if 'batch_processor' in self._services:
                batch_processor = self._services['batch_processor']
                if hasattr(batch_processor, 'shutdown'):
                    await batch_processor.shutdown()
            
            # Clear all services
            self._services.clear()
            self._initialized = False
            
            logger.info("Service container shutdown completed")
            
        except Exception as e:
            logger.exception("Error during service container shutdown")
            raise RuntimeError(f"Service container shutdown failed: {str(e)}")