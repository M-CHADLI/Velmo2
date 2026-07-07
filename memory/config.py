import os
from dotenv import load_dotenv

# Load env variables from .env if present
load_dotenv()

class Settings:
    """Settings configuration for Velmo 2.0 Memory."""

    def __init__(self) -> None:
        # PostgreSQL Database config
        self.database_url: str = os.getenv(
            "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/velmo"
        )

        # Redis config
        self.redis_url: str = os.getenv(
            "REDIS_URL", "redis://localhost:6379/0"
        )

        # Azure OpenAI (Kimi 2.6) config
        self.azure_openai_api_key: str = os.getenv(
            "AZURE_OPENAI_API_KEY", ""
        )
        self.azure_openai_endpoint: str = os.getenv(
            "AZURE_OPENAI_ENDPOINT", ""
        )
        self.azure_openai_deployment_name: str = os.getenv(
            "AZURE_OPENAI_DEPLOYMENT_NAME", "Kimi-K2.6"
        )
        self.azure_openai_api_version: str = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2024-08-01-preview"
        )

        # OpenAI (for embeddings) config
        # Fall back to Azure OpenAI key if OpenAI API key is not set
        self.openai_api_key: str = os.getenv(
            "OPENAI_API_KEY", self.azure_openai_api_key
        )

        # Embedding config
        self.embedding_model: str = os.getenv(
            "EMBEDDING_MODEL", "text-embedding-3-small"
        )
        self.embedding_dimensions: int = int(os.getenv(
            "EMBEDDING_DIMENSIONS", "384"
        ))

        # Memory triggers
        self.short_term_max_messages: int = int(os.getenv(
            "SHORT_TERM_MAX_MESSAGES", "30"  # 15 tours
        ))
        self.extraction_trigger_frequency: int = int(os.getenv(
            "EXTRACTION_TRIGGER_FREQUENCY", "5"  # Every 5 tours (10 messages)
        ))
        self.confidence_threshold: float = float(os.getenv(
            "CONFIDENCE_THRESHOLD", "0.8"
        ))

def load_settings() -> Settings:
    return Settings()
