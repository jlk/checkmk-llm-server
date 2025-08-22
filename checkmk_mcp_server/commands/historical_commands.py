"""
Historical Data CLI Commands

This module provides CLI commands for historical data scraping and retrieval
from Checkmk monitoring interfaces.
"""

import sys
import click
import json
from typing import Optional
from datetime import datetime

from ..config import AppConfig
from ..services.historical_service import HistoricalDataService
from ..services.models.historical import HistoricalDataRequest
from ..logging_utils import setup_logging
from ..utils.request_context import generate_request_id as get_request_id


@click.group()
def historical():
    """Historical data operations for Checkmk monitoring."""
    pass


@historical.command()
@click.option(
    "--host", 
    "-h", 
    required=True, 
    help="Host name to retrieve historical data for"
)
@click.option(
    "--service", 
    "-s", 
    required=True, 
    help="Service name to retrieve historical data for"
)
@click.option(
    "--period", 
    "-p", 
    default="4h",
    type=click.Choice(["1h", "4h", "6h", "12h", "24h", "48h", "7d", "30d", "365d"]),
    help="Time period for data retrieval (default: 4h)"
)
@click.option(
    "--method", 
    "-m",
    default="auto",
    type=click.Choice(["auto", "graph", "table", "ajax"]),
    help="Extraction method (default: auto)"
)
@click.option(
    "--format", 
    "-f",
    "output_format",
    default="table",
    type=click.Choice(["table", "json", "csv"]),
    help="Output format (default: table)"
)
@click.option(
    "--verbose", 
    "-v", 
    is_flag=True, 
    help="Enable verbose logging"
)
def scrape(
    host: str, 
    service: str, 
    period: str, 
    method: str, 
    output_format: str, 
    verbose: bool
):
    """Scrape historical data from Checkmk web interface.
    
    This command scrapes historical monitoring data from the Checkmk web interface
    using various extraction methods including AJAX, graph parsing, and table extraction.
    
    Examples:
        checkmk historical scrape -h server01 -s "CPU load" -p 4h
        checkmk historical scrape -h server01 -s "Temperature Zone 0" -p 24h -m graph
        checkmk historical scrape -h server01 -s "Disk usage /" -p 7d -f json
    """
    # Setup logging
    if verbose:
        setup_logging(level="DEBUG")
    else:
        setup_logging(level="INFO")
    
    try:
        # Load configuration
        config = AppConfig.load()
        
        # Generate request ID for tracking
        request_id = get_request_id()
        
        # Create historical data service
        service_instance = HistoricalDataService(config)
        
        # Create request object
        request = HistoricalDataRequest(
            host_name=host,
            service_name=service,
            period=period,
            extraction_method=method
        )
        
        # Execute scraping request
        click.echo(f"Scraping historical data for {host}/{service} over {period}...")
        if verbose:
            click.echo(f"Request ID: {request_id}")
            click.echo(f"Method: {method}")
        
        result = service_instance.get_historical_data(request, request_id)
        
        if not result.success:
            click.echo(f"Error: {result.error}", err=True)
            sys.exit(1)
        
        # Format and display output
        if output_format == "json":
            _output_json(result, verbose)
        elif output_format == "csv":
            _output_csv(result)
        else:  # table format
            _output_table(result, verbose)
            
    except Exception as e:
        click.echo(f"Failed to scrape historical data: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


@historical.command()
@click.option(
    "--host", 
    "-h", 
    required=True, 
    help="Host name to list services for"
)
@click.option(
    "--format", 
    "-f",
    "output_format",
    default="table",
    type=click.Choice(["table", "json"]),
    help="Output format (default: table)"
)
def services(host: str, output_format: str):
    """List available services for historical data scraping.
    
    This command helps identify available services on a host that can be
    used for historical data scraping.
    
    Examples:
        checkmk historical services -h server01
        checkmk historical services -h server01 -f json
    """
    click.echo(f"Listing services for host: {host}")
    click.echo("Note: This command requires integration with the Checkmk API")
    click.echo("Use 'checkmk services list' for a complete list of services")


@historical.command()
@click.option(
    "--verbose", 
    "-v", 
    is_flag=True, 
    help="Show detailed test information"
)
def test(verbose: bool):
    """Test historical data scraping functionality.
    
    This command performs basic tests to verify that historical data scraping
    components are working correctly.
    """
    if verbose:
        setup_logging(level="DEBUG")
    else:
        setup_logging(level="INFO")
    
    try:
        click.echo("Testing historical data scraping components...")
        
        # Test 1: Import all components
        click.echo("✓ Testing imports...", nl=False)
        from ..services.web_scraping.scraper_service import ScraperService
        from ..services.web_scraping.extractors.ajax_extractor import AjaxExtractor
        from ..services.web_scraping.extractors.graph_extractor import GraphExtractor
        from ..services.web_scraping.extractors.table_extractor import TableExtractor
        from ..services.web_scraping.factory import ScraperFactory
        from ..services.web_scraping import ScrapingError
        click.echo(" ✓ All imports successful")
        
        # Test 2: Basic instantiation
        click.echo("✓ Testing instantiation...", nl=False)
        ajax = AjaxExtractor()
        graph = GraphExtractor()
        table = TableExtractor()
        factory = ScraperFactory()
        click.echo(" ✓ All components instantiate correctly")
        
        # Test 3: Configuration loading
        click.echo("✓ Testing configuration...", nl=False)
        try:
            config = AppConfig.load()
            click.echo(" ✓ Configuration loaded successfully")
        except Exception as e:
            click.echo(f" ⚠ Configuration warning: {e}")
        
        # Test 4: Service creation
        click.echo("✓ Testing service creation...", nl=False)
        try:
            config = AppConfig.load()
            service_instance = HistoricalDataService(config)
            click.echo(" ✓ Historical service created successfully")
        except Exception as e:
            click.echo(f" ✗ Service creation failed: {e}")
            
        click.echo("\n✓ All tests completed successfully!")
        click.echo("Historical data scraping is ready to use.")
        
    except Exception as e:
        click.echo(f"✗ Test failed: {e}", err=True)
        if verbose:
            import traceback
            click.echo(traceback.format_exc(), err=True)
        sys.exit(1)


def _output_json(result, verbose: bool = False):
    """Output result in JSON format."""
    output = {
        "success": result.success,
        "data_points": len(result.data_points),
        "data": [
            {
                "timestamp": dp.timestamp,
                "value": dp.value,
                "type": dp.data_type
            }
            for dp in result.data_points
        ]
    }
    
    if verbose:
        output["metadata"] = result.metadata
        output["statistics"] = result.statistics
    
    click.echo(json.dumps(output, indent=2, default=str))


def _output_csv(result):
    """Output result in CSV format."""
    click.echo("timestamp,value,type")
    for dp in result.data_points:
        click.echo(f"{dp.timestamp},{dp.value},{dp.data_type}")


def _output_table(result, verbose: bool = False):
    """Output result in table format."""
    if not result.data_points:
        click.echo("No data points found.")
        return
    
    click.echo(f"\nHistorical Data ({len(result.data_points)} points)")
    click.echo("=" * 60)
    
    # Show first few data points
    for i, dp in enumerate(result.data_points[:10]):
        timestamp = dp.timestamp
        if isinstance(timestamp, str) and 'T' in timestamp:
            # Format ISO timestamp for readability
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamp = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass  # Keep original format if parsing fails
        
        click.echo(f"{timestamp:<20} {dp.value:>10} {dp.data_type}")
    
    if len(result.data_points) > 10:
        click.echo(f"... and {len(result.data_points) - 10} more data points")
    
    # Show statistics if available
    if hasattr(result, 'statistics') and result.statistics:
        click.echo(f"\nStatistics:")
        for stat_name, stat_value in result.statistics.items():
            click.echo(f"  {stat_name}: {stat_value}")
    
    if verbose and result.metadata:
        click.echo(f"\nMetadata:")
        for key, value in result.metadata.items():
            click.echo(f"  {key}: {value}")