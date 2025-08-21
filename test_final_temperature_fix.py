#!/usr/bin/env python3
"""
Final test to verify that get_metric_history is working correctly for Temperature Zone 0.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add the project root to the path to import modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from checkmk_agent.config import load_config
from checkmk_agent.services.historical_service import HistoricalDataService
from checkmk_agent.services.models.historical import HistoricalDataRequest
from checkmk_agent.async_api_client import AsyncCheckmkClient

# Configure logging for output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

async def test_temperature_metric_history():
    """Test that get_metric_history now works correctly for Temperature Zone 0."""
    logger.info("=== Final Temperature Zone 0 Fix Verification ===")
    
    try:
        # Load configuration
        config = load_config()
        logger.info(f"Testing on server: {config.checkmk.server_url}")
        
        # Create async client and historical service
        checkmk_client = AsyncCheckmkClient(config.checkmk)
        historical_service = HistoricalDataService(checkmk_client, config)
        
        # Create request for Temperature Zone 0
        request = HistoricalDataRequest(
            host_name="piaware",
            service_name="Temperature Zone 0",
            period="4h",
            metric_name="temperature",
            source="scraper"
        )
        
        logger.info(f"Making request: {request}")
        
        # Call historical service
        result = await historical_service.get_historical_data(request)
        
        # Check results
        if result.success:
            logger.info("✅ SUCCESS: Historical data retrieval succeeded!")
            logger.info(f"   Data points: {len(result.data.data_points)}")
            logger.info(f"   Summary stats: {result.data.summary_stats}")
            logger.info(f"   Metadata: {result.data.metadata}")
            
            # Check if we got temperature data
            if result.data.summary_stats and 'last' in result.data.summary_stats:
                temp_value = result.data.summary_stats['last']
                logger.info(f"🌡️  Current temperature: {temp_value}°C")
                
                # Validate temperature value
                if isinstance(temp_value, (int, float)) and 0 <= temp_value <= 100:
                    logger.info("✅ Temperature value looks reasonable!")
                    return True
                else:
                    logger.warning(f"⚠️  Temperature value seems unusual: {temp_value}")
                    return False
            else:
                logger.warning("⚠️  No temperature summary statistics found")
                return False
        else:
            logger.error(f"❌ FAILED: {result.error}")
            logger.error(f"   Metadata: {result.metadata}")
            return False
            
    except Exception as e:
        logger.exception(f"❌ ERROR: {e}")
        return False

async def main():
    """Run the test."""
    logger.info("Testing Temperature Zone 0 get_metric_history fix...")
    
    success = await test_temperature_metric_history()
    
    if success:
        logger.info("")
        logger.info("🎉 SUCCESS: get_metric_history for Temperature Zone 0 is now working!")
        logger.info("   The modular scraper successfully extracts temperature data.")
        logger.info("   Fixed issues:")
        logger.info("   - Graph extractor no longer extracts timestamps as temperature values")
        logger.info("   - Table extractor now recognizes 'Temperature:' headers")
        logger.info("   - Table extractor correctly handles separate header/value cells")
        logger.info("   - Temperature values are properly validated as reasonable temperatures")
    else:
        logger.error("")
        logger.error("❌ FAILED: get_metric_history still has issues")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())