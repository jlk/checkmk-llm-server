"""UI management for enhanced interactive mode."""

import sys
from typing import Optional, List, Dict, Any
from .color_manager import ColorManager, MessageType


class UIManager:
    """Manages UI formatting and user interaction."""
    
    def __init__(self, theme: str = "default", use_colors: Optional[bool] = None, custom_colors: Optional[Dict[str, str]] = None):
        """Initialize UI manager.
        
        Args:
            theme: Color theme to use
            use_colors: Whether to use colored output (auto-detect if None)
            custom_colors: Custom color overrides
        """
        self.color_manager = ColorManager(
            theme=theme,
            use_colors=use_colors,
            custom_colors=custom_colors
        )
        self.use_colors = self.color_manager.use_colors
    
    def colorize(self, text: str, color: str) -> str:
        """Apply color to text.
        
        Args:
            text: Text to colorize
            color: Color name
            
        Returns:
            Colored text or original text if colors disabled
        """
        return self.color_manager.colorize(text, color)
    
    def format_message(self, message: str, msg_type: MessageType = MessageType.INFO) -> str:
        """Format a message with appropriate styling.
        
        Args:
            message: Message text
            msg_type: Type of message
            
        Returns:
            Formatted message
        """
        icon = self.color_manager.get_message_icon(msg_type)
        color = self.color_manager.get_message_color(msg_type)
        
        # Format the message
        if self.use_colors:
            formatted = f"{icon} {self.colorize(message, color)}"
        else:
            formatted = f"{icon} {message}"
        
        return formatted
    
    def print_message(self, message: str, msg_type: MessageType = MessageType.INFO) -> None:
        """Print a formatted message.
        
        Args:
            message: Message text
            msg_type: Type of message
        """
        print(self.format_message(message, msg_type))
    
    def print_success(self, message: str) -> None:
        """Print a success message."""
        self.print_message(message, MessageType.SUCCESS)
    
    def print_error(self, message: str) -> None:
        """Print an error message."""
        self.print_message(message, MessageType.ERROR)
    
    def print_warning(self, message: str) -> None:
        """Print a warning message."""
        self.print_message(message, MessageType.WARNING)
    
    def print_info(self, message: str) -> None:
        """Print an info message."""
        self.print_message(message, MessageType.INFO)
    
    def print_help(self, message: str) -> None:
        """Print a help message."""
        self.print_message(message, MessageType.HELP)
    
    def format_prompt(self, prompt: str = "checkmk") -> str:
        """Format the command prompt.
        
        Args:
            prompt: Base prompt text
            
        Returns:
            Formatted prompt
        """
        icon = self.color_manager.get_message_icon(MessageType.PROMPT)
        prompt_color = self.color_manager.get_message_color(MessageType.PROMPT)
        
        if self.use_colors:
            colored_prompt = self.colorize(prompt, prompt_color)
            return f"{icon} {colored_prompt}> "
        else:
            return f"{icon} {prompt}> "
    
    def print_welcome(self) -> None:
        """Print welcome message for interactive mode."""
        welcome_text = """
🤖 Checkmk LLM Agent - Enhanced Interactive Mode
{'=' * 50}

🚀 New Features:
  • Enhanced help system - Type '?' for help
  • Command history - Use Up/Down arrows
  • Tab completion - Press Tab to autocomplete
  • Fuzzy command matching - Typos are handled gracefully

💡 Quick Start:
  • ?                    - Show help
  • ? hosts              - Help for host commands
  • ? services           - Help for service commands
  • Tab                  - Complete current command
  • Up/Down              - Navigate command history
  • list all hosts       - List all hosts
  • show services        - Show all services

🚪 Exit: Type 'exit', 'quit', or press Ctrl+C
"""
        
        print(welcome_text)
    
    def print_goodbye(self) -> None:
        """Print goodbye message."""
        goodbye_text = "👋 Goodbye! Thanks for using Checkmk LLM Agent!"
        self.print_message(goodbye_text, MessageType.SUCCESS)
    
    def format_command_suggestions(self, suggestions: List[str]) -> str:
        """Format command suggestions.
        
        Args:
            suggestions: List of command suggestions
            
        Returns:
            Formatted suggestions text
        """
        if not suggestions:
            return ""
        
        text = "💡 Did you mean:\n"
        for suggestion in suggestions:
            text += f"  • {suggestion}\n"
        
        return text
    
    def format_error_with_suggestions(self, error: str, suggestions: List[str]) -> str:
        """Format error message with suggestions.
        
        Args:
            error: Error message
            suggestions: List of suggestions
            
        Returns:
            Formatted error with suggestions
        """
        formatted_error = self.format_message(error, MessageType.ERROR)
        
        if suggestions:
            formatted_error += "\n" + self.format_command_suggestions(suggestions)
        
        return formatted_error
    
    def format_host_list(self, hosts: List[Dict[str, Any]]) -> str:
        """Format host list for display.
        
        Args:
            hosts: List of host dictionaries
            
        Returns:
            Formatted host list
        """
        if not hosts:
            return self.format_message("No hosts found.", MessageType.INFO)
        
        text = f"📦 Found {len(hosts)} hosts:\n\n"
        
        for host in hosts:
            host_id = host.get("id", "Unknown")
            extensions = host.get("extensions", {})
            host_folder = extensions.get("folder", "Unknown")
            attributes = extensions.get("attributes", {})
            ip_address = attributes.get("ipaddress", "Not set")
            
            # Format host entry
            text += f"  📦 {self.colorize(host_id, 'bold')}\n"
            text += f"     📁 Folder: {host_folder}\n"
            text += f"     🌐 IP: {ip_address}\n"
            
            if extensions.get("is_cluster"):
                text += f"     🏗️  Type: Cluster\n"
            if extensions.get("is_offline"):
                text += f"     ⚠️  Status: Offline\n"
            
            text += "\n"
        
        return text
    
    def format_service_list(self, services: List[Dict[str, Any]], host_name: Optional[str] = None) -> str:
        """Format service list for display.
        
        Args:
            services: List of service dictionaries
            host_name: Optional host name for context
            
        Returns:
            Formatted service list
        """
        if not services:
            if host_name:
                return self.format_message(f"No services found for host: {host_name}", MessageType.INFO)
            else:
                return self.format_message("No services found.", MessageType.INFO)
        
        if host_name:
            text = f"🔧 Found {len(services)} services for host: {self.colorize(host_name, 'bold')}\n\n"
        else:
            text = f"🔧 Found {len(services)} services:\n\n"
        
        for service in services:
            extensions = service.get('extensions', {})
            service_desc = extensions.get('description', 'Unknown')
            service_state = extensions.get('state', 'Unknown')
            host = extensions.get('host_name', host_name or 'Unknown')
            
            # Choose icon based on state
            if service_state == 'OK' or service_state == 0:
                state_icon = '✅'
                state_color = 'green'
            elif service_state == 'WARNING' or service_state == 1:
                state_icon = '⚠️'
                state_color = 'yellow'
            elif service_state == 'CRITICAL' or service_state == 2:
                state_icon = '❌'
                state_color = 'red'
            else:
                state_icon = '❓'
                state_color = 'white'
            
            # Format service entry
            text += f"  {state_icon} {self.colorize(host, 'bold')}/{service_desc} - "
            text += f"{self.colorize(str(service_state), state_color)}\n"
        
        return text
    
    def format_progress_indicator(self, message: str, show_spinner: bool = True) -> str:
        """Format progress indicator.
        
        Args:
            message: Progress message
            show_spinner: Whether to show spinner
            
        Returns:
            Formatted progress message
        """
        if show_spinner:
            return f"🔄 {message}..."
        else:
            return f"⏳ {message}..."
    
    def confirm_action(self, message: str) -> bool:
        """Ask for user confirmation.
        
        Args:
            message: Confirmation message
            
        Returns:
            True if user confirms, False otherwise
        """
        prompt = f"⚠️  {message} (y/N): "
        
        try:
            response = input(prompt).strip().lower()
            return response in ['y', 'yes']
        except (KeyboardInterrupt, EOFError):
            return False
    
    def format_statistics(self, stats: Dict[str, Any]) -> str:
        """Format statistics for display.
        
        Args:
            stats: Statistics dictionary
            
        Returns:
            Formatted statistics text
        """
        text = "📊 Statistics:\n\n"
        
        for key, value in stats.items():
            # Format key
            formatted_key = key.replace('_', ' ').title()
            text += f"  📈 {formatted_key}: {self.colorize(str(value), 'bold')}\n"
        
        return text
    
    def format_table(self, headers: List[str], rows: List[List[str]]) -> str:
        """Format data as a table.
        
        Args:
            headers: Table headers
            rows: Table rows
            
        Returns:
            Formatted table
        """
        if not rows:
            return self.format_message("No data to display.", MessageType.INFO)
        
        # Calculate column widths
        widths = [len(header) for header in headers]
        for row in rows:
            for i, cell in enumerate(row):
                if i < len(widths):
                    widths[i] = max(widths[i], len(str(cell)))
        
        # Format table
        text = ""
        
        # Header
        header_row = " | ".join(
            header.ljust(width) for header, width in zip(headers, widths)
        )
        text += f"{self.colorize(header_row, 'bold')}\n"
        
        # Separator
        separator = " | ".join("-" * width for width in widths)
        text += f"{separator}\n"
        
        # Rows
        for row in rows:
            formatted_row = " | ".join(
                str(cell).ljust(width) for cell, width in zip(row, widths)
            )
            text += f"{formatted_row}\n"
        
        return text
    
    def truncate_text(self, text: str, max_length: int = 80) -> str:
        """Truncate text to maximum length.
        
        Args:
            text: Text to truncate
            max_length: Maximum length
            
        Returns:
            Truncated text
        """
        if len(text) <= max_length:
            return text
        
        return text[:max_length - 3] + "..."
    
    # Theme management methods
    def set_theme(self, theme_name: str) -> bool:
        """Change current theme.
        
        Args:
            theme_name: Name of theme to set
            
        Returns:
            True if theme was set successfully, False otherwise
        """
        return self.color_manager.set_theme(theme_name)
    
    def get_current_theme(self) -> str:
        """Get current theme name.
        
        Returns:
            Current theme name
        """
        return self.color_manager.get_current_theme_name()
    
    def list_themes(self) -> List[Dict[str, str]]:
        """List available themes.
        
        Returns:
            List of theme info dictionaries
        """
        return self.color_manager.list_themes()
    
    def preview_colors(self) -> str:
        """Generate color preview text.
        
        Returns:
            Formatted preview text showing all colors
        """
        return self.color_manager.preview_colors()
    
    def test_colors(self) -> str:
        """Test color combinations.
        
        Returns:
            Test output with various color combinations
        """
        return self.color_manager.test_colors()
    
    def get_terminal_info(self) -> str:
        """Get terminal capability information.
        
        Returns:
            Formatted terminal information
        """
        return self.color_manager.get_terminal_info()