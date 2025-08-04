"""CLI implementation using MCP client backend."""

import asyncio
import click
import logging
import os
import sys
from typing import Optional, Dict, Any, List
from pathlib import Path

from .config import AppConfig
from .mcp_client import create_mcp_client, CheckmkMCPClient
from .formatters import CLIFormatter
from .logging_utils import setup_logging


logger = logging.getLogger(__name__)


class MCPCLIContext:
    """Context object for MCP-based CLI commands."""

    def __init__(
        self, config: AppConfig, mcp_client: CheckmkMCPClient, formatter: CLIFormatter
    ):
        self.config = config
        self.mcp_client = mcp_client
        self.formatter = formatter


def async_command(f):
    """Decorator to run async commands in the event loop."""

    def wrapper(*args, **kwargs):
        return asyncio.run(f(*args, **kwargs))

    wrapper.__name__ = f.__name__
    wrapper.__doc__ = f.__doc__
    return wrapper


@click.group()
@click.option(
    "--config", "-c", type=click.Path(exists=True), help="Path to configuration file"
)
@click.option(
    "--log-level",
    "-l",
    type=click.Choice(["DEBUG", "INFO", "WARNING", "ERROR"]),
    default="INFO",
    help="Set the logging level",
)
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.pass_context
@async_command
async def cli(ctx, config, log_level, no_color):
    """Checkmk LLM Agent CLI - MCP Edition"""
    # Setup logging
    setup_logging(log_level)

    # Load configuration using the proper load_config function
    from .config import load_config

    config_file_path = config
    app_config = load_config(config_file_path)

    # Create formatter
    formatter = CLIFormatter(use_colors=not no_color)

    # Create and connect MCP client
    async with create_mcp_client(app_config, config_file_path) as mcp_client:
        # Store in context for subcommands
        ctx.obj = MCPCLIContext(app_config, mcp_client, formatter)

        # If this is not a subcommand, just connect and exit
        if ctx.invoked_subcommand is None:
            click.echo("Checkmk MCP CLI connected. Use --help for available commands.")


@cli.group()
@click.pass_obj
def hosts(ctx_obj):
    """Host management commands"""
    pass


@hosts.command("list")
@click.option("--search", "-s", help="Search pattern for host names")
@click.option("--folder", "-f", help="Filter by folder")
@click.option("--limit", "-n", type=int, help="Maximum number of hosts to return")
@click.option("--status", is_flag=True, help="Include host status information")
@click.pass_obj
@async_command
async def list_hosts(ctx_obj: MCPCLIContext, search, folder, limit, status):
    """List all hosts"""
    try:
        result = await ctx_obj.mcp_client.list_hosts(
            search=search, folder=folder, limit=limit, include_status=status
        )

        if result.get("success"):
            data = result.get("data", {})
            click.echo(ctx_obj.formatter.format_host_list(data))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to list hosts: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@hosts.command("create")
@click.argument("name")
@click.option("--folder", "-f", default="/", help="Folder path")
@click.option("--ip", help="IP address")
@click.option("--alias", help="Host alias")
@click.option("--tags", "-t", multiple=True, help="Host tags")
@click.pass_obj
@async_command
async def create_host(ctx_obj: MCPCLIContext, name, folder, ip, alias, tags):
    """Create a new host"""
    try:
        # Build attributes
        attributes = {}
        if alias:
            attributes["alias"] = alias
        if tags:
            attributes["tag_list"] = list(tags)

        result = await ctx_obj.mcp_client.create_host(
            name=name, folder=folder, ip_address=ip, attributes=attributes
        )

        if result.get("success"):
            click.echo(
                ctx_obj.formatter.format_success(f"Successfully created host '{name}'")
            )
            if result.get("data"):
                click.echo(ctx_obj.formatter.format_host_details(result["data"]))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to create host: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@hosts.command("show")
@click.argument("name")
@click.option("--status", is_flag=True, help="Include status information")
@click.pass_obj
@async_command
async def show_host(ctx_obj: MCPCLIContext, name, status):
    """Show details for a specific host"""
    try:
        result = await ctx_obj.mcp_client.get_host(name=name, include_status=status)

        if result.get("success"):
            data = result.get("data", {})
            click.echo(ctx_obj.formatter.format_host_details(data))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to get host details: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@hosts.command("update")
