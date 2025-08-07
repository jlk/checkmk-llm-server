# ServiceOperations Architecture Refactoring Plan

## Executive Summary

The current `ServiceOperationsManager` in `service_operations.py` has grown into a monolithic, hard-to-maintain class with over 1000 lines of code. This document outlines a comprehensive refactoring plan to transform it into a clean, extensible, and testable architecture using established design patterns.

## Current Architecture Problems

### Critical Issues Identified

1. **Massive Monolithic Method**
   - `process_command()` is 120+ lines with enormous action mapping dictionary (lines 42-83)
   - Single method handling 15+ different operations
   - Difficult to test individual operations in isolation

2. **LLM Parsing Brittleness**
   - Complex JSON parsing with fragile fallback logic (lines 192-220)
   - Error-prone response extraction from LLM
   - No validation of LLM response structure

3. **Code Duplication**
   - Same patterns repeated in `HostOperationsManager`
   - Similar action mapping and command processing logic
   - Inconsistent error handling across managers

4. **Performance Issues**
   - LLM called for every command, even trivial ones
   - No caching of parsed commands
   - Synchronous operations block UI

5. **Mixed Concerns**
   - Service operations, parameter operations, and UI formatting in one class
   - Business logic mixed with presentation logic
   - Tight coupling between components

6. **Testing Challenges**
   - Large methods with LLM dependencies are hard to unit test
   - Mock setup is complex and brittle
   - Integration tests are slow due to LLM calls

7. **Extensibility Problems**
   - Adding new operations requires touching multiple places
   - Action mapping becomes unwieldy
   - No clear plugin architecture

### Code Quality Metrics

- **Cyclomatic Complexity**: Very High (>15 in main methods)
- **Lines of Code**: 1034 lines in single file
- **Method Length**: Several methods >100 lines
- **Dependencies**: High coupling to LLM, API client, parameter manager

## Recommended Architecture

### Core Design Principles

1. **Single Responsibility Principle**: Each class has one clear purpose
2. **Command Pattern**: Operations as discrete, testable commands
3. **Dependency Injection**: Loose coupling for better testing
4. **Strategy Pattern**: Pluggable parsing and formatting strategies
5. **Observer Pattern**: Event-driven updates and notifications

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     CLI Interface                           │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                ServiceOperationsFacade                     │ 
│  - Simplified interface for common operations              │
│  - Handles command routing and response formatting         │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│                 CommandRegistry                            │
│  - Register/discover available commands                    │
│  - Route commands to appropriate handlers                  │
│  - Provide command metadata and help                       │
└─────────────┬───────────────────────────┬───────────────────┘
              │                           │
    ┌─────────▼─────────┐       ┌─────────▼─────────┐
    │  CommandParser    │       │  CommandExecutor  │
    │  - Parse commands │       │  - Execute commands│
    │  - Validate input │       │  - Handle errors   │
    │  - Extract params │       │  - Return results  │
    └─────────┬─────────┘       └─────────┬─────────┘
              │                           │
┌─────────────▼─────────────┐   ┌─────────▼─────────┐
│    LLMCommandAnalyzer     │   │   CommandFactory  │
│  - Analyze with LLM       │   │  - Create commands │
│  - Cache results          │   │  - Dependency inj. │
│  - Fallback strategies    │   │  - Lifecycle mgmt  │
└───────────────────────────┘   └───────────────────┘
```

### Command Hierarchy

```
BaseCommand (ABC)
├── ServiceCommand (ABC)
│   ├── ListServicesCommand
│   ├── GetServiceStatusCommand
│   ├── AcknowledgeServiceCommand
│   ├── CreateDowntimeCommand
│   └── DiscoverServicesCommand
├── ParameterCommand (ABC)
│   ├── ViewDefaultParametersCommand
│   ├── ViewServiceParametersCommand
│   ├── SetServiceParametersCommand
│   └── DiscoverRulesetCommand
└── UtilityCommand (ABC)
    ├── GetInstructionsCommand
    ├── TestConnectionCommand
    └── GetStatisticsCommand
