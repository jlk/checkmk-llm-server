TITLE: Temperature Parameter Trending Control Refactoring
DATE: 2025-01-04
PARTICIPANTS: User (jlk), Claude Code, Senior Python Architect, Technical Doc Editor
SUMMARY: Refactored temperature parameter system from scattered filtering logic to clean Strategy Pattern architecture

INITIAL PROMPT: i want the app to not add temperature trending parameters unless the user specified or they were already present on a rule

KEY DECISIONS:
- Replaced scattered boolean filtering logic with Strategy Pattern implementation
- Created centralized ParameterPolicyManager for consistent parameter filtering
- Moved from include_trending boolean parameter to flexible context-based approach
- Deprecated old filtering methods while maintaining backward compatibility
- Implemented proper separation of concerns between policy logic and handler logic

FILES CHANGED:
- checkmk_agent/services/handlers/parameter_policies.py: New Strategy Pattern implementation with TrendingParameterFilter and ParameterPolicyManager
- checkmk_agent/services/handlers/base.py: Added policy management integration and apply_parameter_policies() method
- checkmk_agent/services/handlers/temperature.py: Refactored to use policy-based filtering, removed complex boolean logic
- checkmk_agent/services/parameter_service.py: Simplified interface, replaced include_trending with context parameter, deprecated old filtering method
- checkmk_agent/mcp_server/server.py: Updated tool schema to use context-based approach instead of boolean flags

ARCHITECTURAL IMPROVEMENTS:
- Strategy Pattern for extensible parameter filtering
- Single Responsibility Principle compliance
- Centralized policy management
- Context-driven parameter control
- Clean separation of business logic and infrastructure code
- Improved testability and maintainability

BUSINESS LOGIC:
- Default: trending parameters excluded unless explicitly requested
- Context {"include_trending": true} enables trending parameters
- Existing rules with trending parameters preserve them during updates
- Policy-based filtering applied consistently across all handlers