@click.argument("name")
@click.option("--folder", "-f", help="New folder path")
@click.option("--ip", help="New IP address")
@click.option("--alias", help="New host alias")
@click.option("--add-tag", "-t", multiple=True, help="Add tags")
@click.option("--remove-tag", "-r", multiple=True, help="Remove tags")
@click.pass_obj
@async_command
async def update_host(
    ctx_obj: MCPCLIContext, name, folder, ip, alias, add_tag, remove_tag
):
    """Update an existing host"""
    try:
        # Build update parameters
        update_params = {"name": name}

        if folder:
            update_params["folder"] = folder
        if ip:
            update_params["ip_address"] = ip

        # Build attributes if needed
        attributes = {}
        if alias:
            attributes["alias"] = alias
        if add_tag or remove_tag:
            # Would need to get current tags first in a real implementation
            click.echo(
                ctx_obj.formatter.format_warning(
                    "Tag management not fully implemented in this example"
                )
            )

        if attributes:
            update_params["attributes"] = attributes

        result = await ctx_obj.mcp_client.update_host(**update_params)

        if result.get("success"):
            click.echo(
                ctx_obj.formatter.format_success(f"Successfully updated host '{name}'")
            )
            if result.get("data"):
                click.echo(ctx_obj.formatter.format_host_details(result["data"]))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to update host: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@hosts.command("delete")
@click.argument("name")
@click.option("--force", "-f", is_flag=True, help="Skip confirmation")
@click.pass_obj
@async_command
async def delete_host(ctx_obj: MCPCLIContext, name, force):
    """Delete a host"""
    try:
        if not force:
            if not click.confirm(f"Are you sure you want to delete host '{name}'?"):
                click.echo("Aborted.")
                return

        result = await ctx_obj.mcp_client.delete_host(name=name)

        if result.get("success"):
            click.echo(
                ctx_obj.formatter.format_success(f"Successfully deleted host '{name}'")
            )
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to delete host: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@cli.group()
@click.pass_obj
def services(ctx_obj):
    """Service management commands"""
    pass


@services.command("list")
@click.argument("host_name", required=False)
@click.option(
    "--state",
    "-s",
    type=click.Choice(["OK", "WARNING", "CRITICAL", "UNKNOWN"]),
    multiple=True,
    help="Filter by service state",
)
@click.option("--limit", "-n", type=int, help="Maximum number of services")
@click.option("--details", is_flag=True, help="Include detailed information")
@click.pass_obj
@async_command
async def list_services(ctx_obj: MCPCLIContext, host_name, state, limit, details):
    """List services for a host or all hosts"""
    try:
        if host_name:
            # List services for specific host
            result = await ctx_obj.mcp_client.list_host_services(
                host_name=host_name,
                state_filter=list(state) if state else None,
                include_details=details,
            )
        else:
            # List all services
            result = await ctx_obj.mcp_client.list_all_services(
                state_filter=list(state) if state else None, limit=limit
            )

        if result.get("success"):
            data = result.get("data", {})
            click.echo(ctx_obj.formatter.format_service_list(data))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to list services: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@services.command("status")
@click.argument("host_name")
@click.argument("service_name")
@click.option("--related", is_flag=True, help="Include related services")
@click.pass_obj
@async_command
async def service_status(ctx_obj: MCPCLIContext, host_name, service_name, related):
    """Get detailed status for a specific service"""
    try:
        result = await ctx_obj.mcp_client.get_service_status(
            host_name=host_name, service_name=service_name, include_related=related
        )

        if result.get("success"):
            data = result.get("data", {})
            click.echo(ctx_obj.formatter.format_service_status(data))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to get service status: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@services.command("acknowledge")
