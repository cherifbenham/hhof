"""
Inference Only Script - Read from CSV and perform LLM inference without saving
File: inference_only.py

Usage:
  python inference_only.py <document_id>
  python inference_only.py 9
"""

import sys
import logging
from csv_repository import CSVDocumentRepository
from llm_service import create_llm_service_from_env
from llm_processor import LLMProcessor
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_inference_only(document_id: str):
    """
    Run LLM inference on a document without saving results
    
    Args:
        document_id: ID of the document to process
    """
    logger.info(f"{'='*80}")
    logger.info(f"🔍 INFERENCE ONLY MODE - Document ID: {document_id}")
    logger.info(f"{'='*80}\n")
    
    # Initialize repository (read-only)
    repo = CSVDocumentRepository(csv_file="legal_documents.csv")
    
    try:
        # Get document
        logger.info(f"📄 Loading document {document_id}...")
        doc = repo.get_by_id(document_id)
        
        if not doc:
            logger.error(f"❌ Document {document_id} not found in CSV")
            return
        
        logger.info(f"✅ Document loaded successfully\n")
        
        # Display document info
        print(f"{'─'*80}")
        print(f"📋 DOCUMENT INFORMATION")
        print(f"{'─'*80}")
        print(f"ID:          {doc.get('id')}")
        print(f"Source:      {doc.get('source')}")
        print(f"Date:        {doc.get('date')}")
        print(f"Typologie:   {doc.get('typologie', 'N/A')}")
        print(f"Ministre:    {doc.get('ministre', 'N/A')}")
        print(f"Language:    {doc.get('language', 'N/A')}")
        print(f"Status:      {doc.get('processing_status', 'N/A')}")
        print(f"\nTitre:       {doc.get('titre', 'N/A')[:100]}...")
        print(f"\nURL:         {doc.get('url', 'N/A')}")
        print(f"{'─'*80}\n")
        
        # Get content from file
        content_path = doc.get('content')
        if not content_path:
            logger.error(f"❌ No content path for document {document_id}")
            return
        
        logger.info(f"📂 Reading content from: {content_path}")
        content = repo.read_content_from_file(content_path)
        
        if not content:
            logger.error(f"❌ Could not read content file")
            return
        
        logger.info(f"✅ Content loaded: {len(content)} characters\n")
        
        # Initialize LLM service and processor
        logger.info("🤖 Initializing LLM service...")
        llm_service = create_llm_service_from_env()
        processor = LLMProcessor(llm_service, repo)
        logger.info("✅ LLM service ready\n")
        
        # ===== GENERATE SUMMARY =====
        logger.info(f"{'='*80}")
        logger.info("📝 GENERATING HIERARCHICAL SUMMARY...")
        logger.info(f"{'='*80}\n")
        
        summary = processor._generate_hierarchical_summary(content, doc)
        
        print(f"\n{'='*80}")
        print(f"📝 GENERATED SUMMARY")
        print(f"{'='*80}\n")
        print(summary)
        print(f"\n{'─'*80}")
        print(f"Summary length: {len(summary)} characters")
        print(f"{'─'*80}\n")
        
        # ===== CLASSIFY APPLICABILITY =====
        logger.info(f"{'='*80}")
        logger.info("⚖️  CLASSIFYING APPLICABILITY...")
        logger.info(f"{'='*80}\n")
        
        applicability = processor._classify_applicability(content, doc)
        
        print(f"\n{'='*80}")
        print(f"⚖️  APPLICABILITY CLASSIFICATION")
        print(f"{'='*80}\n")
        
        emoji = "📘" if applicability == "information" else "⚖️" if applicability == "obligation" else "⚖️"
        print(f"{emoji} Classification: {applicability.upper()}\n")
        
        category_details = {
            "information": "Document informatif sans force contraignante (directive, circulaire, avis, rapport, etc.)",
            "obligation": "Texte juridiquement contraignant créant des obligations (loi, règlement, décret, arrêté, convention)",
            "jurisprudence": "Décision de justice ou interprétation judiciaire (arrêt, décision de cours)"
        }
        
        print(f"Description: {category_details.get(applicability, 'N/A')}")
        print(f"{'─'*80}\n")
        
        # ===== SUMMARY =====
        logger.info(f"{'='*80}")
        logger.info("✅ INFERENCE COMPLETE (NOT SAVED)")
        logger.info(f"{'='*80}\n")
        
        print(f"\n{'='*80}")
        print(f"✅ INFERENCE RESULTS (NOT SAVED TO CSV)")
        print(f"{'='*80}")
        print(f"Document ID:     {document_id}")
        print(f"Applicability:   {applicability}")
        print(f"Summary length:  {len(summary)} chars")
        print(f"{'='*80}\n")
        
        # Ask if user wants to save
        print("💡 This was an inference-only operation. Results were NOT saved to CSV.")
        print("   To save results, use: python main.py --process")
        
    except Exception as e:
        logger.error(f"❌ Error during inference: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        repo.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("""
╔════════════════════════════════════════════════════════════════════════════╗
║                          INFERENCE ONLY SCRIPT                             ║
╚════════════════════════════════════════════════════════════════════════════╝

Run LLM inference on a document WITHOUT saving results to CSV.

Usage:
  python inference_only.py <document_id>

Examples:
  python inference_only.py 9
  python inference_only.py JORFTEXT000012345678
  python inference_only.py 32024R0001

What this script does:
  ✅ Reads document from CSV by ID
  ✅ Generates hierarchical summary
  ✅ Classifies applicability (information/obligation/jurisprudence)
  ❌ Does NOT save results to CSV

To save results permanently:
  python main.py --process <batch_size>

Available document IDs (first 10):
""")
        
        # Show available document IDs
        try:
            repo = CSVDocumentRepository(csv_file="legal_documents.csv")
            docs = repo.get_all(limit=10)
            print("  Document IDs:")
            for doc in docs:
                status = "✅" if doc.get('processing_status') == 'processed' else "⏳"
                print(f"    {status} {doc.get('id')} - {doc.get('titre', 'N/A')[:50]}...")
            print("\n  Use: python inference_only.py <ID>")
            repo.close()
        except Exception as e:
            print(f"  Error reading CSV: {e}")
        
        sys.exit(1)
    
    document_id = sys.argv[1]
    run_inference_only(document_id)