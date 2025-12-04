"""
Document Types and Typologies
File: document_types.py

Centralized definitions for all document types used in the legal documents system.
Version française pour EUR-Lex.
"""

from enum import Enum


class Series(str, Enum):
    """EUR-Lex Official Journal Series"""
    L = "L"
    C = "C"


class EURLEXTypology(str, Enum):
    """EUR-Lex Document Typologies (version française)"""
    RESOLUTIONS = "Résolutions, recommandations et avis"
    COMMUNICATIONS = "Communications"
    INFORMATIONS = "Informations"
    ANNONCES = "Annonces"
    RECTIFICATIFS = "Rectificatifs"
    ACTS_NON_LEGISLATIFS = "Actes non législatifs"
    ACT_LEGISLATIFS = "Actes législatifs"


class JORFTypology(str, Enum):
    """JORF Document Typologies"""
    AVIS = "Avis"
    DECRET = "Décret"
    ARRETE = "Arrêté"
    DECISION = "Décision"
    INFORMATION = "Information"
    COMMUNICATION = "Communication"
    ANNONCE = "Annonce"
    AUTRE = "Autre"