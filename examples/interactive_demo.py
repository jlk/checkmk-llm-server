#!/usr/bin/env python3
"""Demonstration of the interactive mode features."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from checkmk_mcp_server.interactive import ReadlineHandler, CommandParser, HelpSystem, TabCompleter, UIManager

def demonstrate_help_system():
    """Demonstrate the help system."""
    print("🔧 Help System Demo")
    print("=" * 50)
    
    help_system = HelpSystem()
    
    # Show general help
    print("\n1. General Help (type '?' or 'help'):")
    print(help_system.show_help())
    
    # Show specific command help
    print("\n2. Specific Command Help (type '? hosts'):")
    print(help_system.show_help("hosts"))
    
    # Show command suggestions
    print("\n3. Command Suggestions for 'hos':")
    suggestions = help_system.get_command_suggestions("hos")
    print(f"Suggestions: {suggestions}")
    
    # Show search functionality
    print("\n4. Search Help for 'service':")
    print(help_system.search_help("service"))

def demonstrate_command_parser():
    """Demonstrate the command parser."""
    print("\n🔧 Command Parser Demo")
    print("=" * 50)
    
    parser = CommandParser()
    
    test_commands = [
        "?",
        "? hosts",
        "help services",
        "list all hosts",
        "create host server01 in folder /web with ip 192.168.1.10",
        "show services for server01",
        "acknowledge CPU load on server01",
        "create 4 hour downtime for disk space on server01",
        "lst hsts",  # Typo test
        "exit"
    ]
    
    for cmd in test_commands:
        intent = parser.parse_command(cmd)
        print(f"\nInput: '{cmd}'")
        print(f"  Command: {intent.command}")
        print(f"  Confidence: {intent.confidence:.2f}")
        print(f"  Is Help: {intent.is_help_request}")
        if intent.help_topic:
            print(f"  Help Topic: {intent.help_topic}")
        if intent.parameters:
            print(f"  Parameters: {intent.parameters}")
        if intent.suggestions:
            print(f"  Suggestions: {intent.suggestions}")

def demonstrate_tab_completion():
    """Demonstrate tab completion."""
    print("\n🔧 Tab Completion Demo")
    print("=" * 50)
    
    completer = TabCompleter()
    
    # Test command completion
    test_prefixes = ["hel", "list", "cre", "serv"]
    
    for prefix in test_prefixes:
        completions = completer._complete_commands(prefix)
        print(f"\nCompletions for '{prefix}': {completions}")

def demonstrate_ui_manager():
    """Demonstrate UI manager."""
    print("\n🔧 UI Manager Demo")
    print("=" * 50)
    
    from checkmk_mcp_server.interactive.ui_manager import MessageType
    ui_manager = UIManager()
    
    # Test different message types
    print("\nMessage Types:")
    ui_manager.print_success("This is a success message")
    ui_manager.print_error("This is an error message")
    ui_manager.print_warning("This is a warning message")
    ui_manager.print_info("This is an info message")
    ui_manager.print_help("This is a help message")
    
    # Test prompt formatting
    print(f"\nPrompt: {ui_manager.format_prompt()}")
    
    # Test command suggestions
    suggestions = ["list hosts", "create host", "show services"]
    print("\nSuggestions:")
    print(ui_manager.format_command_suggestions(suggestions))

def demonstrate_readline_handler():
    """Demonstrate readline handler."""
    print("\n🔧 Readline Handler Demo")
    print("=" * 50)
    
    handler = ReadlineHandler()
    
    print(f"Has readline: {handler.has_readline}")
    print(f"History file: {handler.history_file}")
    print(f"History size: {handler.history_size}")
    
    # Add some test history
    test_commands = ["list hosts", "create host server01", "? hosts", "exit"]
    for cmd in test_commands:
        handler.add_history(cmd)
    
    print(f"\nHistory: {handler.get_history()}")

if __name__ == "__main__":
    print("🎉 Interactive Mode - Feature Demonstration")
    print("=" * 70)
    
    demonstrate_help_system()
    demonstrate_command_parser()
    demonstrate_tab_completion()
    demonstrate_ui_manager()
    demonstrate_readline_handler()
    
    print("\n🎉 Demo complete! Try the interactive mode with:")
    print("   python -m checkmk_mcp_server.cli interactive")
    print("\nNew features you can try:")
    print("   • Type '?' for help")
    print("   • Use Up/Down arrows for command history")
    print("   • Press Tab to autocomplete commands")
    print("   • Type commands with typos - they'll be corrected!")
    print("   • Use '? <command>' for specific help")