"""
Configuration centralisée pour TradeMe.
Utilise Pydantic Settings pour charger les variables d'environnement.
"""
import os
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field

# Charger .env depuis le dossier backend
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))


class Settings(BaseSettings):
    """Configuration globale de l'application."""
    
    # --- Alpaca Trading API ---
    alpaca_api_key: str = Field(default="", alias="ALPACA_API_KEY")
    alpaca_api_secret: str = Field(default="", alias="ALPACA_API_SECRET")
    alpaca_base_url: str = Field(
        default="https://paper-api.alpaca.markets",
        alias="ALPACA_BASE_URL"
    )
    
    # --- OpenRouter API ---
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        alias="OPENROUTER_BASE_URL"
    )
    
    # --- Modèles IA ---
    grok_model: str = Field(default="x-ai/grok-3-mini", alias="GROK_MODEL")
    deepseek_model: str = Field(default="deepseek/deepseek-chat", alias="DEEPSEEK_MODEL")
    openai_model: str = Field(default="openai/gpt-4o", alias="OPENAI_MODEL")
    
    # --- Supabase ---
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_KEY")
    
    # --- Configuration Trading ---
    trading_interval_minutes: int = Field(default=30, alias="TRADING_INTERVAL_MINUTES")
    max_position_percent: float = Field(default=2.0, alias="MAX_POSITION_PERCENT")
    initial_capital_per_ai: float = Field(default=1000.0, alias="INITIAL_CAPITAL_PER_AI")
    simulated_fee_per_trade: float = Field(default=1.0, alias="SIMULATED_FEE_PER_TRADE")
    
    # --- News APIs (optionnelles) ---
    finnhub_api_key: Optional[str] = Field(default=None, alias="FINNHUB_API_KEY")
    alpha_vantage_key: Optional[str] = Field(default=None, alias="ALPHA_VANTAGE_KEY")
    
    # --- X (Twitter) API ---
    x_bearer_token: Optional[str] = Field(default=None, alias="X_BEARER_TOKEN")
    
    # --- API Server ---
    api_host: str = Field(default="0.0.0.0", alias="API_HOST")
    api_port: int = Field(default=8000, alias="API_PORT")
    
    # --- Modes ---
    debug: bool = Field(default=False, alias="DEBUG")
    paper_trading: bool = Field(default=True, alias="PAPER_TRADING")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def is_alpaca_configured(self) -> bool:
        """Vérifie si Alpaca est configuré."""
        return bool(self.alpaca_api_key and self.alpaca_api_secret)
    
    def is_openrouter_configured(self) -> bool:
        """Vérifie si OpenRouter est configuré."""
        return bool(self.openrouter_api_key)
    
    def is_supabase_configured(self) -> bool:
        """Vérifie si Supabase est configuré."""
        return bool(self.supabase_url and self.supabase_key)


@lru_cache()
def get_settings() -> Settings:
    """Retourne une instance mise en cache des settings."""
    return Settings()


# Instance globale
settings = get_settings()


# Mapping des modèles IA
AI_MODELS = {
    "grok": settings.grok_model,
    "deepseek": settings.deepseek_model,
    "openai": settings.openai_model,
}