@click.argument("host_name")
@click.argument("service_name")
@click.option(
    "--comment", "-c", default="Acknowledged via CLI", help="Acknowledgement comment"
)
@click.option("--sticky/--no-sticky", default=True, help="Sticky acknowledgement")
@click.option("--notify/--no-notify", default=True, help="Send notifications")
@click.option(
    "--persistent/--no-persistent", default=False, help="Persist across restarts"
)
@click.pass_obj
@async_command
async def acknowledge_problem(
    ctx_obj: MCPCLIContext, host_name, service_name, comment, sticky, notify, persistent
):
    """Acknowledge a service problem"""
    try:
        result = await ctx_obj.mcp_client.acknowledge_service_problem(
            host_name=host_name,
            service_name=service_name,
            comment=comment,
            sticky=sticky,
            notify=notify,
            persistent=persistent,
        )

        if result.get("success"):
            click.echo(
                ctx_obj.formatter.format_success(
                    f"Successfully acknowledged {host_name}/{service_name}"
                )
            )
            if result.get("data"):
                click.echo(ctx_obj.formatter.format_acknowledge_result(result["data"]))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to acknowledge problem: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@services.command("downtime")
@click.argument("host_name")
@click.argument("service_name")
@click.argument("duration", type=float)
@click.option(
    "--comment", "-c", default="Scheduled downtime via CLI", help="Downtime comment"
)
@click.option("--start", help="Start time (ISO format, default: now)")
@click.option("--fixed/--flexible", default=True, help="Fixed or flexible downtime")
@click.pass_obj
@async_command
async def create_downtime(
    ctx_obj: MCPCLIContext, host_name, service_name, duration, comment, start, fixed
):
    """Create scheduled downtime for a service"""
    try:
        result = await ctx_obj.mcp_client.create_service_downtime(
            host_name=host_name,
            service_name=service_name,
            duration_hours=duration,
            comment=comment,
            start_time=start,
            fixed=fixed,
        )

        if result.get("success"):
            click.echo(
                ctx_obj.formatter.format_success(
                    f"Successfully created {duration}h downtime for {host_name}/{service_name}"
                )
            )
            if result.get("data"):
                click.echo(ctx_obj.formatter.format_downtime_result(result["data"]))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to create downtime: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@services.command("discover")
@click.argument("host_name")
@click.option(
    "--mode",
    "-m",
    type=click.Choice(["refresh", "new", "remove", "fixall"]),
    default="refresh",
    help="Discovery mode",
)
@click.pass_obj
@async_command
async def discover_services(ctx_obj: MCPCLIContext, host_name, mode):
    """Discover services on a host"""
    try:
        result = await ctx_obj.mcp_client.discover_services(
            host_name=host_name, mode=mode
        )

        if result.get("success"):
            click.echo(
                ctx_obj.formatter.format_success(
                    result.get("message", "Discovery completed")
                )
            )
            if result.get("data"):
                click.echo(ctx_obj.formatter.format_discovery_result(result["data"]))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to discover services: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@cli.group()
@click.pass_obj
def status(ctx_obj):
    """Health and status monitoring commands"""
    pass


@status.command("dashboard")
@click.option("--problems-only", is_flag=True, help="Show only hosts with problems")
@click.option("--critical-only", is_flag=True, help="Show only critical problems")
@click.option("--host-filter", "-h", help="Filter by host pattern")
@click.pass_obj
@async_command
async def health_dashboard(
    ctx_obj: MCPCLIContext, problems_only, critical_only, host_filter
):
    """Display infrastructure health dashboard"""
    try:
        result = await ctx_obj.mcp_client.get_health_dashboard(
            host_filter=host_filter,
            problems_only=problems_only,
            critical_only=critical_only,
        )

        if result.get("success"):
            data = result.get("data", {})
            click.echo(ctx_obj.formatter.format_health_dashboard(data))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to get health dashboard: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@status.command("problems")
