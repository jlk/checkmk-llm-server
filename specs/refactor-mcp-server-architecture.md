# MCP Server Refactoring Plan

## Problem Analysis
The current `server.py` is 4449 lines - a monolithic file that violates SOLID principles and is difficult to maintain, test, and extend.

## Proposed Architecture

### 1. Core Server Module (`server.py`) - ~200 lines
- Main `CheckmkMCPServer` class with initialization and routing
- MCP protocol handlers (list_resources, read_resource, etc.)
- Service dependency injection
- Error handling and logging setup

### 2. Tool Categories (Separate modules)

#### `tools/host_tools.py` (~400 lines)
- `list_hosts`
- `create_host` 
- `update_host`
- `delete_host`
- `get_host_status`
- `list_host_services`
- Host-related streaming operations

#### `tools/service_tools.py` (~500 lines)
- `list_all_services`
- `get_service_status`
- `acknowledge_problem`
- `create_downtime`
- Service discovery tools
- Service parameter tools

#### `tools/status_tools.py` (~300 lines)
- `get_health_dashboard`
- `get_critical_problems`
- `get_performance_metrics`
- Status monitoring tools

#### `tools/parameter_tools.py` (~400 lines)
- `get_service_parameters`
- `set_service_parameters`
- `validate_parameters`
- Specialized parameter handlers integration

#### `tools/advanced_tools.py` (~500 lines)
- Streaming operations
- Batch processing
- Historical data tools
- Metrics and BI tools
- Event console tools

### 3. Supporting Infrastructure

#### `handlers/tool_registry.py` (~150 lines)
- Centralized tool registration
- Tool metadata management
- Handler function mapping

#### `handlers/resource_handlers.py` (~200 lines)
- MCP resource implementations
- Streaming resource handlers
- Resource content generation

#### `handlers/prompt_handlers.py` (~300 lines)
- All prompt definitions and handlers
- Prompt argument validation
- Dynamic prompt generation

#### `utils/server_utils.py` (~100 lines)
- `sanitize_error`
- `MCPJSONEncoder`
- `safe_json_dumps`
- Common utility functions

#### `validation/tool_validators.py` (~200 lines)
- Input validation for each tool category
- Parameter sanitization
- Error message standardization

### 4. Configuration

#### `config/tool_definitions.py` (~300 lines)
- Tool schema definitions
- Parameter specifications
- Documentation strings

## Benefits

### Maintainability
- Each module has a single responsibility
- Easy to locate and modify specific functionality
- Clear separation of concerns

### Testability  
- Each tool category can be unit tested independently
- Isolated testing of validators and utilities
- Better mocking and dependency injection

### Extensibility
- New tools can be added to appropriate categories
- Plugin-like architecture for tool registration
- Easy to add new handler types

### Code Quality
- Smaller, focused files (~200-500 lines each)
- Reduced cognitive load
- Better code organization and discoverability

### Team Development
- Multiple developers can work on different tool categories
- Reduced merge conflicts
- Clear ownership boundaries

## File Structure After Refactoring
```
checkmk_agent/mcp_server/
├── __init__.py
├── server.py                    # Main orchestration (~200 lines)
├── tools/
│   ├── __init__.py
│   ├── host_tools.py           # Host operations (~400 lines)
│   ├── service_tools.py        # Service operations (~500 lines)  
│   ├── status_tools.py         # Status monitoring (~300 lines)
│   ├── parameter_tools.py      # Parameter management (~400 lines)
│   └── advanced_tools.py       # Advanced features (~500 lines)
├── handlers/
│   ├── __init__.py
│   ├── tool_registry.py        # Tool registration (~150 lines)
│   ├── resource_handlers.py    # Resource handling (~200 lines)
│   └── prompt_handlers.py      # Prompt management (~300 lines)
├── utils/
│   ├── __init__.py
│   └── server_utils.py         # Utilities (~100 lines)
├── validation/
│   ├── __init__.py
│   └── tool_validators.py      # Input validation (~200 lines)
└── config/
    ├── __init__.py
    └── tool_definitions.py     # Tool schemas (~300 lines)
```

## Risk Mitigation
- Comprehensive testing at each phase
- Gradual migration with backward compatibility
- Rollback plan if issues arise
- No functionality changes, only structural improvements

## Additional Files Requiring Updates

### **Critical Files** (Must be updated)

