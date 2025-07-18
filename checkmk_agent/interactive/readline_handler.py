"""Readline integration for command history and line editing."""

import os
import sys
from typing import Optional, List, Callable
from pathlib import Path

try:
    import readline
    import rlcompleter
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False


class ReadlineHandler:
    """Handles readline integration for command history and completion."""
    
    def __init__(self, history_file: Optional[str] = None, history_size: int = 1000):
        """Initialize readline handler.
        
        Args:
            history_file: Path to history file. Defaults to ~/.checkmk_agent_history
            history_size: Maximum number of history entries to keep
        """
        self.has_readline = HAS_READLINE
        self.history_size = history_size
        self.history_file = history_file or str(Path.home() / '.checkmk_agent_history')
        self.completer_function: Optional[Callable] = None
        
        if self.has_readline:
            self._setup_readline()
    
    def _setup_readline(self) -> None:
        """Setup readline configuration."""
        if not self.has_readline:
            return
        
        # Configure readline
        readline.set_history_length(self.history_size)
        
        # Enable tab completion
        readline.parse_and_bind('tab: complete')
        
        # Enable vi/emacs keybindings based on environment
        if os.environ.get('EDITOR', '').endswith('vi'):
            readline.parse_and_bind('set editing-mode vi')
        else:
            readline.parse_and_bind('set editing-mode emacs')
        
        # Load history if it exists
        self._load_history()
    
    def _load_history(self) -> None:
        """Load command history from file."""
        if not self.has_readline:
            return
        
        try:
            if os.path.exists(self.history_file):
                readline.read_history_file(self.history_file)
        except (IOError, OSError) as e:
            # Silently ignore history loading errors
            pass
    
    def save_history(self) -> None:
        """Save command history to file."""
        if not self.has_readline:
            return
        
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.history_file), exist_ok=True)
            readline.write_history_file(self.history_file)
        except (IOError, OSError) as e:
            # Silently ignore history saving errors
            pass
    
    def set_completer(self, completer_function: Callable) -> None:
        """Set the tab completion function.
        
        Args:
            completer_function: Function that takes (text, state) and returns completion
        """
        if not self.has_readline:
            return
        
        self.completer_function = completer_function
        readline.set_completer(completer_function)
    
    def add_history(self, command: str) -> None:
        """Add a command to history.
        
        Args:
            command: Command to add to history
        """
        if not self.has_readline or not command.strip():
            return
        
        readline.add_history(command)
    
    def get_history(self) -> List[str]:
        """Get current command history.
        
        Returns:
            List of command history entries
        """
        if not self.has_readline:
            return []
        
        history = []
        for i in range(readline.get_current_history_length()):
            try:
                history.append(readline.get_history_item(i + 1))
            except IndexError:
                break
        return history
    
    def clear_history(self) -> None:
        """Clear command history."""
        if not self.has_readline:
            return
        
        readline.clear_history()
    
    def input_with_prompt(self, prompt: str) -> str:
        """Get input with readline support.
        
        Args:
            prompt: Prompt to display
            
        Returns:
            User input string
        """
        if self.has_readline:
            return input(prompt)
        else:
            # Fallback for systems without readline
            return input(prompt)
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - save history."""
        self.save_history()