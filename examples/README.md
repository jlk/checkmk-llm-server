# Configuration Examples

This directory contains example configuration files for different environments and use cases.

## Configuration File Formats

The Checkmk LLM Agent supports multiple configuration file formats:

### YAML (Recommended)
- **Files**: `config.yaml`, `config.yml`
- **Example**: `config.yaml.example`
- **Best for**: Human-readable configuration, comments, complex nested structures

### TOML
- **Files**: `config.toml`
- **Example**: `config.toml.example`
- **Best for**: Python projects, simple key-value pairs

### JSON
- **Files**: `config.json`
- **Example**: `config.json.example`
- **Best for**: Programmatic configuration, CI/CD systems

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

## Usage Examples

### Using a specific config file:
```bash
# YAML config
checkmk-agent --config configs/production.yaml hosts list

# TOML config
checkmk-agent --config config.toml test

# JSON config
checkmk-agent --config config.json interactive
```

### Auto-discovery (place config.yaml in current directory):
```bash
checkmk-agent hosts list
```

### Environment variables override:
```bash
export CHECKMK_SERVER_URL="https://override-server.com"
checkmk-agent --config production.yaml hosts list
# Will use override-server.com instead of the URL in production.yaml
```

## Security Best Practices

1. **Never commit secrets**: Use `.gitignore` to exclude actual config files with secrets
2. **Use environment variables**: For production deployments, use environment variables for sensitive data
3. **File permissions**: Restrict access to config files containing credentials
4. **Template approach**: Commit `.example` files, create actual configs locally

## Creating Your Configuration

1. Copy an example file:
   ```bash
   cp config.yaml.example config.yaml
   ```

2. Edit with your settings:
   ```bash
   editor config.yaml
   ```

3. Test the configuration:
   ```bash
   checkmk-agent test
   ```