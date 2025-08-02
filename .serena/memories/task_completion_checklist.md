# Task Completion Checklist

## Code Quality Checks (Required)
When completing any coding task, run these commands in order:

### 1. Code Formatting
```bash
black checkmk_agent/ tests/
```
- Ensures consistent code formatting
- Must pass without errors

### 2. Linting
```bash
flake8 checkmk_agent/ tests/
```
- Checks for code quality issues
- Must resolve all violations

### 3. Type Checking
```bash
mypy checkmk_agent/
```
- Validates type annotations
- Must pass without type errors

### 4. Testing
```bash
# Run all tests
pytest tests/

# Run with coverage if significant changes
pytest tests/ --cov=checkmk_agent --cov-report=term-missing
```
- All tests must pass (100% pass rate expected)
- Coverage should remain high for new code

## Validation Scripts
```bash
# Validate parameter system (if parameter-related changes)
python validate_parameter_system.py

# Test new features (if applicable)
python test_new_features.py
```

## Documentation Updates
- Update docstrings for any new/modified public methods
- Update README.md if public interface changes
- Update CHANGELOG.md for significant changes
- Add conversation documentation if architectural decisions made

## Configuration Validation
```bash
# Test with example configuration
python -c "from checkmk_agent.config import load_config; load_config('config.yaml.example')"
```

## MCP Server Testing
If MCP-related changes:
```bash
# Start MCP server and verify it loads without errors
python mcp_checkmk_server.py --config config.yaml.example --test-mode

# Test MCP client connection
python checkmk_cli_mcp.py --config config.yaml.example test-connection
```

## Performance Checks
For performance-critical changes:
```bash
# Run benchmark if parameter operations modified
python benchmark_parameter_operations.py

# Run performance tests
pytest tests/test_performance.py
```

## Final Verification
```bash
# Complete validation sequence
black checkmk_agent/ tests/ && \
flake8 checkmk_agent/ tests/ && \
mypy checkmk_agent/ && \
pytest tests/ && \
echo "✅ All checks passed - ready for commit"
```

## Git Best Practices
- Ensure commit messages are descriptive
- Stage only relevant files
- Test the specific change made
- No sensitive data in commits

## Notes
- The project maintains 100% test pass rate - do not break this
- MCP server must load without errors
- All public APIs must have type hints and docstrings
- Follow existing code patterns and conventions
- Use environment variables for sensitive configuration