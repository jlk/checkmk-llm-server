# Checkmk LLM Agent

A Python agent that connects Large Language Models (Claude/ChatGPT) to Checkmk for easier configuration management through natural language interactions.

## What Can It Do?

| Operation                     | CLI Command                                                   | Natural Language Example                              |
| ----------------------------- | ------------------------------------------------------------- | ----------------------------------------------------- |
| **Host Management**           | `hosts list`                                                  | `"list all hosts"`                                    |
| **Host Search**               | `hosts list --search piaware`                                 | `"show hosts like piaware"`                           |
| **Service Status Monitoring** | `status overview`                                             | `"show health dashboard"`                             |
| **Problem Analysis**          | `status problems`, `status critical`                         | `"show critical problems"`, `"list warning issues"`  |
| **Service Monitoring**        | `services list server01`                                      | `"show services for server01"`                        |
| **Service Parameters**        | `services params set server01 "CPU utilization" --warning 85` | `"set CPU warning to 85% for server01"`               |
| **Problem Management**        | `services acknowledge server01 "CPU utilization"`             | `"acknowledge CPU load on server01"`                  |
| **Downtime Scheduling**       | `services downtime server01 "disk space" --hours 4`           | `"create 4 hour downtime for disk space on server01"` |
| **Rule Management**           | `rules create filesystem --folder /web`                       | `"create filesystem rule for web servers"`            |
| **Discovery**                 | `services discover server01`                                  | `"discover services on server01"`                     |

## Features

- 🤖 **Natural Language Interface**: Talk to Checkmk using plain English
- 📊 **Service Status Monitoring**: Real-time health dashboards with color-coded indicators
- 🎯 **Problem Analysis**: Intelligent categorization and urgency scoring of service issues
- 🔧 **Host Management**: List, create, delete, and manage hosts
- 🚀 **Service Operations**: Monitor, acknowledge, and manage service status
- ⚙️ **Service Parameters**: Override thresholds and configure service monitoring
- 📊 **Rule Management**: Create, modify, and delete Checkmk rules
- 🌐 **Multiple LLM Support**: Works with OpenAI GPT and Anthropic Claude
- 📊 **Enhanced Interactive Mode**: Rich CLI with help system, command history, and tab completion
- 🎨 **Rich UI**: Progress bars, health indicators, and color themes
- 🔒 **Secure**: Environment-based configuration with credential management
- 📈 **Comprehensive**: Full support for Checkmk REST API operations

### Interactive Mode Features
- **Enhanced Help System**: Type `?` for contextual help on all commands
- **Command History**: Persistent command history with Up/Down arrow navigation
- **Tab Completion**: Intelligent auto-completion for commands, hosts, and services
- **Fuzzy Matching**: Automatic correction of typos in commands
- **Rich Output**: Colored, formatted output with icons and clear status indicators
- **Natural Language Processing**: Improved understanding of natural language commands
- **Smart Search**: Natural language search with patterns like "hosts like piaware", "find hosts containing web"

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
```

Service status monitoring:
```bash
# Service health dashboard
python -m checkmk_agent.cli status overview

# View critical services only
python -m checkmk_agent.cli status critical

# Show all service problems  
python -m checkmk_agent.cli status problems

# Show acknowledged services
python -m checkmk_agent.cli status acknowledged

# Service status for specific host
python -m checkmk_agent.cli status host server01

# Detailed service status
python -m checkmk_agent.cli status service server01 "CPU utilization"
```

Service operations:
```bash
# List services
python -m checkmk_agent.cli services list server01

# Get service status
python -m checkmk_agent.cli services status server01 "CPU utilization"

# Acknowledge service problems
python -m checkmk_agent.cli services acknowledge server01 "CPU utilization" --comment "Working on it"

# Create service downtime
python -m checkmk_agent.cli services downtime server01 "CPU utilization" --hours 2

# Service parameter management
python -m checkmk_agent.cli services params defaults cpu
python -m checkmk_agent.cli services params show server01 "CPU utilization"
python -m checkmk_agent.cli services params set server01 "CPU utilization" --warning 85 --critical 95
```

Rule management:
```bash
# List rules
python -m checkmk_agent.cli rules list

