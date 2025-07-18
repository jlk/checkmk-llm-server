"""Command-line interface for Checkmk LLM Agent."""

import sys
import click
import logging
from typing import Optional

from .config import load_config
from .api_client import CheckmkClient
from .llm_client import create_llm_client, LLMProvider
from .host_operations import HostOperationsManager
from .utils import setup_logging


@click.group()
@click.option('--log-level', default=None, help='Logging level (DEBUG, INFO, WARNING, ERROR)')
@click.option('--config', '--config-file', help='Path to configuration file (YAML, TOML, or JSON)')
@click.pass_context
def cli(ctx, log_level: str, config: Optional[str]):
    """Checkmk LLM Agent - Natural language interface for Checkmk."""
    ctx.ensure_object(dict)

    # Load configuration first (to get config log_level if CLI flag not set)
    from .config import load_config
    app_config = load_config(config_file=config)
    ctx.obj['config'] = app_config

    # Determine log level: CLI flag overrides config
    effective_log_level = log_level or app_config.log_level

    # Setup logging
    from .logging_utils import setup_logging
    setup_logging(effective_log_level)
    logger = logging.getLogger(__name__)

    try:
        # Initialize clients
        from .api_client import CheckmkClient
        checkmk_client = CheckmkClient(app_config.checkmk)
        ctx.obj['checkmk_client'] = checkmk_client

        # Try to initialize LLM client
        try:
            from .llm_client import create_llm_client
            llm_client = create_llm_client(app_config.llm)
            ctx.obj['llm_client'] = llm_client

            # Initialize host operations manager
            from .host_operations import HostOperationsManager
            host_manager = HostOperationsManager(checkmk_client, llm_client, app_config)
            ctx.obj['host_manager'] = host_manager
            
            # Initialize service operations manager
            from .service_operations import ServiceOperationsManager
            service_manager = ServiceOperationsManager(checkmk_client, llm_client, app_config)
            ctx.obj['service_manager'] = service_manager

        except Exception as e:
            logger.warning(f"LLM client initialization failed: {e}")
            ctx.obj['llm_client'] = None
            ctx.obj['host_manager'] = None
            ctx.obj['service_manager'] = None

    except Exception as e:
        logger.error(f"Initialization failed: {e}")
        import click
        click.echo(f"❌ Error: {e}", err=True)
        import sys
        sys.exit(1)


