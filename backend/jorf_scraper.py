"""
JORF Email Parser and Scraper
File: jorf_scraper.py

Parser for JORF email notifications with content stored in separate text files.
"""

import requests
from bs4 import BeautifulSoup
from datetime import datetime
from typing import List, Dict
import logging
import re
import time
import os
from document_types import JORFTypology

logger = logging.getLogger(__name__)


class JORFEmailParser:
    """JORF email parser with external content storage"""
    
    ACTE_PATTERN = re.compile(r'^\s*(\d+)\s*(.+?)$', re.IGNORECASE | re.MULTILINE | re.UNICODE)
    LINK_PATTERN = re.compile(r'^\s*(https://www\.legifrance\.gouv\.fr/jorf/id/(JORFTEXT\d+))', re.IGNORECASE | re.MULTILINE)
    MINISTERE_PATTERN = re.compile(r'^\s*MINISTERE DE (.*)', re.UNICODE)
    RUBRIQUE_PATTERN = re.compile(r'^\s*(PREMIER MINISTRE|COUR DES COMPTES|AUTORITE DE CONTROLE PRUDENTIEL ET DE RESOLUTION|COMMISSION NATIONALE DES COMPTES DE CAMPAGNE ET DES FINANCEMENTS POLITIQUES|INFORMATIONS PARLEMENTAIRES|AVIS ET COMMUNICATIONS|ANNONCES)\s*$', re.UNICODE)
    CONTENT_DIR = "content_files"
    
    def __init__(self, raw_email_body: str, content_directory: str = None):
        self.raw_email_body = raw_email_body
        self.content_dir = content_directory or self.CONTENT_DIR
        
        # Create organized content directory for JORF
        self.jorf_dir = os.path.join(self.content_dir, "jorf")
        os.makedirs(self.jorf_dir, exist_ok=True)
    
    def parse(self) -> List[Dict]:
        """Parse email and return list of documents"""
        logger.info("Starting JORF email parsing...")
        cleaned_body = re.sub(r'[\t ]+', ' ', self.raw_email_body)
        documents = self._parse_content(cleaned_body)
        logger.info(f"Found {len(documents)} JORF documents")
        return documents
    
    def _determine_typology(self, full_text: str) -> str:
        """Determine document typology"""
        for typo in [JORFTypology.DECRET, JORFTypology.ARRETE, JORFTypology.DECISION, JORFTypology.AVIS]:
            if typo.value in full_text:
                return typo.value
        
        if "Demandes de changement de nom" in full_text:
            return JORFTypology.ANNONCE.value
        if any(x in full_text for x in ["Commissions et organes", "Documents et publications", "Informations diverses"]):
            return JORFTypology.INFORMATION.value
        if "Avis relatif à" in full_text or "Avis de" in full_text:
            return JORFTypology.COMMUNICATION.value
        
        return JORFTypology.AUTRE.value
    
    def _save_content_to_file(self, doc_id: str, content: str) -> str:
        """
        Save document content to a text file and return the relative path.
        
        Args:
            doc_id: Document identifier
            content: Document content to save
            
        Returns:
            Relative path to the saved file
        """
        # Clean doc_id for safe filename
        safe_id = re.sub(r'[^\w\-_\.]', '_', doc_id)
        filename = f"{safe_id}.txt"
        filepath = os.path.join(self.jorf_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.debug(f"Content saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving content to file {filepath}: {e}")
            return None
    
    def _scrape_article_content(self, doc_id: str, url: str) -> str:
        """
        Scrape article content from URL and save to file.
        
        Args:
            doc_id: Document identifier
            url: URL to scrape
            
        Returns:
            Relative path to the saved content file
        """
        logger.info(f"Scraping content for: {url}")
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            content_div = soup.find('div', class_='page-content')
            
            if content_div:
                content = content_div.get_text(separator='\n\n', strip=True)
                # Save to file and return path
                return self._save_content_to_file(doc_id, content)
            else:
                error_msg = "Contenu non trouvé"
                return self._save_content_to_file(doc_id, error_msg)
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            error_msg = f"Erreur: {e}"
            return self._save_content_to_file(doc_id, error_msg)
    
    def _parse_content(self, cleaned_body: str) -> List[Dict]:
        """Parse email content line by line"""
        documents = []
        lignes = cleaned_body.split('\n')
        
        current_ministere = None
        current_rubrique = None
        
        start_index = -1
        for i, ligne in enumerate(lignes):
            if "JOURNAL OFFICIEL" in ligne and "LOIS ET DECRETS" in ligne:
                start_index = i
                break
        
        if start_index == -1:
            logger.error("Cannot find JORF content start")
            return []
        
        for i in range(start_index, len(lignes)):
            ligne = lignes[i].strip()
            
            # Detect rubrique
            if any(r in ligne for r in ["DECRETS, ARRETES, CIRCULAIRES", "MESURES NOMINATIVES", "CONVENTIONS COLLECTIVES", "AVIS ET COMMUNICATIONS", "ANNONCES"]):
                current_rubrique = ligne.split(',')[0].strip()
                current_ministere = None
                continue
            
            # Detect ministère
            match_ministere = self.MINISTERE_PATTERN.search(ligne)
            match_rubrique_ministere = self.RUBRIQUE_PATTERN.search(ligne)
            
            if match_ministere:
                current_ministere = match_ministere.group(1).strip()
                continue
            elif match_rubrique_ministere:
                current_ministere = match_rubrique_ministere.group(1).strip()
                continue
            
            # Detect acte
            match_acte = self.ACTE_PATTERN.search(ligne)
            if match_acte and i + 1 < len(lignes):
                ligne_lien = lignes[i + 1].strip()
                match_lien = self.LINK_PATTERN.search(ligne_lien)
                
                if match_lien:
                    numero_acte = match_acte.group(1).strip()
                    titre_complet = match_acte.group(2).strip()
                    url = match_lien.group(1).strip()
                    
                    typologie = self._determine_typology(titre_complet)
                    ministre = current_ministere if current_ministere else current_rubrique
                    
                    # Scrape content and save to file
                    content_path = self._scrape_article_content(numero_acte, url)
                    time.sleep(1) 
                    
                    document = {
                        'id': numero_acte,
                        'source': 'JORF',
                        'date': datetime.now(),
                        'url': url,
                        'typologie': typologie,
                        'ministre': ministre if ministre else JORFTypology.AUTRE.value,
                        'titre': titre_complet,
                        'abstract': titre_complet,
                        'content': content_path,
                        'language': 'fr'  # JORF is always in French
                    }
                    documents.append(document)
        
        return documents