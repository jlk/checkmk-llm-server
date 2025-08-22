"""UI management for interactive mode."""

import sys
from typing import Optional, List, Dict, Any
from .color_manager import ColorManager, MessageType


class UIManager:
    """Manages UI formatting and user interaction."""

    def __init__(
        self,
        theme: str = "default",
        use_colors: Optional[bool] = None,
        custom_colors: Optional[Dict[str, str]] = None,
    ):
        """Initialize UI manager.

        Args:
            theme: Color theme to use
            use_colors: Whether to use colored output (auto-detect if None)
            custom_colors: Custom color overrides
        """
        self.color_manager = ColorManager(
            theme=theme, use_colors=use_colors, custom_colors=custom_colors
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

    def format_message(
        self, message: str, msg_type: MessageType = MessageType.INFO
    ) -> str:
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

    def print_message(
        self, message: str, msg_type: MessageType = MessageType.INFO
    ) -> None:
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
🤖 Checkmk LLM Agent - Interactive Mode
{'=' * 50}

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

    def format_service_list(
        self, services: List[Dict[str, Any]], host_name: Optional[str] = None
    ) -> str:
        """Format service list for display.

        Args:
            services: List of service dictionaries
            host_name: Optional host name for context

        Returns:
            Formatted service list
        """
        if not services:
            if host_name:
                return self.format_message(
                    f"No services found for host: {host_name}", MessageType.INFO
                )
            else:
                return self.format_message("No services found.", MessageType.INFO)

        if host_name:
            text = f"🔧 Found {len(services)} services for host: {self.colorize(host_name, 'bold')}\n\n"
        else:
            text = f"🔧 Found {len(services)} services:\n\n"

        for service in services:
            extensions = service.get("extensions", {})
            service_desc = extensions.get("description", "Unknown")
            service_state = extensions.get("state", "Unknown")
            host = extensions.get("host_name", host_name or "Unknown")

            # Choose icon based on state
            if service_state == "OK" or service_state == 0:
                state_icon = "✅"
                state_color = "green"
            elif service_state == "WARNING" or service_state == 1:
                state_icon = "⚠️"
                state_color = "yellow"
            elif service_state == "CRITICAL" or service_state == 2:
                state_icon = "❌"
                state_color = "red"
            else:
                state_icon = "❓"
                state_color = "white"

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
            return response in ["y", "yes"]
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
            formatted_key = key.replace("_", " ").title()
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

        return text[: max_length - 3] + "..."

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

    # Service Status UI Methods

    def format_service_health_dashboard(self, dashboard: Dict[str, Any]) -> str:
        """Format comprehensive service health dashboard.

        Args:
            dashboard: Dashboard data from ServiceStatusManager

        Returns:
            Formatted dashboard display
        """
        overall_health = dashboard["overall_health"]
        problem_analysis = dashboard["problem_analysis"]

        result = self.colorize("📊 Service Health Dashboard", "bold") + "\n"
        result += "━" * 60 + "\n\n"

        # Overall health section with color-coded health percentage
        health_pct = overall_health["health_percentage"]
        total_services = overall_health["total_services"]
        problems = overall_health["problems"]

        # Health bar and icon
        health_bar = self.format_health_bar(health_pct)
        health_icon = self.get_health_icon(health_pct)
        health_color = self.get_health_color(health_pct)

        result += f"{health_icon} Overall Health: {self.colorize(f'{health_pct:.1f}%', health_color)} {health_bar}\n"
        result += f"📈 Total Services: {self.colorize(str(total_services), 'bold')}\n"

        if problems > 0:
            result += f"⚠️  Problems: {self.colorize(f'{problems} services need attention', 'yellow')}\n"
        else:
            result += f"✅ {self.colorize('No problems detected!', 'green')}\n"
        result += "\n"

        # Service state distribution
        states = overall_health["states"]
        result += self.colorize("📊 Service States:", "bold") + "\n"
        result += f"  ✅ OK: {self.colorize(str(states['ok']), 'green')} services\n"
        if states["warning"] > 0:
            result += f"  ⚠️  WARNING: {self.colorize(str(states['warning']), 'yellow')} services\n"
        if states["critical"] > 0:
            result += f"  ❌ CRITICAL: {self.colorize(str(states['critical']), 'red')} services\n"
        if states["unknown"] > 0:
            result += f"  ❓ UNKNOWN: {self.colorize(str(states['unknown']), 'white')} services\n"
        result += "\n"

        # Critical issues section
        critical_issues = problem_analysis.get("critical", [])
        if critical_issues:
            result += self.colorize("🔥 Critical Issues:", "red") + "\n"
            for issue in critical_issues[:5]:
                host = issue["host_name"]
                service = issue["description"]
                ack_icon = "🔕" if issue["acknowledged"] else ""
                downtime_icon = "⏸️" if issue["in_downtime"] else ""
                result += f"  ❌ {self.colorize(f'{host}/{service}', 'red')} {ack_icon}{downtime_icon}\n"

                output = issue.get("output", "")
                if output:
                    truncated_output = self.truncate_text(output, 60)
                    result += f"     {self.colorize(truncated_output, 'gray')}\n"

            if len(critical_issues) > 5:
                remaining = len(critical_issues) - 5
                result += f"     {self.colorize(f'... and {remaining} more critical issues', 'red')}\n"
            result += "\n"

        # Warning issues section
        warning_issues = problem_analysis.get("warning", [])
        if warning_issues:
            result += self.colorize("⚠️  Warning Issues:", "yellow") + "\n"
            for issue in warning_issues[:3]:
                host = issue["host_name"]
                service = issue["description"]
                ack_icon = "🔕" if issue["acknowledged"] else ""
                downtime_icon = "⏸️" if issue["in_downtime"] else ""
                result += f"  ⚠️  {self.colorize(f'{host}/{service}', 'yellow')} {ack_icon}{downtime_icon}\n"

            if len(warning_issues) > 3:
                remaining = len(warning_issues) - 3
                result += f"     {self.colorize(f'... and {remaining} more warnings', 'yellow')}\n"
            result += "\n"

        # Urgent problems and recommendations
        urgent_problems = dashboard.get("urgent_problems", [])
        if urgent_problems:
            urgent_count = len(urgent_problems)
            result += f"🚨 {self.colorize(f'{urgent_count} urgent problem(s)', 'red')} require immediate attention\n"
            result += (
                f"   Use {self.colorize('status critical', 'bold')} for details\n\n"
            )

        unhandled = dashboard.get("needs_attention", 0)
        if unhandled > 0:
            result += f"💡 {self.colorize(f'{unhandled} unacknowledged problem(s)', 'yellow')} need review\n"
            result += (
                f"   Use {self.colorize('status problems', 'bold')} to see all issues\n"
            )

        return result

    def format_service_status_card(self, service: Dict[str, Any]) -> str:
        """Format individual service as a status card.

        Args:
            service: Service data dictionary

        Returns:
            Formatted service status card
        """
        extensions = service.get("extensions", {})
        host_name = extensions.get("host_name", "Unknown")
        description = extensions.get("description", "Unknown")
        state = extensions.get("state", 0)
        acknowledged = extensions.get("acknowledged", 0) > 0
        in_downtime = extensions.get("scheduled_downtime_depth", 0) > 0
        output = extensions.get("plugin_output", "")
        last_check = extensions.get("last_check", 0)

        # State information
        state_info = self.get_service_state_info(state)
        state_icon = state_info["icon"]
        state_name = state_info["name"]
        state_color = state_info["color"]

        # Build card
        card = (
            f"┌─ {state_icon} {self.colorize(f'{host_name}/{description}', 'bold')} ─\n"
        )
        card += f"│ State: {self.colorize(state_name, state_color)}\n"

        # Status indicators
        indicators = []
        if acknowledged:
            indicators.append("🔕 Acknowledged")
        if in_downtime:
            indicators.append("⏸️  Downtime")

        if indicators:
            card += f"│ Status: {' '.join(indicators)}\n"

        # Output (truncated)
        if output:
            truncated_output = self.truncate_text(output, 50)
            card += f"│ Output: {self.colorize(truncated_output, 'gray')}\n"

        # Time info
        if last_check:
            try:
                from datetime import datetime

                last_check_time = datetime.fromtimestamp(last_check)
                time_ago = datetime.now() - last_check_time
                time_str = self.format_time_delta(time_ago)
                card += f"│ Last Check: {time_str}\n"
            except:
                card += f"│ Last Check: Unknown\n"

        card += "└─────────────────────────────────────────\n"

        return card

    def format_problem_summary(
        self, problems: List[Dict[str, Any]], title: str = "Service Problems"
    ) -> str:
        """Format a summary of service problems.

        Args:
            problems: List of problem service data
            title: Section title

        Returns:
            Formatted problem summary
        """
        if not problems:
            return f"{self.colorize('🎉 No problems found!', 'green')}\n"

        result = self.colorize(f"🚨 {title} ({len(problems)})", "bold") + "\n"
        result += "━" * 40 + "\n\n"

        # Group by severity
        critical = [p for p in problems if self.get_service_state_from_data(p) == 2]
        warning = [p for p in problems if self.get_service_state_from_data(p) == 1]
        unknown = [p for p in problems if self.get_service_state_from_data(p) == 3]

        # Critical section
        if critical:
            result += self.colorize(f"❌ CRITICAL ({len(critical)}):", "red") + "\n"
            for service in critical[:5]:
                host = self.get_service_host_from_data(service)
                desc = self.get_service_description_from_data(service)
                result += f"  🔴 {host}/{desc}\n"

            if len(critical) > 5:
                result += f"     {self.colorize(f'... and {len(critical) - 5} more', 'red')}\n"
            result += "\n"

        # Warning section
        if warning:
            result += self.colorize(f"⚠️  WARNING ({len(warning)}):", "yellow") + "\n"
            for service in warning[:5]:
                host = self.get_service_host_from_data(service)
                desc = self.get_service_description_from_data(service)
                result += f"  🟡 {host}/{desc}\n"

            if len(warning) > 5:
                result += f"     {self.colorize(f'... and {len(warning) - 5} more', 'yellow')}\n"
            result += "\n"

        # Unknown section
        if unknown:
            result += self.colorize(f"❓ UNKNOWN ({len(unknown)}):", "white") + "\n"
            for service in unknown[:3]:
                host = self.get_service_host_from_data(service)
                desc = self.get_service_description_from_data(service)
                result += f"  🟤 {host}/{desc}\n"

            if len(unknown) > 3:
                result += f"     {self.colorize(f'... and {len(unknown) - 3} more', 'white')}\n"

        return result

    def format_health_bar(self, percentage: float, width: int = 20) -> str:
        """Format a health percentage as a progress bar.

        Args:
            percentage: Health percentage (0-100)
            width: Width of the progress bar

        Returns:
            Formatted progress bar
        """
        filled = int((percentage / 100) * width)
        empty = width - filled

        # Choose color based on health
        if percentage >= 95:
            bar_color = "green"
        elif percentage >= 85:
            bar_color = "yellow"
        else:
            bar_color = "red"

        bar = "█" * filled + "░" * empty
        return f"[{self.colorize(bar, bar_color)}]"

    def get_health_icon(self, percentage: float) -> str:
        """Get health status icon based on percentage.

        Args:
            percentage: Health percentage

        Returns:
            Appropriate emoji icon
        """
        if percentage >= 95:
            return "🟢"
        elif percentage >= 90:
            return "🟡"
        elif percentage >= 80:
            return "🟠"
        else:
            return "🔴"

    def get_health_color(self, percentage: float) -> str:
        """Get health status color based on percentage.

        Args:
            percentage: Health percentage

        Returns:
            Color name for formatting
        """
        if percentage >= 90:
            return "green"
        elif percentage >= 80:
            return "yellow"
        else:
            return "red"

    def get_service_state_info(self, state: int) -> Dict[str, str]:
        """Get service state information.

        Args:
            state: Service state (0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN)

        Returns:
            Dictionary with icon, name, and color
        """
        state_map = {
            0: {"icon": "🟢", "name": "OK", "color": "green"},
            1: {"icon": "🟡", "name": "WARNING", "color": "yellow"},
            2: {"icon": "🔴", "name": "CRITICAL", "color": "red"},
            3: {"icon": "🟤", "name": "UNKNOWN", "color": "white"},
        }
        return state_map.get(state, {"icon": "❓", "name": "UNKNOWN", "color": "white"})

    def format_time_delta(self, delta) -> str:
        """Format time delta as human-readable string.

        Args:
            delta: timedelta object

        Returns:
            Human-readable time string
        """
        total_seconds = int(delta.total_seconds())

        if total_seconds < 60:
            return f"{total_seconds}s ago"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m ago"
        elif total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours}h ago"
        else:
            days = total_seconds // 86400
            return f"{days}d ago"

    def get_service_state_from_data(self, service: Dict[str, Any]) -> int:
        """Extract service state from service data.

        Args:
            service: Service data dictionary

        Returns:
            Service state integer
        """
        return service.get("extensions", {}).get("state", 0)

    def get_service_host_from_data(self, service: Dict[str, Any]) -> str:
        """Extract host name from service data.

        Args:
            service: Service data dictionary

        Returns:
            Host name
        """
        return service.get("extensions", {}).get("host_name", "Unknown")

    def get_service_description_from_data(self, service: Dict[str, Any]) -> str:
        """Extract service description from service data.

        Args:
            service: Service data dictionary

        Returns:
            Service description
        """
        return service.get("extensions", {}).get("description", "Unknown")

    def format_status_summary_card(self, summary: Dict[str, Any]) -> str:
        """Format status summary as a card.

        Args:
            summary: Status summary data

        Returns:
            Formatted summary card
        """
        total_services = summary["total_services"]
        health_pct = summary["health_percentage"]
        problems = summary["problems"]
        status_icon = summary["status_icon"]
        status_message = summary["status_message"]

        health_color = self.get_health_color(health_pct)
        health_bar = self.format_health_bar(health_pct, 15)

        card = f"┌─ {self.colorize('📊 Status Summary', 'bold')} ─\n"
        card += f"│ {status_icon} Health: {self.colorize(f'{health_pct:.1f}%', health_color)} {health_bar}\n"
        card += f"│ 📈 Total Services: {self.colorize(str(total_services), 'bold')}\n"
        card += f"│ 📋 Status: {status_message}\n"

        if problems > 0:
            critical = summary.get("critical", 0)
            warning = summary.get("warning", 0)
            if critical > 0:
                card += f"│ ❌ Critical: {self.colorize(str(critical), 'red')}\n"
            if warning > 0:
                card += f"│ ⚠️  Warning: {self.colorize(str(warning), 'yellow')}\n"

        card += "└────────────────────────────────────\n"

        return card

    def format_host_status_dashboard(self, dashboard: Dict[str, Any]) -> str:
        """Format comprehensive host status dashboard with enhanced visuals.

        Args:
            dashboard: Host dashboard data from ServiceStatusManager

        Returns:
            Rich formatted host dashboard string
        """
        if not dashboard.get("found", True):
            return self.format_message(
                dashboard.get("error", "Host not found"), MessageType.ERROR
            )

        host_name = dashboard["host_name"]
        health_metrics = dashboard["health_metrics"]
        problem_analysis = dashboard["problem_analysis"]
        urgent_issues = dashboard["urgent_issues"]
        maintenance_suggestions = dashboard["maintenance_suggestions"]
        recent_changes = dashboard["recent_changes"]

        result = f"{self.colorize(f'🖥️  Host Status Dashboard: {host_name}', 'bold')}\n"
        result += f"{'━' * 60}\n\n"

        # Health Summary Card
        health_pct = health_metrics["health_percentage"]
        health_grade = health_metrics["health_grade"]
        status_icon = health_metrics["status_icon"]
        trend = health_metrics["health_trend"]

        result += f"{self.colorize('📊 Health Summary', 'bold')}\n"
        result += f"   {status_icon} Overall Health: {self.format_health_bar(health_pct)} Grade: {self.colorize(health_grade, self.get_health_color(health_pct))}\n"
        result += f"   📈 Trend: {self._format_trend(trend)} | 🔧 Services: {health_metrics['total_services']}\n"

        # Infrastructure comparison
        comparison = health_metrics["infrastructure_comparison"]
        if comparison > 0:
            result += f"   🌟 {self.colorize(f'{comparison:+.1f}% above infrastructure average', 'green')}\n"
        elif comparison < 0:
            result += f"   ⚠️  {self.colorize(f'{comparison:+.1f}% below infrastructure average', 'yellow')}\n"
        else:
            result += f"   📊 At infrastructure average\n"

        result += "\n"

        # Service State Distribution
        state_counts = health_metrics["state_counts"]
        result += f"{self.colorize('🔍 Service Distribution', 'bold')}\n"

        if state_counts.get("critical", 0) > 0:
            result += f"   🔴 Critical: {self.colorize(str(state_counts['critical']), 'red')}\n"
        if state_counts.get("warning", 0) > 0:
            result += f"   🟡 Warning: {self.colorize(str(state_counts['warning']), 'yellow')}\n"
        if state_counts.get("unknown", 0) > 0:
            result += f"   🟤 Unknown: {self.colorize(str(state_counts['unknown']), 'white')}\n"
        result += (
            f"   🟢 OK: {self.colorize(str(state_counts.get('ok', 0)), 'green')}\n\n"
        )

        # Urgent Issues Section
        if urgent_issues:
            result += (
                f"{self.colorize('🚨 Urgent Issues Requiring Attention', 'red')}\n"
            )
            for issue in urgent_issues[:3]:  # Show top 3
                severity_color = "red" if issue["state"] == 2 else "yellow"
                critical_mark = " 🔥" if issue["is_critical_service"] else ""
                result += f"   {self.colorize('●', severity_color)} {issue['description']}{critical_mark}\n"

                # Truncate output for display
                output_text = self.truncate_text(issue["output"], 80)
                result += f"     {self.colorize(output_text, 'gray')}\n"
                result += (
                    f"     💡 {self.colorize(issue['recommended_action'], 'cyan')}\n"
                )
            result += "\n"

        # Problem Categories
        summary = problem_analysis.get("summary", {})
        if summary.get("total_problems", 0) > 0:
            result += f"{self.colorize('📋 Problem Categories', 'bold')}\n"
            category_dist = summary.get("category_distribution", {})

            for category, count in category_dist.items():
                if count > 0:
                    icon = self._get_category_icon(category)
                    result += f"   {icon} {category.title()}: {count} issue(s)\n"

            most_affected = summary.get("most_affected_category", "none")
            if most_affected != "none":
                result += f"   📊 Most affected: {self.colorize(most_affected.title(), 'bold')}\n"
            result += "\n"

        # Recent Changes
        if recent_changes.get("state_changes_count", 0) > 0:
            result += f"{self.colorize('📈 Recent Activity', 'bold')}\n"

            if recent_changes.get("recently_recovered"):
                result += f"   {self.colorize('✅ Recent Recoveries:', 'green')}\n"
                for recovery in recent_changes["recently_recovered"]:
                    result += f"      • {recovery['description']} ({recovery['recovered_ago']})\n"

            if recent_changes.get("recently_failed"):
                result += f"   {self.colorize('❌ Recent Failures:', 'red')}\n"
                for failure in recent_changes["recently_failed"]:
                    result += f"      • {failure['description']} → {failure['state_name']} ({failure['failed_ago']})\n"

            stability = recent_changes.get("stability_score", 85.0)
            stability_color = self.get_health_color(stability)
            result += f"   📊 Stability Score: {self.colorize(f'{stability:.1f}%', stability_color)}\n\n"

        # Maintenance Recommendations
        if maintenance_suggestions:
            result += f"{self.colorize('🔧 Recommended Actions', 'bold')}\n"
            for suggestion in maintenance_suggestions:
                result += f"   • {suggestion}\n"
            result += "\n"

        # Summary Message
        summary_msg = dashboard.get("summary_message", "")
        if summary_msg:
            result += f"{self.colorize('📝 Summary', 'bold')}\n"
            result += f"   {summary_msg}\n"

        return result

    def _format_trend(self, trend: str) -> str:
        """Format trend indicator with colors."""
        if trend == "improving":
            return f"{self.colorize('📈 Improving', 'green')}"
        elif trend == "declining":
            return f"{self.colorize('📉 Declining', 'red')}"
        else:
            return f"{self.colorize('➡️  Stable', 'cyan')}"

    def _get_category_icon(self, category: str) -> str:
        """Get icon for problem category."""
        category_icons = {
            "disk": "💾",
            "network": "🌐",
            "performance": "⚡",
            "connectivity": "🔌",
            "monitoring": "🔍",
            "other": "🔧",
        }
        return category_icons.get(category, "🔧")
