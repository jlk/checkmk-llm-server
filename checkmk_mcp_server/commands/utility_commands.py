"""Utility command implementations."""

import logging
from typing import Dict, Any

from .base import BaseCommand, CommandContext, CommandResult, CommandCategory
from ..api_client import CheckmkClient, CheckmkAPIError


class UtilityCommand(BaseCommand):
    """Base class for utility commands."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)

    @property
    def category(self) -> CommandCategory:
        return CommandCategory.UTILITY


class GetInstructionsCommand(UtilityCommand):
    """Command to get instructions for service operations."""

    @property
    def name(self) -> str:
        return "get_instructions"

    @property
    def description(self) -> str:
        return "Get instructions on how to perform service operations"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "instruction_type": {
                "type": str,
                "required": False,
                "description": "Type of instruction to get (add_service, acknowledge_service, create_downtime)",
            },
            "host_name": {
                "type": str,
                "required": False,
                "description": "Hostname for context-specific instructions",
            },
        }

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the get instructions command."""
        instruction_type = context.get_parameter("instruction_type", "")
        host_name = context.get_parameter("host_name", "")

        if instruction_type == "add_service":
            message = f"""📖 How to add a service to {host_name if host_name else 'a host'}:

**Method 1: Service Discovery (Recommended)**
1. Run service discovery to automatically detect services:
   • CLI: `checkmk-mcp-server services discover {host_name if host_name else 'HOSTNAME'}`
   • Interactive: "discover services on {host_name if host_name else 'HOSTNAME'}"

2. Service discovery will:
   • Scan the host for available services
   • Show new services that can be added
   • Show vanished services that can be removed
   • Allow you to accept the changes

**Method 2: Manual Configuration**
1. Log into Checkmk web interface
2. Go to Setup → Hosts → {host_name if host_name else 'HOSTNAME'}
3. Click "Services" tab
4. Use "Service discovery" or manually configure services

**Method 3: Via Checkmk Rules**
1. Create rules in Setup → Services → Service monitoring rules
2. Rules automatically apply to matching hosts

**Next Steps:**
• Run: `checkmk-mcp-server services discover {host_name if host_name else 'HOSTNAME'}` to start
• Or ask: "discover services on {host_name if host_name else 'HOSTNAME'}" for automatic discovery"""

        elif instruction_type == "acknowledge_service":
            message = """📖 How to acknowledge a service problem:

**Purpose:** Acknowledging a service tells Checkmk that you're aware of the problem and working on it.

**Methods:**
1. **CLI Command:**
   `checkmk-mcp-server services acknowledge HOSTNAME SERVICE_NAME "Your comment"`

2. **Interactive Command:**
   "acknowledge SERVICE_NAME on HOSTNAME with comment 'Working on it'"

3. **Examples:**
   • "acknowledge CPU load on server01"
   • "ack disk space on web-server with comment 'Maintenance scheduled'"

**What happens:**
• Service problem is marked as acknowledged
• Notifications for this service are suppressed
• Your comment is logged for reference
• Problem remains until service returns to OK state

**Options:**
• Sticky: Acknowledgment persists until service is OK (default)
• Send notifications: Notify contacts about the acknowledgment"""

        elif instruction_type == "create_downtime":
            message = """📖 How to schedule service downtime:

**Purpose:** Schedule planned maintenance windows to suppress alerts.

**Methods:**
1. **CLI Command:**
   `checkmk-mcp-server services downtime HOSTNAME SERVICE_NAME HOURS "Comment"`

2. **Interactive Command:**
   "create 2 hour downtime for SERVICE_NAME on HOSTNAME"

3. **Examples:**
   • "schedule 4 hour downtime for disk space on server01"
   • "create downtime for memory on web-server for 1 hour"

**What happens:**
• Service monitoring is suppressed during downtime
• No alerts or notifications are sent
• Downtime period is clearly marked in Checkmk
• Service automatically resumes normal monitoring after downtime ends

**Best Practices:**
• Always include a descriptive comment
• Schedule downtimes before maintenance begins
• Use appropriate duration estimates"""

        else:
            message = """📖 Available Service Operations Instructions:

**Service Management:**
• "how can I add a service to HOSTNAME?" - Instructions for adding services
• "how do I acknowledge a service?" - Service acknowledgment guide  
• "how to create downtime?" - Service downtime scheduling guide

**Quick Commands:**
• List services: "show services on HOSTNAME"
• Service status: "check SERVICE_NAME on HOSTNAME"  
• Discover services: "discover services on HOSTNAME"
• Get statistics: "service statistics"

**Need specific help?** Ask:
• "how can I add a service to myserver?"
• "how do I acknowledge CPU alerts?"
• "how to schedule maintenance downtime?"

Type your question to get detailed instructions for any service operation."""

        return CommandResult.success_result(
            data={"instruction_type": instruction_type, "host_name": host_name},
            message=message,
        )


