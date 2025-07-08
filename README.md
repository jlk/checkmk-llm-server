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

2. Install dependencies:
```bash
pip install -r requirements.txt
# Or install with specific LLM support
pip install -e ".[openai]"  # For OpenAI support
pip install -e ".[anthropic]"  # For Anthropic support
pip install -e ".[all]"  # For both
```

3. Configure environment variables:
```bash
cp .env.example .env
# Edit .env with your credentials
```

### Configuration

Set up your `.env` file with the required credentials:

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

## Usage

### Command Line Interface

Test the connection:
```bash
python -m checkmk_agent.cli test
```

Interactive mode:
```bash
python -m checkmk_agent.cli interactive
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

You can also use the agent programmatically:

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
├── tests/
├── docs/
├── requirements.txt
├── setup.py
└── README.md
```

### Running Tests

```bash
pytest tests/
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

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

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