```

## Implementation Plan

### Phase 1: Extract Command System (High Impact)

**Duration**: 1-2 weeks  
**Risk**: Low  
**Impact**: High  

#### 1.1 Create BaseCommand Interface

```python
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class CommandContext:
    """Context information for command execution."""
    user_input: str
    parsed_parameters: Dict[str, Any]
    user_id: Optional[str] = None
    session_id: Optional[str] = None

@dataclass 
class CommandResult:
    """Result of command execution."""
    success: bool
    data: Any = None
    message: str = ""
    error: Optional[str] = None

class BaseCommand(ABC):
    """Abstract base class for all commands."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Command name identifier."""
        pass
    
    @property
    @abstractmethod  
    def description(self) -> str:
        """Human-readable command description."""
        pass
    
    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """Expected parameters and their types."""
        pass
    
    @abstractmethod
    def validate(self, context: CommandContext) -> bool:
        """Validate command parameters."""
        pass
    
    @abstractmethod
    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the command."""
        pass
```

#### 1.2 Implement CommandRegistry

```python
class CommandRegistry:
    """Registry for managing available commands."""
    
    def __init__(self):
        self._commands: Dict[str, BaseCommand] = {}
        self._aliases: Dict[str, str] = {}
    
    def register(self, command: BaseCommand, aliases: List[str] = None):
        """Register a command with optional aliases."""
        self._commands[command.name] = command
        
        if aliases:
            for alias in aliases:
                self._aliases[alias] = command.name
    
    def get_command(self, name: str) -> Optional[BaseCommand]:
        """Get command by name or alias."""
        # Check direct name first
        if name in self._commands:
            return self._commands[name]
        
        # Check aliases
        if name in self._aliases:
            return self._commands[self._aliases[name]]
        
        return None
    
    def list_commands(self, category: str = None) -> List[BaseCommand]:
        """List all registered commands, optionally by category."""
        commands = list(self._commands.values())
        
        if category:
            commands = [cmd for cmd in commands 
                       if getattr(cmd, 'category', None) == category]
        
        return commands
```

#### 1.3 Create CommandFactory

```python
class CommandFactory:
    """Factory for creating command instances with dependencies."""
    
    def __init__(self, checkmk_client: CheckmkClient, 
                 parameter_manager: ServiceParameterManager):
        self.checkmk_client = checkmk_client
        self.parameter_manager = parameter_manager
    
    def create_service_commands(self) -> List[BaseCommand]:
        """Create all service-related commands."""
        return [
            ListServicesCommand(self.checkmk_client),
            GetServiceStatusCommand(self.checkmk_client),
            AcknowledgeServiceCommand(self.checkmk_client),
            CreateDowntimeCommand(self.checkmk_client),
            DiscoverServicesCommand(self.checkmk_client)
        ]
    
    def create_parameter_commands(self) -> List[BaseCommand]:
        """Create all parameter-related commands."""
        return [
            ViewDefaultParametersCommand(self.parameter_manager),
            ViewServiceParametersCommand(self.parameter_manager),
            SetServiceParametersCommand(self.parameter_manager),
            DiscoverRulesetCommand(self.parameter_manager)
        ]
```

### Phase 2: Improve LLM Integration (Medium Impact)

**Duration**: 1-2 weeks  
**Risk**: Medium  
**Impact**: Medium  

#### 2.1 Create LLMCommandAnalyzer

```python
class LLMCommandAnalyzer:
    """Dedicated class for LLM-based command analysis."""
    
    def __init__(self, llm_client: LLMClient, cache_ttl: int = 300):
        self.llm_client = llm_client
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[Dict[str, Any], datetime]] = {}
    
    def analyze_command(self, user_input: str) -> Dict[str, Any]:
        """Analyze command using LLM with caching."""
        # Check cache first
        if self._is_cached(user_input):
            return self._get_cached_result(user_input)
        
        # Try pattern matching for common commands
        pattern_result = self._try_pattern_matching(user_input)
        if pattern_result:
            return pattern_result
        
        # Fall back to LLM analysis
        llm_result = self._analyze_with_llm(user_input)
        self._cache_result(user_input, llm_result)
        
        return llm_result
    
    def _try_pattern_matching(self, user_input: str) -> Optional[Dict[str, Any]]:
        """Try to match common command patterns without LLM."""
        patterns = [
            (r'list services(?:\s+for\s+(\w+))?', 'list_services'),
            (r'show services(?:\s+for\s+(\w+))?', 'list_services'),
            (r'acknowledge\s+(.+)\s+on\s+(\w+)', 'acknowledge_service'),
            (r'ack\s+(.+)\s+on\s+(\w+)', 'acknowledge_service'),
            # Add more patterns as needed
        ]
        
        for pattern, action in patterns:
            match = re.match(pattern, user_input.lower())
            if match:
                return self._extract_parameters_from_match(action, match)
        
        return None
```

#### 2.2 Add Response Validation

```python
class LLMResponseValidator:
    """Validates LLM responses for command analysis."""
    
    REQUIRED_FIELDS = ['action', 'parameters']
    VALID_ACTIONS = [
        'list_services', 'get_service_status', 'acknowledge_service',
        'create_downtime', 'discover_services', 'view_default_parameters',
        'view_service_parameters', 'set_service_parameters'
        # ... more actions
    ]
    
    def validate(self, response: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate LLM response structure and content."""
        # Check required fields
        for field in self.REQUIRED_FIELDS:
            if field not in response:
                return False, f"Missing required field: {field}"
        
        # Validate action
        action = response.get('action')
        if action not in self.VALID_ACTIONS:
            return False, f"Invalid action: {action}"
        
        # Validate parameters structure
        parameters = response.get('parameters', {})
        if not isinstance(parameters, dict):
            return False, "Parameters must be a dictionary"
        
        return True, None
