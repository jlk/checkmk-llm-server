"""
Specialized parameter handlers module.

This module provides specialized parameter handlers for different service types,
enabling domain-specific parameter validation, defaults, and processing.
"""

from .base import BaseParameterHandler, HandlerResult, ValidationSeverity
from .registry import HandlerRegistry, get_handler_registry
from .temperature import TemperatureParameterHandler
from .custom_checks import CustomCheckParameterHandler
from .database import DatabaseParameterHandler
from .network import NetworkServiceParameterHandler

__all__ = [
    "BaseParameterHandler",
    "HandlerResult",
    "ValidationSeverity",
    "HandlerRegistry",
    "get_handler_registry",
    "TemperatureParameterHandler",
    "CustomCheckParameterHandler",
    "DatabaseParameterHandler",
    "NetworkServiceParameterHandler",
]
