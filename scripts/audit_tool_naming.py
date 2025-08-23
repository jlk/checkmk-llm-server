#!/usr/bin/env python3
"""
MCP Tool Naming Convention Audit Script

This script analyzes all MCP tools across the 8 categories to identify:
1. Parameter naming inconsistencies 
2. Verb pattern inconsistencies
3. Tool description clarity issues
4. Missing "When to Use" guidance

Part of Phase 1.1: Standardize Tool Naming Conventions
"""

import os
import re
import ast
import json
from pathlib import Path
from typing import Dict, List, Set, Any
from collections import defaultdict

# Tool categories and their file paths
TOOL_CATEGORIES = {
    "host": "checkmk_mcp_server/mcp_server/tools/host/tools.py",
    "service": "checkmk_mcp_server/mcp_server/tools/service/tools.py", 
    "monitoring": "checkmk_mcp_server/mcp_server/tools/monitoring/tools.py",
    "parameters": "checkmk_mcp_server/mcp_server/tools/parameters/tools.py",
    "events": "checkmk_mcp_server/mcp_server/tools/events/tools.py",
    "metrics": "checkmk_mcp_server/mcp_server/tools/metrics/tools.py",
    "business": "checkmk_mcp_server/mcp_server/tools/business/tools.py",
    "advanced": "checkmk_mcp_server/mcp_server/tools/advanced/tools.py"
}

