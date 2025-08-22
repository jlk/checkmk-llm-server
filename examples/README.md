# Configuration Examples

This directory contains example configuration files for different environments and use cases.

## ⚡ Quick Start: Choose ONE Configuration Method

**Stop here and choose your approach - using both creates unnecessary complexity.**

### 🔧 YAML Configuration (Choose this if you're unsure)
```bash
cp examples/configs/development.yaml config.yaml
# Edit config.yaml with your settings
python mcp_checkmk_server.py --config config.yaml
```

**Best for**: New users, development, complex setups requiring advanced features

### ⚙️ Environment Variables (Choose this for production)
```bash
cp .env.example .env
# Edit .env with your settings  
python mcp_checkmk_server.py
```

**Best for**: Docker deployments, CI/CD pipelines, production with secret management

### ❌ Don't Do This
- Don't use both YAML and environment variables together (unless you specifically need overrides)
- Don't commit real credentials to version control
- Don't mix configuration approaches across your team

## Environment-Specific Configurations

### Development (`configs/development.yaml`)
- Local Checkmk server
- Debug logging
- Faster, cheaper LLM models
- Shorter timeouts for quick feedback

### Production (`configs/production.yaml`)
- Production Checkmk server
- Environment variables for secrets
- Robust retry and timeout settings
- Warning-level logging

### Testing (`configs/testing.yaml`)
- Test environment settings
- Minimal timeouts for fast tests
- Error-only logging

## Configuration Priority

The agent loads configuration in this priority order (highest to lowest):

1. **Environment variables** (highest priority)
2. **Specified config file** (`--config path/to/config.yaml`)
3. **Auto-discovered config file** (see search paths below)
4. **Default values** (lowest priority)

## Auto-Discovery Search Paths

The agent automatically searches for configuration files in these locations:

1. **Current directory**:
   - `config.yaml`, `config.yml`, `config.toml`, `config.json`
   - `.checkmk-agent.yaml`, `.checkmk-agent.yml`, `.checkmk-agent.toml`, `.checkmk-agent.json`

2. **User config directory**:
   - `~/.config/checkmk-agent/config.yaml`
   - `~/.config/checkmk-agent/config.yml`
   - `~/.config/checkmk-agent/config.toml`
   - `~/.config/checkmk-agent/config.json`

## Implementation Examples

Once you've chosen your method, here's how to implement it:

### YAML Configuration Implementation
```bash
# 1. Copy and customize
cp examples/configs/development.yaml config.yaml
vi config.yaml  # Edit your settings

# 2. Run (explicit config file)
python mcp_checkmk_server.py --config config.yaml

# 3. Or run (auto-discovery from current directory)
python mcp_checkmk_server.py
```

### Environment Variables Implementation
```bash
# Option A: Use .env file
cp .env.example .env
vi .env  # Edit your settings
python mcp_checkmk_server.py

# Option B: Set directly in shell (containers/CI/CD)
export CHECKMK_SERVER_URL="https://your-server.com"
export CHECKMK_USERNAME="automation_user"
export CHECKMK_PASSWORD="your_password"
export CHECKMK_SITE="production"
python mcp_checkmk_server.py
```

## Security Best Practices

1. **Never commit secrets**: Use `.gitignore` to exclude actual config files with secrets
2. **Use environment variables**: For production deployments, use environment variables for sensitive data
3. **File permissions**: Restrict access to config files containing credentials
4. **Template approach**: Commit `.example` files, create actual configs locally

## Quick Start Guide

### Option 1: YAML Configuration (Most Users)
```bash
# Copy example and edit
cp examples/configs/development.yaml config.yaml
editor config.yaml

# Test configuration
python -c "
from checkmk_agent.config import load_config
from checkmk_agent.api_client import CheckmkAPIClient
config = load_config('config.yaml')
client = CheckmkAPIClient(config)
print('✅ YAML Configuration test:', client.get_version())
"
```

### Option 2: Environment Variables (Production/Containers)
```bash
# Copy example and edit
cp .env.example .env
editor .env

# Test configuration
source .env
python -c "
from checkmk_agent.config import load_config
from checkmk_agent.api_client import CheckmkAPIClient
config = load_config()  # Auto-loads from environment
client = CheckmkAPIClient(config)
print('✅ Environment Configuration test:', client.get_version())
"
```

## Quick Decision Tree

| Your Situation | Recommended Method | Why |
|----------------|-------------------|-----|
| 🆕 New to this project | YAML Configuration | Easier to understand and modify |
| 🐳 Using Docker/containers | Environment Variables | Better for container environments |
| ⚙️ Need advanced features | YAML Configuration | Environment variables only support basic settings |
| 🔒 Using secret management | Environment Variables | Integrates with external secret systems |
| 👥 Team development | YAML Configuration | Easier to share and document |
| 🚀 Production deployment | Environment Variables | Better security and deployment practices |

**Still unsure?** Start with YAML Configuration - you can always switch later.