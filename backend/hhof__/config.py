"""
Configuration centralisée pour le système de scraping
File: config.py
"""

import os
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


@dataclass
class DatabaseConfig:
    """Configuration de la base de données"""
    db_path: str = "legal_documents.db"
    connection_timeout: int = 30
    max_retries: int = 3
    
    @property
    def db_uri(self) -> str:
        return f"sqlite:///{self.db_path}"


@dataclass
class StorageConfig:
    """Configuration du stockage de fichiers"""
    content_dir: Path = field(default_factory=lambda: Path("content_files"))
    eurlex_l_dir: Path = field(init=False)
    eurlex_c_dir: Path = field(init=False)
    jorf_dir: Path = field(init=False)
    
    def __post_init__(self):
        self.content_dir = Path(self.content_dir)
        self.eurlex_l_dir = self.content_dir / "eurlex" / "eurlex_l"
        self.eurlex_c_dir = self.content_dir / "eurlex" / "eurlex_c"
        self.jorf_dir = self.content_dir / "jorf"
        
        # Créer les répertoires
        for dir_path in [self.eurlex_l_dir, self.eurlex_c_dir, self.jorf_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)


@dataclass
class LLMConfig:
    """Configuration LLM"""
    enabled: bool = True
    provider: str = "openai"
    model: Optional[str] = None
    api_key: Optional[str] = None
    temperature: float = 0.0
    max_tokens: int = 4096
    chunk_size_tokens: int = 3000
    batch_size: int = 10
    cache_enabled: bool = True
    cache_ttl_hours: int = 168  # 1 semaine
    
    def __post_init__(self):
        if self.model is None:
            self.model = self._get_default_model()
        if self.api_key is None:
            self.api_key = self._get_api_key()
    
    def _get_default_model(self) -> str:
        """Modèle par défaut selon le provider"""
        defaults = {
            "openai": "gpt-4o-mini",
            "anthropic": "claude-sonnet-4-20250514",
            "mistral": "mistral-large-latest"
        }
        return defaults.get(self.provider, "gpt-4o-mini")
    
    def _get_api_key(self) -> Optional[str]:
        """Récupère l'API key depuis l'environnement"""
        key_map = {
            "openai": "OPENAI_API_KEY",
            "anthropic": "ANTHROPIC_API_KEY",
            "mistral": "MISTRAL_API_KEY"
        }
        env_var = key_map.get(self.provider)
        return os.getenv(env_var) if env_var else None


@dataclass
class ScraperConfig:
    """Configuration des scrapers"""
    user_agent: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    timeout: int = 30
    retry_delay: int = 1
    max_retries: int = 3
    delay_between_requests: float = 1.0
    auto_process_after_scrape: bool = False


@dataclass
class SchedulerConfig:
    """Configuration du scheduler"""
    eurlex_l_time: str = "09:00"
    eurlex_c_time: str = "09:30"
    llm_processing_interval_hours: int = 2
    statistics_interval_hours: int = 6
    cleanup_interval_hours: int = 24


@dataclass
class MonitoringConfig:
    """Configuration du monitoring"""
    enabled: bool = True
    log_file: str = "scraper.log"
    metrics_file: str = "metrics.json"
    log_level: str = "INFO"


@dataclass
class Config:
    """Configuration globale du système"""
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    scraper: ScraperConfig = field(default_factory=ScraperConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)
    
    @classmethod
    def from_env(cls) -> "Config":
        """Créer configuration depuis variables d'environnement"""
        return cls(
            database=DatabaseConfig(
                db_path=os.getenv("DB_PATH", "legal_documents.db"),
                connection_timeout=int(os.getenv("DB_TIMEOUT", "30")),
            ),
            storage=StorageConfig(
                content_dir=Path(os.getenv("CONTENT_DIR", "content_files"))
            ),
            llm=LLMConfig(
                enabled=os.getenv("LLM_ENABLED", "true").lower() == "true",
                provider=os.getenv("LLM_PROVIDER", "openai"),
                model=os.getenv("LLM_MODEL"),
                temperature=float(os.getenv("LLM_TEMPERATURE", "0.0")),
                max_tokens=int(os.getenv("LLM_MAX_TOKENS", "4096")),
                chunk_size_tokens=int(os.getenv("LLM_CHUNK_SIZE_TOKENS", "3000")),
                batch_size=int(os.getenv("LLM_BATCH_SIZE", "10")),
                cache_enabled=os.getenv("LLM_CACHE_ENABLED", "true").lower() == "true",
            ),
            scraper=ScraperConfig(
                timeout=int(os.getenv("SCRAPER_TIMEOUT", "30")),
                delay_between_requests=float(os.getenv("SCRAPER_DELAY", "1.0")),
                auto_process_after_scrape=os.getenv("AUTO_PROCESS_AFTER_SCRAPE", "false").lower() == "true",
            ),
            scheduler=SchedulerConfig(
                eurlex_l_time=os.getenv("EURLEX_L_TIME", "09:00"),
                eurlex_c_time=os.getenv("EURLEX_C_TIME", "09:30"),
                llm_processing_interval_hours=int(os.getenv("LLM_INTERVAL_HOURS", "2")),
            ),
            monitoring=MonitoringConfig(
                enabled=os.getenv("MONITORING_ENABLED", "true").lower() == "true",
                log_level=os.getenv("LOG_LEVEL", "INFO"),
            )
        )
    
    def validate(self) -> list[str]:
        """Valide la configuration et retourne les erreurs"""
        errors = []
        
        if self.llm.enabled and not self.llm.api_key:
            errors.append(f"LLM enabled but no API key found for provider: {self.llm.provider}")
        
        if self.llm.chunk_size_tokens > self.llm.max_tokens:
            errors.append(f"Chunk size ({self.llm.chunk_size_tokens}) cannot exceed max tokens ({self.llm.max_tokens})")
        
        if not self.storage.content_dir.exists():
            try:
                self.storage.content_dir.mkdir(parents=True)
            except Exception as e:
                errors.append(f"Cannot create content directory: {e}")
        
        return errors


# Instance globale de configuration
_config: Optional[Config] = None


def get_config() -> Config:
    """Récupère la configuration globale (singleton)"""
    global _config
    if _config is None:
        _config = Config.from_env()
        errors = _config.validate()
        if errors:
            raise ValueError(f"Configuration errors: {', '.join(errors)}")
    return _config


def reload_config():
    """Recharge la configuration depuis l'environnement"""
    global _config
    _config = None
    return get_config()