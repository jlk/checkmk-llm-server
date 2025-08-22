#!/usr/bin/env python3
"""
Checkmk MCP Server Entry Point

This script starts the Checkmk MCP server with advanced features:
- Streaming support for large datasets
- Caching layer for improved performance  
- Batch operations for bulk processing
- Performance monitoring and metrics
- Advanced error recovery and resilience

Usage:
    python mcp_checkmk_server.py [--config CONFIG_FILE] [--log-level LEVEL]

The server will run on stdio by default for MCP client integration.
"""

import sys
import asyncio
import logging
import argparse
import signal
import warnings
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from checkmk_mcp_server.config import load_config
from checkmk_mcp_server.mcp_server import CheckmkMCPServer


def setup_logging(log_level: str = "INFO"):
    """Setup logging configuration with request ID support."""
    # Import the proper logging setup function
    from checkmk_mcp_server.logging_utils import setup_logging as proper_setup_logging
    
    # Use the proper setup with request ID support but output to stderr for MCP
    proper_setup_logging(log_level, include_request_id=True)
    
    # Ensure all handlers output to stderr to avoid interfering with stdio MCP transport
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        if hasattr(handler, 'stream') and handler.stream != sys.stderr:
            handler.stream = sys.stderr
    
    # Suppress common shutdown-related warnings and pipe errors
    warnings.filterwarnings("ignore", category=ResourceWarning)
    # Suppress broken pipe errors during normal shutdown
    logging.getLogger("mcp.server.stdio").setLevel(logging.CRITICAL)
    logging.getLogger("anyio").setLevel(logging.WARNING)


# Global shutdown flag and server reference for signal handling
_shutdown_event = None
_server_instance = None

def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    global _shutdown_event
    
    def signal_handler(signum, frame):
        """Handle shutdown signals gracefully."""
        if _shutdown_event:
            _shutdown_event.set()
    
    # Handle common termination signals
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # On Unix systems, handle SIGHUP as well
    if hasattr(signal, 'SIGHUP'):
        signal.signal(signal.SIGHUP, signal_handler)

async def main():
    """Main entry point for the Checkmk MCP server."""
    global _shutdown_event, _server_instance
    
    parser = argparse.ArgumentParser(description="Checkmk MCP Server")
    parser.add_argument(
        "--config", "-c",
        type=str,
        help="Path to configuration file"
    )
    parser.add_argument(
        "--log-level", "-l",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO",
        help="Set the logging level"
    )
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio"],
        default="stdio",
        help="Transport type for MCP server"
    )
    parser.add_argument(
        "--enable-caching",
        action="store_true",
        help="Enable caching layer for improved performance"
    )
    parser.add_argument(
        "--enable-streaming",
        action="store_true", 
        help="Enable streaming for large datasets"
    )
    parser.add_argument(
        "--enable-metrics",
        action="store_true",
        help="Enable performance monitoring and metrics collection"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.log_level)
    logger = logging.getLogger(__name__)
    
    # Setup signal handlers and shutdown event
    _shutdown_event = asyncio.Event()
    setup_signal_handlers()
    
    try:
        # Load configuration
        config = load_config(args.config)
        
        logger.info("Starting Checkmk MCP Server...")
        logger.info(f"Checkmk URL: {config.checkmk.server_url}")
        logger.info(f"Transport: {args.transport}")
        
         # Log advanced features only if enabled
        advanced_features = []
        if args.enable_streaming:
            advanced_features.append("  - ✓ Streaming support for large datasets")
        if args.enable_caching:
            advanced_features.append("  - ✓ Caching layer for improved performance")
        if args.enable_metrics:
            advanced_features.append("  - ✓ Performance monitoring and metrics collection")
        
        if advanced_features:
            logger.info("Features Enabled:")
            for feature in advanced_features:
                logger.info(feature)

        # Create and initialize the server with feature flags
        server = CheckmkMCPServer(config)
        _server_instance = server
        
        # Set advanced feature flags (server implementation can use these)
        server.enable_caching = args.enable_caching
        server.enable_streaming = args.enable_streaming  
        server.enable_metrics = args.enable_metrics
        
        await server.initialize()
        
        logger.info("MCP Server initialized, starting transport...")
        
        # Ensure stdio streams are properly configured for MCP communication
        if args.transport == "stdio":
            # Force stdout/stdin to be unbuffered for reliable MCP communication
            import io
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(line_buffering=False)
            if hasattr(sys.stdin, 'reconfigure'):
                sys.stdin.reconfigure()
            
            # Flush any remaining output to stderr before starting MCP
            sys.stderr.flush()
        
        # Run the server with graceful shutdown handling
        try:
            await server.run(transport_type=args.transport, shutdown_event=_shutdown_event)
        except (BrokenPipeError, ConnectionResetError):
            # Client disconnected - this is normal, don't log as error
            logger.debug("Client disconnected")
        except asyncio.CancelledError:
            # Task was cancelled - normal during shutdown
            logger.debug("Server task cancelled")
        
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        # Only log as fatal error if it's not a connection/pipe issue
        if isinstance(e, (BrokenPipeError, ConnectionResetError)):
            logger.debug(f"Connection error during startup: {e}")
        else:
            logger.exception("Fatal error in MCP server")
            sys.exit(1)
    finally:
        # Ensure clean shutdown
        if _server_instance:
            try:
                await _server_instance.shutdown()
            except Exception:
                # Suppress shutdown errors
                pass


if __name__ == "__main__":
    asyncio.run(main())