"""Setup script for Checkmk LLM Agent."""

from setuptools import setup, find_packages
import os

# Read the README file
def read_readme():
    readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
    if os.path.exists(readme_path):
        with open(readme_path, 'r', encoding='utf-8') as f:
            return f.read()
    return "Checkmk LLM Agent - Natural language interface for Checkmk"

# Read requirements
def read_requirements():
    requirements_path = os.path.join(os.path.dirname(__file__), 'requirements.txt')
    with open(requirements_path, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]

setup(
    name='checkmk-llm-agent',
    version='0.1.0',
    description='LLM-powered agent for Checkmk configuration management',
    long_description=read_readme(),
    long_description_content_type='text/markdown',
    author='Checkmk LLM Agent Team',
    author_email='dev@example.com',
    url='https://github.com/your-org/checkmk-llm-agent',
    
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
            'checkmk-agent=checkmk_agent.cli:cli',
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
    
    keywords='checkmk monitoring llm ai automation',
    
    project_urls={
        'Bug Reports': 'https://github.com/your-org/checkmk-llm-agent/issues',
        'Source': 'https://github.com/your-org/checkmk-llm-agent',
        'Documentation': 'https://github.com/your-org/checkmk-llm-agent/blob/main/README.md',
    },
    
    include_package_data=True,
    zip_safe=False,
)