"""Service operations manager for natural language processing."""

import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta

from .api_client import CheckmkClient, CheckmkAPIError
from .llm_client import LLMClient
from .config import AppConfig


class ServiceOperationsManager:
    """Manager for service operations with natural language processing."""
    
    def __init__(self, checkmk_client: CheckmkClient, llm_client: LLMClient, config: AppConfig):
        self.checkmk_client = checkmk_client
        self.llm_client = llm_client
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def process_command(self, command: str) -> str:
        """
        Process a natural language command related to services.
        
        Args:
            command: The user's command
            
        Returns:
            Human-readable response
        """
        try:
            # Analyze the command using LLM
            analysis = self._analyze_command(command)
            
            # Execute the appropriate operation
            action = analysis['action']
            
            # Map common action variations
            action_mapping = {
                'list_services': 'list_services',
                'show_services': 'list_services',
                'get_services': 'list_services',
                'get_service_status': 'get_service_status',
                'service_status': 'get_service_status',
                'check_service': 'get_service_status',
                'acknowledge_service': 'acknowledge_service',
                'ack_service': 'acknowledge_service',
                'acknowledge': 'acknowledge_service',
                'create_downtime': 'create_downtime',
                'schedule_downtime': 'create_downtime',
                'downtime': 'create_downtime',
                'discover_services': 'discover_services',
                'service_discovery': 'discover_services',
                'discover': 'discover_services',
                'get_instructions': 'get_instructions',
                'instructions': 'get_instructions',
                'help': 'get_instructions',
                'how_to': 'get_instructions'
            }
            
            # Normalize the action
            normalized_action = action_mapping.get(action, action)
            
            if normalized_action == 'list_services':
                return self._handle_list_services(analysis)
            elif normalized_action == 'get_service_status':
                return self._handle_get_service_status(analysis)
            elif normalized_action == 'acknowledge_service':
                return self._handle_acknowledge_service(analysis)
            elif normalized_action == 'create_downtime':
                return self._handle_create_downtime(analysis)
            elif normalized_action == 'discover_services':
                return self._handle_discover_services(analysis)
            elif normalized_action == 'get_instructions':
                return self._handle_get_instructions(analysis)
            else:
                return f"❌ I don't understand how to handle the action: {action} (normalized: {normalized_action}). Available actions: list_services, get_service_status, acknowledge_service, create_downtime, discover_services, get_instructions"
                
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
                "instruction_type": "what they want to know how to do or null"
            }}
        }}
        
        Examples:
        - "list services for server01" -> {{"action": "list_services", "parameters": {{"host_name": "server01"}}}}
        - "how can I add a service to server01?" -> {{"action": "get_instructions", "parameters": {{"host_name": "server01", "instruction_type": "add_service"}}}}
        - "how do I acknowledge a service?" -> {{"action": "get_instructions", "parameters": {{"instruction_type": "acknowledge_service"}}}}
        - "how can I schedule downtime?" -> {{"action": "get_instructions", "parameters": {{"instruction_type": "create_downtime"}}}}
        - "what can I do with services?" -> {{"action": "get_instructions", "parameters": {{"instruction_type": "general"}}}}
        - "discover services on server01" -> {{"action": "discover_services", "parameters": {{"host_name": "server01"}}}}
        - "acknowledge CPU load on server01" -> {{"action": "acknowledge_service", "parameters": {{"host_name": "server01", "service_description": "CPU load", "comment": "Working on it"}}}}
        """
        
        response = self.llm_client.chat_completion(prompt)
        
        try:
            # Try to extract JSON from the response
            # Look for JSON blocks in markdown or plain JSON
            response_clean = response.strip()
            
            # If response contains markdown code blocks, extract the JSON
            if '```json' in response_clean:
                start = response_clean.find('```json') + 7
                end = response_clean.find('```', start)
                if end != -1:
                    response_clean = response_clean[start:end].strip()
            elif '```' in response_clean:
                start = response_clean.find('```') + 3
                end = response_clean.find('```', start)
                if end != -1:
                    response_clean = response_clean[start:end].strip()
            
            # Try to find JSON object in the response
            if not response_clean.startswith('{'):
                # Look for the first { and last }
                start = response_clean.find('{')
                end = response_clean.rfind('}')
                if start != -1 and end != -1 and end > start:
                    response_clean = response_clean[start:end+1]
            
            return json.loads(response_clean)
        except json.JSONDecodeError:
            self.logger.error(f"Failed to parse LLM response: {response}")
            return {"action": "unknown", "parameters": {}}
    
    def _handle_list_services(self, analysis: Dict[str, Any]) -> str:
        """Handle listing services."""
        try:
            params = analysis.get('parameters', {})
            host_name = params.get('host_name')
            
            if host_name:
                # List services for specific host
                services = self.checkmk_client.list_host_services(host_name)
                if not services:
                    return f"📦 No services found for host: {host_name}"
                
                result = f"📦 Found {len(services)} services for host: {host_name}\n\n"
                for service in services:
                    service_desc = service.get('extensions', {}).get('description', 'Unknown')
                    service_state = service.get('extensions', {}).get('state', 'Unknown')
                    state_emoji = self._get_state_emoji(service_state)
                    result += f"  {state_emoji} {service_desc}\n"
                
                return result
            else:
                # List all services
                services = self.checkmk_client.list_all_services()
                if not services:
                    return "📦 No services found"
                
                # Group by host
                services_by_host = {}
                for service in services:
                    host = service.get('extensions', {}).get('host_name', 'Unknown')
                    if host not in services_by_host:
                        services_by_host[host] = []
                    services_by_host[host].append(service)
                
                result = f"📦 Found {len(services)} services across {len(services_by_host)} hosts:\n\n"
                for host, host_services in services_by_host.items():
                    result += f"  🖥️  {host} ({len(host_services)} services)\n"
                    for service in host_services[:3]:  # Show first 3 services
                        service_desc = service.get('extensions', {}).get('description', 'Unknown')
                        service_state = service.get('extensions', {}).get('state', 'Unknown')
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
            params = analysis.get('parameters', {})
            host_name = params.get('host_name')
            service_desc = params.get('service_description')
            
            if host_name and service_desc:
                # Get specific service status
                services = self.checkmk_client.list_host_services(
                    host_name, 
                    query=f"service_description = '{service_desc}'"
                )
                if not services:
                    return f"❌ Service '{service_desc}' not found on host '{host_name}'"
                
                service = services[0]
                service_state = service.get('extensions', {}).get('state', 'Unknown')
                state_emoji = self._get_state_emoji(service_state)
                last_check = service.get('extensions', {}).get('last_check', 'Unknown')
                plugin_output = service.get('extensions', {}).get('plugin_output', 'No output')
                
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
            params = analysis.get('parameters', {})
            host_name = params.get('host_name')
            service_desc = params.get('service_description')
            comment = params.get('comment') or 'Acknowledged via LLM Agent'
            
            if not host_name or not service_desc:
                return "❌ Please specify both host name and service description"
            
            # Ensure comment is a string
            if not isinstance(comment, str):
                comment = 'Acknowledged via LLM Agent'
            
            self.checkmk_client.acknowledge_service_problems(
                host_name=host_name,
                service_description=service_desc,
                comment=comment,
                sticky=True
            )
            
            return f"✅ Acknowledged service problem: {host_name}/{service_desc}\n💬 Comment: {comment}"
            
        except CheckmkAPIError as e:
            return f"❌ Error acknowledging service: {e}"
    
    def _handle_create_downtime(self, analysis: Dict[str, Any]) -> str:
        """Handle creating service downtime."""
        try:
            params = analysis.get('parameters', {})
            host_name = params.get('host_name')
            service_desc = params.get('service_description')
            duration_hours = params.get('duration_hours')
            comment = params.get('comment') or 'Downtime created via LLM Agent'
            
            if not host_name or not service_desc:
                return "❌ Please specify both host name and service description"
            
            # Handle duration_hours
            if duration_hours is None or not isinstance(duration_hours, (int, float)):
                duration_hours = 2  # Default to 2 hours
            
            # Ensure comment is a string
            if not isinstance(comment, str):
                comment = 'Downtime created via LLM Agent'
            
            # Calculate start and end times
            start_time = datetime.now()
            end_time = start_time + timedelta(hours=duration_hours)
            
            self.checkmk_client.create_service_downtime(
                host_name=host_name,
                service_description=service_desc,
                start_time=start_time.isoformat(),
                end_time=end_time.isoformat(),
                comment=comment
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
            params = analysis.get('parameters', {})
            host_name = params.get('host_name')
            mode = params.get('mode') or 'refresh'  # Handle None values
            
            if not host_name:
                return "❌ Please specify a host name"
            
            # Ensure mode is a valid string and normalize it
            if not isinstance(mode, str):
                mode = 'refresh'
            
            # Map common mode variations to valid values
            mode_mapping = {
                'discovery': 'refresh',
                'scan': 'refresh',
                'find': 'refresh',
                'detect': 'refresh',
                'new': 'new',
                'add': 'new',
                'refresh': 'refresh',
                'remove': 'remove',
                'delete': 'remove',
                'fixall': 'fixall',
                'fix': 'fixall',
                'refresh_autochecks': 'refresh_autochecks'
            }
            
            # Normalize the mode
            mode = mode_mapping.get(mode.lower(), 'refresh')
            
            # Start service discovery
            result = self.checkmk_client.start_service_discovery(host_name, mode)
            
            # Get discovery results
            discovery_result = self.checkmk_client.get_service_discovery_result(host_name)
            
            # Format response
            extensions = discovery_result.get('extensions', {})
            vanished = extensions.get('vanished', [])
            new = extensions.get('new', [])
            ignored = extensions.get('ignored', [])
            
            response = f"🔍 Service discovery completed for host: {host_name}\n\n"
            
            if new:
                response += f"✨ New services found ({len(new)}):\n"
                for service in new:
                    service_desc = service.get('service_description', 'Unknown')
                    response += f"  + {service_desc}\n"
                response += "\n"
            
            if vanished:
                response += f"👻 Vanished services ({len(vanished)}):\n"
                for service in vanished:
                    service_desc = service.get('service_description', 'Unknown')
                    response += f"  - {service_desc}\n"
                response += "\n"
            
            if ignored:
                response += f"🚫 Ignored services ({len(ignored)}):\n"
                for service in ignored:
                    service_desc = service.get('service_description', 'Unknown')
                    response += f"  ! {service_desc}\n"
                response += "\n"
            
            if not new and not vanished and not ignored:
                response += "✅ No service changes detected"
            
            return response
            
        except CheckmkAPIError as e:
            return f"❌ Error discovering services: {e}"
    
    def _handle_get_instructions(self, analysis: Dict[str, Any]) -> str:
        """Handle requests for instructions on how to perform service operations."""
        params = analysis.get('parameters', {})
        instruction_type = params.get('instruction_type', '')
        host_name = params.get('host_name', '')
        
        if instruction_type == 'add_service':
            return f"""📖 How to add a service to {host_name if host_name else 'a host'}:

**Method 1: Service Discovery (Recommended)**
1. Run service discovery to automatically detect services:
   • CLI: `checkmk-agent services discover {host_name if host_name else 'HOSTNAME'}`
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
• Run: `checkmk-agent services discover {host_name if host_name else 'HOSTNAME'}` to start
• Or ask: "discover services on {host_name if host_name else 'HOSTNAME'}" for automatic discovery"""

        elif instruction_type == 'acknowledge_service':
            return """📖 How to acknowledge a service problem:

**Purpose:** Acknowledging a service tells Checkmk that you're aware of the problem and working on it.

**Methods:**
1. **CLI Command:**
   `checkmk-agent services acknowledge HOSTNAME SERVICE_NAME "Your comment"`

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

        elif instruction_type == 'create_downtime':
            return """📖 How to schedule service downtime:

**Purpose:** Schedule planned maintenance windows to suppress alerts.

**Methods:**
1. **CLI Command:**
   `checkmk-agent services downtime HOSTNAME SERVICE_NAME HOURS "Comment"`

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
            'OK': '✅',
            'WARN': '⚠️',
            'CRIT': '❌',
            'UNKNOWN': '❓',
            'PENDING': '⏳',
            0: '✅',  # OK
            1: '⚠️',  # WARN
            2: '❌',  # CRIT
            3: '❓',  # UNKNOWN
        }
        return state_map.get(state, '❓')
    
    def get_service_statistics(self) -> str:
        """Get service statistics across all hosts."""
        try:
            services = self.checkmk_client.list_all_services()
            
            if not services:
                return "📊 No services found"
            
            # Count by state
            state_counts = {}
            hosts = set()
            
            for service in services:
                extensions = service.get('extensions', {})
                state = extensions.get('state', 'Unknown')
                host = extensions.get('host_name', 'Unknown')
                
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
            services = self.checkmk_client.list_all_services()
            return f"✅ Connection successful. Found {len(services)} services."
        except CheckmkAPIError as e:
            return f"❌ Connection failed: {e}"