@cli.command()
@click.pass_context
def test(ctx):
    """Test connection to Checkmk API."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        if checkmk_client.test_connection():
            click.echo("✅ Successfully connected to Checkmk API")
        else:
            click.echo("❌ Failed to connect to Checkmk API")
            sys.exit(1)
    except Exception as e:
        click.echo(f"❌ Connection test failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def interactive(ctx):
    """Start enhanced interactive mode for natural language commands."""
    host_manager = ctx.obj.get('host_manager')
    service_manager = ctx.obj.get('service_manager')
    checkmk_client = ctx.obj.get('checkmk_client')
    app_config = ctx.obj.get('config')
    
    if not host_manager:
        click.echo("❌ LLM client not available. Check your API keys in .env file.", err=True)
        sys.exit(1)
    
    # Initialize enhanced interactive components
    from .interactive import ReadlineHandler, CommandParser, HelpSystem, TabCompleter, UIManager
    
    # Setup components with UI configuration
    ui_config = app_config.ui if app_config else None
    ui_manager = UIManager(
        theme=ui_config.theme if ui_config else "default",
        use_colors=ui_config.use_colors if ui_config else None,
        custom_colors=ui_config.custom_colors if ui_config else None
    )
    help_system = HelpSystem()
    command_parser = CommandParser()
    tab_completer = TabCompleter(checkmk_client, help_system)
    
    # Setup readline with history and completion
    with ReadlineHandler() as readline_handler:
        readline_handler.set_completer(tab_completer.complete)
        
        # Print welcome message
        ui_manager.print_welcome()
        
        while True:
            try:
                # Get user input with readline support
                user_input = readline_handler.input_with_prompt(ui_manager.format_prompt()).strip()
                
                if not user_input:
                    continue
                
                # Parse the command
                intent = command_parser.parse_command(user_input)
                
                # Handle help requests
                if intent.is_help_request:
                    help_text = help_system.show_help(intent.help_topic)
                    ui_manager.print_help(help_text)
                    continue
                
                # Handle exit commands
                if intent.command == 'quit':
                    ui_manager.print_goodbye()
                    break
                
                # Handle special commands
                if intent.command == 'stats':
                    result = host_manager.get_host_statistics()
                    ui_manager.print_info(result)
                    continue
                
                if intent.command == 'test':
                    result = host_manager.test_connection()
                    ui_manager.print_info(result)
                    continue
                
                # Handle theme commands
                if intent.command.startswith('theme'):
                    args = intent.command.split()[1:] if len(intent.command.split()) > 1 else []
                    if not args:
                        ui_manager.print_info("Usage: theme [list|set <name>|current]")
                        continue
                    
                    subcommand = args[0].lower()
                    if subcommand == "list":
                        themes = ui_manager.list_themes()
                        ui_manager.print_info("🎨 Available themes:")
                        for theme in themes:
                            current = " (current)" if theme['name'] == ui_manager.get_current_theme() else ""
                            ui_manager.print_info(f"  • {theme['display_name']}{current}: {theme['description']}")
                    elif subcommand == "set" and len(args) > 1:
                        theme_name = args[1]
                        if ui_manager.set_theme(theme_name):
                            ui_manager.print_success(f"Theme changed to: {theme_name}")
                        else:
                            available = [t['name'] for t in ui_manager.list_themes()]
                            ui_manager.print_error(f"Unknown theme: {theme_name}. Available: {', '.join(available)}")
                    elif subcommand == "current":
                        current = ui_manager.get_current_theme()
                        ui_manager.print_info(f"Current theme: {current}")
                    else:
                        ui_manager.print_info("Usage: theme [list|set <name>|current]")
                    continue
                
                # Handle color commands
                if intent.command.startswith('colors'):
                    args = intent.command.split()[1:] if len(intent.command.split()) > 1 else []
                    if not args:
                        ui_manager.print_info("Usage: colors [show|test|terminal]")
                        continue
                    
                    subcommand = args[0].lower()
                    if subcommand == "show":
                        preview = ui_manager.preview_colors()
                        print(preview)
                    elif subcommand == "test":
                        test_output = ui_manager.test_colors()
                        print(test_output)
                    elif subcommand == "terminal":
                        terminal_info = ui_manager.get_terminal_info()
                        print(terminal_info)
                    else:
                        ui_manager.print_info("Usage: colors [show|test|terminal]")
                    continue
                
                # Handle low confidence commands with suggestions
                if intent.confidence < 0.6 and intent.suggestions:
                    error_msg = f"Command not clear: '{user_input}'"
                    formatted_error = ui_manager.format_error_with_suggestions(error_msg, intent.suggestions)
                    print(formatted_error)
                    continue
                
                # Route command to appropriate manager
                # First check if this is clearly a service command based on keywords
                service_keywords = ['service', 'services', 'acknowledge', 'downtime', 'discover', 'cpu', 'disk', 'memory', 'load']
                is_service_command = any(keyword in user_input.lower() for keyword in service_keywords)
                
                # Check if the command has service-related parameters
                has_service_params = 'service_description' in intent.parameters
                
                if is_service_command or has_service_params:
                    if service_manager:
                        result = service_manager.process_command(user_input)
                        ui_manager.print_info(result)
                    else:
                        ui_manager.print_error("Service manager not available. Check your configuration.")
                else:
                    # Only route to host manager if it's clearly a host command
                    command_type = command_parser.get_command_type(intent.command, intent.parameters, user_input)
                    
                    if command_type == 'host' and host_manager:
                        result = host_manager.process_command(user_input)
                        ui_manager.print_info(result)
                    else:
                        # Show error instead of defaulting to host operations
                        ui_manager.print_error(f"Unable to process command: '{user_input}'")
                        ui_manager.print_info("💡 Try 'help' for available commands or '? <command>' for specific help")
                
            except KeyboardInterrupt:
                ui_manager.print_goodbye()
                break
            except EOFError:
                ui_manager.print_goodbye()
                break
            except Exception as e:
                ui_manager.print_error(f"Error: {e}")
                
                # Provide helpful suggestions for common errors
                if "connection" in str(e).lower():
                    ui_manager.print_info("💡 Try: 'test' to check your connection")
                elif "not found" in str(e).lower():
                    ui_manager.print_info("💡 Try: 'list hosts' to see available hosts")
                elif "permission" in str(e).lower():
                    ui_manager.print_info("💡 Check your Checkmk user permissions")


@cli.group()
def hosts():
    """Host management commands."""
    pass


@hosts.command('list')
@click.option('--folder', help='Filter by folder')
@click.option('--search', help='Search term to filter hosts')
@click.option('--effective-attributes', is_flag=True, help='Show effective attributes')
@click.pass_context
def list_hosts(ctx, folder: Optional[str], search: Optional[str], effective_attributes: bool):
    """List all hosts or filter by criteria."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        hosts = checkmk_client.list_hosts(effective_attributes=effective_attributes)
        
        # Apply filters
        if folder or search:
            filtered_hosts = []
            for host in hosts:
                host_id = host.get("id", "")
                extensions = host.get("extensions", {})
                host_folder = extensions.get("folder", "")
                attributes = extensions.get("attributes", {})
                alias = attributes.get("alias", "")
                
                # Filter by folder
                if folder and folder not in host_folder:
                    continue
                
                # Filter by search term
                if search:
                    search_lower = search.lower()
                    if not any(search_lower in field.lower() for field in [host_id, host_folder, alias]):
                        continue
                
                filtered_hosts.append(host)
            
            hosts = filtered_hosts
        
        if not hosts:
            click.echo("No hosts found.")
            return
        
        # Display hosts
        click.echo(f"Found {len(hosts)} hosts:")
        for host in hosts:
            host_id = host.get("id", "Unknown")
            extensions = host.get("extensions", {})
            host_folder = extensions.get("folder", "Unknown")
            attributes = extensions.get("attributes", {})
            ip_address = attributes.get("ipaddress", "Not set")
            
            click.echo(f"  📦 {host_id}")
            click.echo(f"     Folder: {host_folder}")
            click.echo(f"     IP: {ip_address}")
            if extensions.get("is_cluster"):
                click.echo(f"     Type: Cluster")
            if extensions.get("is_offline"):
                click.echo(f"     Status: Offline")
            click.echo()
            
    except Exception as e:
        click.echo(f"❌ Error listing hosts: {e}", err=True)
        sys.exit(1)