# Create a rule
python -m checkmk_agent.cli rules create filesystem --folder /web --comment "Web server rules"

# Delete a rule
python -m checkmk_agent.cli rules delete rule_id_123
```

### Enhanced Interactive Mode

The interactive mode now features enhanced usability with:

- **Enhanced Help System**: Type `?` for help, `? <command>` for specific help
- **Command History**: Use Up/Down arrows to navigate previous commands
- **Tab Completion**: Press Tab to autocomplete commands and parameters
- **Fuzzy Matching**: Commands with typos are automatically corrected
- **Rich Output**: Colored output and improved formatting

```
🔧 checkmk> ?
🔧 Checkmk LLM Agent - Interactive Mode
==================================================

🆘 Getting Help:
  • ?                    - Show this help
  • ? <command>          - Show help for specific command
  • Tab                  - Auto-complete commands
  • Up/Down arrows       - Navigate command history

🔧 checkmk> ? hosts
🔧 Host Management Commands
==================================================

📝 Description:
Commands for managing Checkmk hosts

💡 Examples:
  🔧 checkmk> list all hosts
  🔧 checkmk> create host server01 in folder /web with ip 192.168.1.10
  🔧 checkmk> delete host server01

🔧 checkmk> list all hosts
📦 Found 5 hosts:

  📦 web01
     📁 Folder: /web
     🌐 IP: 192.168.1.10

  📦 db01
     📁 Folder: /database
     🌐 IP: 192.168.1.20

🔧 checkmk> create host server02 in folder /web with ip 192.168.1.20
✅ Successfully created host: server02

🔧 checkmk> show hosts like piaware  # Smart search
📦 Found 1 host:

  📦 piaware-01
     📁 Folder: /network
     🌐 IP: 192.168.1.50

🔧 checkmk> find hosts containing web  # Natural language search
📦 Found 3 hosts:

  📦 web01
     📁 Folder: /web
     🌐 IP: 192.168.1.10

  📦 web02
     📁 Folder: /web
     🌐 IP: 192.168.1.11

🔧 checkmk> lst hsts  # Typo gets corrected
📦 Found 6 hosts:
...
```

**Service Status Monitoring:**
```
🔧 checkmk> show health dashboard
📊 Service Health Dashboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🟢 Overall Health: 92.5% [██████████████████░░]
📈 Total Services: 200
✅ No problems detected!

📊 Service States:
  ✅ OK: 185 services
  ⚠️  WARNING: 12 services
  ❌ CRITICAL: 3 services

🔧 checkmk> show critical problems
🔴 Critical Services (3):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

❌ web01/Database Connection
❌ app02/Memory Usage
❌ db01/Disk Space /var

🔧 checkmk> show warning issues
🟡 Warning Services (5):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚠️  web01/CPU utilization
⚠️  app01/Memory Usage
⚠️  web02/Load Average
⚠️  db01/Connections
⚠️  mail01/Queue Size

🔧 checkmk> health overview
🟢 Overall Health: 92.5%
📈 Total Services: 200 
🚨 3 urgent problem(s) require immediate attention
💡 15 unacknowledged problem(s) need review
```

**Service Operations:**
```
🔧 checkmk> list services for web01
Found 12 services for web01:
- CPU utilization (OK)
- Memory (OK)
- Filesystem / (WARNING)
- Network Interface eth0 (OK)

🔧 checkmk> acknowledge CPU load on web01
✅ Acknowledged CPU load on web01
💬 Comment: Working on it

🔧 checkmk> create 4 hour downtime for disk space on web01
✅ Created 4 hour downtime for Filesystem / on web01
⏰ Downtime period: 2024-01-15 14:00 - 18:00
```

**Service Parameter Management:**
```
🔧 checkmk> show default CPU parameters
📊 Default Parameters for CPU services:
⚠️  Warning Threshold: 80.0%
❌ Critical Threshold: 90.0%
📈 Averaging Period: 15 minutes

