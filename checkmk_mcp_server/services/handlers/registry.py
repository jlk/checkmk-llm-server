"""
Handler registry system for automatic handler selection and management.
"""

import logging
from typing import Dict, List, Optional, Type, Union
from dataclasses import dataclass, field

from .base import BaseParameterHandler


@dataclass
class HandlerRegistration:
    """Registration information for a parameter handler."""

    handler_class: Type[BaseParameterHandler]
    priority: int = 100  # Lower numbers = higher priority
    description: str = ""
    enabled: bool = True


class HandlerRegistry:
    """
    Registry for managing parameter handlers.

    Provides automatic handler selection based on service patterns and rulesets,
    with support for handler chaining and fallback mechanisms.
    """

    def __init__(self):
        """Initialize the handler registry."""
        self.logger = logging.getLogger(__name__)
        self._handlers: Dict[str, HandlerRegistration] = {}
        self._initialized_handlers: Dict[str, BaseParameterHandler] = {}
        self._service_cache: Dict[str, List[str]] = (
            {}
        )  # Cache service -> handler mapping
        self._ruleset_cache: Dict[str, List[str]] = (
            {}
        )  # Cache ruleset -> handler mapping

    def register_handler(
        self,
        handler_class: Type[BaseParameterHandler],
        priority: int = 100,
        description: str = "",
        enabled: bool = True,
    ) -> None:
        """
        Register a parameter handler.

        Args:
            handler_class: The handler class to register
            priority: Priority for handler selection (lower = higher priority)
            description: Optional description of the handler
            enabled: Whether the handler is enabled
        """
        # Create a temporary instance to get the name
        temp_handler = handler_class()
        handler_name = temp_handler.name

        if handler_name in self._handlers:
            self.logger.warning(
                f"Handler '{handler_name}' is already registered, replacing"
            )

        self._handlers[handler_name] = HandlerRegistration(
            handler_class=handler_class,
            priority=priority,
            description=description,
            enabled=enabled,
        )

        # Clear caches when handlers change
        self._service_cache.clear()
        self._ruleset_cache.clear()

        self.logger.debug(
            f"Registered handler '{handler_name}' with priority {priority}"
        )

    def unregister_handler(self, handler_name: str) -> bool:
        """
        Unregister a parameter handler.

        Args:
            handler_name: Name of the handler to unregister

        Returns:
            True if handler was unregistered, False if not found
        """
        if handler_name in self._handlers:
            del self._handlers[handler_name]

            # Clean up initialized instance
            if handler_name in self._initialized_handlers:
                del self._initialized_handlers[handler_name]

            # Clear caches
            self._service_cache.clear()
            self._ruleset_cache.clear()

            self.logger.debug(f"Unregistered handler '{handler_name}'")
            return True

        return False

    def get_handler(self, handler_name: str) -> Optional[BaseParameterHandler]:
        """
        Get a handler instance by name.

        Args:
            handler_name: Name of the handler

        Returns:
            Handler instance or None if not found
        """
        if handler_name not in self._handlers:
            return None

        registration = self._handlers[handler_name]
        if not registration.enabled:
            return None

        # Return cached instance or create new one
        if handler_name not in self._initialized_handlers:
            try:
                self._initialized_handlers[handler_name] = registration.handler_class()
            except Exception as e:
                self.logger.error(f"Failed to initialize handler '{handler_name}': {e}")
                return None

        return self._initialized_handlers[handler_name]

    def get_handlers_for_service(
        self, service_name: str, limit: int = 3
    ) -> List[BaseParameterHandler]:
        """
        Get handlers that can process the given service, ordered by priority.

        Args:
            service_name: Name of the service
            limit: Maximum number of handlers to return

        Returns:
            List of handler instances
        """
        # Check cache first
        cache_key = f"{service_name}:{limit}"
        if cache_key in self._service_cache:
            handler_names = self._service_cache[cache_key]
            return [
                self.get_handler(name)
                for name in handler_names
                if self.get_handler(name)
            ]

        # Find matching handlers
        matching_handlers = []

        for handler_name, registration in self._handlers.items():
            if not registration.enabled:
                continue

            handler = self.get_handler(handler_name)
            if handler and handler.matches_service(service_name):
                matching_handlers.append((handler, registration.priority))

        # Sort by priority and limit
        matching_handlers.sort(
            key=lambda x: x[1]
        )  # Sort by priority (lower = higher priority)
        handlers = [handler for handler, _ in matching_handlers[:limit]]

        # Cache the result
        self._service_cache[cache_key] = [h.name for h in handlers]

        self.logger.debug(
            f"Found {len(handlers)} handlers for service '{service_name}': {[h.name for h in handlers]}"
        )
        return handlers

    def get_handlers_for_ruleset(
        self, ruleset: str, limit: int = 3
    ) -> List[BaseParameterHandler]:
        """
        Get handlers that support the given ruleset, ordered by priority.

        Args:
            ruleset: Name of the ruleset
            limit: Maximum number of handlers to return

        Returns:
            List of handler instances
        """
        # Check cache first
        cache_key = f"{ruleset}:{limit}"
        if cache_key in self._ruleset_cache:
            handler_names = self._ruleset_cache[cache_key]
            return [
                self.get_handler(name)
                for name in handler_names
                if self.get_handler(name)
            ]

        # Find matching handlers
        matching_handlers = []

        for handler_name, registration in self._handlers.items():
            if not registration.enabled:
                continue

            handler = self.get_handler(handler_name)
            if handler and handler.matches_ruleset(ruleset):
                matching_handlers.append((handler, registration.priority))

        # Sort by priority and limit
        matching_handlers.sort(
            key=lambda x: x[1]
        )  # Sort by priority (lower = higher priority)
        handlers = [handler for handler, _ in matching_handlers[:limit]]

        # Cache the result
        self._ruleset_cache[cache_key] = [h.name for h in handlers]

        self.logger.debug(
            f"Found {len(handlers)} handlers for ruleset '{ruleset}': {[h.name for h in handlers]}"
        )
        return handlers

    def get_best_handler(
        self, service_name: Optional[str] = None, ruleset: Optional[str] = None
    ) -> Optional[BaseParameterHandler]:
        """
        Get the best handler for the given service/ruleset combination.

        Args:
            service_name: Optional service name
            ruleset: Optional ruleset name

        Returns:
            Best matching handler or None
        """
        if service_name and ruleset:
            # Find handlers that match both
            service_handlers = set(
                h.name for h in self.get_handlers_for_service(service_name)
            )
            ruleset_handlers = set(
                h.name for h in self.get_handlers_for_ruleset(ruleset)
            )

            # Get intersection and find highest priority
            common_handlers = service_handlers.intersection(ruleset_handlers)
            if common_handlers:
                # Get the handler with highest priority (lowest number)
                best_handler_name = min(
                    common_handlers, key=lambda name: self._handlers[name].priority
                )
                return self.get_handler(best_handler_name)

        # Fall back to service-based or ruleset-based matching
        if service_name:
            handlers = self.get_handlers_for_service(service_name, limit=1)
            if handlers:
                return handlers[0]

        if ruleset:
            handlers = self.get_handlers_for_ruleset(ruleset, limit=1)
            if handlers:
                return handlers[0]

        return None

    def list_handlers(self, enabled_only: bool = True) -> Dict[str, Dict[str, any]]:
        """
        List all registered handlers with their information.

        Args:
            enabled_only: Whether to include only enabled handlers

        Returns:
            Dictionary of handler information
        """
        handlers_info = {}

        for handler_name, registration in self._handlers.items():
            if enabled_only and not registration.enabled:
                continue

            # Get handler instance to access its properties
            handler = self.get_handler(handler_name)

            handlers_info[handler_name] = {
                "class_name": registration.handler_class.__name__,
                "priority": registration.priority,
                "description": registration.description,
                "enabled": registration.enabled,
                "service_patterns": handler.service_patterns if handler else [],
                "supported_rulesets": handler.supported_rulesets if handler else [],
                "initialized": handler_name in self._initialized_handlers,
            }

        return handlers_info

    def enable_handler(self, handler_name: str) -> bool:
        """
        Enable a handler.

        Args:
            handler_name: Name of the handler to enable

        Returns:
            True if handler was enabled, False if not found
        """
        if handler_name in self._handlers:
            self._handlers[handler_name].enabled = True
            self._service_cache.clear()
            self._ruleset_cache.clear()
            self.logger.debug(f"Enabled handler '{handler_name}'")
            return True

        return False

    def disable_handler(self, handler_name: str) -> bool:
        """
        Disable a handler.

        Args:
            handler_name: Name of the handler to disable

        Returns:
            True if handler was disabled, False if not found
        """
        if handler_name in self._handlers:
            self._handlers[handler_name].enabled = False
            self._service_cache.clear()
            self._ruleset_cache.clear()
            self.logger.debug(f"Disabled handler '{handler_name}'")
            return True

        return False

    def clear_cache(self) -> None:
        """Clear all internal caches."""
        self._service_cache.clear()
        self._ruleset_cache.clear()
        self.logger.debug("Cleared handler registry caches")