class ConnectionTestCommand(UtilityCommand):
    """Command to test connection to Checkmk API."""

    def __init__(self, checkmk_client: CheckmkClient):
        super().__init__()
        self.checkmk_client = checkmk_client

    @property
    def name(self) -> str:
        return "test_connection"

    @property
    def description(self) -> str:
        return "Test connection to Checkmk API"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {}

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the test connection command."""
        try:
            if self.checkmk_client.test_connection():
                # Get some basic info to show connection is working
                try:
                    services = self.checkmk_client.list_all_services()
                    service_count = len(services) if services else 0
                    message = (
                        f"✅ Connection successful. Found {service_count} services."
                    )
                except Exception:
                    message = "✅ Connection successful. Basic API access confirmed."

                return CommandResult.success_result(
                    data={
                        "connected": True,
                        "service_count": (
                            service_count if "service_count" in locals() else None
                        ),
                    },
                    message=message,
                )
            else:
                return CommandResult.error_result(
                    "Connection failed: Unable to reach Checkmk API"
                )

        except CheckmkAPIError as e:
            return CommandResult.error_result(f"Connection failed: {e}")
        except Exception as e:
            self.logger.error(f"Unexpected error in test_connection: {e}")
            return CommandResult.error_result(f"Connection test failed: {e}")


class HelpCommand(UtilityCommand):
    """Command to show help information."""

    @property
    def name(self) -> str:
        return "help"

    @property
    def description(self) -> str:
        return "Show help information for commands"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "command_name": {
                "type": str,
                "required": False,
                "description": "Specific command to get help for",
            },
            "category": {
                "type": str,
                "required": False,
                "description": "Command category to list (service, parameter, utility)",
            },
        }

    def execute(self, context: CommandContext) -> CommandResult:
        """Execute the help command."""
        command_name = context.get_parameter("command_name")
        category = context.get_parameter("category")

        if command_name:
            # Help for specific command - this would need registry access
            message = f"""📖 Help for command: {command_name}

This command-specific help would be generated by the command registry.
Use the command registry's get_command() method to get the command instance
and call its get_help_text() method.

For now, this is a placeholder that shows the help system is working."""

        elif category:
            # Help for category
            valid_categories = ["service", "parameter", "utility", "host", "rule"]
            if category not in valid_categories:
                return CommandResult.error_result(
                    f"Invalid category '{category}'. Valid categories: {', '.join(valid_categories)}"
                )

            message = f"""📖 Help for {category.title()} Commands:

This category-specific help would be generated by listing all commands
in the specified category from the command registry.

For now, this is a placeholder that shows the help system is working."""

        else:
            # General help
            message = """📖 Checkmk LLM Agent Help

**Available Command Categories:**
🔧 **Service Commands:** Manage and monitor services
  • list_services - List services for hosts
  • get_service_status - Get detailed service status
  • acknowledge_service - Acknowledge service problems
  • create_downtime - Schedule service downtime
  • discover_services - Discover services on hosts

📊 **Parameter Commands:** Manage service parameters
  • view_default_parameters - Show default service parameters
  • view_service_parameters - Show effective service parameters
  • set_service_parameters - Override service parameters
  • list_parameter_rules - List parameter rules

🛠️  **Utility Commands:** General utilities
  • test_connection - Test API connection
  • get_instructions - Get operation instructions
  • help - Show this help

**Usage:**
• Get specific help: `help COMMAND_NAME`
• Get category help: `help --category service`
• List all commands: `help`

**Examples:**
• "list services for server01"
• "acknowledge CPU load on server01"
• "set CPU warning to 85% for server01"
• "create 2 hour downtime for disk space on server01"

For detailed command help, use: `help COMMAND_NAME`"""

        return CommandResult.success_result(
            data={"command_name": command_name, "category": category}, message=message
        )