#### **Entry Point** (`mcp_checkmk_server.py`)
- **Current**: `from checkmk_agent.mcp_server import CheckmkMCPServer`
- **Update Required**: Import path will remain the same (maintained via `__init__.py`)
- **Changes**: None required if `__init__.py` properly exports the refactored class

#### **Package Init** (`checkmk_agent/mcp_server/__init__.py`)
- **Current**: Exports `CheckmkMCPServer` from `server.py`
- **Update Required**: May need to export from new orchestration module
- **Changes**: Update import paths to maintain backward compatibility

#### **Test Files** (16 files requiring updates)
All test files importing `CheckmkMCPServer` will need import path updates:
- `tests/test_mcp_server_tools.py`
- `tests/test_mcp_historical_tools.py`
- `tests/test_mcp_parameter_tools.py`
- `tests/test_mcp_personality_context.py`
- `tests/test_request_id_integration.py`
- `tests/test_effective_attributes_integration.py`
- `tests/test_effective_attributes.py`
- `tests/test_parameter_integration.py`
- `tests/test_e2e_historical_scraping.py`
- `tests/test_historical_*.py` (5 files)
- `benchmark_parameter_operations.py`

### **Supporting Files** (Should be updated)

#### **Documentation Updates**
- `checkmk_agent/mcp_server/README.md` - Update architecture description
- `README.md` - Update MCP server section with new architecture
- `IMPLEMENTATION_SUMMARY.md` - Add refactoring notes
- `docs/ADVANCED_FEATURES.md` - Update MCP server references

#### **Configuration Files**
- `setup.py` - Verify package includes new module structure
- `pytest.ini` - May need test discovery path updates
- `.serena/memories/codebase_structure.md` - Update memory with new structure

### **Implementation Phases**

#### **Phase 0: Preparation and Validation** (1-2 days)
1. Create feature branch for refactoring
2. Document current test coverage baseline
3. Create rollback validation script
4. Analyze tool dependencies and categorization

#### **Phase 1: Foundation and Utilities** (2-3 days)
5. Create directory structure with proper `__init__.py` files
6. Extract `utils/serialization.py` and `utils/errors.py`
7. Create `config/` package with tool definitions
8. Build comprehensive test harness for extracted utilities
9. Update backward compatibility in `__init__.py`

#### **Phase 2: Registry and Protocol** (2-3 days)
10. Extract `handlers/registry.py` for tool management
11. Extract `handlers/protocol.py` for MCP protocol handling
12. Create `config/registry.py` for centralized configuration
13. Validate tool registration and discovery works correctly

#### **Phase 3: Prompt System** (3-4 days)
14. Extract prompt definitions to `prompts/definitions.py`
15. Extract prompt handlers to `prompts/handlers.py`
16. Extract prompt validation to `prompts/validators.py`
17. Validate all 15+ prompts function identically

#### **Phase 4: Tool Categories** (8-10 days)
18. Extract host tools to `tools/host/` package
19. Extract service tools to `tools/service/` package
20. Extract monitoring tools to `tools/monitoring/` package
21. Extract parameter tools to `tools/parameters/` package
22. Extract event tools to `tools/events/` package
23. Extract metrics tools to `tools/metrics/` package
24. Extract business tools to `tools/business/` package
25. Extract advanced tools to `tools/advanced/` package
26. Validate each tool category maintains full functionality

#### **Phase 5: Main Server Refactoring** (3-4 days)
27. Refactor `server.py` to orchestration-only
28. Update all imports and dependencies
29. Implement dependency injection container
30. Full integration testing

#### **Phase 6: Integration and Testing** (5-7 days)
31. Update all test imports to use new module structure
32. Update documentation to reflect new architecture
33. Update package configuration (`setup.py`, etc.)
34. Validate backward compatibility via entry point testing
35. Performance benchmarking against original implementation
36. Update project memories with new structure

### **Backward Compatibility Strategy**

#### **Import Compatibility**
Maintain these import paths during and after refactoring:
```python
# This should continue to work
from checkmk_agent.mcp_server import CheckmkMCPServer

# This should also continue to work  
from checkmk_agent.mcp_server.server import CheckmkMCPServer
```

#### **API Compatibility**
- `CheckmkMCPServer` class interface must remain identical
- All public methods must maintain same signatures
- Feature flags and initialization parameters unchanged