@hosts.command('create')
@click.argument('host_name')
@click.option('--folder', default='/', help='Folder path (default: /)')
@click.option('--ip', help='IP address')
@click.option('--alias', help='Host alias/description')
@click.option('--bake-agent', is_flag=True, help='Automatically bake agent')
@click.pass_context
def create_host(ctx, host_name: str, folder: str, ip: Optional[str], 
                alias: Optional[str], bake_agent: bool):
    """Create a new host."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        attributes = {}
        if ip:
            attributes['ipaddress'] = ip
        if alias:
            attributes['alias'] = alias
        
        result = checkmk_client.create_host(
            folder=folder,
            host_name=host_name,
            attributes=attributes,
            bake_agent=bake_agent
        )
        
        click.echo(f"✅ Successfully created host: {host_name}")
        click.echo(f"   Folder: {folder}")
        if attributes:
            click.echo(f"   Attributes: {attributes}")
            
    except Exception as e:
        click.echo(f"❌ Error creating host: {e}", err=True)
        sys.exit(1)


@hosts.command('delete')
@click.argument('host_name')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
@click.pass_context
def delete_host(ctx, host_name: str, force: bool):
    """Delete a host."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        # Check if host exists
        try:
            host = checkmk_client.get_host(host_name)
            click.echo(f"Host found: {host_name}")
            extensions = host.get("extensions", {})
            folder = extensions.get("folder", "Unknown")
            click.echo(f"Folder: {folder}")
        except Exception as e:
            click.echo(f"❌ Host '{host_name}' not found: {e}", err=True)
            sys.exit(1)
        
        # Confirmation
        if not force:
            if not click.confirm(f"Are you sure you want to delete host '{host_name}'?"):
                click.echo("❌ Deletion cancelled.")
                return
        
        checkmk_client.delete_host(host_name)
        click.echo(f"✅ Successfully deleted host: {host_name}")
        
    except Exception as e:
        click.echo(f"❌ Error deleting host: {e}", err=True)
        sys.exit(1)


@hosts.command('get')
@click.argument('host_name')
@click.option('--effective-attributes', is_flag=True, help='Show effective attributes')
@click.pass_context
def get_host(ctx, host_name: str, effective_attributes: bool):
    """Get detailed information about a host."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        host = checkmk_client.get_host(host_name, effective_attributes=effective_attributes)
        
        host_id = host.get("id", "Unknown")
        extensions = host.get("extensions", {})
        folder = extensions.get("folder", "Unknown")
        attributes = extensions.get("attributes", {})
        
        click.echo(f"📦 Host Details: {host_id}")
        click.echo(f"   Folder: {folder}")
        click.echo(f"   Cluster: {'Yes' if extensions.get('is_cluster') else 'No'}")
        click.echo(f"   Offline: {'Yes' if extensions.get('is_offline') else 'No'}")
        
        if attributes:
            click.echo("   Attributes:")
            for key, value in attributes.items():
                click.echo(f"     {key}: {value}")
        
        if effective_attributes and extensions.get("effective_attributes"):
            click.echo("   Effective Attributes:")
            for key, value in extensions["effective_attributes"].items():
                click.echo(f"     {key}: {value}")
        
    except Exception as e:
        click.echo(f"❌ Error getting host: {e}", err=True)
        sys.exit(1)


@hosts.command('interactive-create')
@click.pass_context
def interactive_create(ctx):
    """Create a host with interactive prompts."""
    host_manager = ctx.obj.get('host_manager')
    
    if not host_manager:
        click.echo("❌ Host manager not available.", err=True)
        sys.exit(1)
    
    result = host_manager.interactive_create_host()
    click.echo(result)


@cli.group()
def rules():
    """Rule management commands."""
    pass


@rules.command('list')
@click.argument('ruleset_name')
@click.pass_context
def list_rules(ctx, ruleset_name: str):
    """List all rules in a specific ruleset."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        rules = checkmk_client.list_rules(ruleset_name)
        
        if not rules:
            click.echo(f"No rules found in ruleset: {ruleset_name}")
            return
        
        # Display rules
        click.echo(f"Found {len(rules)} rules in ruleset '{ruleset_name}':")
        for rule in rules:
            rule_id = rule.get("id", "Unknown")
            extensions = rule.get("extensions", {})
            folder = extensions.get("folder", "Unknown")
            properties = extensions.get("properties", {})
            disabled = properties.get("disabled", False)
            description = properties.get("description", "")
            
            click.echo(f"  📋 {rule_id}")
            click.echo(f"     Folder: {folder}")
            click.echo(f"     Status: {'Disabled' if disabled else 'Enabled'}")
            if description:
                click.echo(f"     Description: {description}")
            click.echo()
            
    except Exception as e:
        click.echo(f"❌ Error listing rules: {e}", err=True)
        sys.exit(1)


