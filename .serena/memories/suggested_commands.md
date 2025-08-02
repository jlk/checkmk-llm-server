# Suggested Commands

## Development Setup
```bash
# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On macOS/Linux
# venv\Scripts\activate  # On Windows

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## Testing Commands
```bash
# Run all tests
pytest tests/

# Run specific test categories
pytest tests/ -m unit                    # Fast unit tests
pytest tests/ -m integration             # Integration tests
pytest tests/ -m slow                    # Slow running tests
pytest tests/ -m api                     # API interaction tests

# Run tests with coverage
pytest tests/ --cov=checkmk_agent --cov-report=html

# Run specific test files
pytest tests/test_api_client.py
pytest tests/test_mcp_server_tools.py
pytest tests/test_parameter_handlers.py

# Run tests in parallel (if pytest-xdist installed)
pytest tests/ -n auto
```

## Code Quality Commands
```bash
# Format code with Black
black checkmk_agent/ tests/

# Lint with flake8
flake8 checkmk_agent/ tests/

# Type checking with mypy
mypy checkmk_agent/

# Run all quality checks together
black checkmk_agent/ tests/ && flake8 checkmk_agent/ tests/ && mypy checkmk_agent/
```

## Application Entry Points

### MCP Server (Primary)
```bash
# Start MCP server (main entry point)
python mcp_checkmk_server.py --config config.yaml

# Start with debug logging
python mcp_checkmk_server.py --config config.yaml --log-level DEBUG
```

### CLI Interfaces
```bash
# MCP-based CLI (recommended)
python checkmk_cli_mcp.py interactive
python checkmk_cli_mcp.py hosts list
python checkmk_cli_mcp.py status overview

# Direct CLI (legacy)
python -m checkmk_agent.cli interactive
python -m checkmk_agent.cli hosts list
python -m checkmk_agent.cli status overview

# With specific configuration
python checkmk_cli_mcp.py --config /path/to/config.yaml hosts list
```

## Validation and Testing
```bash
# Validate the entire implementation
python validate_parameter_system.py

# Test specific features
python test_new_features.py
python test_status_demo.py

# Benchmark parameter operations
python benchmark_parameter_operations.py
```

## macOS-Specific Utilities
```bash
# macOS equivalents of common commands
ls -la                    # List files with details
find . -name "*.py"       # Find Python files
grep -r "pattern" .       # Search for patterns
cd /path/to/directory     # Change directory
cp file1 file2           # Copy files
mv file1 file2           # Move/rename files
rm file                  # Remove files
mkdir directory          # Create directory
```

## Git Operations
```bash
# Common git operations
git status               # Check working tree status
git add .               # Stage all changes
git commit -m "message" # Commit changes
git push                # Push to remote
git pull                # Pull latest changes
git log --oneline       # View commit history
```

## Configuration Management
```bash
# Copy example configuration
cp config.yaml.example config.yaml
cp examples/configs/development.yaml config.yaml

# Validate configuration
python -c "from checkmk_agent.config import load_config; print('Config valid:', load_config('config.yaml'))"
```