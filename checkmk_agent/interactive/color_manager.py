"""Color management system for enhanced interactive mode."""

import os
import sys
from typing import Dict, List, Optional, Any
from enum import Enum


class MessageType(Enum):
    """Types of messages for formatting."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    HELP = "help"
    PROMPT = "prompt"


class ColorManager:
    """Manages color themes and terminal capabilities."""

    def __init__(
        self,
        theme: str = "default",
        use_colors: Optional[bool] = None,
        custom_colors: Optional[Dict[str, str]] = None,
    ):
        """Initialize color manager.

        Args:
            theme: Theme name to use
            use_colors: Whether to use colors (auto-detect if None)
            custom_colors: Custom color overrides
        """
        self.use_colors = use_colors if use_colors is not None else sys.stdout.isatty()
        self.terminal_capabilities = self._detect_terminal_capabilities()
        self.custom_colors = custom_colors or {}

        # Extended color palette
        self.colors = {
            # Basic colors
            "reset": "\033[0m",
            "bold": "\033[1m",
            "dim": "\033[2m",
            "underline": "\033[4m",
            "strikethrough": "\033[9m",
            # Standard colors
            "black": "\033[30m",
            "red": "\033[31m",
            "green": "\033[32m",
            "yellow": "\033[33m",
            "blue": "\033[34m",
            "magenta": "\033[35m",
            "cyan": "\033[36m",
            "white": "\033[37m",
            "gray": "\033[90m",
            # Bright colors
            "bright_black": "\033[90m",
            "bright_red": "\033[91m",
            "bright_green": "\033[92m",
            "bright_yellow": "\033[93m",
            "bright_blue": "\033[94m",
            "bright_magenta": "\033[95m",
            "bright_cyan": "\033[96m",
            "bright_white": "\033[97m",
            # Additional colors (256-color mode)
            "orange": "\033[38;5;208m",
            "purple": "\033[38;5;129m",
            "pink": "\033[38;5;205m",
            "dark_gray": "\033[38;5;240m",
            "light_gray": "\033[38;5;250m",
            # Background colors
            "bg_red": "\033[41m",
            "bg_green": "\033[42m",
            "bg_yellow": "\033[43m",
            "bg_blue": "\033[44m",
            "bg_magenta": "\033[45m",
            "bg_cyan": "\033[46m",
            "bg_white": "\033[47m",
        }

        # Predefined themes
        self.themes = {
            "default": {
                "name": "Default",
                "description": "Standard color scheme",
                "colors": {
                    "info": "blue",
                    "success": "green",
                    "warning": "yellow",
                    "error": "red",
                    "help": "cyan",
                    "prompt": "magenta",
                },
                "icons": {
                    "info": "ℹ️",
                    "success": "✅",
                    "warning": "⚠️",
                    "error": "❌",
                    "help": "🔧",
                    "prompt": "🔧",
                },
            },
            "dark": {
                "name": "Dark",
                "description": "Optimized for dark terminals with brighter colors",
                "colors": {
                    "info": "bright_blue",
                    "success": "bright_green",
                    "warning": "bright_yellow",
                    "error": "bright_red",
                    "help": "bright_cyan",
                    "prompt": "bright_magenta",
                },
                "icons": {
                    "info": "ℹ️",
                    "success": "✅",
                    "warning": "⚠️",
                    "error": "❌",
                    "help": "🔧",
                    "prompt": "🔧",
                },
            },
            "light": {
                "name": "Light",
                "description": "Optimized for light terminals with darker colors",
                "colors": {
                    "info": "blue",
                    "success": "green",
                    "warning": "orange",
                    "error": "red",
                    "help": "purple",
                    "prompt": "dark_gray",
                },
                "icons": {
                    "info": "ℹ️",
                    "success": "✅",
                    "warning": "⚠️",
                    "error": "❌",
                    "help": "🔧",
                    "prompt": "🔧",
                },
            },
            "minimal": {
                "name": "Minimal",
                "description": "Reduced colors, more monochrome",
                "colors": {
                    "info": "white",
                    "success": "white",
                    "warning": "white",
                    "error": "white",
                    "help": "white",
                    "prompt": "white",
                },
                "icons": {
                    "info": "•",
                    "success": "✓",
                    "warning": "!",
                    "error": "✗",
                    "help": "?",
                    "prompt": ">",
                },
            },
            "high_contrast": {
                "name": "High Contrast",
                "description": "Accessibility-focused with high contrast",
                "colors": {
                    "info": "bright_white",
                    "success": "bright_green",
                    "warning": "bright_yellow",
                    "error": "bright_red",
                    "help": "bright_cyan",
                    "prompt": "bright_white",
                },
                "icons": {
                    "info": "[INFO]",
                    "success": "[SUCCESS]",
                    "warning": "[WARNING]",
                    "error": "[ERROR]",
                    "help": "[HELP]",
                    "prompt": "[PROMPT]",
                },
            },
            "colorful": {
                "name": "Colorful",
                "description": "Vibrant colors for visual appeal",
                "colors": {
                    "info": "bright_blue",
                    "success": "bright_green",
                    "warning": "orange",
                    "error": "bright_red",
                    "help": "purple",
                    "prompt": "pink",
                },
                "icons": {
                    "info": "🔵",
                    "success": "🟢",
                    "warning": "🟡",
                    "error": "🔴",
                    "help": "🟣",
                    "prompt": "🔧",
                },
            },
        }

        # Load theme
        self.current_theme = self._load_theme(theme)

    def _detect_terminal_capabilities(self) -> Dict[str, bool]:
        """Detect what the terminal supports."""
        capabilities = {
            "color": False,
            "color_256": False,
            "color_rgb": False,
            "emoji": True,  # Assume emoji support by default
        }

        if not sys.stdout.isatty():
            return capabilities

        # Check for color support
        term = os.environ.get("TERM", "").lower()
        colorterm = os.environ.get("COLORTERM", "").lower()

        # Basic color support
        if term and ("color" in term or term in ["xterm", "linux", "screen"]):
            capabilities["color"] = True

        # 256-color support
        if (
            "256" in term
            or "256" in colorterm
            or term in ["xterm-256color", "screen-256color"]
            or colorterm in ["gnome-terminal", "xfce4-terminal"]
        ):
            capabilities["color_256"] = True

        # RGB/truecolor support
        if colorterm in ["truecolor", "24bit"] or "truecolor" in term:
            capabilities["color_rgb"] = True

        return capabilities

    def _load_theme(self, theme_name: str) -> Dict[str, Any]:
        """Load a theme by name."""
        if theme_name not in self.themes:
            theme_name = "default"

        theme = self.themes[theme_name].copy()
        theme["name"] = theme_name

        # Apply custom color overrides
        if self.custom_colors:
            theme["colors"].update(self.custom_colors)

        return theme

    def get_color_code(self, color_name: str) -> str:
        """Get ANSI color code for color name.

        Args:
            color_name: Name of the color

        Returns:
            ANSI color code or empty string if colors disabled
        """
        if not self.use_colors or not self.terminal_capabilities.get("color", False):
            return ""

        # Check custom colors first
        if color_name in self.custom_colors:
            color_name = self.custom_colors[color_name]

        return self.colors.get(color_name, "")

    def get_message_color(self, message_type: MessageType) -> str:
        """Get color for specific message type.

        Args:
            message_type: Type of message

        Returns:
            Color name for the message type
        """
        return self.current_theme["colors"].get(message_type.value, "white")

    def get_message_icon(self, message_type: MessageType) -> str:
        """Get icon for specific message type.

        Args:
            message_type: Type of message

        Returns:
            Icon for the message type
        """
        return self.current_theme["icons"].get(message_type.value, "•")

    def colorize(self, text: str, color: str) -> str:
        """Apply color to text.

        Args:
            text: Text to colorize
            color: Color name

        Returns:
            Colored text or original text if colors disabled
        """
        if not self.use_colors:
            return text

        color_code = self.get_color_code(color)
        reset_code = self.get_color_code("reset")

        if not color_code:
            return text

        return f"{color_code}{text}{reset_code}"

    def set_theme(self, theme_name: str) -> bool:
        """Change current theme.

        Args:
            theme_name: Name of theme to set

        Returns:
            True if theme was set successfully, False otherwise
        """
        if theme_name not in self.themes:
            return False

        self.current_theme = self._load_theme(theme_name)
        return True

    def list_themes(self) -> List[Dict[str, str]]:
        """List available themes.

        Returns:
            List of theme info dictionaries
        """
        return [
            {
                "name": name,
                "display_name": theme["name"],
                "description": theme["description"],
            }
            for name, theme in self.themes.items()
        ]

    def get_current_theme_name(self) -> str:
        """Get current theme name.

        Returns:
            Current theme name
        """
        return self.current_theme["name"]

    def preview_colors(self) -> str:
        """Generate color preview text.

        Returns:
            Formatted preview text showing all colors
        """
        preview_lines = []

        # Theme info
        theme_name = self.current_theme["name"]
        preview_lines.append(f"🎨 Current Theme: {self.colorize(theme_name, 'bold')}")
        preview_lines.append("")

        # Message type examples
        preview_lines.append("📋 Message Types:")
        for msg_type in MessageType:
            color = self.get_message_color(msg_type)
            icon = self.get_message_icon(msg_type)
            colored_text = self.colorize(f"Sample {msg_type.value} message", color)
            preview_lines.append(f"  {icon} {colored_text}")

        preview_lines.append("")

        # Color palette
        preview_lines.append("🌈 Available Colors:")
        color_groups = [
            (
                "Basic",
                ["black", "red", "green", "yellow", "blue", "magenta", "cyan", "white"],
            ),
            (
                "Bright",
                [
                    "bright_red",
                    "bright_green",
                    "bright_yellow",
                    "bright_blue",
                    "bright_magenta",
                    "bright_cyan",
                    "bright_white",
                ],
            ),
            (
                "Extended",
                ["orange", "purple", "pink", "gray", "dark_gray", "light_gray"],
            ),
        ]

        for group_name, color_list in color_groups:
            preview_lines.append(f"  {group_name}:")
            color_samples = []
            for color in color_list:
                if color in self.colors:
                    sample = self.colorize(f"{color}", color)
                    color_samples.append(f"{sample}")

            # Display colors in rows of 4
            for i in range(0, len(color_samples), 4):
                row = color_samples[i : i + 4]
                preview_lines.append(f"    {' | '.join(row)}")

        return "\n".join(preview_lines)

    def test_colors(self) -> str:
        """Test color combinations.

        Returns:
            Test output with various color combinations
        """
        test_lines = []

        test_lines.append("🧪 Color Test Output")
        test_lines.append("=" * 50)
        test_lines.append("")

        # Test basic formatting
        test_lines.append("📝 Text Formatting:")
        test_lines.append(f"  Normal text")
        test_lines.append(f"  {self.colorize('Bold text', 'bold')}")
        test_lines.append(f"  {self.colorize('Dim text', 'dim')}")
        test_lines.append(f"  {self.colorize('Underlined text', 'underline')}")
        test_lines.append("")

        # Test message types in context
        test_lines.append("💬 Message Context Test:")
        test_lines.append(
            f"  {self.get_message_icon(MessageType.INFO)} {self.colorize('This is an info message about system status', self.get_message_color(MessageType.INFO))}"
        )
        test_lines.append(
            f"  {self.get_message_icon(MessageType.SUCCESS)} {self.colorize('Operation completed successfully!', self.get_message_color(MessageType.SUCCESS))}"
        )
        test_lines.append(
            f"  {self.get_message_icon(MessageType.WARNING)} {self.colorize('Warning: This action may take some time', self.get_message_color(MessageType.WARNING))}"
        )
        test_lines.append(
            f"  {self.get_message_icon(MessageType.ERROR)} {self.colorize('Error: Unable to connect to server', self.get_message_color(MessageType.ERROR))}"
        )
        test_lines.append(
            f"  {self.get_message_icon(MessageType.HELP)} {self.colorize('Type help for more information', self.get_message_color(MessageType.HELP))}"
        )
        test_lines.append("")

        # Test prompt
        prompt_color = self.get_message_color(MessageType.PROMPT)
        prompt_icon = self.get_message_icon(MessageType.PROMPT)
        test_lines.append("⌨️  Prompt Test:")
        test_lines.append(
            f"  {prompt_icon} {self.colorize('checkmk', prompt_color)}> list hosts"
        )
        test_lines.append("")

        return "\n".join(test_lines)

    def get_terminal_info(self) -> str:
        """Get terminal capability information.

        Returns:
            Formatted terminal information
        """
        info_lines = []

        info_lines.append("🖥️  Terminal Information")
        info_lines.append("=" * 30)
        info_lines.append("")

        # Terminal environment
        term = os.environ.get("TERM", "unknown")
        colorterm = os.environ.get("COLORTERM", "not set")
        info_lines.append(f"TERM: {term}")
        info_lines.append(f"COLORTERM: {colorterm}")
        info_lines.append(f"TTY: {sys.stdout.isatty()}")
        info_lines.append("")

        # Capabilities
        info_lines.append("Capabilities:")
        for capability, supported in self.terminal_capabilities.items():
            status = "✅" if supported else "❌"
            info_lines.append(f"  {status} {capability.replace('_', ' ').title()}")

        info_lines.append("")
        info_lines.append(f"Colors enabled: {'✅' if self.use_colors else '❌'}")

        return "\n".join(info_lines)
