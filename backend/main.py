"""
Main Scheduler for Legal Documents Scraping System (CSV VERSION)
File: main.py

Updated to include LLM processing pipeline.
"""

import logging
import schedule
import time
import os
import sys
import json
from datetime import datetime, date
from dotenv import load_dotenv
from typing import Optional, Dict, List

# Load environment variables from .env file
load_dotenv()

# Import from modular files
from csv_repository import CSVDocumentRepository
from eurlex_scraper import EURLexScraper
from jorf_scraper import JORFEmailParser
from document_types import Series
from llm_service import LLMService, create_llm_service_from_env
from llm_processor import LLMProcessor

# Define the global date format constant
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# UTILS (JSONL Export)
# ============================================================================

def export_to_jsonl(data: List[Dict], filename_suffix: str):
    """Exporte les données scrapées brutes vers un fichier JSONL pour vérification."""
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"scraped_data_{filename_suffix}_{timestamp}.jsonl" 
    
    def serialize_doc(doc):
        serialized = {}
        for k, v in doc.items():
            if isinstance(v, (datetime, date)):
                serialized[k] = v.isoformat() 
            else:
                serialized[k] = v
        return serialized

    serializable_data = [serialize_doc(doc) for doc in data]

    try:
        with open(filename, 'w', encoding='utf-8') as f: 
            for doc in serializable_data:
                f.write(json.dumps(doc, ensure_ascii=False) + '\n') 
        logger.info(f"✅ Export JSONL de {len(data)} documents réussi : {filename}")
    except Exception as e:
        logger.error(f"❌ Échec de l'export JSONL vers {filename}: {e}")


# ============================================================================
# LLM Configuration
# ============================================================================

def create_llm_processor() -> Optional[LLMProcessor]:
    """
    Create and configure LLM processor from environment variables
    
    Returns:
        Configured LLMProcessor or None if LLM is disabled
    """
    # Check if LLM processing is enabled
    llm_enabled = os.getenv("LLM_ENABLED", "true").lower() == "true"
    
    if not llm_enabled:
        logger.info("LLM processing is disabled (LLM_ENABLED=false)")
        return None
    
    try:
        # Create LLM service from environment
        llm_service = create_llm_service_from_env()
        
        # Create repository
        repo = CSVDocumentRepository(csv_file="legal_documents.csv")
        
        # Create processor
        processor = LLMProcessor(
            llm_service=llm_service,
            repository=repo
        )
        
        logger.info("✅ LLM Processor initialized successfully")
        return processor
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize LLM processor: {e}")
        logger.error("LLM processing will be disabled")
        return None


# ============================================================================
# Scraping Jobs
# ============================================================================

def _run_scraper_job(series: Series, scrape_details: bool, source_name: str):
    """Internal function to run scraping for a specific series/source."""
    logger.info("="*60)
    logger.info(f"Starting {source_name} scraping job")
    logger.info("="*60)
    
    repo = CSVDocumentRepository(csv_file="legal_documents.csv")
    scraper = EURLexScraper()
    
    try:
        documents = scraper.scrape_daily_view(series=series, scrape_details=scrape_details)
        
        if documents:
            suffix = source_name.replace(" ", "_").lower()
            export_to_jsonl(documents, suffix) 
            
        created, skipped = repo.bulk_create(documents)
        logger.info(f"{source_name}: {created} created, {skipped} skipped")
        
        # Return number of created documents for potential LLM processing trigger
        return created
        
    except Exception as e:
        logger.error(f"Error in {source_name} job: {e}")
        return 0
    finally:
        scraper.close()
        repo.close()


def scrape_eurlex_l_series():
    """Job: Scrape EUR-LEX L-Series (with full content)"""
    created = _run_scraper_job(Series.L, scrape_details=True, source_name="EUR-LEX L-Series")
    
    # Optionally trigger LLM processing if new documents were created
    if created > 0 and os.getenv("AUTO_PROCESS_AFTER_SCRAPE", "false").lower() == "true":
        logger.info(f"Auto-processing triggered: {created} new documents")
        process_pending_documents(batch_size=created)