@rules.command('create')
@click.argument('ruleset_name')
@click.option('--folder', default='/', help='Folder path (default: /)')
@click.option('--value', help='Rule value as JSON string')
@click.option('--description', help='Rule description')
@click.option('--disabled', is_flag=True, help='Create rule as disabled')
@click.pass_context
def create_rule(ctx, ruleset_name: str, folder: str, value: Optional[str], 
                description: Optional[str], disabled: bool):
    """Create a new rule in a ruleset."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        # If value not provided, prompt for it
        if not value:
            value = click.prompt("Enter rule value as JSON string")
        
        # Build properties
        properties = {}
        if description:
            properties['description'] = description
        if disabled:
            properties['disabled'] = True
        
        result = checkmk_client.create_rule(
            ruleset=ruleset_name,
            folder=folder,
            value_raw=value,
            properties=properties
        )
        
        rule_id = result.get("id", "Unknown")
        click.echo(f"✅ Successfully created rule: {rule_id}")
        click.echo(f"   Ruleset: {ruleset_name}")
        click.echo(f"   Folder: {folder}")
        if properties:
            click.echo(f"   Properties: {properties}")
            
    except Exception as e:
        click.echo(f"❌ Error creating rule: {e}", err=True)
        sys.exit(1)


@rules.command('delete')
@click.argument('rule_id')
@click.option('--force', is_flag=True, help='Skip confirmation prompt')
@click.pass_context
def delete_rule(ctx, rule_id: str, force: bool):
    """Delete a rule."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        # Check if rule exists
        try:
            rule = checkmk_client.get_rule(rule_id)
            extensions = rule.get("extensions", {})
            ruleset = extensions.get("ruleset", "Unknown")
            folder = extensions.get("folder", "Unknown")
            click.echo(f"Rule found: {rule_id}")
            click.echo(f"Ruleset: {ruleset}")
            click.echo(f"Folder: {folder}")
        except Exception as e:
            click.echo(f"❌ Rule '{rule_id}' not found: {e}", err=True)
            sys.exit(1)
        
        # Confirmation
        if not force:
            if not click.confirm(f"Are you sure you want to delete rule '{rule_id}'?"):
                click.echo("❌ Deletion cancelled.")
                return
        
        checkmk_client.delete_rule(rule_id)
        click.echo(f"✅ Successfully deleted rule: {rule_id}")
        
    except Exception as e:
        click.echo(f"❌ Error deleting rule: {e}", err=True)
        sys.exit(1)


@rules.command('get')
@click.argument('rule_id')
@click.pass_context
def get_rule(ctx, rule_id: str):
    """Get detailed information about a rule."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        rule = checkmk_client.get_rule(rule_id)
        
        rule_id = rule.get("id", "Unknown")
        extensions = rule.get("extensions", {})
        ruleset = extensions.get("ruleset", "Unknown")
        folder = extensions.get("folder", "Unknown")
        properties = extensions.get("properties", {})
        value_raw = extensions.get("value_raw", "")
        
        click.echo(f"📋 Rule Details: {rule_id}")
        click.echo(f"   Ruleset: {ruleset}")
        click.echo(f"   Folder: {folder}")
        click.echo(f"   Status: {'Disabled' if properties.get('disabled') else 'Enabled'}")
        
        if properties.get("description"):
            click.echo(f"   Description: {properties['description']}")
        
        if value_raw:
            click.echo(f"   Value: {value_raw}")
        
        if extensions.get("conditions"):
            click.echo(f"   Conditions: {extensions['conditions']}")
        
    except Exception as e:
        click.echo(f"❌ Error getting rule: {e}", err=True)
        sys.exit(1)


@rules.command('move')
@click.argument('rule_id')
@click.argument('position', type=click.Choice(['top_of_folder', 'bottom_of_folder', 'before', 'after']))
@click.option('--folder', help='Target folder for the rule')
@click.option('--target-rule', help='Target rule ID for before/after positioning')
@click.pass_context
def move_rule(ctx, rule_id: str, position: str, folder: Optional[str], target_rule: Optional[str]):
    """Move a rule to a new position."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        if position in ['before', 'after'] and not target_rule:
            raise ValueError(f"--target-rule is required when position is '{position}'")
        
        result = checkmk_client.move_rule(
            rule_id=rule_id,
            position=position,
            folder=folder,
            target_rule_id=target_rule
        )
        
        click.echo(f"✅ Successfully moved rule: {rule_id}")
        click.echo(f"   Position: {position}")
        if folder:
            click.echo(f"   Target folder: {folder}")
        if target_rule:
            click.echo(f"   Target rule: {target_rule}")
        
    except Exception as e:
        click.echo(f"❌ Error moving rule: {e}", err=True)
        sys.exit(1)


@cli.group()
def services():
    """Service management commands."""
    pass


