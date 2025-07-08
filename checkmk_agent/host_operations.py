"""Host operations module combining Checkmk API with LLM processing."""

import logging
from typing import Dict, List, Optional, Any

from .api_client import CheckmkClient, CheckmkAPIError
from .llm_client import LLMClient, HostOperation, ParsedCommand
from .config import AppConfig
from .utils import validate_hostname, sanitize_folder_path


class HostOperationsManager:
    """Manages host operations with natural language processing."""
    
    def __init__(self, checkmk_client: CheckmkClient, llm_client: LLMClient, config: AppConfig):
        self.checkmk = checkmk_client
        self.llm = llm_client
        self.config = config
        self.logger = logging.getLogger(__name__)
    
    def process_command(self, user_input: str) -> str:
        """Process natural language command and execute appropriate operation."""
        try:
            # Parse the command using LLM
            parsed_command = self.llm.parse_command(user_input)
            self.logger.info(f"Parsed command: {parsed_command}")
            
            # Execute the operation
            result = self._execute_operation(parsed_command)
            
            # Format response using LLM
            return self.llm.format_response(
                parsed_command.operation, 
                result, 
                success=True
            )
            
        except Exception as e:
            self.logger.error(f"Command processing failed: {e}")
            return self.llm.format_response(
                HostOperation.LIST,  # Default operation for error formatting
                None,
                success=False,
                error=str(e)
            )
    
    def _execute_operation(self, command: ParsedCommand) -> Any:
        """Execute the parsed command operation."""
        if command.operation == HostOperation.LIST:
            return self._list_hosts(command.parameters)
        
        elif command.operation == HostOperation.CREATE:
            return self._create_host(command.parameters)
        
        elif command.operation == HostOperation.DELETE:
            return self._delete_host(command.parameters)
        
        elif command.operation == HostOperation.GET:
            return self._get_host(command.parameters)
        
        elif command.operation == HostOperation.UPDATE:
            return self._update_host(command.parameters)
        
        else:
            raise ValueError(f"Unsupported operation: {command.operation}")
    
    def _list_hosts(self, parameters: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List hosts with optional filtering."""
        effective_attributes = parameters.get("effective_attributes", False)
        search_term = parameters.get("search_term")
        
        hosts = self.checkmk.list_hosts(effective_attributes=effective_attributes)
        
        # Apply search filtering if provided
        if search_term:
            search_term_lower = search_term.lower()
            filtered_hosts = []
            
            for host in hosts:
                host_id = host.get("id", "").lower()
                extensions = host.get("extensions", {})
                folder = extensions.get("folder", "").lower()
                attributes = extensions.get("attributes", {})
                alias = attributes.get("alias", "").lower()
                
                if (search_term_lower in host_id or 
                    search_term_lower in folder or 
                    search_term_lower in alias):
                    filtered_hosts.append(host)
            
            hosts = filtered_hosts
        
        return hosts
    
    def _create_host(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new host."""
        host_name = parameters.get("host_name")
        if not host_name:
            raise ValueError("Host name is required for creation")
        
        # Validate hostname
        if not validate_hostname(host_name):
            raise ValueError(f"Invalid hostname format: {host_name}")
        
        folder = sanitize_folder_path(parameters.get("folder", self.config.default_folder))
        attributes = parameters.get("attributes", {})
        bake_agent = parameters.get("bake_agent", False)
        
        # Add common attributes if not specified
        if "ipaddress" in parameters and "ipaddress" not in attributes:
            attributes["ipaddress"] = parameters["ipaddress"]
        
        if "alias" in parameters and "alias" not in attributes:
            attributes["alias"] = parameters["alias"]
        
        return self.checkmk.create_host(
            folder=folder,
            host_name=host_name,
            attributes=attributes,
            bake_agent=bake_agent
        )
    
    def _delete_host(self, parameters: Dict[str, Any]) -> None:
        """Delete a host."""
        host_name = parameters.get("host_name")
        if not host_name:
            raise ValueError("Host name is required for deletion")
        
        # Check if host exists first
        try:
            self.checkmk.get_host(host_name)
        except CheckmkAPIError as e:
            if e.status_code == 404:
                raise ValueError(f"Host '{host_name}' not found")
            raise
        
        self.checkmk.delete_host(host_name)
    
    def _get_host(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get host details."""
        host_name = parameters.get("host_name")
        if not host_name:
            raise ValueError("Host name is required")
        
        effective_attributes = parameters.get("effective_attributes", False)
        
        return self.checkmk.get_host(host_name, effective_attributes=effective_attributes)
    
    def _update_host(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Update host configuration."""
        host_name = parameters.get("host_name")
        if not host_name:
            raise ValueError("Host name is required for update")
        
        attributes = parameters.get("attributes", {})
        if not attributes:
            raise ValueError("Attributes are required for update")
        
        etag = parameters.get("etag")
        
        return self.checkmk.update_host(host_name, attributes, etag=etag)
    
    def test_connection(self) -> str:
        """Test connection to Checkmk and return status."""
        try:
            if self.checkmk.test_connection():
                return "✅ Successfully connected to Checkmk API"
            else:
                return "❌ Failed to connect to Checkmk API"
        except Exception as e:
            return f"❌ Connection test failed: {e}"
    
    def get_host_statistics(self) -> str:
        """Get basic statistics about hosts."""
        try:
            hosts = self.checkmk.list_hosts()
            total_hosts = len(hosts)
            
            # Count by folder
            folder_counts = {}
            cluster_count = 0
            offline_count = 0
            
            for host in hosts:
                extensions = host.get("extensions", {})
                folder = extensions.get("folder", "/")
                
                folder_counts[folder] = folder_counts.get(folder, 0) + 1
                
                if extensions.get("is_cluster", False):
                    cluster_count += 1
                
                if extensions.get("is_offline", False):
                    offline_count += 1
            
            # Format statistics
            stats = [f"📊 Host Statistics:"]
            stats.append(f"Total hosts: {total_hosts}")
            stats.append(f"Cluster hosts: {cluster_count}")
            stats.append(f"Offline hosts: {offline_count}")
            stats.append("")
            stats.append("Hosts by folder:")
            
            for folder, count in sorted(folder_counts.items()):
                stats.append(f"  {folder}: {count}")
            
            return "\n".join(stats)
            
        except Exception as e:
            return f"❌ Failed to get host statistics: {e}"
    
    def interactive_create_host(self) -> str:
        """Interactive host creation with prompts."""
        logger = logging.getLogger(__name__)
        try:
            logger.info("🔧 Interactive Host Creation")
            logger.info("=" * 30)
            
            # Get host name
            while True:
                host_name = input("Host name: ").strip()
                if host_name:
                    if validate_hostname(host_name):
                        break
                    else:
                        logger.warning("❌ Invalid hostname format. Use only letters, numbers, dots, hyphens, and underscores.")
                else:
                    logger.warning("❌ Host name is required.")
            
            # Get folder
            folder = input(f"Folder (default: {self.config.default_folder}): ").strip()
            if not folder:
                folder = self.config.default_folder
            folder = sanitize_folder_path(folder)
            
            # Get optional attributes
            attributes = {}
            
            ip_address = input("IP address (optional): ").strip()
            if ip_address:
                attributes["ipaddress"] = ip_address
            
            alias = input("Alias/Description (optional): ").strip()
            if alias:
                attributes["alias"] = alias
            
            # Confirm creation
            logger.info(f"\n📋 Host Configuration:")
            logger.info(f"  Name: {host_name}")
            logger.info(f"  Folder: {folder}")
            if attributes:
                logger.info(f"  Attributes: {attributes}")
            
            confirm = input("\nCreate this host? (y/N): ").strip().lower()
            if confirm != 'y':
                return "❌ Host creation cancelled."
            
            # Create the host
            result = self.checkmk.create_host(
                folder=folder,
                host_name=host_name,
                attributes=attributes
            )
            
            return f"✅ Successfully created host: {host_name}"
            
        except KeyboardInterrupt:
            return "\n❌ Host creation cancelled."
        except Exception as e:
            return f"❌ Failed to create host: {e}"