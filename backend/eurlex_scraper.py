"""
EUR-Lex Scraper
File: eurlex_scraper.py

Scraper for EUR-Lex Official Journal documents with content stored in separate text files.
Version française avec filtrage des documents non pertinents.
Supporte le scraping par date spécifique ou intervalle de dates.
"""

import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Union
import logging
import re
import time
import os
from urllib.parse import urljoin
from document_types import Series, EURLEXTypology

logger = logging.getLogger(__name__)


class EURLexScraper:
    """EUR-Lex scraper with external content storage and date range support"""
    
    BASE_URL = "https://eur-lex.europa.eu"
    DAILY_VIEW_L_URL = f"{BASE_URL}/oj/daily-view/L-series/default.html?locale=fr"
    DAILY_VIEW_C_URL = f"{BASE_URL}/oj/daily-view/C-series/default.html?locale=fr"
    CONTENT_DIR = "content_files"
    
    def __init__(self, content_directory: str = None):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.content_dir = content_directory or self.CONTENT_DIR
        
        # Create organized content directories
        self.eurlex_l_dir = os.path.join(self.content_dir, "eurlex", "eurlex_l")
        self.eurlex_c_dir = os.path.join(self.content_dir, "eurlex", "eurlex_c")
        
        os.makedirs(self.eurlex_l_dir, exist_ok=True)
        os.makedirs(self.eurlex_c_dir, exist_ok=True)
    
    def scrape_daily_view(
        self, 
        series: Series = Series.L, 
        scrape_details: bool = True,
        target_date: Optional[Union[str, datetime]] = None
    ) -> List[Dict]:
        """
        Scrape documents for a specific date for a specified Official Journal Series (L or C).
        
        Args:
            series: Series L (Legislation) or C (Information and Notices)
            scrape_details: Whether to scrape full document content
            target_date: Date to scrape (str 'YYYY-MM-DD' or datetime). Defaults to today.
        
        Returns:
            List of document dictionaries
        """
        # Parse target date
        if target_date is None:
            date_obj = datetime.now()
        elif isinstance(target_date, str):
            try:
                date_obj = datetime.strptime(target_date, '%Y-%m-%d')
            except ValueError:
                logger.error(f"Invalid date format: {target_date}. Use YYYY-MM-DD")
                return []
        else:
            date_obj = target_date
        
        date_str = date_obj.strftime("%d%m%Y")
        params = {
            'ojDate': date_str, 
            'sortCriterion': 'BY_CATEGORY', 
            'orderCriterion': 'ASCENDING', 
            'locale': 'fr'
        }
        
        url = self.DAILY_VIEW_L_URL if series == Series.L else self.DAILY_VIEW_C_URL
        logger.info(f"Scraping EUR-Lex {series.value}-Series (version française) pour {date_obj.strftime('%d/%m/%Y')}")
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            documents = self._parse_daily_view(soup, date_obj, scrape_details, series)
            logger.info(f"Found {len(documents)} documents in {series.value}-Series for {date_obj.strftime('%d/%m/%Y')}")
            return documents
        except Exception as e:
            logger.error(f"Error scraping {series.value}-Series for {date_obj.strftime('%d/%m/%Y')}: {e}")
            return []
    
    def scrape_date_range(
        self,
        series: Series = Series.L,
        scrape_details: bool = True,
        date_from: Optional[Union[str, datetime]] = None,
        date_to: Optional[Union[str, datetime]] = None
    ) -> List[Dict]:
        """
        Scrape documents for a date range.
        
        Args:
            series: Series L (Legislation) or C (Information and Notices)
            scrape_details: Whether to scrape full document content
            date_from: Start date (str 'YYYY-MM-DD' or datetime). Defaults to today.
            date_to: End date (str 'YYYY-MM-DD' or datetime). Defaults to date_from.
        
        Returns:
            List of all document dictionaries from the date range
        """
        # Parse dates
        if date_from is None:
            start_date = datetime.now()
        elif isinstance(date_from, str):
            try:
                start_date = datetime.strptime(date_from, '%Y-%m-%d')
            except ValueError:
                logger.error(f"Invalid date_from format: {date_from}. Use YYYY-MM-DD")
                return []
        else:
            start_date = date_from
        
        if date_to is None:
            end_date = start_date
        elif isinstance(date_to, str):
            try:
                end_date = datetime.strptime(date_to, '%Y-%m-%d')
            except ValueError:
                logger.error(f"Invalid date_to format: {date_to}. Use YYYY-MM-DD")
                return []
        else:
            end_date = date_to
        
        # Ensure start <= end
        if start_date > end_date:
            start_date, end_date = end_date, start_date
        
        # Calculate number of days
        delta = (end_date - start_date).days + 1
        logger.info(f"Scraping EUR-Lex {series.value}-Series from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({delta} days)")
        
        all_documents = []
        current_date = start_date
        
        while current_date <= end_date:
            documents = self.scrape_daily_view(
                series=series,
                scrape_details=scrape_details,
                target_date=current_date
            )
            all_documents.extend(documents)
            
            # Wait between days to be respectful
            if current_date < end_date:
                time.sleep(2)
            
            current_date += timedelta(days=1)
        
        logger.info(f"Total: {len(all_documents)} documents scraped for {delta} days")
        return all_documents
    
    def _parse_daily_view(self, soup: BeautifulSoup, date: datetime, scrape_details: bool, series: Series) -> List[Dict]:
        """Parse the daily view page"""
        documents = []
        seen_ids = set() 
        panels = soup.find_all('div', class_='panel panel-default panelOjAba')
        
        for panel in panels:
            typologie = self._extract_typologie(panel)
            doc_containers = panel.find_all('div', class_='container')
            
            for container in doc_containers:
                if not isinstance(container, (Tag, NavigableString)):
                    continue 
                
                try: 
                    doc_data = self._extract_document_info(container, date, typologie)
                    if doc_data:
                        if doc_data['id'] in seen_ids:
                            continue
                        
                        seen_ids.add(doc_data['id'])
                        
                        if scrape_details and doc_data.get('url'):
                            details = self._scrape_document_details(doc_data['id'], doc_data['url'], series) 
                            doc_data.update(details)
                            time.sleep(1)
                        documents.append(doc_data)
                    
                except Exception as e:
                    logger.error(f"Failed to process document container {container.get_text(strip=True)[:50]}... Error: {e}")
                    continue
        
        return documents
    
    def _extract_typologie(self, panel) -> str:
        """Extract document typology from panel"""
        heading = panel.find('div', class_='panel-heading')
        if heading:
            button = heading.find('button')
            if button:
                text = button.get_text(strip=True)
                for typo in EURLEXTypology:
                    if typo.value in text:
                        return typo.value
        return None
    
    def _extract_document_info(self, container, date: datetime, typologie: str) -> Dict:
        """Extract basic document information"""
        try:
            row = container.find('div', class_='row daily-view-row-spacing')
            if not row: return None
            
            doc_id_div = row.find('div', class_='col-md-2')
            if not doc_id_div: return None
            doc_id = doc_id_div.get_text(strip=True)
            
            link_div = row.find('div', class_='col-md-7')
            if not link_div: return None
            link = link_div.find('a')
            if not link: return None
            
            titre = link.get_text(strip=True)
            relative_url = link.get('href', '')
            if not relative_url: return None
            
            # FILTRAGE : Si le titre indique que le document ne concerne pas la version française
            if "rectificatif ne concerne pas la version française" in titre.lower():
                logger.info(f"Document {doc_id} ignoré : ne concerne pas la version française")
                return None
            
            # Ajouter locale=fr à l'URL
            url = urljoin(self.BASE_URL, relative_url)
            if '?' in url:
                url += '&locale=fr'
            else:
                url += '?locale=fr'
            
            language = "fr"
            
            return {
                'id': doc_id,
                'source': 'EURLEX',
                'date': date,
                'url': url,
                'typologie': typologie,
                'ministre': None,
                'titre': titre,
                'abstract': None,
                'content': None,
                'language': language
            }
        except Exception as e:
            logger.error(f"Error extracting document info: {e}")
            return None
    
    def _save_content_to_file(self, doc_id: str, content: str, series: Series) -> str:
        """Save document content to a text file and return the relative path."""
        safe_id = re.sub(r'[^\w\-_\.]', '_', doc_id)
        filename = f"{safe_id}.txt"
        
        target_dir = self.eurlex_l_dir if series == Series.L else self.eurlex_c_dir
        filepath = os.path.join(target_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            logger.debug(f"Content saved to {filepath}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving content to file {filepath}: {e}")
            return None
    
    def _scrape_document_details(self, doc_id: str, url: str, series: Series) -> Dict: 
        """Scrape and clean content, store in external file."""
        soup = None
        abstract = None
        raw_content = ""

        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
        except requests.exceptions.RequestException as e:
            logger.error(f"HTTP/Connection Error scraping details from {url}: {e}")
            return {'abstract': None, 'content': None}
        except Exception as e:
            logger.error(f"General Error scraping details from {url}: {e}")
            return {'abstract': None, 'content': None}

        # Extract Abstract
        abstract_div = soup.find('div', class_='abstract')
        if abstract_div:
            abstract = abstract_div.get_text(separator=' ', strip=True)

        # Extract Content
        content_div = soup.find('div', {'id': 'PP4Contents'})
        
        if not content_div:
            return {'abstract': abstract, 'content': None}

        # Pre-cleaning: Inject paragraph markers
        paragraph_tags = ['p', 'div', 'h1', 'h2', 'h3', 'h4']
        
        for tag_name in paragraph_tags:
            for tag in content_div.find_all(tag_name):
                tag.append('\n\n') 

        for tag in content_div.find_all(['sup', 'a']):
            tag.decompose()
        
        raw_content = content_div.get_text(separator='\n', strip=True)

        # POST-EXTRACTION CLEANING
        cleaned_content = re.sub(r'\s+', ' ', raw_content).strip()
        
        PHRASE_DEBUT = r'(DÉCISION D\'EXÉCUTION DE LA COMMISSION|LA COMMISSION EUROPÉENNE,|LE CONSEIL DE L\'UNION EUROPÉENNE,|A ADOPTÉ LA PRÉSENTE DÉCISION:|A ADOPTÉ LE PRÉSENT RÈGLEMENT:)'
        match_start = re.search(PHRASE_DEBUT, cleaned_content, re.IGNORECASE)

        if match_start:
            cleaned_content = cleaned_content[match_start.start():].strip()
        
        def glue_article_points(match):
            article_part = match.group(1)
            point_part = match.group(0).split(article_part)[1].replace(' ', '')
            return article_part + point_part
            
        cleaned_content = re.sub(r'(Article \d+)\s*\((?:\d+|[a-z])\)', glue_article_points, cleaned_content)
        cleaned_content = re.sub(r'\(\s*(\d+)\s*\)', r'(\1)', cleaned_content)
        cleaned_content = re.sub(r'([A-Z]{2,4})\s*\((.*?)\)', r'\1(\2)', cleaned_content)
        
        keywords_to_break_before = [
            'LE CONSEIL DE L\'UNION EUROPÉENNE,',
            'LA COMMISSION EUROPÉENNE,',
            'vu le traité sur le fonctionnement de l\'Union européenne,', 
            'considérant ce qui suit:',
            'A ADOPTÉ LA PRÉSENTE DÉCISION:',
            'A ADOPTÉ LE PRÉSENT RÈGLEMENT:',
            r'Article \d+', 
            'ANNEXE', 
            'DOCUMENT DE PROJET',
        ]
        
        for keyword in keywords_to_break_before:
            cleaned_content = re.sub(rf'\s*({keyword})', r'\n\n\1', cleaned_content, flags=re.IGNORECASE)

        cleaned_content = re.sub(r'(?<!\n\n)\s*\((\d+|[a-z])\)', r'\n\n(\1)', cleaned_content)
        cleaned_content = re.sub(r'(?<!\n\n)\s*—\s*', r'\n\n— ', cleaned_content)

        content = re.sub(r'(\n\s*){2,}', '\n\n', cleaned_content).strip()
        
        content_path = self._save_content_to_file(doc_id, content, series)
            
        return {'abstract': abstract, 'content': content_path}
        
    def close(self):
        """Close the session"""
        self.session.close()