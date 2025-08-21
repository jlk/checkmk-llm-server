#!/usr/bin/env python3
"""
Debug script to test get_metric_history for Temperature Zone 0 specifically.
This will help identify exactly what's going wrong in the call chain.
"""

import asyncio
import json
import logging
import sys
import os
from datetime import datetime
from pathlib import Path

# Add the project root to the path to import modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from checkmk_agent.config import load_config
from checkmk_agent.async_api_client import AsyncCheckmkClient
from checkmk_agent.services.historical_service import HistoricalDataService
from checkmk_agent.services.models.historical import HistoricalDataRequest
from checkmk_agent.mcp_server import CheckmkMCPServer

# Configure logging for debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def test_historical_service_directly():
    """Test the historical service directly to see if it can get Temperature Zone 0 data."""
    logger.info("=== Testing Historical Service Directly ===")
    
    try:
        # Load configuration
        config = load_config()
        logger.info(f"Loaded config for server: {config.checkmk.server_url}")
        
        # Create async client
        checkmk_client = AsyncCheckmkClient(config.checkmk)
        
        # Create historical service
        historical_service = HistoricalDataService(checkmk_client, config)
        
        # Create request for Temperature Zone 0
        request = HistoricalDataRequest(
            host_name="piaware",
            service_name="Temperature Zone 0",
            period="4h",
            metric_name="temperature",
            source="scraper"
        )
        
        logger.info(f"Making historical data request: {request}")
        
        # Call historical service
        result = await historical_service.get_historical_data(request)
        
        logger.info(f"Historical service result: success={result.success}")
        if result.success:
            logger.info(f"Data points: {len(result.data.data_points)}")
            logger.info(f"Summary stats: {result.data.summary_stats}")
            logger.info(f"Metadata: {result.data.metadata}")
            
            # Show sample data points
            if result.data.data_points:
                logger.info("Sample data points:")
                for i, dp in enumerate(result.data.data_points[:5]):
                    logger.info(f"  {i+1}: {dp.timestamp} = {dp.value} {dp.unit or ''}")
        else:
            logger.error(f"Historical service failed: {result.error}")
            logger.error(f"Metadata: {result.metadata}")
        
        return result
        
    except Exception as e:
        logger.exception(f"Error testing historical service: {e}")
        return None

async def test_scraper_service_directly():
    """Test the scraper service directly to see if it can get Temperature Zone 0 data."""
    logger.info("=== Testing Scraper Service Directly ===")
    
    try:
        # Load configuration
        config = load_config()
        
        # Import and create scraper service
        from checkmk_agent.services.web_scraping.scraper_service import ScraperService
        
        scraper = ScraperService(config.checkmk)
        
        logger.info("Calling scraper.scrape_historical_data directly")
        
        # Call scraper directly
        raw_result = scraper.scrape_historical_data(
            period="4h",
            host="piaware",
            service="Temperature Zone 0"
        )
        
        logger.info(f"Scraper returned: {type(raw_result)} with {len(raw_result) if isinstance(raw_result, list) else 'unknown'} items")
        
        if isinstance(raw_result, list):
            logger.info("Sample raw results:")
            for i, item in enumerate(raw_result[:10]):
                logger.info(f"  {i+1}: {item}")
        else:
            logger.info(f"Raw result: {raw_result}")
        
        return raw_result
        
    except Exception as e:
        logger.exception(f"Error testing scraper service: {e}")
        return None

async def test_mcp_tool_get_metric_history():
    """Test the MCP tool get_metric_history specifically."""
    logger.info("=== Testing MCP Tool get_metric_history ===")
    
    try:
        # Load configuration
        config = load_config()
        
        # Create MCP server
        mcp_server = CheckmkMCPServer(config)
        await mcp_server._init_services()
        
        # Get the metrics tools
        metrics_tools = mcp_server.metrics_tools
        
        # Get the get_metric_history handler
        handlers = metrics_tools.get_handlers()
        get_metric_history = handlers.get("get_metric_history")
        
        if not get_metric_history:
            logger.error("get_metric_history handler not found!")
            return None
        
        logger.info("Calling get_metric_history handler with scraper data source")
        
        # Call the handler
        result = await get_metric_history(
            host_name="piaware",
            service_description="Temperature Zone 0",
            metric_id="temperature",
            time_range_hours=4,
            data_source="scraper"
        )
        
        logger.info(f"MCP tool result: {json.dumps(result, indent=2, default=str)}")
        
        return result
        
    except Exception as e:
        logger.exception(f"Error testing MCP tool: {e}")
        return None

async def main():
    """Run all tests to identify the issue."""
    logger.info("Starting Temperature Zone 0 debug tests")
    logger.info("=" * 60)
    
    # Test 1: Scraper service directly
    scraper_result = await test_scraper_service_directly()
    logger.info("\n" + "=" * 60)
    
    # Test 2: Historical service
    historical_result = await test_historical_service_directly()
    logger.info("\n" + "=" * 60)
    
    # Test 3: MCP tool
    mcp_result = await test_mcp_tool_get_metric_history()
    logger.info("\n" + "=" * 60)
    
    # Summary
    logger.info("=== SUMMARY ===")
    logger.info(f"Scraper service: {'SUCCESS' if scraper_result else 'FAILED'}")
    logger.info(f"Historical service: {'SUCCESS' if historical_result and historical_result.success else 'FAILED'}")
    logger.info(f"MCP tool: {'SUCCESS' if mcp_result and mcp_result.get('success') else 'FAILED'}")
    
    if mcp_result and not mcp_result.get('success'):
        logger.error(f"MCP tool error: {mcp_result.get('error')}")

if __name__ == "__main__":
    asyncio.run(main())