def scrape_eurlex_c_series():
    """Job: Scrape EUR-LEX C-Series (with full content)"""
    created = _run_scraper_job(Series.C, scrape_details=True, source_name="EUR-LEX C-Series")
    
    # Optionally trigger LLM processing if new documents were created
    if created > 0 and os.getenv("AUTO_PROCESS_AFTER_SCRAPE", "false").lower() == "true":
        logger.info(f"Auto-processing triggered: {created} new documents")
        process_pending_documents(batch_size=created)


def scrape_jorf_from_email(email_body: str):
    """Job: Parse JORF email and scrape documents"""
    logger.info("="*60)
    logger.info("Starting JORF email parsing job")
    logger.info("="*60)
    
    repo = CSVDocumentRepository(csv_file="legal_documents.csv")
    
    try:
        parser = JORFEmailParser(email_body)
        documents = parser.parse()
        
        if documents:
            export_to_jsonl(documents, "jorf") 

        created, skipped = repo.bulk_create(documents)
        logger.info(f"JORF: {created} created, {skipped} skipped")
        
        # Optionally trigger LLM processing if new documents were created
        if created > 0 and os.getenv("AUTO_PROCESS_AFTER_SCRAPE", "false").lower() == "true":
            logger.info(f"Auto-processing triggered: {created} new documents")
            process_pending_documents(batch_size=created)
            
        return created
        
    except Exception as e:
        logger.error(f"Error in JORF parsing job: {e}")
        return 0
    finally:
        repo.close()


# ============================================================================
# LLM Processing Job
# ============================================================================

def process_pending_documents(batch_size: int = 10):
    """
    Job: Process pending documents with LLM
    
    Args:
        batch_size: Number of documents to process in this batch
    """
    logger.info("="*60)
    logger.info(f"Starting LLM processing job (batch size: {batch_size})")
    logger.info("="*60)
    
    # Create LLM processor
    processor = create_llm_processor()
    
    if processor is None:
        logger.warning("⚠️ LLM processing is disabled or failed to initialize")
        return
    
    try:
        # Process batch
        stats = processor.process_batch(batch_size=batch_size)
        
        logger.info("="*60)
        logger.info("LLM Processing Results:")
        logger.info(f"  ✅ Processed: {stats['processed']}")
        logger.info(f"  ❌ Failed: {stats['failed']}")
        logger.info(f"  ⏭️  Skipped: {stats['skipped']}")
        logger.info("="*60)
        
    except Exception as e:
        logger.error(f"❌ Error in LLM processing job: {e}")
    finally:
        # Close repository
        processor.repo.close()


# ============================================================================
# Statistics Job
# ============================================================================

def print_statistics():
    """Job: Print CSV statistics"""
    logger.info("="*60)
    logger.info("CSV File Statistics")
    logger.info("="*60)
    
    repo = CSVDocumentRepository(csv_file="legal_documents.csv")
    
    try:
        eurlex_count = repo.count_by_source('EURLEX')
        jorf_count = repo.count_by_source('JORF')
        
        # Get all documents to count by processing status
        all_docs = repo.get_all(skip=0, limit=100000)
        pending = sum(1 for doc in all_docs if doc.get('processing_status') == 'pending')
        processed = sum(1 for doc in all_docs if doc.get('processing_status') == 'processed')
        error = sum(1 for doc in all_docs if doc.get('processing_status') == 'error')
        
        logger.info(f"EUR-LEX documents: {eurlex_count}")
        logger.info(f"JORF documents: {jorf_count}")
        logger.info(f"Total documents: {eurlex_count + jorf_count}")
        logger.info(f"")
        logger.info(f"Processing Status:")
        logger.info(f"  ⏳ Pending: {pending}")
        logger.info(f"  ✅ Processed: {processed}")
        logger.info(f"  ❌ Error: {error}")
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
    finally:
        repo.close()


# ============================================================================
# Scheduler Setup
# ============================================================================

