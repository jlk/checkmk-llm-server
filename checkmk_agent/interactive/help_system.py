"""Comprehensive help system with contextual and searchable help."""

import re
from typing import Dict, List, Optional, Any
from dataclasses import dataclass


@dataclass
class HelpContent:
    """Represents help content for a command or topic."""
    title: str
    description: str
    usage: List[str]
    examples: List[str]
    related: List[str]
    aliases: List[str]


class HelpSystem:
    """Comprehensive help system with contextual and searchable help."""
    
    def __init__(self):
        """Initialize the help system."""
        self.help_content = self._initialize_help_content()
        self.command_categories = {
            'Host Management': ['list', 'create', 'delete', 'get', 'show'],
            'Service Management': ['services', 'acknowledge', 'downtime', 'discover', 'status'],
            'System': ['help', 'stats', 'test', 'exit', 'quit'],
            'Special': ['?', 'h', 'man']
        }
    
    def _initialize_help_content(self) -> Dict[str, HelpContent]:
        """Initialize help content database."""
        return {
            'general': HelpContent(
                title="Checkmk LLM Agent - Interactive Mode",
                description="Natural language interface for Checkmk monitoring system",
                usage=[
                    "Type commands in natural language",
                    "Use ? or help for assistance",
                    "Use tab completion for commands"
                ],
                examples=[
                    "list all hosts",
                    "create host server01 in folder /web",
                    "show services for server01",
                    "acknowledge CPU load on server01"
                ],
                related=['hosts', 'services', 'help'],
                aliases=['?', 'help', 'h']
            ),
            
            'hosts': HelpContent(
                title="Host Management Commands",
                description="Commands for managing Checkmk hosts",
                usage=[
                    "list [all] hosts",
                    "show hosts like <search_term>",
                    "find hosts containing <search_term>",
                    "search hosts matching <search_term>",
                    "create host <name> [in folder <path>] [with ip <address>]",
                    "delete host <name>",
                    "show details for <name>",
                    "get host <name>"
                ],
                examples=[
                    "list all hosts",
                    "show hosts like piaware",
                    "find hosts containing web",
                    "search hosts matching db",
                    "hosts similar to test",
                    "show hosts in folder /web",
                    "create host server01 in folder /web with ip 192.168.1.10",
                    "delete host server01",
                    "show details for server01"
                ],
                related=['services', 'create', 'delete', 'list'],
                aliases=['host', 'server', 'machine']
            ),
            
            'services': HelpContent(
                title="Service Management Commands", 
                description="Commands for monitoring and managing services",
                usage=[
                    "list services [for <host>]",
                    "show services [for <host>]",
                    "acknowledge <service> on <host>",
                    "create downtime for <service> on <host>",
                    "discover services on <host>"
                ],
                examples=[
                    "list services for server01",
                    "show all services",
                    "acknowledge CPU load on server01",
                    "create 4 hour downtime for disk space on server01",
                    "discover services on server01"
                ],
                related=['hosts', 'acknowledge', 'downtime', 'discover'],
                aliases=['service', 'svc']
            ),
            
            'acknowledge': HelpContent(
                title="Acknowledge Service Problems",
                description="Acknowledge service problems to suppress notifications",
                usage=[
                    "acknowledge <service> on <host>",
                    "ack <service> on <host> [with comment \"<text>\"]"
                ],
                examples=[
                    "acknowledge CPU load on server01",
                    "ack disk space on server01 with comment \"investigating\"",
                    "acknowledge Memory on web01"
                ],
                related=['services', 'downtime'],
                aliases=['ack']
            ),
            
            'downtime': HelpContent(
                title="Service Downtime Management",
                description="Schedule downtime periods for planned maintenance",
                usage=[
                    "create downtime for <service> on <host>",
                    "create <X> hour downtime for <service> on <host>",
                    "downtime <service> on <host> [for <X> hours]"
                ],
                examples=[
                    "create downtime for CPU utilization on server01",
                    "create 4 hour downtime for disk space on server01",
                    "downtime Memory on web01 for 2 hours"
                ],
                related=['services', 'acknowledge'],
                aliases=['dt']
            ),
            
            'discover': HelpContent(
                title="Service Discovery",
                description="Discover new services on hosts",
                usage=[
                    "discover services on <host>",
                    "find services on <host>",
                    "scan <host>"
                ],
                examples=[
                    "discover services on server01",
                    "find services on web01",
                    "scan db01"
                ],
                related=['services', 'hosts'],
                aliases=['find', 'scan']
            ),
            
            'create': HelpContent(
                title="Create Resources",
                description="Create new hosts or other resources",
                usage=[
                    "create host <name> [in folder <path>] [with ip <address>]",
                    "add host <name> [in folder <path>] [with ip <address>]",
                    "new host <name> [in folder <path>] [with ip <address>]"
                ],
                examples=[
                    "create host server01",
                    "create host web01 in folder /web",
                    "create host db01 in folder /database with ip 192.168.1.20",
                    "add host app01 with ip 10.0.0.5"
                ],
                related=['hosts', 'delete', 'list'],
                aliases=['add', 'new']
            ),
            
            'delete': HelpContent(
                title="Delete Resources",
                description="Delete hosts or other resources",
                usage=[
                    "delete host <name>",
                    "remove host <name>",
                    "destroy host <name>"
                ],
                examples=[
                    "delete host server01",
                    "remove host old-server",
                    "destroy host test-host"
                ],
                related=['hosts', 'create', 'list'],
                aliases=['remove', 'destroy', 'rm', 'del']
            ),
            
            'list': HelpContent(
                title="List Resources",
                description="List hosts, services, or other resources with optional search/filtering",
                usage=[
                    "list [all] hosts",
                    "show [all] hosts",
                    "find hosts like <search_term>",
                    "search hosts containing <search_term>",
                    "list services [for <host>]",
                    "show services [for <host>]"
                ],
                examples=[
                    "list all hosts",
                    "show hosts",
                    "find hosts like piaware",
                    "search hosts containing web",
                    "show hosts matching db",
                    "list services for server01",
                    "show all services"
                ],
                related=['hosts', 'services', 'get'],
                aliases=['show', 'display', 'ls', 'find', 'search']
            ),
            
            'get': HelpContent(
                title="Get Details",
                description="Get detailed information about resources",
                usage=[
                    "get host <name>",
                    "show details for <name>",
                    "info <name>"
                ],
                examples=[
                    "get host server01",
                    "show details for web01",
                    "info db01"
                ],
                related=['hosts', 'list'],
                aliases=['info', 'details', 'show']
            ),
            
            'stats': HelpContent(
                title="Statistics",
                description="Show system statistics and summaries",
                usage=[
                    "stats",
                    "statistics",
                    "show stats"
                ],
                examples=[
                    "stats",
                    "statistics",
                    "show stats"
                ],
                related=['hosts', 'services'],
                aliases=['statistics']
            ),
            
            'test': HelpContent(
                title="Test Connection",
                description="Test connection to Checkmk API",
                usage=[
                    "test",
                    "test connection",
                    "check connection"
                ],
                examples=[
                    "test",
                    "test connection",
                    "check connection"
                ],
                related=['stats'],
                aliases=['check']
            ),
            
            'help': HelpContent(
                title="Help System",
                description="Get help on commands and topics",
                usage=[
                    "help [<command>]",
                    "? [<command>]",
                    "h [<command>]",
                    "man <command>"
                ],
                examples=[
                    "help",
                    "? hosts",
                    "help services",
                    "man create"
                ],
                related=['general'],
                aliases=['?', 'h', 'man']
            ),
            
            'find': HelpContent(
                title="Find/Search Resources",
                description="Search for hosts, services, or other resources using various patterns",
                usage=[
                    "find hosts like <search_term>",
                    "search hosts containing <search_term>",
                    "show hosts matching <search_term>",
                    "hosts similar to <search_term>",
                    "hosts called <search_term>",
                    "hosts named <search_term>"
                ],
                examples=[
                    "find hosts like piaware",
                    "search hosts containing web",
                    "show hosts matching db",
                    "hosts similar to test",
                    "hosts called proxy",
                    "hosts named mail"
                ],
                related=['list', 'hosts', 'show'],
                aliases=['search', 'like', 'containing', 'matching', 'similar']
            ),
            
            'search': HelpContent(
                title="Search Resources",
                description="Search and filter resources using natural language patterns",
                usage=[
                    "search hosts like <term>",
                    "search hosts containing <term>",
                    "search hosts matching <term>",
                    "search for <term>"
                ],
                examples=[
                    "search hosts like piaware",
                    "search hosts containing production",
                    "search hosts matching web",
                    "search for backup"
                ],
                related=['find', 'list', 'hosts'],
                aliases=['find', 'like', 'containing', 'matching']
            ),
            
            'exit': HelpContent(
                title="Exit Interactive Mode",
                description="Exit the interactive mode",
                usage=[
                    "exit",
                    "quit",
                    "q"
                ],
                examples=[
                    "exit",
                    "quit",
                    "q"
                ],
                related=[],
                aliases=['quit', 'q']
            )
        }
    
    def show_help(self, topic: Optional[str] = None) -> str:
        """Show help for a specific topic or general help.
        
        Args:
            topic: Specific topic to show help for
            
        Returns:
            Formatted help text
        """
        if not topic:
            return self._show_general_help()
        
        # Normalize topic
        topic = topic.lower().strip()
        
        # Find exact match
        if topic in self.help_content:
            return self._format_help_content(self.help_content[topic])
        
        # Find by alias
        for cmd, content in self.help_content.items():
            if topic in content.aliases:
                return self._format_help_content(content)
        
        # Find partial matches
        matches = []
        for cmd, content in self.help_content.items():
            if topic in cmd or cmd in topic:
                matches.append(cmd)
        
        if len(matches) == 1:
            return self._format_help_content(self.help_content[matches[0]])
        elif len(matches) > 1:
            return self._show_ambiguous_help(topic, matches)
        
        return self._show_no_help_found(topic)
    
    def _show_general_help(self) -> str:
        """Show general help overview."""
        general_content = self.help_content['general']
        help_text = f"""
🔧 {general_content.title}
{'=' * 50}

{general_content.description}

📋 Available Commands by Category:
"""
        
        for category, commands in self.command_categories.items():
            help_text += f"\n📁 {category}:\n"
            for cmd in commands:
                if cmd in self.help_content:
                    content = self.help_content[cmd]
                    help_text += f"  • {cmd:<12} - {content.description}\n"
        
        help_text += f"""
💡 Quick Start:
"""
        for example in general_content.examples:
            help_text += f"  🔧 checkmk> {example}\n"
        
        help_text += f"""
🆘 Getting Help:
  • ?                    - Show this help
  • ? <command>          - Show help for specific command
  • help <command>       - Show help for specific command
  • Tab                  - Auto-complete commands
  • Up/Down arrows       - Navigate command history
  
🚪 Exit: Type 'exit', 'quit', or press Ctrl+C
"""
        
        return help_text
    
    def _format_help_content(self, content: HelpContent) -> str:
        """Format help content for display.
        
        Args:
            content: HelpContent object to format
            
        Returns:
            Formatted help text
        """
        help_text = f"""
🔧 {content.title}
{'=' * 50}

📝 Description:
{content.description}

📋 Usage:
"""
        
        for usage in content.usage:
            help_text += f"  🔧 checkmk> {usage}\n"
        
        help_text += "\n💡 Examples:\n"
        for example in content.examples:
            help_text += f"  🔧 checkmk> {example}\n"
        
        if content.aliases:
            help_text += f"\n🔗 Aliases: {', '.join(content.aliases)}\n"
        
        if content.related:
            help_text += f"\n📚 Related Commands: {', '.join(content.related)}\n"
        
        help_text += f"\n💡 Tip: Use '? <command>' for help on specific commands\n"
        
        return help_text
    
    def _show_ambiguous_help(self, topic: str, matches: List[str]) -> str:
        """Show help for ambiguous topic matches.
        
        Args:
            topic: Original topic searched
            matches: List of matching command names
            
        Returns:
            Formatted help text for ambiguous matches
        """
        help_text = f"""
❓ Multiple matches found for '{topic}':

"""
        
        for match in matches:
            if match in self.help_content:
                content = self.help_content[match]
                help_text += f"  • {match:<12} - {content.description}\n"
        
        help_text += f"""
💡 Be more specific:
"""
        for match in matches:
            help_text += f"  🔧 checkmk> ? {match}\n"
        
        return help_text
    
    def _show_no_help_found(self, topic: str) -> str:
        """Show message when no help is found.
        
        Args:
            topic: Topic that was searched
            
        Returns:
            No help found message
        """
        # Suggest similar commands
        all_commands = list(self.help_content.keys())
        all_aliases = []
        for content in self.help_content.values():
            all_aliases.extend(content.aliases)
        
        import difflib
        suggestions = difflib.get_close_matches(
            topic, 
            all_commands + all_aliases, 
            n=3, 
            cutoff=0.4
        )
        
        help_text = f"""
❌ No help found for '{topic}'

"""
        
        if suggestions:
            help_text += "🔍 Did you mean:\n"
            for suggestion in suggestions:
                help_text += f"  • {suggestion}\n"
            help_text += "\n"
        
        help_text += """💡 Available topics:
  • ? hosts          - Host management
  • ? services       - Service management  
  • ? acknowledge    - Acknowledge problems
  • ? downtime       - Create downtime
  • ? discover       - Service discovery
  • ?                - General help

💡 Or try: 'help' for full command overview
"""
        
        return help_text
    
    def search_help(self, query: str) -> str:
        """Search help content for a query.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        query = query.lower()
        results = []
        
        for cmd, content in self.help_content.items():
            score = 0
            
            # Check title
            if query in content.title.lower():
                score += 10
            
            # Check description
            if query in content.description.lower():
                score += 5
            
            # Check usage
            for usage in content.usage:
                if query in usage.lower():
                    score += 3
            
            # Check examples
            for example in content.examples:
                if query in example.lower():
                    score += 2
            
            # Check aliases
            for alias in content.aliases:
                if query in alias.lower():
                    score += 1
            
            if score > 0:
                results.append((cmd, content, score))
        
        # Sort by score
        results.sort(key=lambda x: x[2], reverse=True)
        
        if not results:
            return f"❌ No help found for search: '{query}'"
        
        help_text = f"🔍 Search results for '{query}':\n\n"
        
        for cmd, content, score in results[:5]:  # Show top 5 results
            help_text += f"• {cmd:<12} - {content.description}\n"
        
        if len(results) > 5:
            help_text += f"\n... and {len(results) - 5} more results\n"
        
        help_text += f"\n💡 Use '? <command>' for detailed help on any command\n"
        
        return help_text
    
    def get_command_suggestions(self, partial_command: str) -> List[str]:
        """Get command suggestions for partial input.
        
        Args:
            partial_command: Partial command string
            
        Returns:
            List of suggested commands
        """
        suggestions = []
        partial = partial_command.lower()
        
        # Exact prefix matches
        for cmd in self.help_content:
            if cmd.startswith(partial):
                suggestions.append(cmd)
        
        # Alias matches
        for cmd, content in self.help_content.items():
            for alias in content.aliases:
                if alias.startswith(partial):
                    suggestions.append(alias)
        
        # Fuzzy matches
        if len(suggestions) < 5:
            import difflib
            all_commands = list(self.help_content.keys())
            all_aliases = []
            for content in self.help_content.values():
                all_aliases.extend(content.aliases)
            
            fuzzy_matches = difflib.get_close_matches(
                partial, 
                all_commands + all_aliases, 
                n=5 - len(suggestions), 
                cutoff=0.3
            )
            
            for match in fuzzy_matches:
                if match not in suggestions:
                    suggestions.append(match)
        
        return suggestions[:5]