"""Configuration management for Checkmk LLM Agent."""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import logging

try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    YAML_AVAILABLE = False

try:
    import tomli
    TOML_AVAILABLE = True
except ImportError:
    TOML_AVAILABLE = False


class CheckmkConfig(BaseModel):
    """Configuration for Checkmk API connection."""
    
    server_url: str = Field(..., description="Checkmk server URL")
    username: str = Field(..., description="Checkmk username")
    password: str = Field(..., description="Checkmk password")
    site: str = Field(..., description="Checkmk site name")
    max_retries: int = Field(default=3, description="Maximum API retry attempts")
    request_timeout: int = Field(default=30, description="Request timeout in seconds")


class LLMConfig(BaseModel):
    """Configuration for LLM integration."""
    
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key")
    default_model: str = Field(default="gpt-3.5-turbo", description="Default LLM model")


class AppConfig(BaseModel):
    """Main application configuration."""
    
    checkmk: CheckmkConfig
    llm: LLMConfig
    default_folder: str = Field(default="/", description="Default folder for host creation")
    log_level: str = Field(default="INFO", description="Logging level")


def load_config_file(config_path: Union[str, Path]) -> Dict[str, Any]:
    """Load configuration from a file."""
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    logger = logging.getLogger(__name__)
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                if not YAML_AVAILABLE:
                    raise ImportError("PyYAML is required for YAML config files. Install with: pip install pyyaml")
                return yaml.safe_load(f) or {}
            
            elif config_path.suffix.lower() == '.toml':
                if not TOML_AVAILABLE:
                    raise ImportError("tomli is required for TOML config files. Install with: pip install tomli")
                return tomli.load(f.buffer)
            
            elif config_path.suffix.lower() == '.json':
                return json.load(f) or {}
            
            else:
                raise ValueError(f"Unsupported config file format: {config_path.suffix}")
                
    except Exception as e:
        logger.error(f"Failed to load config file {config_path}: {e}")
        raise


def find_config_file() -> Optional[Path]:
    """Find configuration file in standard locations."""
    search_paths = [
        Path.cwd() / "config.yaml",
        Path.cwd() / "config.yml", 
        Path.cwd() / "config.toml",
        Path.cwd() / "config.json",
        Path.cwd() / ".checkmk-agent.yaml",
        Path.cwd() / ".checkmk-agent.yml",
        Path.cwd() / ".checkmk-agent.toml",
        Path.cwd() / ".checkmk-agent.json",
        Path.home() / ".config" / "checkmk-agent" / "config.yaml",
        Path.home() / ".config" / "checkmk-agent" / "config.yml",
        Path.home() / ".config" / "checkmk-agent" / "config.toml",
        Path.home() / ".config" / "checkmk-agent" / "config.json",
    ]
    
    for config_path in search_paths:
        if config_path.exists():
            return config_path
    
    return None


def merge_config(base_config: Dict[str, Any], override_config: Dict[str, Any]) -> Dict[str, Any]:
    """Merge configuration dictionaries with override taking precedence."""
    merged = base_config.copy()
    
    for key, value in override_config.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = merge_config(merged[key], value)
        else:
            merged[key] = value
    
    return merged


def load_config(config_file: Optional[Union[str, Path]] = None) -> AppConfig:
    """Load configuration from multiple sources with priority order.
    
    Priority (highest to lowest):
    1. Environment variables
    2. Specified config file (if provided)
    3. Auto-discovered config file
    4. Default values
    """
    logger = logging.getLogger(__name__)
    
    # Start with empty config
    config_data = {}
    
    # 1. Load from config file (lowest priority)
    if config_file:
        # Use specified config file
        config_path = Path(config_file)
        if config_path.exists():
            config_data = load_config_file(config_path)
            logger.info(f"Loaded configuration from: {config_path}")
        else:
            raise FileNotFoundError(f"Specified config file not found: {config_path}")
    else:
        # Auto-discover config file
        config_path = find_config_file()
        if config_path:
            config_data = load_config_file(config_path)
            logger.info(f"Auto-discovered configuration file: {config_path}")
    
    # 2. Load .env file (medium priority)
    load_dotenv()
    
    # 3. Override with environment variables (highest priority)
    env_config = {
        "checkmk": {
            "server_url": os.getenv("CHECKMK_SERVER_URL"),
            "username": os.getenv("CHECKMK_USERNAME"),
            "password": os.getenv("CHECKMK_PASSWORD"),
            "site": os.getenv("CHECKMK_SITE"),
            "max_retries": os.getenv("MAX_RETRIES"),
            "request_timeout": os.getenv("REQUEST_TIMEOUT"),
        },
        "llm": {
            "openai_api_key": os.getenv("OPENAI_API_KEY"),
            "anthropic_api_key": os.getenv("ANTHROPIC_API_KEY"),
            "default_model": os.getenv("DEFAULT_MODEL"),
        },
        "default_folder": os.getenv("DEFAULT_FOLDER"),
        "log_level": os.getenv("LOG_LEVEL"),
    }
    
    # Remove None values from env config
    def remove_none_values(d):
        if isinstance(d, dict):
            return {k: remove_none_values(v) for k, v in d.items() if v is not None}
        return d
    
    env_config = remove_none_values(env_config)
    
    # Merge configurations
    final_config = merge_config(config_data, env_config)
    
    # Apply defaults and create config objects
    checkmk_data = final_config.get("checkmk", {})
    checkmk_config = CheckmkConfig(
        server_url=checkmk_data.get("server_url", ""),
        username=checkmk_data.get("username", ""),
        password=checkmk_data.get("password", ""),
        site=checkmk_data.get("site", ""),
        max_retries=int(checkmk_data.get("max_retries", 3)),
        request_timeout=int(checkmk_data.get("request_timeout", 30))
    )
    
    llm_data = final_config.get("llm", {})
    llm_config = LLMConfig(
        openai_api_key=llm_data.get("openai_api_key"),
        anthropic_api_key=llm_data.get("anthropic_api_key"),
        default_model=llm_data.get("default_model", "gpt-3.5-turbo")
    )
    
    return AppConfig(
        checkmk=checkmk_config,
        llm=llm_config,
        default_folder=final_config.get("default_folder", "/"),
        log_level=final_config.get("log_level", "INFO")
    )