@services.command('list')
@click.argument('host_name', required=False)
@click.option('--sites', multiple=True, help='Restrict to specific sites')
@click.option('--query', help='Livestatus query expressions')
@click.option('--columns', multiple=True, help='Desired columns')
@click.pass_context
def list_services(ctx, host_name: Optional[str], sites: tuple, query: Optional[str], columns: tuple):
    """List services for a host or all services."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        if host_name:
            # List services for specific host
            services = checkmk_client.list_host_services(
                host_name=host_name,
                sites=list(sites) if sites else None,
                query=query,
                columns=list(columns) if columns else None
            )
        else:
            # List all services
            services = checkmk_client.list_all_services(
                sites=list(sites) if sites else None,
                query=query,
                columns=list(columns) if columns else None
            )
        
        if not services:
            if host_name:
                click.echo(f"No services found for host: {host_name}")
            else:
                click.echo("No services found.")
            return
        
        # Display services
        if host_name:
            click.echo(f"Found {len(services)} services for host: {host_name}")
        else:
            click.echo(f"Found {len(services)} services")
        
        for service in services:
            extensions = service.get('extensions', {})
            service_desc = extensions.get('description', 'Unknown')
            service_state = extensions.get('state', 'Unknown')
            host = extensions.get('host_name', host_name or 'Unknown')
            
            state_emoji = '✅' if service_state == 'OK' or service_state == 0 else '❌'
            click.echo(f"  {state_emoji} {host}/{service_desc} - {service_state}")
            
    except Exception as e:
        click.echo(f"❌ Error listing services: {e}", err=True)
        sys.exit(1)


@services.command('status')
@click.argument('host_name')
@click.argument('service_description')
@click.pass_context
def get_service_status(ctx, host_name: str, service_description: str):
    """Get detailed status of a specific service."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        services = checkmk_client.list_host_services(
            host_name=host_name,
            query=f"service_description = '{service_description}'"
        )
        
        if not services:
            click.echo(f"❌ Service '{service_description}' not found on host '{host_name}'")
            sys.exit(1)
        
        service = services[0]
        extensions = service.get('extensions', {})
        service_state = extensions.get('state', 'Unknown')
        last_check = extensions.get('last_check', 'Unknown')
        plugin_output = extensions.get('plugin_output', 'No output')
        
        state_emoji = '✅' if service_state == 'OK' or service_state == 0 else '❌'
        
        click.echo(f"📊 Service Status: {host_name}/{service_description}")
        click.echo(f"{state_emoji} State: {service_state}")
        click.echo(f"⏰ Last Check: {last_check}")
        click.echo(f"💬 Output: {plugin_output}")
        
    except Exception as e:
        click.echo(f"❌ Error getting service status: {e}", err=True)
        sys.exit(1)


@services.command('acknowledge')
@click.argument('host_name')
@click.argument('service_description')
@click.option('--comment', default='Acknowledged via CLI', help='Acknowledgment comment')
@click.option('--sticky', is_flag=True, help='Make acknowledgment sticky')
@click.pass_context
def acknowledge_service(ctx, host_name: str, service_description: str, comment: str, sticky: bool):
    """Acknowledge a service problem."""
    checkmk_client = ctx.obj['checkmk_client']
    config = ctx.obj['config']
    
    try:
        author = config.checkmk.username
        
        checkmk_client.acknowledge_service_problems(
            host_name=host_name,
            service_description=service_description,
            comment=comment,
            author=author,
            sticky=sticky
        )
        
        click.echo(f"✅ Acknowledged service problem: {host_name}/{service_description}")
        click.echo(f"💬 Comment: {comment}")
        
    except Exception as e:
        click.echo(f"❌ Error acknowledging service: {e}", err=True)
        sys.exit(1)


@services.command('downtime')
@click.argument('host_name')
@click.argument('service_description')
@click.option('--hours', default=2, type=int, help='Duration in hours (default: 2)')
@click.option('--comment', default='Downtime created via CLI', help='Downtime comment')
@click.pass_context
def create_service_downtime(ctx, host_name: str, service_description: str, hours: int, comment: str):
    """Create downtime for a service."""
    checkmk_client = ctx.obj['checkmk_client']
    config = ctx.obj['config']
    
    try:
        from datetime import datetime, timedelta
        
        start_time = datetime.now()
        end_time = start_time + timedelta(hours=hours)
        author = config.checkmk.username
        
        checkmk_client.create_service_downtime(
            host_name=host_name,
            service_description=service_description,
            start_time=start_time.isoformat(),
            end_time=end_time.isoformat(),
            comment=comment,
            author=author
        )
        
        click.echo(f"✅ Created downtime for service: {host_name}/{service_description}")
        click.echo(f"⏰ Duration: {hours} hours")
        click.echo(f"🕐 Start: {start_time.strftime('%Y-%m-%d %H:%M')}")
        click.echo(f"🕑 End: {end_time.strftime('%Y-%m-%d %H:%M')}")
        click.echo(f"💬 Comment: {comment}")
        
    except Exception as e:
        click.echo(f"❌ Error creating downtime: {e}", err=True)
        sys.exit(1)


@services.command('discover')
@click.argument('host_name')
@click.option('--mode', default='refresh', 
              type=click.Choice(['refresh', 'new', 'remove', 'fixall', 'refresh_autochecks']),
              help='Discovery mode (default: refresh)')
