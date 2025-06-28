from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )
    
    # Database configuration
    database_url: str = Field(
        default="sqlite:///./events.db",
        description="Database connection URL"
    )
    
    # Authentication configuration
    auth_username: str = Field(
        default="admin",
        description="Username for basic authentication"
    )
    auth_password: str = Field(
        description="Password for basic authentication (required)"
    )
    
    # Application configuration
    app_title: str = Field(
        default="Community Events Calendar",
        description="Application title"
    )
    app_description: str = Field(
        default="API for managing community events with ICS calendar generation",
        description="Application description"
    )
    calendar_prodid: str = Field(
        default="-//Community Events Calendar//EN",
        description="Calendar product identifier for ICS generation"
    )


# Global settings instance
settings = Settings()