def setup_scheduler():
    """Configure scheduled jobs"""
    
    # EUR-LEX scrapers - run daily at specific times
    schedule.every().day.at("09:00").do(scrape_eurlex_l_series)
    schedule.every().day.at("09:30").do(scrape_eurlex_c_series)
    
    # LLM processing - run every 2 hours if enabled
    llm_enabled = os.getenv("LLM_ENABLED", "true").lower() == "true"
    if llm_enabled:
        batch_size = int(os.getenv("LLM_BATCH_SIZE", "10"))
        schedule.every(2).hours.do(lambda: process_pending_documents(batch_size=batch_size))
        logger.info(f"✅ LLM processing scheduled (every 2 hours, batch size: {batch_size})")
    else:
        logger.info("⚠️ LLM processing is disabled")
    
    # Statistics - run every 6 hours
    schedule.every(6).hours.do(print_statistics)
    
    logger.info("Scheduler configured successfully")


def run_scheduler():
    """Run the scheduler indefinitely"""
    logger.info("Starting scheduler...")
    setup_scheduler()
    
    # Run statistics immediately on startup
    print_statistics()
    
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            logger.error(f"Error running scheduled jobs: {e}")
        time.sleep(60)


# ============================================================================
# Manual Testing Functions
# ============================================================================

def run_once_now():
    """Run all scrapers once immediately (for testing)"""
    logger.info("Running all scrapers once for testing...")
    
    scrape_eurlex_l_series()
    scrape_eurlex_c_series()
    
    print_statistics()


def run_llm_processing_test(batch_size: int = 5):
    """Run LLM processing once immediately (for testing)"""
    logger.info(f"Running LLM processing test (batch size: {batch_size})...")
    
    process_pending_documents(batch_size=batch_size)
    print_statistics()


def run_jorf_once(filename: str = "jorf.txt"):
    """Run JORF email parser once immediately (for testing)"""
    logger.info("="*60)
    logger.info(f"Starting JORF scraping from file: {filename}")
    logger.info("="*60)
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            email_content = f.read()
        
        scrape_jorf_from_email(email_content)
        
    except FileNotFoundError:
        logger.error(f"❌ Le fichier {filename} n'a pas été trouvé. Assurez-vous qu'il existe.")
    except Exception as e:
        logger.error(f"❌ Erreur lors du traitement du fichier JORF: {e}")


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    
    # Initialize CSV file on first run
    logger.info("Initializing CSV repository...")
    repo = CSVDocumentRepository(csv_file="legal_documents.csv")
    repo.close()
    logger.info("CSV repository initialized successfully")
    
    # Display LLM configuration
    llm_enabled = os.getenv("LLM_ENABLED", "true").lower() == "true"
    logger.info(f"LLM Processing: {'✅ ENABLED' if llm_enabled else '⚠️ DISABLED'}")
    if llm_enabled:
        provider = os.getenv("LLM_PROVIDER", "openai")
        logger.info(f"LLM Provider: {provider.upper()}")
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--test":
            logger.info("Running in TEST mode (scrapers only)")
            run_once_now()
            
        elif sys.argv[1] == "--jorf": 
            logger.info("Running in JORF mode")
            filename = sys.argv[2] if len(sys.argv) > 2 else "jorf.txt"
            run_jorf_once(filename)
            print_statistics()
            
        elif sys.argv[1] == "--process":
            logger.info("Running in LLM PROCESSING mode")
            batch_size = int(sys.argv[2]) if len(sys.argv) > 2 else 5
            run_llm_processing_test(batch_size=batch_size)
            
        elif sys.argv[1] == "--full-test":
            logger.info("Running FULL TEST mode (scraping + LLM processing)")
            run_once_now()
            time.sleep(2)
            run_llm_processing_test(batch_size=5)
            
        else:
            logger.error(f"Unknown argument: {sys.argv[1]}")
            logger.info("Usage: python main.py [--test|--jorf [filename]|--process [batch_size]|--full-test]")
            
    else:
        logger.info("Running in SCHEDULER mode")
        logger.info("Press Ctrl+C to stop")
        try:
            run_scheduler()
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")