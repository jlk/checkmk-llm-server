#!/usr/bin/env python3
"""
Debug script specifically for table extraction to see what's going wrong.
"""

import re
import logging
import sys
from pathlib import Path

# Add the project root to the path to import modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from checkmk_agent.config import load_config
from checkmk_agent.services.web_scraping.scraper_service import ScraperService

# Configure logging for debug output
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def test_table_extraction():
    """Test table extraction specifically."""
    logger.info("=== Testing Table Extraction Specifically ===")
    
    try:
        # Load configuration
        config = load_config()
        
        # Create scraper service
        scraper = ScraperService(config.checkmk)
        
        # Get authenticated session and fetch the page
        if not scraper.session or not scraper.auth_handler.validate_session():
            scraper.session = scraper.auth_handler.authenticate_session()
        
        # Fetch the page
        html_content = scraper._fetch_page("4h", "piaware", "Temperature Zone 0")
        
        # Parse HTML
        soup = scraper.html_parser.parse_html(html_content)
        
        # Create table extractor
        from checkmk_agent.services.web_scraping.extractors.table_extractor import TableExtractor
        table_extractor = TableExtractor()
        
        # Find data tables
        data_tables = table_extractor.find_data_tables(soup)
        
        logger.info(f"Found {len(data_tables)} data tables")
        
        # Process each table
        for i, table in enumerate(data_tables):
            logger.info(f"Processing table {i+1}")
            
            # Get all cells
            all_cells = table.find_all(['td', 'th'])
            logger.info(f"Table {i+1} has {len(all_cells)} cells")
            
            # Check each cell for temperature patterns
            for j, cell in enumerate(all_cells):
                cell_text = cell.get_text().strip()
                logger.info(f"Cell {j+1}: '{cell_text}'")
                
                # Test our patterns
                patterns = [
                    r'(min|minimum)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                    r'(max|maximum)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                    r'(avg|average|mean)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                    r'(last|current|latest)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                    r'(temperature)\s*:?\s*(\d+\.?\d*)\s*°?[cf]?',
                    r'temperature:\s*(\d+\.?\d*)\s*°?[cf]?',
                ]
                
                for pattern_idx, pattern in enumerate(patterns):
                    matches = re.finditer(pattern, cell_text.lower(), re.IGNORECASE)
                    for match in matches:
                        logger.info(f"  Pattern {pattern_idx+1} matched: {match.groups()}")
                        logger.info(f"  Pattern: {pattern}")
                        logger.info(f"  Full match: '{match.group()}'")
            
            # Now try the actual extraction
            stats = table_extractor._extract_statistics_from_table(table, i+1)
            logger.info(f"Table {i+1} extracted {len(stats)} statistics: {stats}")
    
    except Exception as e:
        logger.exception(f"Error in table extraction test: {e}")

if __name__ == "__main__":
    test_table_extraction()