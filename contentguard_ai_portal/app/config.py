import os
from pydantic_settings import BaseSettings
# from dotenv import load_dotenv
from pathlib import Path
# load_dotenv()
from pathlib import Path
from pydantic_settings import BaseSettings
# points to contentguardportal_v2
class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "ContentGuard AI"
    APP_VERSION: str = "4.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here")

    # Database – now only SQLite

    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DATABASE_URL: str = f"sqlite:///{BASE_DIR / 'contentguard.db'}"

    # Get the project root directory (two levels up from this config file if inside app/)



    # DATABASE_URL = f"sqlite:///{DB_PATH}"
    # DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./contentguard.db")

    # Encryption
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "Nb4nVeZkLJej1XjUFjQF1eoZdhe_sKhhFQI8_ZeQbjQ=")

# ENCRYPTION_KEY=Nb4nVeZkLJej1XjUFjQF1eoZdhe_sKhhFQI8_ZeQbjQ=
    # JWT Settings
    JWT_SECRET: str = os.getenv("JWT_SECRET", "jwt-secret-key")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Pagination
    PER_PAGE: int = 20

    # ML Model Paths
    MODEL_LEVEL1_PATH: str = "models/level1_model.pkl"
    MODEL_LEVEL2_PATH: str = "models/level2_model.pkl"
    MODEL_LEVEL3_PATH: str = "models/level3_model.pkl"

    class Config:
        env_file = ".env"

settings = Settings()