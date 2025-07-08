"""Configuration management for Checkmk LLM Agent."""

import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field


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


def load_config() -> AppConfig:
    """Load configuration from environment variables."""
    load_dotenv()
    
    # Checkmk configuration
    checkmk_config = CheckmkConfig(
        server_url=os.getenv("CHECKMK_SERVER_URL", ""),
        username=os.getenv("CHECKMK_USERNAME", ""),
        password=os.getenv("CHECKMK_PASSWORD", ""),
        site=os.getenv("CHECKMK_SITE", ""),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "30"))
    )
    
    # LLM configuration
    llm_config = LLMConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
        default_model=os.getenv("DEFAULT_MODEL", "gpt-3.5-turbo")
    )
    
    return AppConfig(
        checkmk=checkmk_config,
        llm=llm_config,
        default_folder=os.getenv("DEFAULT_FOLDER", "/"),
        log_level=os.getenv("LOG_LEVEL", "INFO")
    )