🔧 checkmk> set CPU warning to 85% for web01
✅ Created parameter override for web01/CPU utilization
⚠️  Warning: 85.0%
❌ Critical: 90.0%
🆔 Rule ID: rule_abc123

🔧 checkmk> what are the memory thresholds for web01?
📊 Effective Parameters for web01/Memory:
⚠️  Warning: 80.0%
❌ Critical: 90.0%
📋 Using default parameters (no custom rules found)
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
from checkmk_agent.service_operations import ServiceOperationsManager
from checkmk_agent.service_parameters import ServiceParameterManager
from checkmk_agent.service_status import ServiceStatusManager

# Load configuration
config = load_config()

# Initialize clients
checkmk_client = CheckmkClient(config.checkmk)
llm_client = create_llm_client(config.llm)

# Create operations managers
host_manager = HostOperationsManager(checkmk_client, llm_client, config)
service_manager = ServiceOperationsManager(checkmk_client, llm_client, config)
parameter_manager = ServiceParameterManager(checkmk_client, config)
status_manager = ServiceStatusManager(checkmk_client, config)

# Process natural language commands
result = host_manager.process_command("list all hosts")
service_result = service_manager.process_command("list services for web01")
param_result = parameter_manager.get_default_parameters("cpu")

# Service status monitoring
health_dashboard = status_manager.get_service_health_dashboard()
status_summary = status_manager.generate_status_summary()
problem_analysis = status_manager.analyze_service_problems()

print(result)
print(service_result)
print(param_result)
print(f"Health: {status_summary['health_percentage']}%")
print(f"Problems: {status_summary['problems']}")
```

## Architecture

The agent consists of several key components:

- **CheckmkClient**: Handles all interactions with the Checkmk REST API
- **LLMClient**: Processes natural language using OpenAI or Anthropic APIs
- **HostOperationsManager**: Host management operations with natural language processing
- **ServiceOperationsManager**: Service monitoring, acknowledgment, and downtime management
- **ServiceStatusManager**: Real-time service status monitoring and health dashboards
- **ServiceParameterManager**: Service parameter and threshold management
- **RuleOperationsManager**: Checkmk rule creation and management
- **CLI**: Command-line interface for user interaction
- **Interactive UI**: Enhanced interactive mode with rich formatting and status visualization

## API Coverage

Currently supports the following Checkmk operations:

### Host Operations
- ✅ List hosts (`GET /domain-types/host_config/collections/all`)
- ✅ Create host (`POST /domain-types/host_config/collections/all`)
- ✅ Delete host (`DELETE /objects/host_config/{host_name}`)
- ✅ Get host details (`GET /objects/host_config/{host_name}`)
- ✅ Update host (`PUT /objects/host_config/{host_name}`)
- ✅ Bulk create hosts
- ✅ Bulk delete hosts

### Service Operations
- ✅ List services (`GET /domain-types/service/collections/all`)
- ✅ Get service status and details
- ✅ Acknowledge service problems (`POST /domain-types/acknowledge/collections/service`)
- ✅ Create service downtime (`POST /domain-types/downtime/collections/service`)
- ✅ Service discovery (`POST /objects/host/{host_name}/actions/discover_services`)
- ✅ Service statistics and monitoring

### Service Status Monitoring
- ✅ Real-time health dashboards with service state distribution
- ✅ Problem analysis with severity categorization and urgency scoring
- ✅ Service health percentage calculations
- ✅ Critical, warning, and unknown service identification
- ✅ Acknowledged and downtime service tracking
- ✅ Livestatus query integration for advanced filtering
- ✅ Rich UI formatting with color-coded status indicators
- ✅ Natural language status queries

### Rule Management
- ✅ List rules (`GET /domain-types/rule/collections/all`)
- ✅ Create rules (`POST /domain-types/rule/collections/all`)
- ✅ Delete rules (`DELETE /objects/rule/{rule_id}`)
- ✅ Get rule details (`GET /objects/rule/{rule_id}`)
- ✅ List rulesets (`GET /domain-types/ruleset/collections/all`)

### Service Parameter Management
- ✅ View default service parameters for CPU, memory, disk, network
- ✅ Override service parameters for specific hosts
- ✅ Create parameter rules with custom thresholds
- ✅ Discover appropriate rulesets for services
- ✅ Rule precedence analysis and validation

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
│   ├── api_client.py          # Checkmk REST API client with status methods
│   ├── llm_client.py          # LLM integration
│   ├── host_operations.py     # Host operations logic
│   ├── service_operations.py  # Service operations logic
│   ├── service_status.py      # Service status monitoring and health dashboards
│   ├── service_parameters.py  # Service parameter management
│   ├── rule_operations.py     # Rule management operations
│   ├── cli.py                 # Command-line interface with status commands
│   ├── config.py              # Configuration management
│   ├── logging_utils.py       # Logging utilities
│   ├── utils.py               # Common utilities
│   └── interactive/           # Enhanced interactive mode
│       ├── __init__.py
│       ├── color_manager.py   # Color theme management
│       ├── command_parser.py  # Enhanced command parsing with status routing
│       ├── help_system.py     # Contextual help system
│       ├── readline_handler.py # Command history and completion
│       ├── tab_completer.py   # Tab completion functionality
│       └── ui_manager.py      # Rich UI formatting with status indicators
├── tests/                     # Test suite (212+ tests)
│   ├── test_service_status.py # Service status monitoring tests
│   └── test_api_client_status.py # API client status method tests
├── docs/                      # Documentation
├── examples/                  # Configuration examples
├── specs/                     # Technical specifications
├── tasks/                     # Project-specific task tracking
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

Run the full test suite (212+ tests):
```bash
pytest tests/
```

Run specific test categories:
```bash
pytest tests/test_api_client.py              # API client tests
pytest tests/test_api_client_status.py       # API client status method tests
pytest tests/test_service_status.py          # Service status monitoring tests
pytest tests/test_host_operations.py         # Host operation tests
pytest tests/test_service_operations.py      # Service operation tests
pytest tests/test_service_parameters.py      # Service parameter tests
pytest tests/test_service_parameters_integration.py  # Integration tests
pytest tests/test_integration.py            # General integration tests
pytest tests/test_cli.py                    # CLI tests
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

