
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="OCU_", extra="ignore")
    app_name: str = "OpenClaw Ultimate"
    log_level: str = "INFO"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:8b"
    enable_shell_tool: bool = False
    workspace_root: Path = Field(default_factory=Path.cwd)

def load_settings() -> Settings:
    return Settings()