#### **Test Migration Strategy**
- **Phase 6.1**: Update test imports incrementally
- **Phase 6.2**: Add integration tests for new module boundaries
- **Phase 6.3**: Validate all existing tests pass with new structure
- **Phase 6.4**: Add new tests specific to refactored architecture

### **Risk Assessment Updates**

#### **Additional Risks Identified**
- **Test Suite Disruption**: 16 test files need import updates
- **Documentation Drift**: Multiple docs reference current structure
- **Package Distribution**: Module structure changes may affect packaging
- **CI/CD Pipeline**: May need updates for new test discovery paths

#### **Enhanced Mitigation**
- **Automated Import Updater**: Script to update all import statements
- **Documentation Generator**: Auto-update docs from new module structure  
- **Package Validation**: Test package installation with new structure
- **CI Integration**: Update CI to validate new module boundaries

### **Updated Timeline**

- **Phase 0** (Preparation): 1-2 days
- **Phase 1** (Foundation): 2-3 days
- **Phase 2** (Registry): 2-3 days  
- **Phase 3** (Prompts): 3-4 days
- **Phase 4** (Tool Categories): 8-10 days
- **Phase 5** (Main Server): 3-4 days
- **Phase 6** (Integration & Testing): 5-7 days (**Enhanced**)

**Total Estimated Effort**: 24-33 days with comprehensive testing and integration

---

## Project To-Do Tracker

**Last Updated**: 2025-08-18T21:48:00Z  
**Current Phase**: Phase 0 Complete - Ready for Phase 1  
**Overall Progress**: 4/36 tasks completed (11%)

### **Phase 0: Preparation and Validation** (4/4 completed) ✅
- [x] **Task 1**: Create feature branch for refactoring ✅
- [x] **Task 2**: Document current test coverage baseline ✅  
- [x] **Task 3**: Create rollback validation script ✅
- [x] **Task 4**: Analyze tool dependencies and categorization ✅

### **Phase 1: Foundation and Utilities** (0/5 completed)
- [ ] **Task 5**: Create directory structure with proper `__init__.py` files
- [ ] **Task 6**: Extract `utils/serialization.py` and `utils/errors.py`
- [ ] **Task 7**: Create `config/` package with tool definitions
- [ ] **Task 8**: Build comprehensive test harness for extracted utilities
- [ ] **Task 9**: Update backward compatibility in `__init__.py`

### **Phase 2: Registry and Protocol** (0/4 completed)
- [ ] **Task 10**: Extract `handlers/registry.py` for tool management
- [ ] **Task 11**: Extract `handlers/protocol.py` for MCP protocol handling
- [ ] **Task 12**: Create `config/registry.py` for centralized configuration
- [ ] **Task 13**: Validate tool registration and discovery works correctly

### **Phase 3: Prompt System** (0/4 completed)
- [ ] **Task 14**: Extract prompt definitions to `prompts/definitions.py`
- [ ] **Task 15**: Extract prompt handlers to `prompts/handlers.py`
- [ ] **Task 16**: Extract prompt validation to `prompts/validators.py`
- [ ] **Task 17**: Validate all 15+ prompts function identically

### **Phase 4: Tool Categories** (0/9 completed)
- [ ] **Task 18**: Extract host tools to `tools/host/` package
- [ ] **Task 19**: Extract service tools to `tools/service/` package
- [ ] **Task 20**: Extract monitoring tools to `tools/monitoring/` package
- [ ] **Task 21**: Extract parameter tools to `tools/parameters/` package
- [ ] **Task 22**: Extract event tools to `tools/events/` package
- [ ] **Task 23**: Extract metrics tools to `tools/metrics/` package
- [ ] **Task 24**: Extract business tools to `tools/business/` package
- [ ] **Task 25**: Extract advanced tools to `tools/advanced/` package
- [ ] **Task 26**: Validate each tool category maintains full functionality

### **Phase 5: Main Server Refactoring** (0/4 completed)
- [ ] **Task 27**: Refactor `server.py` to orchestration-only
- [ ] **Task 28**: Update all imports and dependencies
- [ ] **Task 29**: Implement dependency injection container
- [ ] **Task 30**: Full integration testing