@click.pass_context
def discover_services(ctx, host_name: str, mode: str):
    """Discover services on a host."""
    checkmk_client = ctx.obj['checkmk_client']
    
    try:
        # Start service discovery
        click.echo(f"🔍 Starting service discovery for host: {host_name} (mode: {mode})")
        checkmk_client.start_service_discovery(host_name, mode)
        
        # Get discovery results
        discovery_result = checkmk_client.get_service_discovery_result(host_name)
        
        # Format response
        extensions = discovery_result.get('extensions', {})
        vanished = extensions.get('vanished', [])
        new = extensions.get('new', [])
        ignored = extensions.get('ignored', [])
        
        click.echo(f"✅ Service discovery completed for host: {host_name}")
        
        if new:
            click.echo(f"\n✨ New services found ({len(new)}):")
            for service in new:
                service_desc = service.get('service_description', 'Unknown')
                click.echo(f"  + {service_desc}")
        
        if vanished:
            click.echo(f"\n👻 Vanished services ({len(vanished)}):")
            for service in vanished:
                service_desc = service.get('service_description', 'Unknown')
                click.echo(f"  - {service_desc}")
        
        if ignored:
            click.echo(f"\n🚫 Ignored services ({len(ignored)}):")
            for service in ignored:
                service_desc = service.get('service_description', 'Unknown')
                click.echo(f"  ! {service_desc}")
        
        if not new and not vanished and not ignored:
            click.echo("\n✅ No service changes detected")
        
    except Exception as e:
        click.echo(f"❌ Error discovering services: {e}", err=True)
        sys.exit(1)


@services.command('stats')
@click.pass_context
def service_stats(ctx):
    """Show service statistics."""
    service_manager = ctx.obj.get('service_manager')
    
    if not service_manager:
        # Fallback to basic stats without LLM
        checkmk_client = ctx.obj['checkmk_client']
        try:
            services = checkmk_client.list_all_services()
            click.echo(f"📊 Total services: {len(services)}")
        except Exception as e:
            click.echo(f"❌ Error getting statistics: {e}", err=True)
        return
    
    result = service_manager.get_service_statistics()
    click.echo(result)


# Service parameter commands

@services.group('params')
def service_params():
    """Service parameter management commands."""
    pass


@service_params.command('defaults')
@click.argument('service_type', required=False, default='cpu')
@click.pass_context
def view_default_parameters(ctx, service_type: str):
    """View default parameters for a service type."""
    service_manager = ctx.obj.get('service_manager')
    
    if not service_manager:
        click.echo("❌ Service manager not available", err=True)
        sys.exit(1)
    
    # Use parameter manager directly
    from checkmk_agent.service_parameters import ServiceParameterManager
    checkmk_client = ctx.obj['checkmk_client']
    config = ctx.obj['config']
    param_manager = ServiceParameterManager(checkmk_client, config)
    
    try:
        default_params = param_manager.get_default_parameters(service_type)
        
        if not default_params:
            click.echo(f"❌ No default parameters found for service type: {service_type}")
            return
        
        click.echo(f"📊 Default Parameters for {service_type.upper()} services:")
        click.echo()
        
        if 'levels' in default_params:
            warning, critical = default_params['levels']
            click.echo(f"⚠️  Warning Threshold: {warning}%")
            click.echo(f"❌ Critical Threshold: {critical}%")
        
        if 'average' in default_params:
            click.echo(f"📈 Averaging Period: {default_params['average']} minutes")
        
        if 'magic_normsize' in default_params:
            click.echo(f"💾 Magic Normsize: {default_params['magic_normsize']} GB")
        
        if 'magic' in default_params:
            click.echo(f"🎯 Magic Factor: {default_params['magic']}")
        
        # Show applicable ruleset
        ruleset_map = param_manager.PARAMETER_RULESETS.get(service_type, {})
        default_ruleset = ruleset_map.get('default', 'Unknown')
        click.echo()
        click.echo(f"📋 Default Ruleset: {default_ruleset}")
        
    except Exception as e:
        click.echo(f"❌ Error viewing default parameters: {e}", err=True)
        sys.exit(1)


@service_params.command('show')
@click.argument('host_name')
@click.argument('service_description')
@click.pass_context
def view_service_parameters(ctx, host_name: str, service_description: str):
    """View effective parameters for a specific service."""
    service_manager = ctx.obj.get('service_manager')
    
    if not service_manager:
        click.echo("❌ Service manager not available", err=True)
        sys.exit(1)
    
    from checkmk_agent.service_parameters import ServiceParameterManager
    checkmk_client = ctx.obj['checkmk_client']
    config = ctx.obj['config']
    param_manager = ServiceParameterManager(checkmk_client, config)
    
    try:
        param_info = param_manager.get_service_parameters(host_name, service_description)
        
        if param_info['source'] == 'default':
            click.echo(f"📊 Parameters for {host_name}/{service_description}:")
            click.echo("📋 Using default parameters (no custom rules found)")
        else:
            click.echo(f"📊 Effective Parameters for {host_name}/{service_description}:")
            click.echo()
            
            effective_params = param_info['parameters']
            if 'levels' in effective_params:
                warning, critical = effective_params['levels']
                click.echo(f"⚠️  Warning: {warning}%")
                click.echo(f"❌ Critical: {critical}%")
            
            if 'average' in effective_params:
                click.echo(f"📈 Average: {effective_params['average']} min")
            
            if 'magic_normsize' in effective_params:
                click.echo(f"💾 Magic Normsize: {effective_params['magic_normsize']} GB")
            
            primary_rule = param_info.get('primary_rule')
            if primary_rule:
                rule_id = primary_rule.get('id', 'Unknown')
                click.echo()
                click.echo(f"🔗 Source: Rule {rule_id}")
            
            # Show rule precedence if multiple rules
            all_rules = param_info.get('all_rules', [])
            if len(all_rules) > 1:
                click.echo()
                click.echo(f"📊 Rule Precedence ({len(all_rules)} rules):")
                for i, rule in enumerate(all_rules[:3], 1):
                    rule_id = rule.get('id', 'Unknown')
                    is_primary = i == 1
                    status = "" if is_primary else " [OVERRIDDEN]"
                    click.echo(f"{i}. Rule {rule_id}{status}")
                
                if len(all_rules) > 3:
                    click.echo(f"... and {len(all_rules) - 3} more rules")
        
    except Exception as e:
        click.echo(f"❌ Error viewing service parameters: {e}", err=True)
        sys.exit(1)


