#!/usr/bin/env python3
"""
MCP Server Tool Analysis Script

This script analyzes the current 4449-line server.py file to:
1. Extract all tool definitions and their handlers  
2. Categorize tools into logical groups
3. Analyze dependencies between tools
4. Generate a categorization report for refactoring
"""

import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from datetime import datetime
from collections import defaultdict, Counter

class ToolAnalyzer:
    """Analyzes MCP server tools and their structure."""
    
    def __init__(self, server_file_path: str):
        self.server_file = Path(server_file_path)
        self.content = self.server_file.read_text()
        self.lines = self.content.split('\n')
        
        # Analysis results
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.handlers: Dict[str, Dict[str, Any]] = {}
        self.categories: Dict[str, List[str]] = {}
        self.dependencies: Dict[str, Set[str]] = {}
        
    def extract_tool_definitions(self) -> Dict[str, Dict[str, Any]]:
        """Extract all tool definitions from the server file."""
        print("🔍 Extracting tool definitions...")
        
        # Look for tool handler registrations: self._tool_handlers["tool_name"] = function_name
        tool_registration_pattern = r'self\._tool_handlers\["([^"]+)"\] = (\w+)'
        
        tools = {}
        registered_tools = {}
        
        # First, find all tool registrations
        for i, line in enumerate(self.lines):
            match = re.search(tool_registration_pattern, line)
            if match:
                tool_name = match.group(1)
                func_name = match.group(2)
                registered_tools[tool_name] = func_name
                print(f"  Found tool registration: {tool_name} -> {func_name}")
        
        # Now find the function definitions for each registered tool
        for tool_name, func_name in registered_tools.items():
            func_info = self._find_function_definition(func_name)
            if func_info:
                tool_info = self._extract_tool_info(tool_name, func_name, func_info)
                tools[tool_name] = tool_info
        
        print(f"📊 Found {len(tools)} tools total")
        return tools
    
    def _find_function_definition(self, func_name: str) -> Optional[Dict[str, Any]]:
        """Find the definition of a function by name."""
        func_pattern = rf'async def {func_name}\('
        
        for i, line in enumerate(self.lines):
            if re.search(func_pattern, line):
                func_end = self._find_function_end(i)
                return {
                    'start_line': i + 1,
                    'end_line': func_end,
                    'func_line': i
                }
        return None
    
    def _extract_tool_info(self, tool_name: str, func_name: str, func_info: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive information about a tool."""
        start_line = func_info['func_line']
        end_line = func_info['end_line']
        
        # Extract docstring
        docstring = self._extract_docstring(start_line)
        
        # Extract function body and analyze dependencies
        func_body = '\n'.join(self.lines[start_line:end_line])
        dependencies = self._analyze_dependencies(func_body)
        
        # Categorize the tool
        category = self._categorize_tool(tool_name, dependencies, docstring)
        
        return {
            'name': tool_name,
            'function_name': func_name,
            'start_line': func_info['start_line'],
            'end_line': end_line,
            'docstring': docstring,
            'dependencies': list(dependencies),
            'category': category,
            'line_count': end_line - start_line,
            'body': func_body if len(func_body) < 1000 else func_body[:1000] + "...[truncated]"
        }
    
    def _extract_single_tool(self, decorator_line: int) -> Optional[Dict[str, Any]]:
        """Extract information about a single tool starting from its decorator."""
        
        # Look for the async def line after the decorator
        func_line = None
        for i in range(decorator_line + 1, min(decorator_line + 5, len(self.lines))):
            if 'async def ' in self.lines[i]:
                func_line = i
                break
        
        if func_line is None:
            return None
        
        # Extract function name
        func_match = re.search(r'async def (\w+)\(', self.lines[func_line])
        if not func_match:
            return None
        
        tool_name = func_match.group(1)
        
        # Extract docstring
        docstring = self._extract_docstring(func_line)
        
        # Extract function body (simplified - just get the line range)
        func_end = self._find_function_end(func_line)
        
        # Analyze function body for service dependencies
        func_body = '\n'.join(self.lines[func_line:func_end])
        dependencies = self._analyze_dependencies(func_body)
        
        # Categorize based on name and dependencies
        category = self._categorize_tool(tool_name, dependencies, docstring)
        
        return {
            'name': tool_name,
            'start_line': func_line + 1,  # 1-indexed
            'end_line': func_end,
            'docstring': docstring,
            'dependencies': list(dependencies),  # Convert set to list for JSON serialization
            'category': category,
            'line_count': func_end - func_line,
            'body': func_body if len(func_body) < 1000 else func_body[:1000] + "...[truncated]"
        }
    
    def _extract_docstring(self, func_line: int) -> str:
        """Extract the docstring for a function."""
        # Look for triple quotes after the function definition
        for i in range(func_line + 1, min(func_line + 10, len(self.lines))):
            line = self.lines[i].strip()
            if '"""' in line:
                if line.count('"""') == 2:
                    # Single line docstring
                    return line.strip('"').strip()
                else:
                    # Multi-line docstring
                    docstring_lines = [line.split('"""')[1]]
                    for j in range(i + 1, len(self.lines)):
                        if '"""' in self.lines[j]:
                            docstring_lines.append(self.lines[j].split('"""')[0])
                            break
                        docstring_lines.append(self.lines[j].strip())
                    return ' '.join(docstring_lines).strip()
        return ""
    
    def _find_function_end(self, func_line: int) -> int:
        """Find the end of a function by tracking indentation."""
        func_indent = len(self.lines[func_line]) - len(self.lines[func_line].lstrip())
        
        for i in range(func_line + 1, len(self.lines)):
            line = self.lines[i]
            if line.strip() == "":
                continue
            
            current_indent = len(line) - len(line.lstrip())
            if current_indent <= func_indent and not line.strip().startswith('@'):
                return i
        
        return len(self.lines)
    
    def _analyze_dependencies(self, func_body: str) -> Set[str]:
        """Analyze function body for service dependencies."""
        dependencies = set()
        
        # Look for service method calls
        service_patterns = {
            'host_service': r'self\.host_service\.',
            'status_service': r'self\.status_service\.',
            'service_service': r'self\.service_service\.',
            'parameter_service': r'self\.parameter_service\.',
            'event_service': r'self\.event_service\.',
            'metrics_service': r'self\.metrics_service\.',
            'bi_service': r'self\.bi_service\.',
            'historical_service': r'self\.historical_service\.',
            'streaming_host_service': r'self\.streaming_host_service\.',
            'streaming_service_service': r'self\.streaming_service_service\.',
            'cached_host_service': r'self\.cached_host_service\.',
            'batch_processor': r'self\.batch_processor\.',
            'checkmk_client': r'self\.checkmk_client\.',
        }
        
        for service, pattern in service_patterns.items():
            if re.search(pattern, func_body):
                dependencies.add(service)
        
        return dependencies
    
    def _categorize_tool(self, tool_name: str, dependencies: Set[str], docstring: str) -> str:
        """Categorize a tool based on its name, dependencies, and purpose."""
        
        # Host-related tools
        if 'host' in tool_name.lower() or 'host_service' in dependencies:
            return 'host_tools'
        
        # Service-related tools
        if ('service' in tool_name.lower() and 'host' not in tool_name.lower()) or \
           'service_service' in dependencies:
            return 'service_tools'
        
        # Status and monitoring tools
        if any(keyword in tool_name.lower() for keyword in ['status', 'health', 'dashboard', 'problem', 'monitor']) or \
           'status_service' in dependencies:
            return 'status_tools'
        
        # Parameter management tools
        if any(keyword in tool_name.lower() for keyword in ['parameter', 'rule', 'config']) or \
           'parameter_service' in dependencies:
            return 'parameter_tools'
        
        # Event and metrics tools
        if any(keyword in tool_name.lower() for keyword in ['event', 'alert', 'notification']) or \
           'event_service' in dependencies:
            return 'event_tools'
        
        if any(keyword in tool_name.lower() for keyword in ['metric', 'performance', 'graph']) or \
           'metrics_service' in dependencies:
            return 'metrics_tools'
        
        # Business Intelligence tools
        if any(keyword in tool_name.lower() for keyword in ['bi', 'business', 'aggregate']) or \
           'bi_service' in dependencies:
            return 'business_tools'
        
        # Historical data tools
        if any(keyword in tool_name.lower() for keyword in ['historical', 'history', 'trend']) or \
           'historical_service' in dependencies:
            return 'historical_tools'
        
        # Advanced features (streaming, batch, etc.)
        if any(service in dependencies for service in ['streaming_host_service', 'streaming_service_service', 
                                                      'cached_host_service', 'batch_processor']):
            return 'advanced_tools'
        
        # Default to miscellaneous
        return 'misc_tools'
    
    def analyze_tool_complexity(self) -> Dict[str, Any]:
        """Analyze tool complexity metrics."""
        print("📊 Analyzing tool complexity...")
        
        complexity_metrics = {
            'total_tools': len(self.tools),
            'lines_per_tool': {},
            'dependencies_per_tool': {},
            'category_distribution': Counter(),
            'largest_tools': [],
            'most_dependent_tools': [],
            'average_lines_per_tool': 0,
            'total_tool_lines': 0
        }
        
        total_lines = 0
        for tool_name, tool_info in self.tools.items():
            lines = tool_info['line_count']
            deps = len(tool_info['dependencies'])
            category = tool_info['category']
            
            complexity_metrics['lines_per_tool'][tool_name] = lines
            complexity_metrics['dependencies_per_tool'][tool_name] = deps
            complexity_metrics['category_distribution'][category] += 1
            total_lines += lines
        
        complexity_metrics['total_tool_lines'] = total_lines
        complexity_metrics['average_lines_per_tool'] = total_lines / len(self.tools) if self.tools else 0
        
        # Find largest tools
        complexity_metrics['largest_tools'] = sorted(
            [(name, info['line_count']) for name, info in self.tools.items()],
            key=lambda x: x[1], reverse=True
        )[:10]
        
        # Find most dependent tools
        complexity_metrics['most_dependent_tools'] = sorted(
            [(name, len(info['dependencies'])) for name, info in self.tools.items()],
            key=lambda x: x[1], reverse=True
        )[:10]
        
        return complexity_metrics
    
    def generate_categorization_plan(self) -> Dict[str, Any]:
        """Generate a refactoring plan based on the analysis."""
        print("📋 Generating categorization plan...")
        
        # Group tools by category
        categorized_tools = defaultdict(list)
        for tool_name, tool_info in self.tools.items():
            categorized_tools[tool_info['category']].append({
                'name': tool_name,
                'lines': tool_info['line_count'],
                'dependencies': list(tool_info['dependencies']),
                'docstring': tool_info['docstring'][:100] + "..." if len(tool_info['docstring']) > 100 else tool_info['docstring']
            })
        
        # Calculate estimated lines per module
        estimated_modules = {}
        for category, tools in categorized_tools.items():
            total_lines = sum(tool['lines'] for tool in tools)
            estimated_modules[category] = {
                'tool_count': len(tools),
                'estimated_lines': total_lines + 50,  # Add overhead for imports, class structure
                'tools': tools
            }
        
        return {
            'categories': dict(categorized_tools),
            'estimated_modules': estimated_modules,
            'refactoring_priority': self._calculate_refactoring_priority(estimated_modules),
            'dependency_graph': self._build_dependency_graph()
        }
    
    def _calculate_refactoring_priority(self, modules: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Calculate refactoring priority based on complexity and dependencies."""
        priority_list = []
        
        for category, info in modules.items():
            # Priority score: lines + tool_count * 10 (more tools = higher priority)
            score = info['estimated_lines'] + info['tool_count'] * 10
            
            priority_list.append({
                'category': category,
                'score': score,
                'tool_count': info['tool_count'], 
                'estimated_lines': info['estimated_lines'],
                'rationale': self._get_priority_rationale(category, info)
            })
        
        return sorted(priority_list, key=lambda x: x['score'], reverse=True)
    
    def _get_priority_rationale(self, category: str, info: Dict[str, Any]) -> str:
        """Get rationale for refactoring priority."""
        rationales = {
            'host_tools': "Core infrastructure management - high usage",
            'service_tools': "Essential monitoring operations - high complexity",
            'status_tools': "Real-time monitoring - performance critical",
            'parameter_tools': "Configuration management - complex dependencies",
            'advanced_tools': "Complex features - architectural impact",
            'event_tools': "Event processing - moderate complexity",
            'metrics_tools': "Performance monitoring - specialized domain",
            'business_tools': "Business intelligence - specialized domain",
            'historical_tools': "Data analysis - potentially large",
            'misc_tools': "Miscellaneous functionality - low priority"
        }
        
        base_rationale = rationales.get(category, "Unknown category")
        return f"{base_rationale} ({info['tool_count']} tools, ~{info['estimated_lines']} lines)"
    
    def _build_dependency_graph(self) -> Dict[str, List[str]]:
        """Build a dependency graph showing service usage."""
        graph = defaultdict(list)
        
        for tool_name, tool_info in self.tools.items():
            for dep in tool_info['dependencies']:
                graph[dep].append(tool_name)
        
        return dict(graph)
    
    def run_analysis(self) -> Dict[str, Any]:
        """Run complete analysis of the MCP server tools."""
        print(f"🚀 Analyzing MCP server: {self.server_file}")
        print(f"📏 File size: {len(self.lines):,} lines")
        
        # Extract tools
        self.tools = self.extract_tool_definitions()
        
        # Analyze complexity
        complexity = self.analyze_tool_complexity()
        
        # Generate categorization plan
        categorization = self.generate_categorization_plan()
        
        # Build final report
        report = {
            'analysis_timestamp': datetime.now().isoformat(),
            'source_file': str(self.server_file),
            'source_stats': {
                'total_lines': len(self.lines),
                'file_size_bytes': self.server_file.stat().st_size,
            },
            'tools': {name: {k: v for k, v in info.items() if k != 'body'} 
                     for name, info in self.tools.items()},
            'complexity_metrics': complexity,
            'categorization_plan': categorization,
            'summary': {
                'total_tools_found': len(self.tools),
                'categories_identified': len(set(tool['category'] for tool in self.tools.values())),
                'average_tool_size': complexity['average_lines_per_tool'],
                'refactoring_feasibility': 'HIGH' if len(self.tools) > 40 else 'MEDIUM'
            }
        }
        
        return report

def main():
    """Main function to run tool analysis."""
    server_file = "checkmk_mcp_server/mcp_server/server.py"
    
    if not Path(server_file).exists():
        print(f"❌ Error: {server_file} not found")
        return 1
    
    analyzer = ToolAnalyzer(server_file)
    report = analyzer.run_analysis()
    
    # Save detailed report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    scripts_dir = Path("scripts")
    scripts_dir.mkdir(exist_ok=True)
    
    report_file = scripts_dir / f"tool_analysis_{timestamp}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    # Print summary
    print("\n" + "="*60)
    print("📊 MCP SERVER TOOL ANALYSIS SUMMARY")
    print("="*60)
    
    summary = report['summary']
    print(f"Tools Found: {summary['total_tools_found']}")
    print(f"Categories: {summary['categories_identified']}")
    print(f"Average Tool Size: {summary['average_tool_size']:.1f} lines")
    print(f"Refactoring Feasibility: {summary['refactoring_feasibility']}")
    
    print(f"\n📈 COMPLEXITY METRICS")
    print("-"*30)
    complexity = report['complexity_metrics']
    print(f"Total Tool Lines: {complexity['total_tool_lines']:,}")
    print(f"Category Distribution:")
    for category, count in complexity['category_distribution'].most_common():
        print(f"  {category}: {count} tools")
    
    print(f"\n🏆 LARGEST TOOLS")
    print("-"*20)
    for tool_name, lines in complexity['largest_tools'][:5]:
        print(f"  {tool_name}: {lines} lines")
    
    print(f"\n🔗 MOST DEPENDENT TOOLS")
    print("-"*25)
    for tool_name, deps in complexity['most_dependent_tools'][:5]:
        print(f"  {tool_name}: {deps} dependencies")
    
    print(f"\n📋 REFACTORING PRIORITY")
    print("-"*25)
    for item in report['categorization_plan']['refactoring_priority'][:5]:
        print(f"  {item['category']}: {item['tool_count']} tools (~{item['estimated_lines']} lines)")
        print(f"     {item['rationale']}")
    
    print(f"\n📁 Detailed report saved: {report_file}")
    
    return 0

if __name__ == "__main__":
    exit(main())