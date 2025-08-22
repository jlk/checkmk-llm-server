"""Service operations manager for natural language processing."""

import logging
import json
from typing import Dict, Any
from datetime import datetime, timedelta

from .api_client import CheckmkClient, CheckmkAPIError
from .llm_client import LLMClient
from .config import AppConfig
from .service_parameters import ServiceParameterManager


class ServiceOperationsManager:
    """Manager for service operations with natural language processing."""

    def __init__(
        self, checkmk_client: CheckmkClient, llm_client: LLMClient, config: AppConfig
    ):
        self.checkmk_client = checkmk_client
        self.llm_client = llm_client
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.parameter_manager = ServiceParameterManager(checkmk_client, config)

    def process_command(self, command: str) -> str:
        """
        Process a natural language command related to services.

        Args:
            command: The user's command

        Returns:
            Human-readable response
        """
        try:
            # Handle direct compound commands first (from CLI-style interactive commands)
            command_lower = command.lower().strip()
            if command_lower.startswith("services list"):
                # Extract hostname from "services list hostname"
                parts = command.split()
                if len(parts) >= 3:
                    host_name = parts[2]
                    return self._handle_list_services(
                        {"parameters": {"host_name": host_name}}
                    )
                else:
                    return self._handle_list_services({"parameters": {}})

            # Analyze the command using LLM
            analysis = self._analyze_command(command)

            # Execute the appropriate operation
            action = analysis["action"]

            # Map common action variations
            action_mapping = {
                "list_services": "list_services",
                "show_services": "list_services",
                "get_services": "list_services",
                "get_service_status": "get_service_status",
                "service_status": "get_service_status",
                "check_service": "get_service_status",
                "acknowledge_service": "acknowledge_service",
                "ack_service": "acknowledge_service",
                "acknowledge": "acknowledge_service",
                "create_downtime": "create_downtime",
                "schedule_downtime": "create_downtime",
                "downtime": "create_downtime",
                "discover_services": "discover_services",
                "service_discovery": "discover_services",
                "discover": "discover_services",
                "get_instructions": "get_instructions",
                "instructions": "get_instructions",
                "help": "get_instructions",
                "how_to": "get_instructions",
                # Parameter operations
                "view_default_parameters": "view_default_parameters",
                "show_default_parameters": "view_default_parameters",
                "default_parameters": "view_default_parameters",
                "view_service_parameters": "view_service_parameters",
                "show_service_parameters": "view_service_parameters",
                "service_parameters": "view_service_parameters",
                "show_parameters": "view_service_parameters",
                "set_service_parameters": "set_service_parameters",
                "override_parameters": "set_service_parameters",
                "set_parameters": "set_service_parameters",
                "override_service": "set_service_parameters",
                "create_parameter_rule": "create_parameter_rule",
                "create_rule": "create_parameter_rule",
                "list_parameter_rules": "list_parameter_rules",
                "show_rules": "list_parameter_rules",
                "list_rules": "list_parameter_rules",
                "delete_parameter_rule": "delete_parameter_rule",
                "delete_rule": "delete_parameter_rule",
                "discover_ruleset": "discover_ruleset",
                "find_ruleset": "discover_ruleset",
            }

            # Normalize the action
            normalized_action = action_mapping.get(action, action)

            if normalized_action == "list_services":
                return self._handle_list_services(analysis)
            elif normalized_action == "get_service_status":
                return self._handle_get_service_status(analysis)
            elif normalized_action == "acknowledge_service":
                return self._handle_acknowledge_service(analysis)
            elif normalized_action == "create_downtime":
                return self._handle_create_downtime(analysis)
            elif normalized_action == "discover_services":
                return self._handle_discover_services(analysis)
            elif normalized_action == "get_instructions":
                return self._handle_get_instructions(analysis)
            # Parameter operations
            elif normalized_action == "view_default_parameters":
                return self._handle_view_default_parameters(analysis)
            elif normalized_action == "view_service_parameters":
                return self._handle_view_service_parameters(analysis)
            elif normalized_action == "set_service_parameters":
                return self._handle_set_service_parameters(analysis)
            elif normalized_action == "create_parameter_rule":
                return self._handle_create_parameter_rule(analysis)
            elif normalized_action == "list_parameter_rules":
                return self._handle_list_parameter_rules(analysis)
            elif normalized_action == "delete_parameter_rule":
                return self._handle_delete_parameter_rule(analysis)
            elif normalized_action == "discover_ruleset":
                return self._handle_discover_ruleset(analysis)
            else:
                available_actions = "list_services, get_service_status, acknowledge_service, create_downtime, discover_services, view_default_parameters, view_service_parameters, set_service_parameters, create_parameter_rule, list_parameter_rules, delete_parameter_rule, discover_ruleset, get_instructions"
                return f"❌ I don't understand how to handle the action: {action} (normalized: {normalized_action}). Available actions: {available_actions}"

        except Exception as e:
            self.logger.error(f"Error processing service command: {e}")
            return f"❌ Error processing command: {e}"

    def _analyze_command(self, command: str) -> Dict[str, Any]:
        """
        Analyze a natural language command to extract intent and parameters.

        Args:
            command: The user's command

        Returns:
            Dictionary with action and parameters
        """
        prompt = f"""
        Analyze this service-related command and extract the intent and parameters. You must return ONLY valid JSON.
        
        Command: "{command}"
        
        IMPORTANT: Determine if the user wants to PERFORM an action or GET INFORMATION/INSTRUCTIONS.
        
        Use EXACTLY one of these actions:
        - list_services: List services for a host or all services  
        - get_service_status: Get status of specific services
        - acknowledge_service: Acknowledge service problems
        - create_downtime: Create/schedule downtime for services
        - discover_services: ONLY when user explicitly wants to run discovery (e.g., "discover services", "scan for services")
        - view_default_parameters: View default parameters for a service type
        - view_service_parameters: View effective parameters for a specific service
        - set_service_parameters: Set/override parameters for a service
        - create_parameter_rule: Create a new parameter rule
        - list_parameter_rules: List existing parameter rules
        - delete_parameter_rule: Delete a parameter rule
        - discover_ruleset: Find the appropriate ruleset for a service
        - get_instructions: When user asks HOW TO do something or wants instructions
        
        Return ONLY this JSON format:
        {{
            "action": "one_of_the_exact_actions_above",
            "parameters": {{
                "host_name": "hostname or null",
                "service_description": "service name or null",
                "comment": "comment text or null",
                "duration_hours": number_or_null,
                "mode": "discovery mode or null",
                "instruction_type": "what they want to know how to do or null",
                "service_type": "cpu|memory|disk|filesystem|network or null",
                "parameter_type": "warning|critical|both or null",
                "threshold_value": number_or_null,
                "warning_value": number_or_null,
                "critical_value": number_or_null,
                "ruleset_name": "specific ruleset or null",
                "rule_id": "rule_id or null"
            }}
        }}
        
        Examples:
        - "list services for server01" -> {{"action": "list_services", "parameters": {{"host_name": "server01"}}}}
        - "show default CPU parameters" -> {{"action": "view_default_parameters", "parameters": {{"service_type": "cpu"}}}}
        - "what are CPU thresholds for server01?" -> {{"action": "view_service_parameters", "parameters": {{"host_name": "server01", "service_description": "CPU utilization"}}}}
        - "show parameters for \"Temperature Zone 0\" on piaware" -> {{"action": "view_service_parameters", "parameters": {{"host_name": "piaware", "service_description": "Temperature Zone 0"}}}}
        - "show parameters for CPU on server01" -> {{"action": "view_service_parameters", "parameters": {{"host_name": "server01", "service_description": "CPU"}}}}
        - "view thresholds for \"Filesystem /\" on server01" -> {{"action": "view_service_parameters", "parameters": {{"host_name": "server01", "service_description": "Filesystem /"}}}}
        - "set CPU warning to 85% for server01" -> {{"action": "set_service_parameters", "parameters": {{"host_name": "server01", "service_description": "CPU utilization", "parameter_type": "warning", "warning_value": 85}}}}
        - "override disk critical to 95% for server01" -> {{"action": "set_service_parameters", "parameters": {{"host_name": "server01", "service_description": "Filesystem", "parameter_type": "critical", "critical_value": 95}}}}
        - "create memory rule for production hosts" -> {{"action": "create_parameter_rule", "parameters": {{"service_type": "memory", "comment": "production hosts rule"}}}}
        - "show all parameter rules" -> {{"action": "list_parameter_rules", "parameters": {{}}}}
        - "what ruleset controls CPU on server01?" -> {{"action": "discover_ruleset", "parameters": {{"host_name": "server01", "service_description": "CPU utilization"}}}}
        - "acknowledge CPU load on server01" -> {{"action": "acknowledge_service", "parameters": {{"host_name": "server01", "service_description": "CPU load", "comment": "Working on it"}}}}
        """

        response = self.llm_client.chat_completion(prompt)

        try:
            # Try to extract JSON from the response
            # Look for JSON blocks in markdown or plain JSON
            response_clean = response.strip()

            # If response contains markdown code blocks, extract the JSON
            if "```json" in response_clean:
                start = response_clean.find("```json") + 7
                end = response_clean.find("```", start)
                if end != -1:
                    response_clean = response_clean[start:end].strip()
            elif "```" in response_clean:
                start = response_clean.find("```") + 3
                end = response_clean.find("```", start)
                if end != -1:
                    response_clean = response_clean[start:end].strip()

            # Try to find JSON object in the response
            if not response_clean.startswith("{"):
                # Look for the first { and last }
                start = response_clean.find("{")
                end = response_clean.rfind("}")
                if start != -1 and end != -1 and end > start:
                    response_clean = response_clean[start : end + 1]

            return json.loads(response_clean)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse LLM response: {response}")
            return {"action": "unknown", "parameters": {}}

    def _handle_list_services(self, analysis: Dict[str, Any]) -> str:
        """Handle listing services."""
        try:
            params = analysis.get("parameters", {})
            host_name = params.get("host_name")

            if host_name:
                # List services for specific host with status columns
                services = self.checkmk_client.list_host_services(
                    host_name, columns=["description", "state", "plugin_output"]
                )
                if not services:
                    return f"📦 No services found for host: {host_name}"

                result = f"📦 Found {len(services)} services for host: {host_name}\n\n"
                for service in services:
                    extensions = service.get("extensions", {})
                    service_desc = extensions.get("description", "Unknown")
                    service_state = extensions.get("state", "Unknown")
                    plugin_output = extensions.get("plugin_output", "")

                    # Convert numeric state to text and get emoji
                    if isinstance(service_state, int):
                        state_map = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}
                        state_text = state_map.get(
                            service_state, f"STATE_{service_state}"
                        )
                        state_emoji = {
                            "OK": "✅",
                            "WARNING": "⚠️",
                            "CRITICAL": "❌",
                            "UNKNOWN": "❓",
                        }.get(state_text, "❓")
                    else:
                        state_text = str(service_state)
                        state_emoji = "✅" if state_text == "OK" else "❌"

                    # Show service with status and brief output
                    output_snippet = (
                        plugin_output[:50] + "..."
                        if len(plugin_output) > 50
                        else plugin_output
                    )
                    if output_snippet:
                        result += f"  {state_emoji} {host_name}/{service_desc} - {state_text} ({output_snippet})\n"
                    else:
                        result += f"  {state_emoji} {host_name}/{service_desc} - {state_text}\n"

                return result
            else:
                # List all services
                services = self.checkmk_client.list_all_services(
                    columns=["description", "state", "plugin_output"]
                )
                if not services:
                    return "📦 No services found"

                # Group by host
                services_by_host = {}
                for service in services:
                    host = service.get("extensions", {}).get("host_name", "Unknown")
                    if host not in services_by_host:
                        services_by_host[host] = []
                    services_by_host[host].append(service)

                result = f"📦 Found {len(services)} services across {len(services_by_host)} hosts:\n\n"
                for host, host_services in services_by_host.items():
                    result += f"  🖥️  {host} ({len(host_services)} services)\n"
                    for service in host_services[:3]:  # Show first 3 services
                        service_desc = service.get("extensions", {}).get(
                            "description", "Unknown"
                        )
                        service_state = service.get("extensions", {}).get(
                            "state", "Unknown"
                        )
                        state_emoji = self._get_state_emoji(service_state)
                        result += f"    {state_emoji} {service_desc}\n"
                    if len(host_services) > 3:
                        result += f"    ... and {len(host_services) - 3} more\n"
                    result += "\n"

                return result

        except CheckmkAPIError as e:
            return f"❌ Error listing services: {e}"

    def _handle_get_service_status(self, analysis: Dict[str, Any]) -> str:
        """Handle getting service status."""
        try:
            params = analysis.get("parameters", {})
            host_name = params.get("host_name")
            service_desc = params.get("service_description")

            if host_name and service_desc:
                # Get specific service status
                services = self.checkmk_client.list_host_services(
                    host_name, query=f"service_description = '{service_desc}'"
                )
                if not services:
                    return (
                        f"❌ Service '{service_desc}' not found on host '{host_name}'"
                    )

                service = services[0]
                service_state = service.get("extensions", {}).get("state", "Unknown")
                state_emoji = self._get_state_emoji(service_state)
                last_check = service.get("extensions", {}).get("last_check", "Unknown")
                plugin_output = service.get("extensions", {}).get(
                    "plugin_output", "No output"
                )

                return f"""📊 Service Status: {host_name}/{service_desc}
{state_emoji} State: {service_state}
⏰ Last Check: {last_check}
💬 Output: {plugin_output}"""
            else:
                return "❌ Please specify both host name and service description"

        except CheckmkAPIError as e:
            return f"❌ Error getting service status: {e}"

    def _handle_acknowledge_service(self, analysis: Dict[str, Any]) -> str:
        """Handle acknowledging service problems."""
        try:
            params = analysis.get("parameters", {})
            host_name = params.get("host_name")
            service_desc = params.get("service_description")
            comment = params.get("comment") or "Acknowledged via LLM Agent"

            if not host_name or not service_desc:
                return "❌ Please specify both host name and service description"

            # Ensure comment is a string
            if not isinstance(comment, str):
                comment = "Acknowledged via LLM Agent"

            self.checkmk_client.acknowledge_service_problems(
                host_name=host_name,
                service_description=service_desc,
                comment=comment,
                sticky=True,
            )

            return f"✅ Acknowledged service problem: {host_name}/{service_desc}\n💬 Comment: {comment}"

        except CheckmkAPIError as e:
            return f"❌ Error acknowledging service: {e}"

    def _handle_create_downtime(self, analysis: Dict[str, Any]) -> str:
        """Handle creating service downtime."""
        try:
            params = analysis.get("parameters", {})
            host_name = params.get("host_name")
            service_desc = params.get("service_description")
            duration_hours = params.get("duration_hours")
            comment = params.get("comment") or "Downtime created via LLM Agent"

            if not host_name or not service_desc:
                return "❌ Please specify both host name and service description"

            # Handle duration_hours
            if duration_hours is None or not isinstance(duration_hours, (int, float)):
                duration_hours = 2  # Default to 2 hours

            # Ensure comment is a string
            if not isinstance(comment, str):
                comment = "Downtime created via LLM Agent"

            # Calculate start and end times
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=duration_hours)

            self.checkmk_client.create_service_downtime(
                host_name=host_name,
                service_description=service_desc,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                comment=comment,
            )

            return f"""✅ Created downtime for service: {host_name}/{service_desc}
⏰ Duration: {duration_hours} hours
🕐 Start: {start_time.strftime('%Y-%m-%d %H:%M')}
🕑 End: {end_time.strftime('%Y-%m-%d %H:%M')}
💬 Comment: {comment}"""

        except CheckmkAPIError as e:
            return f"❌ Error creating downtime: {e}"

    def _handle_discover_services(self, analysis: Dict[str, Any]) -> str:
        """Handle service discovery."""
        try:
            params = analysis.get("parameters", {})
            host_name = params.get("host_name")
            mode = params.get("mode") or "refresh"  # Handle None values

            if not host_name:
                return "❌ Please specify a host name"

            # Ensure mode is a valid string and normalize it
            if not isinstance(mode, str):
                mode = "refresh"

            # Map common mode variations to valid values
            mode_mapping = {
                "discovery": "refresh",
                "scan": "refresh",
                "find": "refresh",
                "detect": "refresh",
                "new": "new",
                "add": "new",
                "refresh": "refresh",
                "remove": "remove",
                "delete": "remove",
                "fixall": "fixall",
                "fix": "fixall",
                "refresh_autochecks": "refresh_autochecks",
            }

            # Normalize the mode
            mode = mode_mapping.get(mode.lower(), "refresh")

            # Start service discovery
            result = self.checkmk_client.start_service_discovery(host_name, mode)

            # Get discovery results
            discovery_result = self.checkmk_client.get_service_discovery_result(
                host_name
            )

            # Format response
            extensions = discovery_result.get("extensions", {})
            vanished = extensions.get("vanished", [])
            new = extensions.get("new", [])
            ignored = extensions.get("ignored", [])

            response = f"🔍 Service discovery completed for host: {host_name}\n\n"

            if new:
                response += f"✨ New services found ({len(new)}):\n"
                for service in new:
                    service_desc = service.get("service_description", "Unknown")
                    response += f"  + {service_desc}\n"
                response += "\n"

            if vanished:
                response += f"👻 Vanished services ({len(vanished)}):\n"
                for service in vanished:
                    service_desc = service.get("service_description", "Unknown")
                    response += f"  - {service_desc}\n"
                response += "\n"

            if ignored:
                response += f"🚫 Ignored services ({len(ignored)}):\n"
                for service in ignored:
                    service_desc = service.get("service_description", "Unknown")
                    response += f"  ! {service_desc}\n"
                response += "\n"

            if not new and not vanished and not ignored:
                response += "✅ No service changes detected"

            return response

        except CheckmkAPIError as e:
            return f"❌ Error discovering services: {e}"

    def _handle_get_instructions(self, analysis: Dict[str, Any]) -> str:
        """Handle requests for instructions on how to perform service operations."""
        params = analysis.get("parameters", {})
        instruction_type = params.get("instruction_type", "")
        host_name = params.get("host_name", "")

        if instruction_type == "add_service":
            return f"""📖 How to add a service to {host_name if host_name else 'a host'}:

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
            return """📖 How to acknowledge a service problem:

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
            return """📖 How to schedule service downtime:

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
            return """📖 Available Service Operations Instructions:

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

    def _get_state_emoji(self, state: str) -> str:
        """Get emoji for service state."""
        state_map = {
            "OK": "✅",
            "WARN": "⚠️",
            "CRIT": "❌",
            "UNKNOWN": "❓",
            "PENDING": "⏳",
            0: "✅",  # OK
            1: "⚠️",  # WARN
            2: "❌",  # CRIT
            3: "❓",  # UNKNOWN
        }
        return state_map.get(state, "❓")

    def get_service_statistics(self) -> str:
        """Get service statistics across all hosts."""
        try:
            services = self.checkmk_client.list_all_services(
                columns=["description", "state", "plugin_output"]
            )

            if not services:
                return "📊 No services found"

            # Count by state
            state_counts = {}
            hosts = set()

            for service in services:
                extensions = service.get("extensions", {})
                state = extensions.get("state", "Unknown")
                host = extensions.get("host_name", "Unknown")

                hosts.add(host)
                state_counts[state] = state_counts.get(state, 0) + 1

            result = f"📊 Service Statistics:\n\n"
            result += f"🖥️  Total Hosts: {len(hosts)}\n"
            result += f"🔧 Total Services: {len(services)}\n\n"

            result += "Service States:\n"
            for state, count in state_counts.items():
                emoji = self._get_state_emoji(state)
                result += f"  {emoji} {state}: {count}\n"

            return result

        except CheckmkAPIError as e:
            return f"❌ Error getting service statistics: {e}"

    def test_connection(self) -> str:
        """Test connection by listing services."""
        try:
            services = self.checkmk_client.list_all_services(
                columns=["description", "state", "plugin_output"]
            )
            return f"✅ Connection successful. Found {len(services)} services."
        except CheckmkAPIError as e:
            return f"❌ Connection failed: {e}"

    # Parameter operation handlers

    def _handle_view_default_parameters(self, analysis: Dict[str, Any]) -> str:
        """Handle viewing default parameters for service types."""
        try:
            params = analysis.get("parameters", {})
            service_type = params.get("service_type", "cpu")

            # Get default parameters
            default_params = self.parameter_manager.get_default_parameters(service_type)

            if not default_params:
                return (
                    f"❌ No default parameters found for service type: {service_type}"
                )

            result = f"📊 Default Parameters for {service_type.upper()} services:\n\n"

            # Format parameters nicely
            if "levels" in default_params:
                warning, critical = default_params["levels"]
                result += f"⚠️  Warning Threshold: {warning:.1f}%\n"
                result += f"❌ Critical Threshold: {critical:.1f}%\n"

            if "average" in default_params:
                result += f"📈 Averaging Period: {default_params['average']} minutes\n"

            if "magic_normsize" in default_params:
                result += f"💾 Magic Normsize: {default_params['magic_normsize']} GB\n"

            if "magic" in default_params:
                result += f"🎯 Magic Factor: {default_params['magic']}\n"

            # Show applicable ruleset
            ruleset_map = self.parameter_manager.PARAMETER_RULESETS.get(
                service_type, {}
            )
            default_ruleset = ruleset_map.get("default", "Unknown")
            result += f"\n📋 Default Ruleset: {default_ruleset}"

            return result

        except Exception as e:
            self.logger.error(f"Error viewing default parameters: {e}")
            return f"❌ Error viewing default parameters: {e}"

    def _handle_view_service_parameters(self, analysis: Dict[str, Any]) -> str:
        """Handle viewing parameters for a specific service."""
        try:
            params = analysis.get("parameters", {})
            host_name = params.get("host_name")
            service_description = params.get("service_description")

            if not host_name or not service_description:
                return "❌ Please specify both host name and service description"

            # Try to get actual service monitoring data with real thresholds
            try:
                # Get service monitoring data including state, output, and performance data
                services = self.checkmk_client.get_service_monitoring_data(
                    host_name, service_description
                )

                # The API call already filtered by service description
                if services and len(services) > 0:
                    target_service = services[0]  # Take the first match
                    # Debug: Let's see what the service object actually contains
                    self.logger.debug(f"Service object structure: {target_service}")

                    # Extract real threshold values from monitoring data
                    # The exact structure depends on what the Checkmk API returns
                    extensions = target_service.get("extensions", {})

                    # Extract monitoring data from the columns we requested
                    output = extensions.get("plugin_output", "")
                    perf_data = extensions.get("perf_data", "")
                    state = extensions.get("state", 0)
                    check_command = extensions.get("check_command", "")

                    result = f"📊 Current Parameters for {host_name}/{service_description}:\n\n"

                    # Debug: Show what data we found
                    if output:
                        self.logger.debug(f"Found output: {output}")
                    if perf_data:
                        self.logger.debug(f"Found perf_data: {perf_data}")

                    # If we don't have monitoring data, show what we do have
                    if not output and not perf_data:
                        result += "🔍 Service found, but checking available data...\n"
                        result += (
                            f"📋 Service structure: {list(target_service.keys())}\n"
                        )
                        if extensions:
                            result += (
                                f"📋 Extensions available: {list(extensions.keys())}\n"
                            )
                        result += "💡 May need to check service state or use different API endpoint.\n"
                        return result

                    # Parse performance data for thresholds (format: metric=value;warn;crit;min;max)
                    thresholds_found = False

                    if perf_data:
                        # Parse performance data to extract warning/critical thresholds
                        metrics = perf_data.split()
                        for metric in metrics:
                            if "=" in metric:
                                parts = metric.split("=")
                                if len(parts) == 2:
                                    metric_name = parts[0]
                                    values = parts[1].split(";")
                                    if len(values) >= 3:
                                        current_value = values[0]
                                        warn_threshold = (
                                            values[1] if values[1] else None
                                        )
                                        crit_threshold = (
                                            values[2] if values[2] else None
                                        )

                                        if warn_threshold and crit_threshold:
                                            # Determine unit from metric name or service description
                                            unit = ""
                                            if any(
                                                temp_word in service_description.lower()
                                                for temp_word in ["temperature", "temp"]
                                            ):
                                                unit = "°C"
                                            elif any(
                                                util_word in service_description.lower()
                                                for util_word in [
                                                    "cpu",
                                                    "memory",
                                                    "disk",
                                                    "utilization",
                                                ]
                                            ):
                                                unit = "%"

                                            result += f"📈 Metric: {metric_name}\n"
                                            result += f"📊 Current Value: {current_value}{unit}\n"
                                            result += f"⚠️  Warning Threshold: {warn_threshold}{unit}\n"
                                            result += f"❌ Critical Threshold: {crit_threshold}{unit}\n"
                                            thresholds_found = True
                                            break

                    # If no thresholds in perf_data, try to parse from output text
                    if not thresholds_found and output:
                        result += f"📊 Service Status: {output}\n"

                        # Look for threshold patterns in output
                        import re

                        threshold_patterns = [
                            r"warn/crit at ([\d.]+)[°%]?[^/]*/?([\d.]+)[°%]?",
                            r"warning at ([\d.]+)[°%]?.*critical at ([\d.]+)[°%]?",
                            r"warn: ([\d.]+)[°%]?.*crit: ([\d.]+)[°%]?",
                        ]

                        for pattern in threshold_patterns:
                            match = re.search(pattern, output, re.IGNORECASE)
                            if match:
                                warn_val = match.group(1)
                                crit_val = match.group(2)
                                unit = (
                                    "°C"
                                    if "temperature" in service_description.lower()
                                    or "temp" in service_description.lower()
                                    else "%"
                                )
                                result += f"\n⚠️  Warning Threshold: {warn_val}{unit}\n"
                                result += f"❌ Critical Threshold: {crit_val}{unit}\n"
                                thresholds_found = True
                                break

                    if thresholds_found:
                        result += f"\n✅ These are the ACTUAL values from your Checkmk system!"
                        return result
                    else:
                        result += (
                            "\n💡 No threshold information found in monitoring data.\n"
                        )
                        result += "   The service may not have warning/critical thresholds configured.\n"
                        return result

                else:
                    result = f"📊 Parameters for {host_name}/{service_description}:\n"
                    result += f"❌ Service '{service_description}' not found on host '{host_name}'\n"
                    result += "   Please check the service name and host name.\n"
                    return result

            except CheckmkAPIError as e:
                self.logger.error(f"Error getting service monitoring data: {e}")
                result = f"📊 Parameters for {host_name}/{service_description}:\n"
                result += f"❌ Could not retrieve service monitoring data: {e}\n"
                return result

        except Exception as e:
            self.logger.error(f"Error viewing service parameters: {e}")
            return f"❌ Error viewing service parameters: {e}"

    def _handle_set_service_parameters(self, analysis: Dict[str, Any]) -> str:
        """Handle setting/overriding service parameters."""
        try:
            params = analysis.get("parameters", {})
            host_name = params.get("host_name")
            service_description = params.get("service_description")

            if not host_name or not service_description:
                return "❌ Please specify both host name and service description"

            # Extract threshold values
            warning_value = params.get("warning_value")
            critical_value = params.get("critical_value")
            parameter_type = params.get("parameter_type", "both")

            # Determine thresholds to set
            if parameter_type == "warning" and warning_value is not None:
                # Only setting warning, need to get current critical
                current_params = self.parameter_manager.get_service_parameters(
                    host_name, service_description
                )
                current_levels = current_params.get("parameters", {}).get(
                    "levels", (80.0, 90.0)
                )
                critical_value = current_levels[1] if len(current_levels) > 1 else 90.0
            elif parameter_type == "critical" and critical_value is not None:
                # Only setting critical, need to get current warning
                current_params = self.parameter_manager.get_service_parameters(
                    host_name, service_description
                )
                current_levels = current_params.get("parameters", {}).get(
                    "levels", (80.0, 90.0)
                )
                warning_value = current_levels[0] if len(current_levels) > 0 else 80.0
            elif warning_value is not None and critical_value is not None:
                # Setting both
                pass
            else:
                return "❌ Please specify warning and/or critical threshold values"

            # Create simple override
            comment = (
                params.get("comment")
                or f"Override thresholds for {service_description} on {host_name}"
            )

            rule_id = self.parameter_manager.create_simple_override(
                host_name=host_name,
                service_name=service_description,
                warning=warning_value,
                critical=critical_value,
                comment=comment,
            )

            result = (
                f"✅ Created parameter override for {host_name}/{service_description}\n"
            )
            result += f"⚠️  Warning: {warning_value:.1f}%\n"
            result += f"❌ Critical: {critical_value:.1f}%\n"
            result += f"🆔 Rule ID: {rule_id}\n"
            result += f"💬 Comment: {comment}\n"
            result += "⏱️  Changes will take effect after next service check cycle"

            return result

        except Exception as e:
            self.logger.error(f"Error setting service parameters: {e}")
            return f"❌ Error setting service parameters: {e}"

    def _handle_create_parameter_rule(self, analysis: Dict[str, Any]) -> str:
        """Handle creating a new parameter rule."""
        try:
            params = analysis.get("parameters", {})
            service_type = params.get("service_type", "cpu")
            comment = params.get(
                "comment", f"Parameter rule for {service_type} services"
            )

            # Get default parameters for the service type
            default_params = self.parameter_manager.get_default_parameters(service_type)
            if not default_params:
                return (
                    f"❌ No default parameters found for service type: {service_type}"
                )

            # Determine ruleset
            ruleset_map = self.parameter_manager.PARAMETER_RULESETS.get(
                service_type, {}
            )
            ruleset = ruleset_map.get("default")
            if not ruleset:
                return f"❌ No ruleset found for service type: {service_type}"

            # For now, create a general rule - in practice this would need more specific conditions
            result = f"📋 To create a parameter rule for {service_type} services:\n\n"
            result += f"🔧 Service Type: {service_type}\n"
            result += f"📊 Ruleset: {ruleset}\n"
            result += f"📝 Default Parameters: {default_params}\n\n"
            result += (
                "ℹ️  Use specific host/service combinations for actual rule creation.\n"
            )
            result += f"Example: 'set {service_type} warning to 85% for server01'"

            return result

        except Exception as e:
            self.logger.error(f"Error creating parameter rule: {e}")
            return f"❌ Error creating parameter rule: {e}"

    def _handle_list_parameter_rules(self, analysis: Dict[str, Any]) -> str:
        """Handle listing parameter rules."""
        try:
            params = analysis.get("parameters", {})
            ruleset_name = params.get("ruleset_name")

            # List available rulesets if no specific ruleset requested
            if not ruleset_name:
                rulesets = self.parameter_manager.list_parameter_rulesets()

                result = f"📋 Available Parameter Rulesets ({len(rulesets)}):\n\n"

                # Group by category
                categories = {}
                for ruleset in rulesets:
                    ruleset_id = ruleset.get("id", "Unknown")
                    # Categorize based on name
                    if "cpu" in ruleset_id:
                        categories.setdefault("CPU", []).append(ruleset_id)
                    elif "memory" in ruleset_id:
                        categories.setdefault("Memory", []).append(ruleset_id)
                    elif "filesystem" in ruleset_id:
                        categories.setdefault("Filesystem", []).append(ruleset_id)
                    elif "interface" in ruleset_id or "network" in ruleset_id:
                        categories.setdefault("Network", []).append(ruleset_id)
                    else:
                        categories.setdefault("Other", []).append(ruleset_id)

                for category, rulesets_list in categories.items():
                    result += f"📁 {category}:\n"
                    for ruleset_id in rulesets_list:
                        result += f"  📊 {ruleset_id}\n"
                    result += "\n"

                result += "💡 Specify a ruleset to see its rules: 'show rules for cpu_utilization_linux'"

                return result
            else:
                # List rules for specific ruleset
                rules = self.checkmk_client.list_rules(ruleset_name)

                if not rules:
                    return f"📋 No rules found for ruleset: {ruleset_name}"

                result = f"📋 Rules for {ruleset_name} ({len(rules)}):\n\n"

                for rule in rules[:10]:  # Show first 10 rules
                    rule_id = rule.get("id", "Unknown")
                    extensions = rule.get("extensions", {})
                    conditions = extensions.get("conditions", {})
                    properties = extensions.get("properties", {})

                    result += f"🔧 Rule {rule_id}\n"

                    # Show conditions
                    if conditions.get("host_name"):
                        hosts = ", ".join(conditions["host_name"][:3])
                        if len(conditions["host_name"]) > 3:
                            hosts += f" (and {len(conditions['host_name']) - 3} more)"
                        result += f"  🖥️  Hosts: {hosts}\n"

                    if conditions.get("service_description"):
                        services = ", ".join(conditions["service_description"][:2])
                        if len(conditions["service_description"]) > 2:
                            services += f" (and {len(conditions['service_description']) - 2} more)"
                        result += f"  🔧 Services: {services}\n"

                    if properties.get("description"):
                        desc = properties["description"][:50]
                        if len(properties["description"]) > 50:
                            desc += "..."
                        result += f"  💬 Description: {desc}\n"

                    result += "\n"

                if len(rules) > 10:
                    result += f"... and {len(rules) - 10} more rules"

                return result

        except Exception as e:
            self.logger.error(f"Error listing parameter rules: {e}")
            return f"❌ Error listing parameter rules: {e}"

    def _handle_delete_parameter_rule(self, analysis: Dict[str, Any]) -> str:
        """Handle deleting a parameter rule."""
        try:
            params = analysis.get("parameters", {})
            rule_id = params.get("rule_id")

            if not rule_id:
                return "❌ Please specify a rule ID to delete"

            # Get rule info before deletion
            try:
                rule_info = self.checkmk_client.get_rule(rule_id)
                extensions = rule_info.get("extensions", {})
                ruleset = extensions.get("ruleset", "Unknown")
                conditions = extensions.get("conditions", {})
            except CheckmkAPIError:
                ruleset = "Unknown"
                conditions = {}

            # Delete the rule
            self.parameter_manager.delete_parameter_rule(rule_id)

            result = f"✅ Deleted parameter rule: {rule_id}\n"
            result += f"📊 Ruleset: {ruleset}\n"

            if conditions.get("host_name"):
                hosts = ", ".join(conditions["host_name"][:3])
                result += f"🖥️  Affected Hosts: {hosts}\n"

            result += "⏱️  Changes will take effect after configuration activation"

            return result

        except Exception as e:
            self.logger.error(f"Error deleting parameter rule: {e}")
            return f"❌ Error deleting parameter rule: {e}"

    def _handle_discover_ruleset(self, analysis: Dict[str, Any]) -> str:
        """Handle discovering the appropriate ruleset for a service."""
        try:
            params = analysis.get("parameters", {})
            host_name = params.get("host_name")
            service_description = params.get("service_description")

            if not service_description:
                return "❌ Please specify a service description"

            # Discover ruleset
            ruleset = self.parameter_manager.discover_service_ruleset(
                host_name or "unknown", service_description
            )

            if not ruleset:
                return f"❌ Could not determine appropriate ruleset for service: {service_description}"

            result = f"🔍 Service: {service_description}\n"
            if host_name:
                result += f"🖥️  Host: {host_name}\n"
            result += f"📋 Recommended Ruleset: {ruleset}\n\n"

            # Show default parameters for this ruleset
            service_type = (
                "cpu"
                if "cpu" in ruleset
                else (
                    "memory"
                    if "memory" in ruleset
                    else "filesystem" if "filesystem" in ruleset else "network"
                )
            )
            default_params = self.parameter_manager.get_default_parameters(service_type)

            if default_params:
                result += "📊 Default Parameters:\n"
                if "levels" in default_params:
                    warning, critical = default_params["levels"]
                    result += f"  ⚠️  Warning: {warning:.1f}%\n"
                    result += f"  ❌ Critical: {critical:.1f}%\n"

                if "average" in default_params:
                    result += f"  📈 Average: {default_params['average']} min\n"

            result += f"\n💡 To override parameters: 'set {service_type} warning to 85% for {host_name or 'HOSTNAME'}'"

            return result

        except Exception as e:
            self.logger.error(f"Error discovering ruleset: {e}")
            return f"❌ Error discovering ruleset: {e}"