class ToolAnalyzer:
    """Analyzes MCP tools for naming convention issues."""
    
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.issues: Dict[str, List[str]] = defaultdict(list)
        
    def analyze_all_tools(self) -> Dict[str, Any]:
        """Analyze all tools across all categories."""
        
        for category, file_path in TOOL_CATEGORIES.items():
            full_path = self.base_path / file_path
            if full_path.exists():
                print(f"Analyzing {category} tools: {file_path}")
                tools = self._extract_tools_from_file(full_path, category)
                self.tools[category] = tools
            else:
                print(f"Warning: Tool file not found: {full_path}")
                
        # Run analysis passes
        self._analyze_parameter_naming()
        self._analyze_verb_patterns() 
        self._analyze_descriptions()
        self._analyze_schema_consistency()
        
        return self._generate_report()
    
    def _extract_tools_from_file(self, file_path: Path, category: str) -> Dict[str, Any]:
        """Extract tool definitions from a Python file."""
        tools = {}
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
                
            # Look for Tool() instantiations 
            tool_pattern = r'self\._tools\["([^"]+)"\]\s*=\s*Tool\(\s*name="([^"]+)",\s*description="([^"]+)"'
            matches = re.findall(tool_pattern, content, re.MULTILINE | re.DOTALL)
            
            for tool_key, tool_name, description in matches:
                # Extract input schema for this tool
                schema_start = content.find(f'self._tools["{tool_key}"]')
                if schema_start != -1:
                    # Find the schema section
                    schema_match = re.search(
                        r'inputSchema=\{(.*?)\}',
                        content[schema_start:schema_start+2000],
                        re.DOTALL
                    )
                    schema_text = schema_match.group(1) if schema_match else ""
                    
                    # Extract parameter names from schema
                    param_names = re.findall(r'"([^"]+)"\s*:\s*\{', schema_text)
                    
                    tools[tool_key] = {
                        'name': tool_name,
                        'description': description,
                        'category': category,
                        'parameters': param_names,
                        'schema_text': schema_text.strip()
                    }
                    
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")
            
        return tools
        
    def _analyze_parameter_naming(self):
        """Analyze parameter naming consistency."""
        # Standard parameter names we want to see
        standard_names = {
            'host_name': ['host_name', 'hostname', 'host'],
            'service_name': ['service_name', 'servicename', 'service'],
            'rule_id': ['rule_id', 'ruleid', 'id'],
            'folder': ['folder', 'folder_path', 'path']
        }
        
        for category, tools in self.tools.items():
            for tool_name, tool_info in tools.items():
                params = tool_info['parameters']
                
                # Check for inconsistent host naming
                host_params = [p for p in params if any(h in p.lower() for h in ['host', 'hostname'])]
                if host_params and 'host_name' not in host_params:
                    self.issues['parameter_naming'].append(
                        f"{category}.{tool_name}: Uses {host_params} instead of 'host_name'"
                    )
                
                # Check for inconsistent service naming
                service_params = [p for p in params if any(s in p.lower() for s in ['service', 'servicename'])]
                if service_params and 'service_name' not in service_params:
                    self.issues['parameter_naming'].append(
                        f"{category}.{tool_name}: Uses {service_params} instead of 'service_name'"
                    )
                    
    def _analyze_verb_patterns(self):
        """Analyze verb pattern consistency in tool names."""
        verb_categories = {
            'list_': ['list_', 'get_all_', 'show_'],
            'get_': ['get_', 'show_', 'fetch_', 'retrieve_'],
            'create_': ['create_', 'add_', 'new_'],
            'update_': ['update_', 'modify_', 'edit_', 'change_'],
            'delete_': ['delete_', 'remove_', 'destroy_']
        }
        
        for category, tools in self.tools.items():
            for tool_name, tool_info in tools.items():
                name = tool_info['name']
                
                # Identify verb pattern
                found_patterns = []
                for standard_verb, variants in verb_categories.items():
                    for variant in variants:
                        if name.startswith(variant):
                            found_patterns.append((standard_verb, variant))
                            
                if found_patterns:
                    standard_verb, used_verb = found_patterns[0]
                    if used_verb != standard_verb:
                        self.issues['verb_patterns'].append(
                            f"{category}.{tool_name}: Uses '{used_verb}' instead of standard '{standard_verb}'"
                        )
                        
    def _analyze_descriptions(self):
        """Analyze tool description quality and clarity."""
        required_elements = [
            ('when_to_use', ['when', 'use case', 'purpose']),
            ('prerequisites', ['require', 'need', 'must have']),
            ('workflow', ['workflow', 'step', 'process', 'then'])
        ]
        
        for category, tools in self.tools.items():
            for tool_name, tool_info in tools.items():
                description = tool_info['description'].lower()
                
                # Check for "When to Use" guidance
                if not any(keyword in description for keyword in ['when', 'use for', 'purpose']):
                    self.issues['missing_when_to_use'].append(
                        f"{category}.{tool_name}: Missing 'When to Use' guidance"
                    )
                
                # Check for workflow context
                if category in ['parameters', 'service'] and not any(keyword in description for keyword in ['workflow', 'step', 'then', 'after']):
                    self.issues['missing_workflow_context'].append(
                        f"{category}.{tool_name}: Complex tool missing workflow context"
                    )
                    
                # Check for vague descriptions
                vague_words = ['manage', 'handle', 'work with', 'deal with']
                if any(vague in description for vague in vague_words):
                    self.issues['vague_descriptions'].append(
                        f"{category}.{tool_name}: Description uses vague language"
                    )
                    
    def _analyze_schema_consistency(self):
        """Analyze input schema consistency."""
        for category, tools in self.tools.items():
            for tool_name, tool_info in tools.items():
                schema_text = tool_info['schema_text']
                params = tool_info['parameters']
                
                # Check for missing descriptions
                for param in params:
                    if f'"{param}"' in schema_text and 'description' not in schema_text[schema_text.find(f'"{param}"'):schema_text.find(f'"{param}"')+200]:
                        self.issues['missing_param_descriptions'].append(
                            f"{category}.{tool_name}: Parameter '{param}' missing description"
                        )
                        
    def _generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive analysis report."""
        total_tools = sum(len(tools) for tools in self.tools.values())
        
        report = {
            'summary': {
                'total_tools_analyzed': total_tools,
                'categories': list(TOOL_CATEGORIES.keys()),
                'total_issues': sum(len(issues) for issues in self.issues.values()),
                'issue_categories': list(self.issues.keys())
            },
            'tools_by_category': {
                category: {
                    'count': len(tools),
                    'tool_names': list(tools.keys())
                }
                for category, tools in self.tools.items()
            },
            'issues': dict(self.issues),
            'recommendations': self._generate_recommendations()
        }
        
        return report
        
    def _generate_recommendations(self) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if self.issues['parameter_naming']:
            recommendations.append(
                "PRIORITY 1: Standardize parameter naming - Use 'host_name' and 'service_name' consistently"
            )
            
        if self.issues['verb_patterns']:
            recommendations.append(
                "PRIORITY 2: Standardize verb patterns - Use list_, get_, create_, update_, delete_ prefixes"
            )
            
        if self.issues['missing_when_to_use']:
            recommendations.append(
                "PRIORITY 3: Add 'When to Use' guidance to tool descriptions for better LLM selection"
            )
            
        if self.issues['missing_workflow_context']:
            recommendations.append(
                "PRIORITY 4: Add workflow context to complex parameter and service tools"
            )
            
        return recommendations

def main():
    """Run the tool naming audit."""
    base_path = "/Users/jlk/code-local/checkmk_mcp_server"
    analyzer = ToolAnalyzer(base_path)
    
    print("🔍 Starting MCP Tool Naming Convention Audit...")
    print("=" * 60)
    
    report = analyzer.analyze_all_tools()
    
    # Print summary
    print("\n📊 AUDIT SUMMARY")
    print("-" * 30)
    print(f"Total Tools Analyzed: {report['summary']['total_tools_analyzed']}")
    print(f"Total Issues Found: {report['summary']['total_issues']}")
    print(f"Categories: {', '.join(report['summary']['categories'])}")
    
    # Print tools by category
    print("\n🗂️  TOOLS BY CATEGORY")
    print("-" * 30)
    for category, info in report['tools_by_category'].items():
        print(f"{category.upper()}: {info['count']} tools")
        for tool_name in info['tool_names']:
            print(f"  - {tool_name}")
    
    # Print issues
    print("\n⚠️  ISSUES FOUND")
    print("-" * 30)
    for issue_type, issues in report['issues'].items():
        if issues:
            print(f"\n{issue_type.upper().replace('_', ' ')} ({len(issues)} issues):")
            for issue in issues:
                print(f"  - {issue}")
    
    # Print recommendations
    print("\n💡 RECOMMENDATIONS")
    print("-" * 30)
    for i, recommendation in enumerate(report['recommendations'], 1):
        print(f"{i}. {recommendation}")
    
    # Save detailed report
    output_file = Path(base_path) / "scripts" / "tool_naming_audit_report.json"
    with open(output_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {output_file}")
    print("\n✅ Audit complete!")

if __name__ == "__main__":
    main()