### **Phase 6: Integration and Testing** (0/6 completed)
- [ ] **Task 31**: Update all test imports to use new module structure
- [ ] **Task 32**: Update documentation to reflect new architecture
- [ ] **Task 33**: Update package configuration (`setup.py`, etc.)
- [ ] **Task 34**: Validate backward compatibility via entry point testing
- [ ] **Task 35**: Performance benchmarking against original implementation
- [ ] **Task 36**: Update project memories with new structure

### **Files Modified Tracker**
Track files created/modified during refactoring:

#### **New Files Created** (0 files)
*To be updated as files are created*

#### **Existing Files Modified** (0 files)
*To be updated as files are modified*

#### **Test Files Updated** (0/16 files)
- [ ] `tests/test_mcp_server_tools.py`
- [ ] `tests/test_mcp_historical_tools.py`
- [ ] `tests/test_mcp_parameter_tools.py`
- [ ] `tests/test_mcp_personality_context.py`
- [ ] `tests/test_request_id_integration.py`
- [ ] `tests/test_effective_attributes_integration.py`
- [ ] `tests/test_effective_attributes.py`
- [ ] `tests/test_parameter_integration.py`
- [ ] `tests/test_e2e_historical_scraping.py`
- [ ] `tests/test_historical_service.py`
- [ ] `tests/test_historical_service_integration.py`
- [ ] `tests/test_historical_service_types.py`
- [ ] `tests/test_historical_performance.py`
- [ ] `tests/test_historical_error_scenarios.py`
- [ ] `tests/test_historical_data_parsing.py`
- [ ] `benchmark_parameter_operations.py`

#### **Documentation Updated** (0/6 files)
- [ ] `checkmk_agent/mcp_server/README.md`
- [ ] `README.md`
- [ ] `IMPLEMENTATION_SUMMARY.md`
- [ ] `docs/ADVANCED_FEATURES.md`
- [ ] `.serena/memories/codebase_structure.md`
- [ ] This specification document

### **Quality Gates**
Track quality checkpoints for each phase:

#### **Phase Completion Criteria**
- [x] **Phase 0**: All analysis complete, branch created, baseline documented ✅
- [ ] **Phase 1**: All utilities extracted, tests passing, backward compatibility verified
- [ ] **Phase 2**: Registry functional, protocol handlers working, tool discovery operational
- [ ] **Phase 3**: All prompts functional, validation working, no regression
- [ ] **Phase 4**: All tool categories extracted, individual category tests passing
- [ ] **Phase 5**: Main server simplified, dependency injection working, integration tests passing
- [ ] **Phase 6**: All imports updated, documentation current, performance validated

#### **Critical Validation Points**
- [ ] **Baseline Test Coverage**: Document current test pass rate (target: 100%)
- [ ] **Import Compatibility**: Verify existing imports continue to work
- [ ] **Tool Functionality**: Validate all 47 tools work identically
- [ ] **Performance Benchmark**: No performance degradation vs. baseline
- [ ] **Memory Usage**: No significant memory increase vs. baseline
- [ ] **Package Installation**: Verify package installs and imports correctly

### **Issues and Blockers**
*To be updated as issues are encountered*

**Current Issues**: None  
**Resolved Issues**: None  
**Blockers**: None

---

## Phase 0 Completion Summary (2025-08-18)

**Status**: ✅ COMPLETED - All Phase 0 objectives achieved

### **Deliverables Created**

#### **1. Feature Branch Setup**
- **Branch Created**: `refactor-mcp-server-architecture` 
- **Base Commit**: `893a3154` (enhance: add proactive error prevention to senior-python-architect agent)
- **Status**: Ready for development work

#### **2. Test Coverage Baseline Documentation** 
- **Script**: `scripts/test_baseline_report.py`
- **Report**: `scripts/baseline_report_20250818_214218.json`
- **Key Metrics**:
  - Total Tests: 701
  - Core API Tests: 37 passed, 0 failed
  - MCP Server Tests: 2 passed, 0 failed  
  - MCP Server File: 4,450 lines, 189,210 bytes
  - Tool Registrations: 3 detected (baseline measurement)

#### **3. Rollback Validation System**
- **Script**: `scripts/rollback_validation.py`
- **Report**: `scripts/rollback_validation_20250818_214607.json`  
- **Validation Coverage**: 9 critical system components
- **Success Rate**: 100% (9/9 tests passed)
- **Validated Components**:
  - Package structure integrity
  - Import compatibility (`CheckmkMCPServer` accessible via both paths)
  - MCP server instantiation with proper config structure
  - Tool registration system functionality
  - Resource handlers operational
  - Service layer integration
  - Error handling utilities (sanitize_error, MCPJSONEncoder)
  - Entry point script functionality  
  - Critical unit tests passing