@service_params.command('set')
@click.argument('host_name')
@click.argument('service_description')
@click.option('--warning', type=float, help='Warning threshold')
@click.option('--critical', type=float, help='Critical threshold')
@click.option('--comment', help='Comment for the rule')
@click.pass_context
def set_service_parameters(ctx, host_name: str, service_description: str, 
                          warning: float, critical: float, comment: str):
    """Set/override parameters for a service."""
    if not warning and not critical:
        click.echo("❌ Please specify at least one of --warning or --critical", err=True)
        sys.exit(1)
    
    service_manager = ctx.obj.get('service_manager')
    
    if not service_manager:
        click.echo("❌ Service manager not available", err=True)
        sys.exit(1)
    
    from checkmk_agent.service_parameters import ServiceParameterManager
    checkmk_client = ctx.obj['checkmk_client']
    config = ctx.obj['config']
    param_manager = ServiceParameterManager(checkmk_client, config)
    
    try:
        # Get current parameters to fill in missing values
        current_params = param_manager.get_service_parameters(host_name, service_description)
        current_levels = current_params.get('parameters', {}).get('levels', (80.0, 90.0))
        
        # Use provided values or fall back to current/default
        final_warning = warning if warning is not None else (current_levels[0] if len(current_levels) > 0 else 80.0)
        final_critical = critical if critical is not None else (current_levels[1] if len(current_levels) > 1 else 90.0)
        
        # Validate thresholds
        if final_warning >= final_critical:
            click.echo("❌ Warning threshold must be less than critical threshold", err=True)
            sys.exit(1)
        
        # Create override
        final_comment = comment or f"Override thresholds for {service_description} on {host_name}"
        
        rule_id = param_manager.create_simple_override(
            host_name=host_name,
            service_name=service_description,
            warning=final_warning,
            critical=final_critical,
            comment=final_comment
        )
        
        click.echo(f"✅ Created parameter override for {host_name}/{service_description}")
        click.echo(f"⚠️  Warning: {final_warning}%")
        click.echo(f"❌ Critical: {final_critical}%")
        click.echo(f"🆔 Rule ID: {rule_id}")
        click.echo(f"💬 Comment: {final_comment}")
        click.echo("⏱️  Changes will take effect after next service check cycle")
        
    except Exception as e:
        click.echo(f"❌ Error setting service parameters: {e}", err=True)
        sys.exit(1)


@service_params.command('rules')
@click.option('--ruleset', help='Show rules for specific ruleset')
@click.pass_context
def list_parameter_rules(ctx, ruleset: str):
    """List parameter rules."""
    service_manager = ctx.obj.get('service_manager')
    
    if not service_manager:
        click.echo("❌ Service manager not available", err=True)
        sys.exit(1)
    
    from checkmk_agent.service_parameters import ServiceParameterManager
    checkmk_client = ctx.obj['checkmk_client']
    config = ctx.obj['config']
    param_manager = ServiceParameterManager(checkmk_client, config)
    
    try:
        if not ruleset:
            # List available rulesets
            rulesets = param_manager.list_parameter_rulesets()
            
            click.echo(f"📋 Available Parameter Rulesets ({len(rulesets)}):")
            click.echo()
            
            # Group by category
            categories = {}
            for ruleset_obj in rulesets:
                ruleset_id = ruleset_obj.get('id', 'Unknown')
                # Categorize based on name
                if 'cpu' in ruleset_id:
                    categories.setdefault('CPU', []).append(ruleset_id)
                elif 'memory' in ruleset_id:
                    categories.setdefault('Memory', []).append(ruleset_id)
                elif 'filesystem' in ruleset_id:
                    categories.setdefault('Filesystem', []).append(ruleset_id)
                elif 'interface' in ruleset_id or 'network' in ruleset_id:
                    categories.setdefault('Network', []).append(ruleset_id)
                else:
                    categories.setdefault('Other', []).append(ruleset_id)
            
            for category, rulesets_list in categories.items():
                click.echo(f"📁 {category}:")
                for ruleset_id in rulesets_list:
                    click.echo(f"  📊 {ruleset_id}")
                click.echo()
            
            click.echo("💡 Use --ruleset <name> to see rules for a specific ruleset")
        else:
            # List rules for specific ruleset
            rules = checkmk_client.list_rules(ruleset)
            
            if not rules:
                click.echo(f"📋 No rules found for ruleset: {ruleset}")
                return
            
            click.echo(f"📋 Rules for {ruleset} ({len(rules)}):")
            click.echo()
            
            for rule in rules[:10]:  # Show first 10 rules
                rule_id = rule.get('id', 'Unknown')
                extensions = rule.get('extensions', {})
                conditions = extensions.get('conditions', {})
                properties = extensions.get('properties', {})
                
                click.echo(f"🔧 Rule {rule_id}")
                
                # Show conditions
                if conditions.get('host_name'):
                    hosts = ', '.join(conditions['host_name'][:3])
                    if len(conditions['host_name']) > 3:
                        hosts += f" (and {len(conditions['host_name']) - 3} more)"
                    click.echo(f"  🖥️  Hosts: {hosts}")
                
                if conditions.get('service_description'):
                    services = ', '.join(conditions['service_description'][:2])
                    if len(conditions['service_description']) > 2:
                        services += f" (and {len(conditions['service_description']) - 2} more)"
                    click.echo(f"  🔧 Services: {services}")
                
                if properties.get('description'):
                    desc = properties['description'][:50]
                    if len(properties['description']) > 50:
                        desc += "..."
                    click.echo(f"  💬 Description: {desc}")
                
                click.echo()
            
            if len(rules) > 10:
                click.echo(f"... and {len(rules) - 10} more rules")
        
    except Exception as e:
        click.echo(f"❌ Error listing parameter rules: {e}", err=True)
        sys.exit(1)


