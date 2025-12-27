import os


class Settings:
    """Application configuration settings."""
    
    # Timing Configuration - Adjusted for 5 RPM free tier limit
    API_CALL_DELAY_SECONDS: float = float(os.getenv("API_CALL_DELAY", "15.0"))  # Changed from 2.0
    URL_VALIDATION_TIMEOUT: int = int(os.getenv("URL_TIMEOUT", "3"))
    GEMINI_API_TIMEOUT: int = int(os.getenv("GEMINI_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "2"))  # Changed from 3 to save quota
    
    # Quality Thresholds
    MIN_CONFIDENCE_THRESHOLD: float = float(os.getenv("MIN_CONFIDENCE", "0.5"))
    HIGH_VARIANCE_THRESHOLD: float = float(os.getenv("HIGH_VARIANCE", "1.5"))
    
    # Limits - Stricter for free tier
    MAX_IMAGES_PER_PRODUCT: int = int(os.getenv("MAX_IMAGES", "3"))  # Changed from 5
    MAX_CONCURRENT_VALIDATIONS: int = int(os.getenv("MAX_CONCURRENT", "5"))  # Changed from 10
    
    # Model Configuration
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    FALLBACK_MODELS: list = [
        "gemini-2.5-flash",      # Primary (currently exhausted)
        "gemini-2.5-flash-lite", # Fallback 1 - 0/20 used, FRESH!
        "gemini-3-flash-preview",        # Fallback 2 - 0/20 used, FRESH!
    ]


settings = Settings()
