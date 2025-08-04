#!/usr/bin/env python3
"""
Verification script for the async/await coroutine fix.

This script demonstrates that the fix resolves the original error:
AttributeError: 'coroutine' object has no attribute 'get'
"""

import asyncio
import sys
from unittest.mock import MagicMock

# Add the project directory to the path
sys.path.insert(0, '/Users/jlk/code-local/checkmk_llm_agent')

from checkmk_agent.async_api_client import AsyncCheckmkClient
from checkmk_agent.api_client import CheckmkClient
from checkmk_agent.config import AppConfig
from checkmk_agent.services.parameter_service import ParameterService


async def verify_fix():
    """Verify that the coroutine fix works correctly."""
    
    print("🔧 Verifying async/await coroutine fix...")
    print("=" * 50)
    
    # Set up mocked components
    mock_sync_client = MagicMock(spec=CheckmkClient)
    async_client = AsyncCheckmkClient(mock_sync_client)
    
    mock_config = MagicMock(spec=AppConfig)
    mock_config.checkmk = MagicMock()
    mock_config.checkmk.url = "https://test-checkmk.com"
    mock_config.checkmk.username = "test_user"
    mock_config.checkmk.password = "test_password"
    
    parameter_service = ParameterService(async_client, mock_config)
    
    # Test 1: Success scenario
    print("Test 1: Success scenario")
    mock_sync_client.get_service_effective_parameters.return_value = {
        "host_name": "test-host",
        "service_name": "CPU load",
        "parameters": {"levels": (80.0, 90.0)},
        "status": "success"
    }
    
    result = await parameter_service.get_effective_parameters("test-host", "CPU load")
    
    if result.success:
        print("✅ SUCCESS: Async call returned proper result object")
        print(f"   Host: {result.data.host_name}")
        print(f"   Service: {result.data.service_name}")
        print(f"   Parameters: {result.data.parameters}")
    else:
        print("❌ FAILED: Success scenario failed")
        return False
    
    # Test 2: Error status scenario (the original line 341 issue)
    print("\nTest 2: Error status scenario (line 341 fix)")
    mock_sync_client.get_service_effective_parameters.return_value = {
        "host_name": "test-host",
        "service_name": "Temperature sensors", 
        "parameters": {"error": "Connection failed"},
        "status": "error"  # This triggers line 341: if effective_result.get("status") == "error":
    }
    
    try:
        result = await parameter_service.get_effective_parameters("test-host", "Temperature sensors")
        
        if result.success:
            print("✅ SUCCESS: Error status handled gracefully")
            print("   - No AttributeError about coroutine object")
            print("   - Fallback parameters provided")
            print(f"   - Warnings: {len(result.data.warnings)} warning(s)")
        else:
            print("❌ FAILED: Error status not handled properly")
            return False
            
    except AttributeError as e:
        if "'coroutine' object has no attribute 'get'" in str(e):
            print("❌ FAILED: Original coroutine error still occurs!")
            print(f"   Error: {e}")
            return False
        else:
            print(f"❌ FAILED: Unexpected AttributeError: {e}")
            return False
    except Exception as e:
        print(f"❌ FAILED: Unexpected exception: {e}")
        return False
    
    # Test 3: Verify async wrapper returns dictionary
    print("\nTest 3: Async wrapper dictionary verification")
    mock_sync_client.get_service_effective_parameters.return_value = {
        "status": "partial",
        "parameters": {"note": "Limited data"}
    }
    
    result = await async_client.get_service_effective_parameters("host", "service")
    
    if asyncio.iscoroutine(result):
        print("❌ FAILED: Async wrapper returned coroutine object")
        return False
    elif isinstance(result, dict):
        print("✅ SUCCESS: Async wrapper returned dictionary")
        print(f"   Can call .get() method: {result.get('status')}")
    else:
        print(f"❌ FAILED: Unexpected result type: {type(result)}")
        return False
    
    # Test 4: Concurrent calls
    print("\nTest 4: Concurrent calls verification")
    mock_sync_client.get_service_effective_parameters.return_value = {
        "status": "success",
        "parameters": {"levels": (70.0, 85.0)}
    }
    
    tasks = [
        parameter_service.get_effective_parameters(f"host-{i}", f"service-{i}")
        for i in range(3)
    ]
    
    results = await asyncio.gather(*tasks)
    
    all_success = all(result.success for result in results)
    no_coroutines = all(not asyncio.iscoroutine(result) for result in results)
    
    if all_success and no_coroutines:
        print("✅ SUCCESS: Concurrent calls work properly")
        print(f"   Processed {len(results)} concurrent requests")
    else:
        print("❌ FAILED: Concurrent calls failed")
        return False
    
    print("\n" + "=" * 50)
    print("🎉 ALL TESTS PASSED - Coroutine fix verified!")
    print("\nSummary:")
    print("- async/await properly implemented")
    print("- No more 'coroutine' object has no attribute 'get' errors")
    print("- Line 341 in parameter_service.py works correctly")
    print("- Dictionary objects returned instead of coroutines")
    print("- Concurrent operations work properly")
    
    return True


async def main():
    """Main verification function."""
    try:
        success = await verify_fix()
        if success:
            print("\n✅ Verification completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Verification failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n💥 Verification crashed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())