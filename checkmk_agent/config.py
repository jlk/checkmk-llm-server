"""Configuration management for Checkmk LLM Agent."""

import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, Union
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
import logging
from urllib.parse import urlparse

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
    
    @field_validator('server_url')
    @classmethod
    def validate_server_url(cls, v: str) -> str:
        """Validate that server_url is a properly formatted URL."""
        if not v:
            raise ValueError("server_url cannot be empty")
        
        # Add https:// if no scheme provided
        if not v.startswith(('http://', 'https://')):
            v = f'https://{v}'
        
        parsed = urlparse(v)
        if not parsed.netloc:
            raise ValueError(f"Invalid server URL format: {v}")
            
        return v
    
    @field_validator('username', 'password', 'site')
    @classmethod
    def validate_required_strings(cls, v: str) -> str:
        """Validate required string fields are not empty."""
        if not v or not v.strip():
            raise ValueError("Field cannot be empty")
        return v.strip()
    
    @field_validator('max_retries')
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        """Validate max_retries is reasonable."""
        if v < 0:
            raise ValueError("max_retries cannot be negative")
        if v > 10:
            raise ValueError("max_retries should not exceed 10 (excessive retrying)")
        return v
    
    @field_validator('request_timeout')
    @classmethod
    def validate_request_timeout(cls, v: int) -> int:
        """Validate request_timeout is reasonable."""
        if v <= 0:
            raise ValueError("request_timeout must be positive")
        if v > 300:  # 5 minutes
            raise ValueError("request_timeout should not exceed 300 seconds")
        return v


class LLMConfig(BaseModel):
    """Configuration for LLM integration."""
    
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key")
    default_model: str = Field(default="gpt-3.5-turbo", description="Default LLM model")


class UIConfig(BaseModel):
    """Configuration for UI appearance."""
    
    theme: str = Field(default="default", description="Color theme name")
    use_colors: bool = Field(default=True, description="Enable colored output")
    auto_detect_terminal: bool = Field(default=True, description="Auto-detect terminal capabilities")
    custom_colors: Optional[Dict[str, str]] = Field(None, description="Custom color overrides")


class AppConfig(BaseModel):
    """Main application configuration."""
    
    checkmk: CheckmkConfig
    llm: LLMConfig
    ui: UIConfig = Field(default_factory=UIConfig, description="UI configuration")
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
        "ui": {
            "theme": os.getenv("CHECKMK_UI_THEME"),
            "use_colors": os.getenv("CHECKMK_UI_USE_COLORS"),
            "auto_detect_terminal": os.getenv("CHECKMK_UI_AUTO_DETECT_TERMINAL"),
            "custom_colors": {
                "info": os.getenv("CHECKMK_UI_INFO_COLOR"),
                "success": os.getenv("CHECKMK_UI_SUCCESS_COLOR"),
                "warning": os.getenv("CHECKMK_UI_WARNING_COLOR"),
                "error": os.getenv("CHECKMK_UI_ERROR_COLOR"),
                "help": os.getenv("CHECKMK_UI_HELP_COLOR"),
                "prompt": os.getenv("CHECKMK_UI_PROMPT_COLOR"),
            }
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
    
    ui_data = final_config.get("ui", {})
    # Handle boolean environment variables
    use_colors = ui_data.get("use_colors", True)
    if isinstance(use_colors, str):
        use_colors = use_colors.lower() in ('true', '1', 'yes', 'on')
    
    auto_detect_terminal = ui_data.get("auto_detect_terminal", True)
    if isinstance(auto_detect_terminal, str):
        auto_detect_terminal = auto_detect_terminal.lower() in ('true', '1', 'yes', 'on')
    
    # Handle custom colors
    custom_colors = ui_data.get("custom_colors", {})
    if custom_colors:
        # Remove None values from custom colors
        custom_colors = {k: v for k, v in custom_colors.items() if v is not None}
    
    ui_config = UIConfig(
        theme=ui_data.get("theme", "default"),
        use_colors=use_colors,
        auto_detect_terminal=auto_detect_terminal,
        custom_colors=custom_colors if custom_colors else None
    )
    
    return AppConfig(
        checkmk=checkmk_config,
        llm=llm_config,
        ui=ui_config,
        default_folder=final_config.get("default_folder", "/"),
        log_level=final_config.get("log_level", "INFO")
    )