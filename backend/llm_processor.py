"""
LLM Processor - Responsible for document classification and metadata enrichment
File: llm_processor.py

Adds summary, applicability classification, and theme classification to legal documents 
using a one-shot approach with a 10,000 token input limit.
"""

import logging
import json
import os
from typing import Dict, Optional, List
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from llm_service import LLMService, LLMProvider 
from csv_repository import CSVDocumentRepository

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


# ============================================================================
# Pydantic Models for Structured Output
# ============================================================================

class ThemeClassification(BaseModel):
    """Classification de document par thèmes santé & sécurité"""
    themes: List[str] = Field(
        ...,
        description="Liste ordonnée de 3 thèmes max, du plus au moins représentatif",
        min_length=1,
        max_length=3
    )
    reasoning: str = Field(
        ..., 
        description="Justification courte (2-3 phrases) des thèmes choisis"
    )


class LLMProcessor:
    """
    LLM-based document processor for metadata enrichment
    
    Generates:
    - Summary (one-shot, max 10k tokens input)
    - Applicability classification (Information, Obligation, Jurisprudence)
    - Theme classification (Health & Safety themes)
    """
    
    # Classification categories
    APPLICABILITY_CATEGORIES = {
        "information": [
            "Directive européenne", "Circulaire", "Instruction", "Normes",
            "Communiqué", "Avis", "Recommandation", "Décision ou résumé de décisions",
            "Rapport"
        ],
        "obligation": [
            "Loi", "Règlement", "Décret", "Arrêté", "Convention"
        ],
        "jurisprudence": [
            "Arrêt", "Décision", "Cour de cassation", "Conseil constitutionnel",
            "Cour de justice de l'union européenne", "Tribunal de l'union européenne"
        ]
    }
    
    # Health & Safety Themes (categorized)
    THEMES = {
        "Principes généraux": [
            "Principes de prévention",
            "Rôles & Responsabilités",
            "Affichage",
            "Signalisation",
            "Reporting"
        ],
        "Accidents & Maladies": [
            "AT & MP",
            "ATMP",
            "PARIPRAC",
            "T"
        ],
        "Santé": [
            "Inspections",
            "Santé publique",
            "Santé au travail",
            "SPST",
            "Secours"
        ],
        "Construction & Aménagement": [
            "Construction",
            "Démolition",
            "Aménagement",
            "ERP",
            "Stockage (non chimique)",
            "Chutes d'objet",
            "Amiante",
            "Chantiers",
            "CSPS",
            "Conception",
            "Accessibilité",
            "Urbanisme",
            "Infrastructures",
            "Réseaux"
        ],
        "Équipements & Protection": [
            "Machines",
            "Outils",
            "EPI",
            "Protection collective",
            "Equipements sous pression",
            "Equipements de froid",
            "Consignation",
            "Maintenance",
            "Contrôles",
            "Normes",
            "Ventilation",
            "Drones"
        ],
        "Conditions de travail": [
            "Bruit",
            "Vibrations",
            "Milieu hyperbare",
            "Travail en hauteur",
            "Ergonomie",
            "Eclairage",
            "Travail sur écran",
            "Manutention manuelle",
            "Manutention mécanique",
            "Espaces confinés",
            "Ambiances thermiques",
            "Travail tertiaire",
            "Milieu souterrain",
            "Travail en laboratoire"
        ],
        "Incendie & Urgences": [
            "Incendie",
            "Pyrotechnie",
            "ATEX",
            "Evacuation",
            "Situations d'urgence",
            "Extinction",
            "Résistance au feu",
            "Exercices"
        ],
        "Risques physiques": [
            "Risques électriques",
            "Rayonnements ionisants",
            "Rayonnements non ionisants",
            "Champs électromagnétiques",
            "Radon"
        ],
        "Risques chimiques": [
            "VLEP",
            "CLP",
            "REACH",
            "CMR",
            "ACD",
            "Biocides & Phytos",
            "Biocides",
            "Phytos",
            "Engrais",
            "POP",
            "Nano-matériaux",
            "Perturbateurs endocriniens",
            "Toxicologie",
            "Stockage (chimique)",
            "F-Gas",
            "PIC",
            "Substances vénéneuses",
            "Précurseurs stupéfiants",
            "Risque chimique"
        ],
        "Risques biologiques": [
            "Risque biologique",
            "COVID-19",
            "Grippe",
            "Légionelles"
        ],
        "Risques routiers": [
            "Risques routiers",
            "Chargement & Déchargement",
            "Piétons",
            "Circulation",
            "Poids lourds",
            "Transports en commun",
            "Automobiles",
            "Transport de marchandises"
        ],
        "Organisation du travail": [
            "Télétravail",
            "RPS",
            "Travail de nuit",
            "Travail posté",
            "Travail isolé",
            "Co-activité",
            "Entreprises extérieures",
            "Plan de prévention",
            "Sous-traitance",
            "Intérim"
        ],
        "Représentation": [
            "Représentants du personnel",
            "CSE & CSSCT",
            "CSE",
            "CSSCT",
            "Compétences",
            "Droits d'alerte et de retrait",
            "Droit d'alerte",
            "Droit de retrait"
        ],
        "Populations spécifiques": [
            "Travailleurs étrangers",
            "Travailleurs détachés",
            "Travailleurs mineurs",
            "Femmes enceintes et allaitantes",
            "Femmes enceintes",
            "Femmes allaitantes",
            "Stagiaires",
            "Apprentis",
            "Travailleurs handicapés"
        ],
        "Contrôle & Gouvernance": [
            "Inspection du travail",
            "DIRECCTE",
            "Assureurs",
            "Corporate",
            "Règlement intérieur"
        ],
        "Documentation": [
            "Articles & Guides"
        ]
    }
    
    def __init__(
        self,
        llm_service: LLMService,
        repository: CSVDocumentRepository,
        chunk_size_tokens: Optional[int] = None
    ):
        """
        Initialize LLM Processor
        
        Args:
            llm_service: Configured LLM service
            repository: Document repository
            chunk_size_tokens: Max tokens for content processing (used as the one-shot limit)
        """
        self.llm = llm_service
        self.repo = repository
        self.one_shot_limit_tokens = chunk_size_tokens or int(os.getenv("LLM_CHUNK_SIZE_TOKENS", "10000"))
        
        # Flatten themes for easier lookup
        self.all_themes = []
        for category, themes in self.THEMES.items():
            self.all_themes.extend(themes)
        
        logger.info(f"LLM Processor initialized (One-shot content limit: {self.one_shot_limit_tokens} tokens)")
        logger.info(f"Loaded {len(self.all_themes)} health & safety themes")
    
    def process_document(self, document_id: str) -> bool:
        """
        Process a single document: generate summary, classify applicability, and identify themes
        """
        logger.info(f"Processing document: {document_id}")
        
        doc = self.repo.get_by_id(document_id)
        if not doc:
            logger.error(f"Document {document_id} not found")
            return False
        
        content_path = doc.get('content')
        if not content_path:
            logger.error(f"No content path for document {document_id}")
            return False
        
        content = self.repo.read_content_from_file(content_path)
        if not content:
            logger.error(f"Could not read content for document {document_id}")
            return False
        
        try:
            # Generate one-shot summary
            summary = self._generate_one_shot_summary(content, doc)
            
            # Classify applicability
            applicability = self._classify_applicability(content, doc)
            
            # Classify themes
            theme_result = self._classify_themes(content, doc)
            
            # Update document
            updates = {
                'summary': summary,
                'applicability': applicability,
                'themes': theme_result.themes,
                'keywords': None,
                'processing_status': 'processed'
            }
            
            success = self.repo.update_document(document_id, updates)
            
            if success:
                logger.info(f"✅ Document {document_id} processed successfully")
                logger.info(f"   Applicability: {applicability}")
                logger.info(f"   Themes (ordered): {', '.join(theme_result.themes)}")
                logger.info(f"   Summary length: {len(summary)} chars")
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing document {document_id}: {e}")
            self.repo.update_processing_status(document_id, 'error')
            return False

    def _generate_one_shot_summary(self, content: str, doc: Dict) -> str:
        """Generate one-shot summary with strict token limit"""
        logger.info("Génération du résumé one-shot...")
        
        content_tokens = self.llm.count_tokens(content)
        logger.info(f"Nombre total de tokens du document : ~{content_tokens}")

        TARGET_TOKEN_LIMIT = self.one_shot_limit_tokens 
        MAX_CHAR_LIMIT = TARGET_TOKEN_LIMIT * 4
        
        content_to_summarize = content
        
        if content_tokens > TARGET_TOKEN_LIMIT:
            logger.warning(
                f"Document trop long ({content_tokens} tokens). "
                f"Troncature à environ {TARGET_TOKEN_LIMIT} tokens."
            )
            
            content_to_summarize = content[:MAX_CHAR_LIMIT]
            content_to_summarize += "\n\n[... DOCUMENT TRONQUÉ POUR LIMITER LE CONTEXTE ...]"
            
            truncated_tokens = self.llm.count_tokens(content_to_summarize)
            logger.info(f"Tokens envoyés au modèle : ~{truncated_tokens}")
        
        return self._summarize_document_content(content_to_summarize, doc)
    
    def _summarize_document_content(self, content: str, doc: Dict) -> str:
        """Summarize the entire (potentially truncated) content"""
        system_prompt = """Tu es un expert juridique spécialisé dans l'analyse de documents légaux.
Ta tâche est de produire un résumé TRÈS COURT et précis en une seule phrase."""
        
        doc_type = doc.get('typologie', 'document')
        source = doc.get('source', 'inconnu')
        
        prompt = f"""Analyse ce document juridique et produis un résumé ULTRA-COURT.

**Type de document**: {doc_type}
**Source**: {source}

**Contenu**:
{content}

**Instructions CRITIQUES**:
1. Produis UN RÉSUMÉ EN UNE SEULE PHRASE de maximum 500 caractères
2. Capture UNIQUEMENT l'idée principale du document
3. Sois extrêmement concis et direct
4. Évite les mots inutiles et les formules de politesse
5. Va droit au but

Exemple de format attendu:
"Décret sur la protection des travailleurs contre les risques électriques"
"Directive européenne relative aux équipements de protection individuelle"

Résumé (max 500 caractères):"""
        
        summary = self.llm.generate(prompt, system_prompt=system_prompt).strip()
        
        # Assurer que le résumé ne dépasse pas 500 caractères
        if len(summary) > 500:
            summary = summary[:497] + "..."
        
        return summary
    
    def _classify_applicability(self, content: str, doc: Dict) -> str:
        """
        Classify document applicability
        Returns format: "category/document_type" (e.g., "obligation/Règlement")
        """
        logger.info("Classifying applicability...")
        
        # Troncature du contenu si nécessaire
        max_content_chars = 15000
        if len(content) > max_content_chars:
            content = content[:10000] + "\n\n[...]\n\n" + content[-5000:]
        
        system_prompt = """Tu es un expert en classification de documents juridiques.
Ta tâche est de classifier le document selon son applicabilité juridique et d'identifier son type précis."""
        
        titre = doc.get('titre', 'Sans titre')
        doc_type = doc.get('typologie', 'inconnu')
        abstract = doc.get('abstract', '')
        
        # Construire la liste des types par catégorie
        types_list = []
        for category, doc_types in self.APPLICABILITY_CATEGORIES.items():
            for dt in doc_types:
                types_list.append(f"- {category}/{dt}")
        types_text = "\n".join(types_list)
        
        prompt = f"""Classifie ce document juridique selon son applicabilité ET son type précis.

**Titre**: {titre}
**Type déclaré**: {doc_type}
**Résumé**: {abstract}

**Contenu** (extrait):
{content}

**Classifications possibles** (catégorie/type):
{types_text}

**Instructions**:
1. Analyse le contenu et le type de document
2. Identifie la catégorie d'applicabilité:
- **information**: Document informatif sans force contraignante
- **obligation**: Texte juridiquement contraignant créant des obligations
- **jurisprudence**: Décision de justice ou interprétation judiciaire

3. Identifie le type de document précis parmi la liste fournie

4. Réponds UNIQUEMENT avec le format: catégorie/type
Exemples: "obligation/Règlement", "information/Circulaire", "jurisprudence/Arrêt"

Classification (catégorie/type):"""
        
        response = self.llm.generate(prompt, system_prompt=system_prompt).strip()
        
        # Nettoyer la réponse (enlever guillemets, espaces, etc.)
        response = response.strip('"\'').strip()
        
        # Valider le format de la réponse
        if '/' in response:
            parts = response.split('/', 1)
            category = parts[0].lower().strip()
            doc_type_response = parts[1].strip()
            
            # Vérifier que la catégorie est valide
            if category in self.APPLICABILITY_CATEGORIES:
                # Vérifier que le type existe dans cette catégorie
                valid_types = self.APPLICABILITY_CATEGORIES[category]
                
                # Recherche exacte ou approximative du type
                matched_type = None
                for valid_type in valid_types:
                    if valid_type.lower() == doc_type_response.lower():
                        matched_type = valid_type
                        break
                
                if matched_type:
                    result = f"{category}/{matched_type}"
                    logger.info(f"Classified as: {result}")
                    return result
                else:
                    # Type non trouvé, utiliser le premier de la catégorie par défaut
                    default_type = valid_types[0]
                    result = f"{category}/{default_type}"
                    logger.warning(f"Type '{doc_type_response}' not found in {category}. Using: {result}")
                    return result
        
        # Fallback: essayer de détecter au moins la catégorie
        response_lower = response.lower()
        for category in ["obligation", "jurisprudence", "information"]:
            if category in response_lower:
                default_type = self.APPLICABILITY_CATEGORIES[category][0]
                result = f"{category}/{default_type}"
                logger.warning(f"Partial match. Defaulting to: {result}")
                return result
        
        # Dernier recours
        default_result = "information/Avis"
        logger.warning(f"Unexpected response: '{response}'. Defaulting to: {default_result}")
        return default_result
    
    def _classify_themes(self, content: str, doc: Dict) -> ThemeClassification:
        """Classify document themes using structured output"""
        logger.info("Classifying themes...")
        
        max_content_chars = 15000
        if len(content) > max_content_chars:
            content = content[:10000] + "\n\n[...]\n\n" + content[-5000:]
        
        titre = doc.get('titre', 'Sans titre')
        doc_type = doc.get('typologie', 'inconnu')
        abstract = doc.get('abstract', '')
        
        # Check if using Azure OpenAI with function calling support
        if self.llm.provider.value == "azure_openai":
            return self._classify_themes_with_function_calling(content, titre, doc_type, abstract)
        else:
            return self._classify_themes_standard(content, titre, doc_type, abstract)
    
    def _classify_themes_with_function_calling(
        self, 
        content: str, 
        titre: str, 
        doc_type: str, 
        abstract: str
    ) -> ThemeClassification:
        """Classify themes using Azure OpenAI function calling"""
        
        theme_tool = {
            "type": "function",
            "function": {
                "name": "classify_themes",
                "description": "Classify a legal document into health & safety themes",
                "parameters": ThemeClassification.model_json_schema(),
            },
        }
        
        system_prompt = """Tu es un expert en santé et sécurité au travail spécialisé dans la classification de documents juridiques.
Ta tâche est d'identifier les thèmes les plus pertinents dans chaque document."""
        
        themes_text = "\n".join([f"- {theme}" for theme in self.all_themes])
        
        user_prompt = f"""Analyse ce document juridique et identifie les thèmes santé-sécurité pertinents.

**Titre**: {titre}
**Type**: {doc_type}
**Résumé**: {abstract}

**Contenu** (extrait):
{content}

**Thèmes disponibles**:
{themes_text}

**Instructions**:
1. Identifie les 3 thèmes les PLUS PERTINENTS pour ce document
2. Classe-les par ordre DÉCROISSANT de représentativité (le plus important en premier)
3. Tu peux identifier 1, 2 ou 3 thèmes selon la pertinence
4. Fournis une explication courte (2-3 phrases) justifiant tes choix
5. Utilise EXACTEMENT les noms de thèmes fournis dans la liste

Réponds en utilisant la fonction classify_themes."""
        
        try:
            from openai import AzureOpenAI
            
            client = AzureOpenAI(
                api_key=os.getenv("AZURE_OPENAI_API_KEY"),
                api_version=self.llm.api_version,
                azure_endpoint=self.llm.azure_endpoint
            )
            
            response = client.chat.completions.create(
                model=self.llm.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                tools=[theme_tool],
                tool_choice={"type": "function", "function": {"name": "classify_themes"}},
                temperature=0.0
            )
            
            tool_call = response.choices[0].message.tool_calls[0]
            raw_args = tool_call.function.arguments
            
            theme_classification = ThemeClassification.model_validate_json(raw_args)
            
            logger.info(f"Themes (ordered by relevance): {', '.join(theme_classification.themes)}")
            return theme_classification
            
        except Exception as e:
            logger.error(f"Error in function calling theme classification: {e}")
            return ThemeClassification(
                themes=["Articles & Guides"],
                reasoning="Classification failed, using default theme"
            )
    
    def _classify_themes_standard(
        self, 
        content: str, 
        titre: str, 
        doc_type: str, 
        abstract: str
    ) -> ThemeClassification:
        """Fallback theme classification using standard prompting"""
        
        system_prompt = """Tu es un expert en santé et sécurité au travail.
Réponds UNIQUEMENT avec un objet JSON valide."""
        
        themes_text = "\n".join([f"- {theme}" for theme in self.all_themes])
        
        prompt = f"""Analyse ce document juridique et identifie les thèmes santé-sécurité pertinents.

**Titre**: {titre}
**Type**: {doc_type}
**Résumé**: {abstract}

**Contenu** (extrait):
{content}

**Thèmes disponibles**:
{themes_text}

**Instructions**:
1. Identifie les 3 thèmes les PLUS PERTINENTS
2. Classe-les par ordre DÉCROISSANT de représentativité
3. Fournis une explication courte

Réponds UNIQUEMENT avec ce JSON (pas de texte avant/après):
{{
  "themes": ["thème1", "thème2", "thème3"],
  "reasoning": "explication courte"
}}"""
        
        try:
            response = self.llm.generate(prompt, system_prompt=system_prompt, response_format="json")
            result = json.loads(response)
            
            return ThemeClassification(
                themes=result.get("themes", ["Articles & Guides"])[:3],
                reasoning=result.get("reasoning", "Classified using standard prompting")
            )
            
        except Exception as e:
            logger.error(f"Error in standard theme classification: {e}")
            return ThemeClassification(
                themes=["Articles & Guides"],
                reasoning="Classification failed, using default theme"
            )
    
    def process_batch(self, batch_size: int = 10) -> Dict[str, int]:
        """Process a batch of pending documents"""
        logger.info(f"Starting batch processing (max {batch_size} documents)...")
        
        pending_docs = self.repo.get_pending_for_processing(limit=batch_size)
        
        if not pending_docs:
            logger.info("No pending documents to process")
            return {"processed": 0, "failed": 0, "skipped": 0}
        
        logger.info(f"Found {len(pending_docs)} pending documents")
        
        stats = {"processed": 0, "failed": 0, "skipped": 0}
        
        for i, doc in enumerate(pending_docs, 1):
            doc_id = doc.get('id')
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing {i}/{len(pending_docs)}: {doc_id}")
            logger.info(f"{'='*60}")
            
            try:
                success = self.process_document(doc_id)
                if success:
                    stats["processed"] += 1
                else:
                    stats["failed"] += 1
            except Exception as e:
                logger.error(f"Failed to process {doc_id}: {e}")
                stats["failed"] += 1
        
        logger.info(f"\n{'='*60}")
        logger.info("Batch processing complete")
        logger.info(f"Processed: {stats['processed']}")
        logger.info(f"Failed: {stats['failed']}")
        logger.info(f"{'='*60}")
        
        return stats