@service_params.command('discover')
@click.argument('host_name', required=False)
@click.argument('service_description')
@click.pass_context
def discover_ruleset(ctx, host_name: str, service_description: str):
    """Discover the appropriate ruleset for a service."""
    service_manager = ctx.obj.get('service_manager')
    
    if not service_manager:
        click.echo("❌ Service manager not available", err=True)
        sys.exit(1)
    
    from checkmk_agent.service_parameters import ServiceParameterManager
    checkmk_client = ctx.obj['checkmk_client']
    config = ctx.obj['config']
    param_manager = ServiceParameterManager(checkmk_client, config)
    
    try:
        # Discover ruleset
        ruleset = param_manager.discover_service_ruleset(host_name or 'unknown', service_description)
        
        if not ruleset:
            click.echo(f"❌ Could not determine appropriate ruleset for service: {service_description}")
            return
        
        click.echo(f"🔍 Service: {service_description}")
        if host_name:
            click.echo(f"🖥️  Host: {host_name}")
        click.echo(f"📋 Recommended Ruleset: {ruleset}")
        click.echo()
        
        # Show default parameters for this ruleset
        service_type = 'cpu' if 'cpu' in ruleset else 'memory' if 'memory' in ruleset else 'filesystem' if 'filesystem' in ruleset else 'network'
        default_params = param_manager.get_default_parameters(service_type)
        
        if default_params:
            click.echo("📊 Default Parameters:")
            if 'levels' in default_params:
                warning, critical = default_params['levels']
                click.echo(f"  ⚠️  Warning: {warning}%")
                click.echo(f"  ❌ Critical: {critical}%")
            
            if 'average' in default_params:
                click.echo(f"  📈 Average: {default_params['average']} min")
        
        click.echo()
        click.echo(f"💡 To override parameters: checkmk-agent services params set {host_name or 'HOSTNAME'} '{service_description}' --warning 85 --critical 95")
        
    except Exception as e:
        click.echo(f"❌ Error discovering ruleset: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def stats(ctx):
    """Show host statistics."""
    host_manager = ctx.obj.get('host_manager')
    
    if not host_manager:
        # Fallback to basic stats without LLM
        checkmk_client = ctx.obj['checkmk_client']
        try:
            hosts = checkmk_client.list_hosts()
            click.echo(f"📊 Total hosts: {len(hosts)}")
        except Exception as e:
            click.echo(f"❌ Error getting statistics: {e}", err=True)
        return
    
    result = host_manager.get_host_statistics()
    click.echo(result)


def show_help():
    """Show detailed help information."""
    click.echo("""
🔧 Available Commands:

Natural Language Commands - Host Management:
  - "list all hosts" / "show hosts"
  - "create host server01 in folder /web"
  - "delete host server01"
  - "show details for server01"

Natural Language Commands - Service Management:
  - "list services for server01" / "show all services"
  - "acknowledge CPU load on server01"
  - "create downtime for disk space on server01"
  - "discover services on server01"

Special Commands:
  - help/h        Show this help
  - stats         Show host statistics
  - test          Test API connection
  - exit/quit/q   Exit interactive mode

Examples:
  🔧 checkmk> list all hosts
  🔧 checkmk> create host web01 with ip 192.168.1.10
  🔧 checkmk> show services for web01
  🔧 checkmk> acknowledge CPU load on web01 with comment "investigating"
  🔧 checkmk> create 4 hour downtime for disk space on web01
  🔧 checkmk> discover services on web01
""")


if __name__ == '__main__':
    cli()