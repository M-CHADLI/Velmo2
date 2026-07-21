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

        # Azure OpenAI (DeepSeek-V4-Flash) config
        self.azure_openai_api_key: str = os.getenv(
            "AZURE_OPENAI_API_KEY", ""
        )
        self.azure_openai_endpoint: str = os.getenv(
            "AZURE_OPENAI_ENDPOINT", ""
        )
        self.azure_openai_deployment_name: str = os.getenv(
            "AZURE_OPENAI_DEPLOYMENT_NAME", "DeepSeek-V4-Flash"
        )
        self.azure_openai_api_version: str = os.getenv(
            "AZURE_OPENAI_API_VERSION", "2026-04-23"
        )

        # --- Latency tuning (see docs/OPTIMISATIONS_LATENCE.md) ---
        # Classifier only needs to emit one category word → cap output tokens.
        # A dedicated (lighter/faster) deployment can be pointed here without
        # touching the main response model; defaults to the main deployment.
        self.classifier_deployment_name: str = (
            os.getenv("CLASSIFIER_DEPLOYMENT_NAME") or self.azure_openai_deployment_name
        )
        self.classifier_max_tokens: int = int(os.getenv("CLASSIFIER_MAX_TOKENS", "16"))
        # Support answers are short; bound worst-case generation latency.
        self.response_max_tokens: int = int(os.getenv("RESPONSE_MAX_TOKENS", "512"))

        # LangSmith (Observability - Chantier 3)
        self.langsmith_tracing: bool = os.getenv(
            "LANGSMITH_TRACING", "false"
        ).lower() in ("1", "true", "yes")
        self.langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
        self.langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "velmo-2.0")
        self.langsmith_endpoint: str = os.getenv(
            "LANGSMITH_ENDPOINT", "https://api.smith.langchain.com"
        )

        # OVH SMS config
        self.ovh_consumer_key: str = os.getenv("OVH_CONSUMER_KEY", "")
        self.ovh_service_name: str = os.getenv("OVH_SERVICE_NAME", "")
        self.ovh_sender: str = os.getenv("OVH_SENDER", "Velmo2")
        self.ovh_app_key: str = os.getenv("OVH_APP_KEY", "")
        self.ovh_app_secret: str = os.getenv("OVH_APP_SECRET", "")

        # Twilio WhatsApp config
        self.twilio_account_sid: str = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.twilio_auth_token: str = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.twilio_whatsapp_number: str = os.getenv("TWILIO_WHATSAPP_NUMBER", "")


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


# Module-level singleton for convenience imports (e.g. `from velmo.config import settings`)
settings = load_settings()
