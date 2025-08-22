# Fix Interactive Mode "List Hosts" Bug

## Problem Description

When a syntax error occurs in interactive mode, the system incorrectly runs "list hosts" instead of just displaying an error message. This creates a confusing user experience where malformed commands trigger unintended operations.

## Root Cause Analysis

### 1. LLM Client Fallback Logic (`llm_client.py:302`)
Both OpenAI and Anthropic clients have a `_fallback_parse()` method that defaults to `HostOperation.LIST` when parsing fails:

```python
def _fallback_parse(self, user_input: str) -> ParsedCommand:
    """Fallback parsing using simple keyword matching."""
    # ... keyword matching logic ...
    
    # Default to list - THIS IS THE PROBLEM
    return ParsedCommand(HostOperation.LIST, {}, 0.5, user_input)
```

### 2. Error Handling Flow (`host_operations.py:41`)
When exceptions occur during command processing, the error handler still uses `HostOperation.LIST` for formatting:

```python
except Exception as e:
    self.logger.error(f"Command processing failed: {e}")
    return self.llm.format_response(
        HostOperation.LIST,  # Default operation for error formatting
        None,
        success=False,
        error=str(e)
    )
```

### 3. Interactive Mode Processing (`cli.py:148`)
The CLI processes even malformed commands through the operation managers without additional validation.

## Solution Plan

### Step 1: Add SYNTAX_ERROR Operation Type
Add a new operation type to handle syntax errors without executing commands:

**File**: `checkmk_mcp_server/llm_client.py`
- Add `SYNTAX_ERROR = "syntax_error"` to `HostOperation` enum
- Update `ParsedCommand` class to handle syntax errors appropriately

### Step 2: Fix LLM Client Fallback Logic
Modify both OpenAI and Anthropic clients' `_fallback_parse()` methods:

**File**: `checkmk_mcp_server/llm_client.py`
- Change default fallback from `HostOperation.LIST` to `HostOperation.SYNTAX_ERROR`
- Add better detection for truly unrecognized commands
- Preserve current keyword matching for valid commands

### Step 3: Update Error Handling in Operations Managers
Prevent execution of operations when syntax errors occur:

**Files**: 
- `checkmk_mcp_server/host_operations.py`
- `checkmk_mcp_server/service_operations.py`

- Update `_execute_operation()` to handle `SYNTAX_ERROR` operations
- Modify exception handling to not default to `LIST` operation
- Add specific error messages for syntax errors

### Step 4: Improve Interactive Mode Error Display
Better error handling in CLI interactive mode:

**File**: `checkmk_mcp_server/cli.py`
- Add validation before passing commands to operation managers
- Improve error message display for syntax errors

## Implementation Details

### 1. HostOperation Enum Update
```python
class HostOperation(Enum):
    """Supported operations."""
    LIST = "list"
    CREATE = "create"
    DELETE = "delete"
    GET = "get"
    UPDATE = "update"
    SYNTAX_ERROR = "syntax_error"  # NEW
    # ... other operations
```

### 2. Updated Fallback Logic
```python
def _fallback_parse(self, user_input: str) -> ParsedCommand:
    """Fallback parsing using simple keyword matching."""
    user_input_lower = user_input.lower()
    
    # Existing keyword matching logic for valid commands
    if "list" in user_input_lower or "show" in user_input_lower:
        return ParsedCommand(HostOperation.LIST, {}, 0.6, user_input)
    elif "create" in user_input_lower or "add" in user_input_lower:
        # ... existing create logic
    elif "delete" in user_input_lower or "remove" in user_input_lower:
        # ... existing delete logic
    
    # Default to syntax error instead of LIST
    return ParsedCommand(HostOperation.SYNTAX_ERROR, {}, 0.1, user_input)
```

### 3. Updated Error Handling
```python
def _execute_operation(self, command: ParsedCommand) -> Any:
    """Execute the parsed command operation."""
    if command.operation == HostOperation.SYNTAX_ERROR:
        raise ValueError(f"Unrecognized command: {command.raw_text}")
    elif command.operation == HostOperation.LIST:
        return self._list_hosts(command.parameters)
    # ... other operations
```

## Expected Outcomes

1. **Syntax errors display appropriate error messages** without executing any commands
2. **Valid commands continue to work** as expected with proper keyword matching
3. **Interactive mode provides better user experience** with clear error feedback
4. **No unintended command execution** when users make typos or syntax errors

## Testing Requirements

1. Test syntax error handling with malformed commands
2. Verify valid commands still work correctly
3. Test both OpenAI and Anthropic LLM clients
4. Test both host and service operations
5. Test interactive mode error display

## Files to Modify

- `/Users/jlk/code-local/checkmk_llm_agent/checkmk_mcp_server/llm_client.py`
- `/Users/jlk/code-local/checkmk_llm_agent/checkmk_mcp_server/host_operations.py`
- `/Users/jlk/code-local/checkmk_llm_agent/checkmk_mcp_server/service_operations.py`
- `/Users/jlk/code-local/checkmk_llm_agent/checkmk_mcp_server/cli.py` (optional improvements)

## Priority

**High** - This bug affects user experience and creates confusion in interactive mode.

## Implementation Status

✅ **COMPLETED** - All implementation steps have been completed successfully:

1. ✅ Added `SYNTAX_ERROR` operation type to `HostOperation` enum
2. ✅ Updated OpenAI client `_fallback_parse()` method to return `SYNTAX_ERROR` instead of `LIST`
3. ✅ Updated Anthropic client `_fallback_parse()` method to return `SYNTAX_ERROR` instead of `LIST`
4. ✅ Updated `host_operations.py` to handle `SYNTAX_ERROR` operations appropriately
5. ✅ Updated error handling in `host_operations.py` to avoid triggering unintended operations
6. ✅ Verified `service_operations.py` already has proper error handling
7. ✅ Added comprehensive tests to verify the fix works correctly
8. ✅ Updated existing tests to match new error handling behavior

## Testing Results

- All LLM client tests pass (26/26)
- All host operations tests pass (30/30) 
- All service operations tests pass (17/17)
- New syntax error test confirms proper behavior
- Fallback parsing now correctly returns `SYNTAX_ERROR` for unrecognized commands
- Error handling no longer triggers unintended "list hosts" operations

## Files Modified

- ✅ `/Users/jlk/code-local/checkmk_llm_agent/checkmk_mcp_server/llm_client.py` - Added SYNTAX_ERROR enum and updated fallback logic
- ✅ `/Users/jlk/code-local/checkmk_llm_agent/checkmk_mcp_server/host_operations.py` - Added SYNTAX_ERROR handling and improved error messages
- ✅ `/Users/jlk/code-local/checkmk_llm_agent/tests/test_host_operations.py` - Updated and added tests for new behavior

The fix ensures that syntax errors in interactive mode display appropriate error messages without executing any unintended commands like "list hosts".