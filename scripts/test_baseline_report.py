#!/usr/bin/env python3
"""
Test Baseline Report Generator for MCP Server Refactoring

This script generates a comprehensive baseline report of the current test suite
before refactoring begins, to ensure no regressions are introduced.
"""

import subprocess
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Any
import sys

def run_command(cmd: List[str], timeout: int = 60) -> Tuple[str, str, int]:
    """Run a command and return stdout, stderr, and return code."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired:
        return "", f"Command timed out after {timeout}s", 1
    except Exception as e:
        return "", str(e), 1

def count_tests() -> Dict[str, Any]:
    """Count total number of tests in the suite."""
    stdout, stderr, code = run_command(["python", "-m", "pytest", "--collect-only", "-q"])
    
    if code != 0:
        return {"error": f"Failed to collect tests: {stderr}"}
    
    lines = stdout.strip().split('\n')
    test_count = len([line for line in lines if '::' in line and not line.startswith('===')])
    
    return {
        "total_tests": test_count,
        "collection_output": stdout,
        "stderr": stderr
    }

def run_core_api_tests() -> Dict[str, Any]:
    """Run core API client tests to establish baseline."""
    test_files = [
        "tests/test_api_client.py",
        "tests/test_api_client_status.py",
        "tests/test_async_api_client.py"
    ]
    
    results = {}
    for test_file in test_files:
        if Path(test_file).exists():
            stdout, stderr, code = run_command(
                ["python", "-m", "pytest", test_file, "-v", "--tb=short"],
                timeout=120
            )
            
            # Parse results
            passed = stdout.count(" PASSED")
            failed = stdout.count(" FAILED")
            errors = stdout.count(" ERROR")
            skipped = stdout.count(" SKIPPED")
            
            results[test_file] = {
                "passed": passed,
                "failed": failed,
                "errors": errors,
                "skipped": skipped,
                "return_code": code,
                "output": stdout if len(stdout) < 2000 else stdout[:2000] + "...[truncated]"
            }
    
    return results

def run_mcp_server_tests() -> Dict[str, Any]:
    """Run MCP server related tests."""
    mcp_test_patterns = [
        "tests/test_mcp_server_tools.py",
        "tests/test_mcp_*.py"
    ]
    
    results = {}
    
    # Test the main MCP server tools file
    if Path("tests/test_mcp_server_tools.py").exists():
        stdout, stderr, code = run_command(
            ["python", "-m", "pytest", "tests/test_mcp_server_tools.py", "-v"],
            timeout=60
        )
        
        passed = stdout.count(" PASSED")
        failed = stdout.count(" FAILED")
        errors = stdout.count(" ERROR")
        
        results["mcp_server_tools"] = {
            "passed": passed,
            "failed": failed,
            "errors": errors,
            "return_code": code,
            "output": stdout if len(stdout) < 1500 else stdout[:1500] + "...[truncated]"
        }
    
    return results

def analyze_mcp_server_file() -> Dict[str, Any]:
    """Analyze the current MCP server file structure."""
    server_file = Path("checkmk_mcp_server/mcp_server/server.py")
    
    if not server_file.exists():
        return {"error": "MCP server file not found"}
    
    content = server_file.read_text()
    lines = content.split('\n')
    
    # Count various elements
    class_count = len([line for line in lines if line.strip().startswith('class ')])
    function_count = len([line for line in lines if line.strip().startswith('def ')])
    async_function_count = len([line for line in lines if line.strip().startswith('async def ')])
    import_count = len([line for line in lines if line.strip().startswith('import ') or line.strip().startswith('from ')])
    
    # Look for MCP tool registrations
    tool_registrations = []
    for i, line in enumerate(lines):
        if '@server.call_tool()' in line or 'call_tool(' in line:
            # Look for the function name in nearby lines
            for j in range(i, min(i+5, len(lines))):
                if 'async def ' in lines[j]:
                    func_name = lines[j].split('async def ')[1].split('(')[0].strip()
                    tool_registrations.append(func_name)
                    break
    
    return {
        "file_size_bytes": server_file.stat().st_size,
        "total_lines": len(lines),
        "non_empty_lines": len([line for line in lines if line.strip()]),
        "class_count": class_count,
        "function_count": function_count,
        "async_function_count": async_function_count,
        "import_count": import_count,
        "tool_registrations_found": len(tool_registrations),
        "tool_names": tool_registrations[:10],  # First 10 tools found
        "last_modified": datetime.fromtimestamp(server_file.stat().st_mtime).isoformat()
    }

def generate_baseline_report() -> Dict[str, Any]:
    """Generate comprehensive baseline report."""
    print("🔍 Generating test baseline report...")
    
    report = {
        "report_timestamp": datetime.now().isoformat(),
        "git_branch": None,
        "git_commit": None,
        "test_counts": count_tests(),
        "core_api_tests": run_core_api_tests(),
        "mcp_server_tests": run_mcp_server_tests(),
        "mcp_server_analysis": analyze_mcp_server_file()
    }
    
    # Get git information
    try:
        stdout, _, code = run_command(["git", "branch", "--show-current"])
        if code == 0:
            report["git_branch"] = stdout.strip()
        
        stdout, _, code = run_command(["git", "rev-parse", "HEAD"])
        if code == 0:
            report["git_commit"] = stdout.strip()[:8]
    except:
        pass
    
    return report

def main():
    """Main function to generate and save baseline report."""
    # Ensure scripts directory exists
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    
    # Generate report
    report = generate_baseline_report()
    
    # Save to file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = scripts_dir / f"baseline_report_{timestamp}.json"
    
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print(f"\n📊 Test Baseline Report Generated: {report_file}")
    print("=" * 60)
    
    if "error" not in report["test_counts"]:
        print(f"Total Tests: {report['test_counts']['total_tests']}")
    
    print(f"Git Branch: {report['git_branch']}")
    print(f"Git Commit: {report['git_commit']}")
    
    # Core API tests summary
    if report["core_api_tests"]:
        print("\nCore API Tests:")
        for test_file, results in report["core_api_tests"].items():
            print(f"  {test_file}: {results['passed']} passed, {results['failed']} failed, {results['errors']} errors")
    
    # MCP server tests summary  
    if report["mcp_server_tests"]:
        print("\nMCP Server Tests:")
        for test_name, results in report["mcp_server_tests"].items():
            print(f"  {test_name}: {results['passed']} passed, {results['failed']} failed, {results['errors']} errors")
    
    # MCP server file analysis
    server_analysis = report["mcp_server_analysis"]
    if "error" not in server_analysis:
        print(f"\nMCP Server File Analysis:")
        print(f"  File size: {server_analysis['file_size_bytes']:,} bytes")
        print(f"  Total lines: {server_analysis['total_lines']:,}")
        print(f"  Functions: {server_analysis['function_count']}")
        print(f"  Async functions: {server_analysis['async_function_count']}")
        print(f"  Classes: {server_analysis['class_count']}")
        print(f"  Tool registrations found: {server_analysis['tool_registrations_found']}")
    
    print(f"\n📁 Full report saved to: {report_file.absolute()}")
    return report_file

if __name__ == "__main__":
    main()