```

### Phase 3: Separate Concerns (Medium Impact)

**Duration**: 2-3 weeks  
**Risk**: Medium  
**Impact**: High  

#### 3.1 Split ServiceOperationsManager

```python
# New structure:
# - ServiceOperationsFacade: Main interface
# - ServiceManager: Core service operations  
# - ParameterManager: Parameter operations (existing)
# - ResponseFormatter: UI formatting
# - ErrorHandler: Centralized error handling

class ServiceOperationsFacade:
    """Simplified facade for service operations."""
    
    def __init__(self, command_registry: CommandRegistry,
                 response_formatter: ResponseFormatter,
                 error_handler: ErrorHandler):
        self.registry = command_registry
        self.formatter = response_formatter  
        self.error_handler = error_handler
    
    def process_command(self, user_input: str) -> str:
        """Process command using the new architecture."""
        try:
            # Parse command
            analysis = self.analyzer.analyze_command(user_input)
            
            # Get appropriate command
            command = self.registry.get_command(analysis['action'])
            if not command:
                return self.error_handler.handle_unknown_command(analysis['action'])
            
            # Create context
            context = CommandContext(
                user_input=user_input,
                parsed_parameters=analysis.get('parameters', {})
            )
            
            # Validate and execute
            if not command.validate(context):
                return self.error_handler.handle_validation_error(command, context)
            
            result = command.execute(context)
            
            # Format response
            return self.formatter.format_response(command, result)
            
        except Exception as e:
            return self.error_handler.handle_unexpected_error(e)
```

#### 3.2 Create ResponseFormatter

```python
class ResponseFormatter:
    """Handles formatting of command responses."""
    
    def __init__(self, ui_manager: UIManager):
        self.ui_manager = ui_manager
    
    def format_response(self, command: BaseCommand, result: CommandResult) -> str:
        """Format command result for user display."""
        if not result.success:
            return self.format_error_response(command, result)
        
        # Use command-specific formatting
        formatter_method = f"format_{command.name}_response"
        if hasattr(self, formatter_method):
            return getattr(self, formatter_method)(result)
        
        # Default formatting
        return self.format_default_response(result)
    
    def format_list_services_response(self, result: CommandResult) -> str:
        """Format list services response."""
        services = result.data
        if not services:
            return "📦 No services found"
        
        # Format based on whether it's single host or all hosts
        # ... formatting logic
        
    def format_acknowledge_service_response(self, result: CommandResult) -> str:
        """Format acknowledge service response."""
        # ... specific formatting for acknowledgments