# Global registry instance
_global_registry: Optional[HandlerRegistry] = None


def get_handler_registry() -> HandlerRegistry:
    """
    Get the global handler registry instance.

    Returns:
        Global HandlerRegistry instance
    """
    global _global_registry

    if _global_registry is None:
        _global_registry = HandlerRegistry()

        # Register default handlers
        _register_default_handlers(_global_registry)

    return _global_registry


def _register_default_handlers(registry: HandlerRegistry) -> None:
    """Register all default handlers with the registry."""
    try:
        # Import handlers here to avoid circular imports
        from .temperature import TemperatureParameterHandler
        from .custom_checks import CustomCheckParameterHandler
        from .database import DatabaseParameterHandler
        from .network import NetworkServiceParameterHandler

        # Register handlers with appropriate priorities
        registry.register_handler(
            TemperatureParameterHandler,
            priority=10,
            description="Specialized handler for temperature monitoring parameters",
        )

        registry.register_handler(
            CustomCheckParameterHandler,
            priority=20,
            description="Handler for custom check parameters and MRPE checks",
        )

        registry.register_handler(
            DatabaseParameterHandler,
            priority=15,
            description="Handler for database monitoring parameters",
        )

        registry.register_handler(
            NetworkServiceParameterHandler,
            priority=25,
            description="Handler for network service monitoring parameters",
        )

    except ImportError as e:
        logging.getLogger(__name__).warning(
            f"Could not register some default handlers: {e}"
        )