@click.argument("host_name", required=False)
@click.option("--category", "-c", help="Filter by problem category")
@click.option(
    "--severity",
    "-s",
    type=click.Choice(["critical", "warning", "unknown"]),
    help="Filter by severity",
)
@click.pass_obj
@async_command
async def show_problems(ctx_obj: MCPCLIContext, host_name, category, severity):
    """Show current problems"""
    try:
        if host_name:
            # Get problems for specific host
            result = await ctx_obj.mcp_client.get_host_problems(
                host_name=host_name, category_filter=category, severity_filter=severity
            )
        else:
            # Get all critical problems
            result = await ctx_obj.mcp_client.get_critical_problems()

        if result.get("success"):
            data = result.get("data", {})
            click.echo(ctx_obj.formatter.format_problem_summary(data))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to get problems: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@status.command("analyze")
@click.argument("host_name")
@click.option("--grade", is_flag=True, help="Include health grade")
@click.option("--recommendations", is_flag=True, help="Include recommendations")
@click.option("--compare", is_flag=True, help="Compare to peer hosts")
@click.pass_obj
@async_command
async def analyze_host(
    ctx_obj: MCPCLIContext, host_name, grade, recommendations, compare
):
    """Analyze host health in detail"""
    try:
        result = await ctx_obj.mcp_client.analyze_host_health(
            host_name=host_name,
            include_grade=grade,
            include_recommendations=recommendations,
            compare_to_peers=compare,
        )

        if result.get("success"):
            data = result.get("data", {})
            click.echo(ctx_obj.formatter.format_host_analysis(data))
        else:
            click.echo(
                ctx_obj.formatter.format_error(
                    f"Failed to analyze host: {result.get('error', 'Unknown error')}"
                )
            )
            sys.exit(1)

    except Exception as e:
        click.echo(ctx_obj.formatter.format_error(f"Error: {str(e)}"))
        sys.exit(1)


@cli.command()
@click.option("--prompt", "-p", help="Initial prompt to send")
@click.option("--history", "-h", is_flag=True, help="Load command history")
@click.pass_obj
@async_command
async def interactive(ctx_obj: MCPCLIContext, prompt, history):
    """Start interactive mode with natural language interface"""
    click.echo(ctx_obj.formatter.format_header("Checkmk Interactive Mode (MCP)"))
    click.echo("Type 'help' for available commands or 'exit' to quit.\n")

    # Import interactive components
    from .interactive.mcp_session import InteractiveSession

    # Create and run interactive session
    session = InteractiveSession(
        mcp_client=ctx_obj.mcp_client,
        formatter=ctx_obj.formatter,
        config=ctx_obj.config,
    )

    await session.run(initial_prompt=prompt, load_history=history)


@cli.command()
@click.pass_obj
def resources(ctx_obj: MCPCLIContext):
    """List available MCP resources"""
    click.echo(ctx_obj.formatter.format_header("Available MCP Resources"))
    click.echo()

    resources = [
        ("checkmk://dashboard/health", "Real-time infrastructure health dashboard"),
        (
            "checkmk://dashboard/problems",
            "Current critical problems across infrastructure",
        ),
        ("checkmk://hosts/status", "Current status of all monitored hosts"),
        ("checkmk://services/problems", "Current service problems requiring attention"),
        ("checkmk://metrics/performance", "Real-time performance metrics and trends"),
    ]

    for uri, description in resources:
        click.echo(f"  {ctx_obj.formatter.format_info(uri)}")
        click.echo(f"    {description}")
        click.echo()


@cli.command()
@click.pass_obj
def prompts(ctx_obj: MCPCLIContext):
    """List available MCP prompt templates"""
    click.echo(ctx_obj.formatter.format_header("Available MCP Prompt Templates"))
    click.echo()

    prompts = [
        (
            "analyze_host_health",
            "Analyze the health of a specific host with detailed recommendations",
        ),
        (
            "troubleshoot_service",
            "Comprehensive troubleshooting analysis for a service problem",
        ),
        (
            "infrastructure_overview",
            "Get a comprehensive overview of infrastructure health and trends",
        ),
        (
            "optimize_parameters",
            "Get parameter optimization recommendations for a service",
        ),
    ]

    for name, description in prompts:
        click.echo(f"  {ctx_obj.formatter.format_info(name)}")
        click.echo(f"    {description}")
        click.echo()


def main():
    """Main entry point for MCP CLI"""
    cli()


if __name__ == "__main__":
    main()
