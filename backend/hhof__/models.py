"""
Modèles de données pour le système de scraping
File: models.py
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List
from pathlib import Path


class DocumentSource(Enum):
    """Sources de documents"""
    EURLEX = "EURLEX"
    JORF = "JORF"


class ProcessingStatus(Enum):
    """Statuts de traitement"""
    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    ERROR = "error"


class Applicability(Enum):
    """Catégories d'applicabilité"""
    INFORMATION = "information"
    OBLIGATION = "obligation"
    JURISPRUDENCE = "jurisprudence"


class Series(Enum):
    """Séries EUR-LEX"""
    L = "L"
    C = "C"


class EURLEXTypology(Enum):
    """Typologies EUR-LEX"""
    REGULATION = "Règlement"
    DIRECTIVE = "Directive"
    DECISION = "Décision"
    RECOMMENDATION = "Recommandation"
    OPINION = "Avis"
    OTHER = "Autre"


class JORFTypology(Enum):
    """Typologies JORF"""
    LOI = "Loi"
    DECRET = "Décret"
    ARRETE = "Arrêté"
    DECISION = "Décision"
    AVIS = "Avis"
    COMMUNICATION = "Communication"
    ANNONCE = "Annonce"
    INFORMATION = "Information"
    AUTRE = "Autre"


@dataclass
class Document:
    """Modèle de document juridique"""
    id: str
    source: DocumentSource
    date: datetime
    url: str
    titre: str
    
    # Métadonnées optionnelles
    typologie: Optional[str] = None
    ministre: Optional[str] = None
    abstract: Optional[str] = None
    language: str = "en"
    
    # Contenu (chemin vers fichier)
    content_path: Optional[Path] = None
    
    # Métadonnées enrichies par LLM
    summary: Optional[str] = None
    theme: Optional[str] = None
    applicability: Optional[Applicability] = None
    keywords: List[str] = field(default_factory=list)
    
    # Statut de traitement
    processing_status: ProcessingStatus = ProcessingStatus.PENDING
    processing_error: Optional[str] = None
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    
    def to_dict(self) -> dict:
        """Convertit en dictionnaire pour stockage"""
        return {
            'id': self.id,
            'source': self.source.value,
            'date': self.date.isoformat(),
            'url': self.url,
            'titre': self.titre,
            'typologie': self.typologie,
            'ministre': self.ministre,
            'abstract': self.abstract,
            'language': self.language,
            'content_path': str(self.content_path) if self.content_path else None,
            'summary': self.summary,
            'theme': self.theme,
            'applicability': self.applicability.value if self.applicability else None,
            'keywords': ','.join(self.keywords) if self.keywords else None,
            'processing_status': self.processing_status.value,
            'processing_error': self.processing_error,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Document":
        """Crée un document depuis un dictionnaire"""
        return cls(
            id=data['id'],
            source=DocumentSource(data['source']),
            date=datetime.fromisoformat(data['date']),
            url=data['url'],
            titre=data['titre'],
            typologie=data.get('typologie'),
            ministre=data.get('ministre'),
            abstract=data.get('abstract'),
            language=data.get('language', 'en'),
            content_path=Path(data['content_path']) if data.get('content_path') else None,
            summary=data.get('summary'),
            theme=data.get('theme'),
            applicability=Applicability(data['applicability']) if data.get('applicability') else None,
            keywords=data['keywords'].split(',') if data.get('keywords') else [],
            processing_status=ProcessingStatus(data.get('processing_status', 'pending')),
            processing_error=data.get('processing_error'),
            created_at=datetime.fromisoformat(data['created_at']) if data.get('created_at') else datetime.now(),
            updated_at=datetime.fromisoformat(data['updated_at']) if data.get('updated_at') else datetime.now(),
            processed_at=datetime.fromisoformat(data['processed_at']) if data.get('processed_at') else None,
        )
    
    def mark_as_processing(self):
        """Marque le document comme en cours de traitement"""
        self.processing_status = ProcessingStatus.PROCESSING
        self.updated_at = datetime.now()
    
    def mark_as_processed(self, summary: str, applicability: Applicability):
        """Marque le document comme traité"""
        self.summary = summary
        self.applicability = applicability
        self.processing_status = ProcessingStatus.PROCESSED
        self.processed_at = datetime.now()
        self.updated_at = datetime.now()
        self.processing_error = None
    
    def mark_as_error(self, error: str):
        """Marque le document comme en erreur"""
        self.processing_status = ProcessingStatus.ERROR
        self.processing_error = error
        self.updated_at = datetime.now()


@dataclass
class ScrapingStats:
    """Statistiques de scraping"""
    total_found: int = 0
    created: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    
    def __str__(self) -> str:
        return (
            f"Scraping Stats: "
            f"Found={self.total_found}, "
            f"Created={self.created}, "
            f"Skipped={self.skipped}, "
            f"Errors={self.errors}, "
            f"Duration={self.duration_seconds:.2f}s"
        )


@dataclass
class ProcessingStats:
    """Statistiques de traitement LLM"""
    total: int = 0
    processed: int = 0
    failed: int = 0
    skipped: int = 0
    cache_hits: int = 0
    duration_seconds: float = 0.0
    
    @property
    def cache_hit_rate(self) -> float:
        """Taux de cache hits"""
        return (self.cache_hits / self.total * 100) if self.total > 0 else 0.0
    
    def __str__(self) -> str:
        return (
            f"Processing Stats: "
            f"Total={self.total}, "
            f"Processed={self.processed}, "
            f"Failed={self.failed}, "
            f"Cache hits={self.cache_hits} ({self.cache_hit_rate:.1f}%), "
            f"Duration={self.duration_seconds:.2f}s"
        )