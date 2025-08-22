"""Setup script for Checkmk MCP Server."""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Checkmk MCP Server - Model Context Protocol server for Checkmk monitoring"

# Read requirements
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    with open(requirements_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='checkmk-mcp-server',
    version='0.1.0',
    description='MCP (Model Context Protocol) server for Checkmk monitoring integration',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    author='Checkmk MCP Server Team',
    author_email='dev@example.com',
    url='https://github.com/your-org/checkmk-mcp-server',
    
    packages=find_packages(),
    python_requires='>=3.8',
    install_requires=[
        'requests>=2.31.0',
        'pydantic>=2.0.0',
        'click>=8.1.0',
        'python-dotenv>=1.0.0',
    ],
    
    extras_require={
        'openai': ['openai>=1.0.0'],
        'anthropic': ['anthropic>=0.18.0'],
        'all': ['openai>=1.0.0', 'anthropic>=0.18.0'],
        'dev': [
            'pytest>=7.4.0',
            'pytest-cov>=4.1.0',
            'black>=23.0.0',
            'flake8>=6.0.0',
            'mypy>=1.5.0',
        ],
        'cli': ['rich>=13.0.0'],
    },
    
    entry_points={
        'console_scripts': [
            'checkmk-mcp-server=checkmk_mcp_server.cli:cli',
        ],
    },
    
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: System Administrators',
        'Topic :: System :: Systems Administration',
        'Topic :: System :: Monitoring',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    
    keywords='checkmk monitoring mcp model-context-protocol ai automation',
    
    project_urls={
        'Bug Reports': 'https://github.com/your-org/checkmk-mcp-server/issues',
        'Source': 'https://github.com/your-org/checkmk-mcp-server',
        'Documentation': 'https://github.com/your-org/checkmk-mcp-server/blob/main/README.md',
    },
    
    include_package_data=True,
    zip_safe=False,
)