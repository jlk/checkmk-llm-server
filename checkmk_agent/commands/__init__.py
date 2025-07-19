"""Command system for Checkmk LLM Agent.

This module implements a command-based architecture for handling user operations.
It provides a clean separation of concerns with:

- BaseCommand: Abstract interface for all commands
- CommandContext: Input context for command execution
- CommandResult: Standardized result structure
- CommandRegistry: Registration and discovery of commands
- CommandFactory: Dependency injection for commands
- LLMCommandAnalyzer: LLM-based command analysis with caching
- ServiceOperationsFacade: Simplified facade for service operations
- BackwardCompatibilityWrapper: Maintains API compatibility

This replaces the monolithic process_command approach with a modular,
testable, and extensible system.
"""

from .base import BaseCommand, CommandContext, CommandResult, CommandCategory
from .registry import CommandRegistry
from .factory import CommandFactory
from .analyzer import LLMCommandAnalyzer, AnalysisResult
from .facade import ServiceOperationsFacade, BackwardCompatibilityWrapper

__all__ = [
    'BaseCommand',
    'CommandContext', 
    'CommandResult',
    'CommandCategory',
    'CommandRegistry',
    'CommandFactory',
    'LLMCommandAnalyzer',
    'AnalysisResult',
    'ServiceOperationsFacade',
    'BackwardCompatibilityWrapper'
]