```

### Phase 4: Enhance Testing & Performance (Low Impact)

**Duration**: 1-2 weeks  
**Risk**: Low  
**Impact**: Medium  

#### 4.1 Mock-Friendly Design

```python
# Commands now take dependencies via constructor
class ListServicesCommand(BaseCommand):
    def __init__(self, checkmk_client: CheckmkClient):
        self.checkmk_client = checkmk_client
    
    # Easy to mock in tests:
    def test_list_services():
        mock_client = Mock()
        mock_client.list_host_services.return_value = [...]
        
        command = ListServicesCommand(mock_client)
        context = CommandContext(user_input="list services", parsed_parameters={})
        
        result = command.execute(context)
        assert result.success
```

#### 4.2 Performance Optimizations

```python
class CachedLLMAnalyzer(LLMCommandAnalyzer):
    """LLM analyzer with advanced caching."""
    
    def __init__(self, llm_client: LLMClient, cache_backend: CacheBackend):
        super().__init__(llm_client)
        self.cache = cache_backend
    
    async def analyze_command_async(self, user_input: str) -> Dict[str, Any]:
        """Async command analysis for better performance."""
        # ... async implementation
```

## Migration Strategy

### Step 1: Non-Breaking Introduction (Week 1)
- Add new command classes alongside existing code
- Implement CommandRegistry with basic commands
- Add comprehensive tests for new components
- No changes to existing API

### Step 2: Parallel Operation (Week 2-3)
- Route new command types through new system
- Keep existing functionality for compatibility
- Add feature flags to control routing
- Gradual migration of operations

### Step 3: Full Migration (Week 4-5)
- Migrate all operations to new system
- Remove old process_command method
- Update CLI interface to use new facade
- Complete test coverage

### Step 4: Cleanup (Week 6)
- Remove deprecated code
- Final documentation updates
- Performance testing and optimization
- Release new architecture

## Expected Benefits

### Quantitative Improvements
- **50% reduction** in method complexity (cyclomatic complexity)
- **80% faster** command processing (with caching)
- **90% test coverage** (vs current ~60%)
- **3x easier** to add new commands

### Qualitative Improvements
- **Easier testing** with isolated, mockable components
- **Better performance** with caching and pattern matching  
- **Simpler extensions** - new commands are just new classes
- **Cleaner separation** of concerns
- **Consistent patterns** across the codebase
- **Better error handling** and user feedback

### Developer Experience
- Clear extension points for new functionality
- Self-documenting command structure
- Easy to understand and modify individual commands
- Comprehensive test coverage builds confidence

## Risk Assessment

### Low Risk
- ✅ Command pattern is well-established
- ✅ Non-breaking migration possible
- ✅ Extensive testing planned

### Medium Risk  
- ⚠️  LLM integration changes may need tuning
- ⚠️  Performance optimization requires measurement
- ⚠️  Migration complexity grows with codebase

### Mitigation Strategies
- Feature flags for gradual rollout
- Comprehensive test suite before migration
- Performance benchmarks at each step
- Rollback plan if issues arise

## Success Metrics

### Technical Metrics
- Cyclomatic complexity < 10 for all methods
- Test coverage > 90%
- Average command execution time < 100ms
- Zero breaking changes during migration

### Operational Metrics  
- No user-facing functionality regressions
- All existing CLI commands work unchanged
- Documentation updated and accurate
- Development velocity maintained

## Conclusion

This refactoring plan transforms the monolithic `ServiceOperationsManager` into a clean, maintainable, and extensible architecture. The phased approach minimizes risk while delivering significant improvements in code quality, testability, and performance.

The new command-based architecture follows established design patterns and provides clear extension points for future functionality. With proper execution, this refactoring will make the codebase significantly easier to maintain and extend.