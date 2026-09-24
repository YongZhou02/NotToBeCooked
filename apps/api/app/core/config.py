from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dynamic path resolution to prevent searching .env at repository root
_ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


# Duplicate value of a variable follows a priority system where
# system variable (e.g. Docker) > values in .env > values in config.py
class Settings(BaseSettings):
    # App Settings
    PROJECT_NAME: str = "NotToBeCooked API"
    VERSION: str = "0.0.1"

    # JWT Authentication Settings
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_SECRET: str = "dev_access_token_secret_key_change_in_prod"
    REFRESH_TOKEN_SECRET: str = "dev_refresh_token_secret_key_change_in_prod"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    # Local development runs over plain HTTP, where browsers reject Secure
    # cookies. Production deployments must set this to true when using HTTPS.
    AUTH_COOKIE_SECURE: bool = False

    # Database Settings
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/not_to_be_cooked"

    # Echo every statement the engine runs. False by default, which is a change
    # from the hard-coded echo=True that shipped in db/database.py: on the OCI
    # box those lines land in the system journal, several per request, carrying
    # bound parameter values with them. Set SQL_ECHO=true in .env on a machine
    # where you want them back.
    SQL_ECHO: bool = False

    # Embedding Settings
    BATCH_SIZE: int = 32
    EMBEDDINGS_DIM: int = 1024
    MODEL_TYPE: str = "jinaai/jina-embeddings-v5-text-small"
    CHUNKER_VERSION: str = "chunker-1"

    # File Storage Settings
    #
    # STORAGE_DIR is a local directory today and an object-store bucket later.
    # FILE.storage_key is documented as "an object-store key, not a filesystem
    # path" for that reason -- the key is stable across the move, only the thing
    # that resolves it changes. See app/services/storage.py.
    STORAGE_DIR: Path = _ENV_FILE.parent / "storage"

    # Enforced while streaming, not after. Reading a 4 GB upload into memory to
    # discover it is too large is the failure this guards against.
    MAX_UPLOAD_BYTES: int = 50 * 1024 * 1024

    # Gemini Settings
    GEMINI_API_KEY: SecretStr = SecretStr("")
    GEMINI_MODEL_NAME: str = "gemini-3.5-flash-lite"
    GEMINI_API_BASE_URL: str = "https://generativelanguage.googleapis.com/v1beta"
    GEMINI_API_TIMEOUT_SECONDS: float = 30.0

    # LLM Calls Settings
    LLM_FAKE_MODE: bool = Field(default=True)

    # Load from .env file automatically
    model_config = SettingsConfigDict(
        env_file=(_ENV_FILE, ".env"), env_file_encoding="utf-8", extra="ignore"
    )


settings = Settings()  # pyright: ignore[reportCallIssue]
