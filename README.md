# Checkmk LLM Agent

A Python agent that connects Large Language Models (Claude/ChatGPT) to Checkmk for easier configuration management through natural language interactions.

## Features

- 🤖 **Natural Language Interface**: Talk to Checkmk using plain English
- 🔧 **Host Management**: List, create, delete, and manage hosts
- 🌐 **Multiple LLM Support**: Works with OpenAI GPT and Anthropic Claude
- 📊 **Interactive CLI**: Command-line interface with both direct commands and interactive mode
- 🔒 **Secure**: Environment-based configuration with credential management
- 📈 **Comprehensive**: Full support for Checkmk REST API host operations

## Quick Start

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd checkmk_llm_agent
```

2. Set up Python virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Configure the application:
```bash
# Copy an example configuration file
cp config.yaml.example config.yaml
# Edit config.yaml with your Checkmk server details and API keys
```

> **Note**: Virtual environment is strongly recommended to avoid dependency conflicts. Always activate the virtual environment before running the application or tests.

### Configuration

The agent supports multiple configuration methods with flexible priority handling:

#### Configuration File Formats

Choose from **YAML** (recommended), **TOML**, or **JSON**:

```bash
# Copy and customize an example
cp config.yaml.example config.yaml
# OR
cp config.toml.example config.toml  
# OR
cp config.json.example config.json
```

**YAML Configuration (config.yaml):**
```yaml
checkmk:
  server_url: "https://your-checkmk-server.com"
  username: "automation_user" 
  password: "your_secure_password"
  site: "mysite"

llm:
  openai_api_key: "sk-your-openai-api-key"
  # OR anthropic_api_key: "your-anthropic-api-key"
  default_model: "gpt-3.5-turbo"

default_folder: "/"
log_level: "INFO"
```

#### Environment Variables (.env)

```env
# Checkmk Configuration
CHECKMK_SERVER_URL=https://your-checkmk-server.com
CHECKMK_USERNAME=your_username
CHECKMK_PASSWORD=your_password
CHECKMK_SITE=your_site

# LLM Configuration (choose one or both)
OPENAI_API_KEY=your_openai_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key

# Optional Configuration
DEFAULT_FOLDER=/
LOG_LEVEL=INFO
```

#### Configuration Priority

Configuration is loaded in this order (highest to lowest priority):

1. **Environment variables** (highest)
2. **Specified config file** (`--config path/to/config.yaml`)
3. **Auto-discovered config file** (current directory, user config directory)
4. **Default values** (lowest)

#### Auto-Discovery

The agent automatically finds configuration files in standard locations:
- Current directory: `config.yaml`, `config.yml`, `config.toml`, `config.json`
- User config: `~/.config/checkmk-agent/config.yaml`

See `examples/` directory for environment-specific configuration examples.

## Usage

### Command Line Interface

First, activate your virtual environment:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Test the connection:
```bash
python -m checkmk_agent.cli test
# OR with specific config file
python -m checkmk_agent.cli --config config.yaml test
```

Interactive mode:
```bash
python -m checkmk_agent.cli interactive
# OR with specific config
python -m checkmk_agent.cli --config examples/configs/production.yaml interactive
```

Direct host management:
```bash
# List hosts
python -m checkmk_agent.cli hosts list

# Create a host
python -m checkmk_agent.cli hosts create server01 --folder /web --ip 192.168.1.10

# Delete a host
python -m checkmk_agent.cli hosts delete server01

# Get host details
python -m checkmk_agent.cli hosts get server01

# Use specific configuration file
python -m checkmk_agent.cli --config examples/configs/development.yaml hosts list
```

### Interactive Mode Examples

Once in interactive mode, you can use natural language:

```
🔧 checkmk> list all hosts
Found 5 hosts:
- web01 (folder: /web)
- db01 (folder: /database)
- app01 (folder: /applications)

🔧 checkmk> create host server02 in folder /web with ip 192.168.1.20
Successfully created host: server02

🔧 checkmk> show details for web01
Host Details:
- Name: web01
- Folder: /web
- IP Address: 192.168.1.10
- Cluster: No
- Offline: No

🔧 checkmk> delete host server02
Host deleted successfully.
```

### Python API

You can also use the agent programmatically. First, ensure your virtual environment is activated:

```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Then use the agent in your Python code:

```python
from checkmk_agent.config import load_config
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.llm_client import create_llm_client
from checkmk_agent.host_operations import HostOperationsManager

# Load configuration
config = load_config()

# Initialize clients
checkmk_client = CheckmkClient(config.checkmk)
llm_client = create_llm_client(config.llm)

# Create host operations manager
host_manager = HostOperationsManager(checkmk_client, llm_client, config)

# Process natural language commands
result = host_manager.process_command("list all hosts")
print(result)
```

## Architecture

The agent consists of several key components:

- **CheckmkClient**: Handles all interactions with the Checkmk REST API
- **LLMClient**: Processes natural language using OpenAI or Anthropic APIs
- **HostOperationsManager**: Combines API and LLM functionality
- **CLI**: Command-line interface for user interaction

## API Coverage

Currently supports the following Checkmk host operations:

- ✅ List hosts (`GET /domain-types/host_config/collections/all`)
- ✅ Create host (`POST /domain-types/host_config/collections/all`)
- ✅ Delete host (`DELETE /objects/host_config/{host_name}`)
- ✅ Get host details (`GET /objects/host_config/{host_name}`)
- ✅ Update host (`PUT /objects/host_config/{host_name}`)
- ✅ Bulk create hosts
- ✅ Bulk delete hosts

## Development

### Setting Up Development Environment

1. Clone the repository and set up virtual environment:
```bash
git clone <repository-url>
cd checkmk_llm_agent
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install development dependencies:
```bash
pip install -r requirements.txt
```

3. Configure for development:
```bash
cp config.yaml.example config.yaml
# Edit config.yaml with your development settings
```

### Project Structure

```
checkmk_llm_agent/
├── checkmk_agent/
│   ├── __init__.py
│   ├── api_client.py          # Checkmk REST API client
│   ├── llm_client.py          # LLM integration
│   ├── host_operations.py     # Host operations logic
│   ├── cli.py                 # Command-line interface
│   ├── config.py              # Configuration management
│   └── utils.py               # Common utilities
├── tests/                     # Test suite (114 tests)
├── docs/                      # Documentation
├── examples/                  # Configuration examples
├── venv/                      # Virtual environment (created locally)
├── requirements.txt           # Python dependencies
├── setup.py                   # Package configuration
└── README.md
```

### Running Tests

Always activate the virtual environment first:
```bash
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

Run the full test suite (114 tests):
```bash
pytest tests/
```

Run specific test categories:
```bash
pytest tests/test_api_client.py     # API client tests
pytest tests/test_integration.py   # Integration tests
pytest tests/test_cli.py           # CLI tests
```

Run tests with coverage:
```bash
pytest tests/ --cov=checkmk_agent
```

### Code Formatting

```bash
black checkmk_agent/
flake8 checkmk_agent/
```

## Roadmap

Future enhancements planned:

- 🔄 Service management operations
- 📊 Rule and ruleset management
- 🚨 Problem acknowledgment and downtime management
- 📈 Business Intelligence operations
- 🔐 Enhanced authentication methods
- 🌐 Web interface
- 📊 Monitoring dashboards

## Troubleshooting

### Virtual Environment Issues

**Problem**: Command not found or import errors
```bash
# Solution: Ensure virtual environment is activated
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

**Problem**: Dependencies missing after installation
```bash
# Solution: Reinstall dependencies in virtual environment
source venv/bin/activate
pip install -r requirements.txt
```

**Problem**: Tests failing with import errors
```bash
# Solution: Run tests from project root with virtual environment activated
source venv/bin/activate
pytest tests/
```

**Problem**: Virtual environment not working on Windows
```bash
# Use Windows-specific activation script
venv\Scripts\activate
```

### Common Issues

**Problem**: Connection errors to Checkmk server
- Check your `config.yaml` file has correct server URL and credentials
- Verify the Checkmk server is accessible from your network
- Ensure the site name matches your Checkmk installation

**Problem**: LLM API errors
- Verify your OpenAI or Anthropic API keys are correct in configuration
- Check your API key has sufficient quota/credits
- Ensure you're using supported model names


## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions or issues:

1. Check the documentation
2. Review existing issues
3. Create a new issue with detailed information

## Security

This agent handles sensitive Checkmk credentials and API keys. Always:

- Use environment variables for credentials
- Never commit secrets to version control
- Use HTTPS for all API communications
- Follow the principle of least privilege for Checkmk user accounts