## Documentation

Comprehensive documentation is available in the `docs/` directory:

- **[Service Parameter Management](docs/service-parameter-management.md)** - Complete guide to managing service thresholds and parameters
- **[Technical Specifications](specs/add-service-modification-functionality.md)** - Detailed implementation specifications
- **[Configuration Examples](examples/)** - Environment-specific configuration templates
- **[Service Parameter Templates](examples/service_parameter_templates.yaml)** - Pre-defined parameter configurations

### Key Documentation Highlights:

- **CLI Reference**: Complete command reference with examples
- **Natural Language Guide**: Supported command patterns and examples
- **Best Practices**: Recommended approaches for different environments
- **Troubleshooting**: Common issues and solutions
- **API Integration**: How to use the Python API programmatically

## Roadmap

Future enhancements planned:

- 📈 Business Intelligence operations
- 🔐 Enhanced authentication methods
- 🌐 Web interface
- 📊 Monitoring dashboards
- 🔄 Service discovery automation
- 📊 Advanced analytics and reporting
- 🔗 External integrations (Slack, Teams, etc.)
- 🎯 Machine learning for anomaly detection

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

**Problem**: Service parameter commands not working
- Ensure you have proper Checkmk permissions (`wato.rulesets`, `wato.edit`)
- Check that the service exists on the specified host
- Verify the service name matches exactly (case-sensitive)
- Use `services params discover` to find the correct ruleset

**Problem**: Parameter overrides not taking effect
- Check that the rule was created successfully (`services params show`)
- Verify the rule has higher precedence than existing rules
- Ensure Checkmk configuration changes were activated
- Wait for the next service check cycle (typically 1-5 minutes)


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