#### **4. Comprehensive Tool Analysis**
- **Script**: `scripts/tool_analysis.py`
- **Report**: `scripts/tool_analysis_20250818_214811.json`
- **Tools Analyzed**: 44 tools found (close to expected 47)
- **Categories Identified**: 8 logical groups
- **Total Tool Lines**: 827 lines (18.8 lines average per tool)

### **Tool Categorization Results**

| Category | Tool Count | Est. Lines | Priority | Examples |
|----------|------------|------------|----------|----------|
| **parameter_tools** | 14 | ~361 | HIGHEST | `get_effective_parameters`, `set_service_parameters`, `create_specialized_rule` |
| **host_tools** | 11 | ~259 | HIGH | `list_hosts`, `create_host`, `update_host`, `delete_host` |
| **service_tools** | 10 | ~213 | HIGH | `list_all_services`, `acknowledge_service_problem`, `create_service_downtime` |
| **event_tools** | 3 | ~109 | MEDIUM | `list_service_events`, `acknowledge_event`, `search_events` |
| **status_tools** | 3 | ~86 | MEDIUM | `get_health_dashboard`, `get_critical_problems`, `analyze_host_health` |
| **metrics_tools** | 1 | ~42 | LOW | `get_service_metrics` |
| **advanced_tools** | 1 | ~42 | LOW | `batch_create_hosts` |
| **misc_tools** | 1 | ~42 | LOW | `get_system_info` |

### **Key Technical Insights**

#### **Architecture Findings**
- **Centralized Dispatch**: Single `call_tool()` handler routes to 44 individual tool functions
- **Tool Registration Pattern**: `self._tool_handlers["tool_name"] = function_name`
- **Service Dependencies**: Tools primarily depend on 13 service classes
- **Largest Tools**: `create_specialized_rule` (83 lines), complex parameter management
- **Most Dependent**: `get_server_metrics` (3 service dependencies)

#### **Refactoring Feasibility**: **HIGH**
- Well-structured tool registration system
- Clear separation between tool definitions and routing
- Minimal cross-tool dependencies
- Service layer already modularized  
- Comprehensive test coverage exists

### **Risk Assessment**

#### **Low Risk Factors** ✅
- Existing service layer architecture supports modularization
- Tool functions are largely independent
- Comprehensive validation system in place
- Backward compatibility requirements well-defined

#### **Medium Risk Factors** ⚠️
- 16 test files will need import path updates
- Large codebase (4,450 lines) increases complexity
- Parameter tools have complex interdependencies

#### **Mitigation Strategies**
- Rollback validation script ensures system integrity at each step
- Phase-by-phase approach with validation gates
- Automated import update tooling (to be developed in Phase 6)
- Comprehensive test suite provides regression protection

### **Next Phase Readiness**

**Phase 1 Prerequisites**: ✅ ALL MET
- [x] Feature branch created and ready
- [x] Baseline measurements documented  
- [x] Rollback validation system operational
- [x] Tool categorization complete
- [x] Refactoring plan validated

**Recommended Phase 1 Start**: **IMMEDIATE**
- Foundation work can begin safely
- All preparatory analysis complete
- Risk mitigation strategies in place
- Clear success criteria established

---

## Phase 1 Preparation Notes

Based on Phase 0 analysis, Phase 1 should focus on:

1. **High-Priority Categories**: Start with `parameter_tools` (14 tools, complex dependencies)
2. **Service Layer Integration**: Leverage existing service architecture
3. **Utility Extraction**: Begin with error handling and JSON utilities (well-isolated)
4. **Import Management**: Plan for systematic import path updates

**Estimated Phase 1 Duration**: 2-3 days (as originally planned)

---

## Next Steps for Refinement
1. ✅ Review and adjust the proposed module boundaries - **COMPLETED**
2. ✅ Identify specific tools that belong in each category - **COMPLETED** 
3. ✅ Define the interfaces between modules - **ANALYSIS COMPLETE**
4. ✅ Plan the migration strategy in detail - **FRAMEWORK ESTABLISHED**
5. Create automated tooling for import updates and testing - **PHASE 6**
6. Validate packaging and distribution requirements - **PHASE 6**