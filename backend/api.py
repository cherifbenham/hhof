"""
FastAPI for Legal Documents Scraping System
File: api.py

REST API endpoints for EUR-LEX and JORF scraping, document retrieval, and LLM processing.
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.responses import JSONResponse, StreamingResponse  # <-- Added StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
import csv 
from io import StringIO  # <-- Added StringIO
import json
import asyncio

# Import from existing modules
from csv_repository import CSVDocumentRepository
from eurlex_scraper import EURLexScraper
from jorf_scraper import JORFEmailParser
from document_types import Series
from llm_processor import LLMProcessor
from llm_service import create_llm_service_from_env

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('api.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Legal Documents Scraping API",
    description="API for scraping EUR-LEX and JORF documents with LLM processing",
    version="1.0.0"
)


class DateRangeScrapingStatus(BaseModel):
    """Response model for date range scraping operations"""
    status: str
    message: str
    date_from: str
    date_to: str
    days_scraped: int = 0
    documents_found: int = 0
    documents_created: int = 0
    documents_skipped: int = 0


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite default
        "http://localhost:5174",  # Vite alt/preview
        "http://localhost:3000",  # Create React App default
        "http://localhost:8080",  # Alternative port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Static frontend build (optional)
BASE_DIR = Path(__file__).resolve().parent
FRONTEND_DIST = BASE_DIR.parent / "frontend" / "dist"

if FRONTEND_DIST.exists():
    app.mount("/app", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
    logger.info(f"Serving built frontend from {FRONTEND_DIST}")
else:
    logger.info(f"No built frontend found at {FRONTEND_DIST}. Run `npm run build` in frontend to enable static hosting.")


# ============================================================================
# Models
# ============================================================================

class SeriesEnum(str, Enum):
    """EUR-LEX Official Journal Series"""
    L = "L"
    C = "C"


class ScrapingStatus(BaseModel):
    """Response model for scraping operations"""
    status: str
    message: str
    documents_found: int = 0
    documents_created: int = 0
    documents_skipped: int = 0
    task_id: Optional[str] = None


class JORFEmailRequest(BaseModel):
    """Request model for JORF email parsing"""
    email_body: str = Field(..., description="Full JORF email content")


class ProcessingStatus(BaseModel):
    """Response model for LLM processing operations"""
    status: str
    message: str
    processed: int = 0
    failed: int = 0
    skipped: int = 0


class DocumentFilter(BaseModel):
    """Query parameters for document filtering"""
    source: Optional[str] = None
    typologie: Optional[str] = None
    language: Optional[str] = None
    processing_status: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None


class SelectedDocumentsRequest(BaseModel):
    """Request model for exporting a specific list of documents"""
    document_ids: List[str] = Field(..., description="List of document IDs to export")

class DeleteDocumentsRequest(BaseModel):
    """Request model for deleting documents"""
    document_ids: List[str] = Field(..., description="List of document IDs to delete")


# ============================================================================
# Helper Functions
# ============================================================================

def get_repository():
    """Get CSV repository instance"""
    return CSVDocumentRepository(csv_file="legal_documents.csv")


def create_llm_processor_instance() -> Optional[LLMProcessor]:
    """Create LLM processor instance"""
    llm_enabled = os.getenv("LLM_ENABLED", "true").lower() == "true"
    
    if not llm_enabled:
        logger.warning("LLM processing is disabled")
        return None
    
    try:
        llm_service = create_llm_service_from_env()
        repo = get_repository()
        processor = LLMProcessor(llm_service=llm_service, repository=repo)
        return processor
    except Exception as e:
        logger.error(f"Failed to create LLM processor: {e}")
        return None


def filter_documents(documents: List[Dict], filters: DocumentFilter) -> List[Dict]:
    """Apply filters to document list"""
    filtered = documents
    
    if filters.source:
        filtered = [d for d in filtered if d.get('source') == filters.source]
    
    if filters.typologie:
        filtered = [d for d in filtered if d.get('typologie') == filters.typologie]
    
    if filters.language:
        filtered = [d for d in filtered if d.get('language') == filters.language]
    
    if filters.processing_status:
        filtered = [d for d in filtered if d.get('processing_status') == filters.processing_status]
    
    if filters.date_from:
        try:
            date_from = datetime.strptime(filters.date_from, '%Y-%m-%d').date()
            # Ensure the date field exists and is comparable
            filtered = [d for d in filtered if d.get('date') and datetime.strptime(str(d.get('date')), '%Y-%m-%d').date() >= date_from]
        except ValueError:
            pass # Invalid date format in filter
        except TypeError:
            pass # Handle case where date in doc is not a string
    
    if filters.date_to:
        try:
            date_to = datetime.strptime(filters.date_to, '%Y-%m-%d').date()
            # Ensure the date field exists and is comparable
            filtered = [d for d in filtered if d.get('date') and datetime.strptime(str(d.get('date')), '%Y-%m-%d').date() <= date_to]
        except ValueError:
            pass # Invalid date format in filter
        except TypeError:
            pass # Handle case where date in doc is not a string
    
    return filtered


@app.get("/api/config/classification")
def get_classification_config():
    """
    Return default classification config (applicability categories and themes).
    """
    return {
        "applicability_categories": LLMProcessor.APPLICABILITY_CATEGORIES,
        "themes": LLMProcessor.THEMES
    }


def serialize_document(doc: Dict) -> Dict:
    """Convert document to JSON-serializable format"""
    serialized = {}
    for key, value in doc.items():
        if isinstance(value, (datetime)):
            serialized[key] = value.isoformat()
        elif hasattr(value, '__dict__'):
            serialized[key] = str(value)
        else:
            serialized[key] = value
    return serialized


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root():
    """API root endpoint"""
    return {
        "name": "Legal Documents Scraping API",
        "version": "1.0.0",
        "endpoints": {
            "scrape_eurlex": "/api/scrape/eurlex",
            "scrape_jorf": "/api/scrape/jorf",
            "get_documents": "/api/documents",
            "process_documents": "/api/process/llm",
            "export_csv": "/api/documents/export/csv", # <-- Added export endpoint
            "export_selected_csv": "/api/documents/export/selected/csv",
            "stats": "/api/stats",
            "frontend": "/app (served when frontend is built)"
        }
    }




@app.post("/api/scrape/jorf", response_model=ScrapingStatus)
async def scrape_jorf(request: JORFEmailRequest):
    """
    Parse and scrape JORF documents from email content
    
    - **email_body**: Full JORF email notification content
    """
    logger.info("API: Starting JORF email parsing")
    
    try:
        repo = get_repository()
        parser = JORFEmailParser(request.email_body)
        
        # Parse email and scrape documents
        documents = parser.parse()
        
        if not documents:
            return ScrapingStatus(
                status="success",
                message="No JORF documents found in email",
                documents_found=0
            )
        
        # Bulk create documents
        created, skipped = repo.bulk_create(documents)
        
        repo.close()
        
        logger.info(f"JORF: {created} created, {skipped} skipped")
        
        return ScrapingStatus(
            status="success",
            message="JORF email parsing completed",
            documents_found=len(documents),
            documents_created=created,
            documents_skipped=skipped
        )
        
    except Exception as e:
        logger.error(f"Error in JORF parsing: {e}")
        raise HTTPException(status_code=500, detail=f"JORF parsing failed: {str(e)}")


@app.get("/api/documents")
async def get_documents(
    skip: int = Query(0, ge=0, description="Number of documents to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of documents to return"),
    source: Optional[str] = Query(None, description="Filter by source (EURLEX, JORF)"),
    typologie: Optional[str] = Query(None, description="Filter by document type"),
    language: Optional[str] = Query(None, description="Filter by language"),
    processing_status: Optional[str] = Query(None, description="Filter by processing status"),
    date_from: Optional[str] = Query(None, description="Filter by date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (YYYY-MM-DD)")
):
    """
    Get all documents with optional filters and pagination
    
    - **skip**: Pagination offset
    - **limit**: Maximum results (1-1000)
    - **source**: Filter by EURLEX or JORF
    - **typologie**: Filter by document type
    - **language**: Filter by language code
    - **processing_status**: Filter by processing status (pending, processed, error)
    - **date_from**: Filter documents from date (YYYY-MM-DD)
    - **date_to**: Filter documents until date (YYYY-MM-DD)
    """
    try:
        repo = get_repository()
        
        # Get all documents
        documents = repo.get_all(skip=0, limit=10000)  # Get large set for filtering
        
        # Apply filters
        filters = DocumentFilter(
            source=source,
            typologie=typologie,
            language=language,
            processing_status=processing_status,
            date_from=date_from,
            date_to=date_to
        )
        
        filtered_docs = filter_documents(documents, filters)
        
        # Apply pagination
        paginated_docs = filtered_docs[skip:skip + limit]
        
        # Serialize documents
        serialized = [serialize_document(doc) for doc in paginated_docs]
        
        repo.close()
        
        return {
            "total": len(filtered_docs),
            "skip": skip,
            "limit": limit,
            "count": len(serialized),
            "documents": serialized
        }
        
    except Exception as e:
        logger.error(f"Error retrieving documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve documents: {str(e)}")


@app.get("/api/documents/export/xlsx")
async def export_documents_xlsx(
    source: Optional[str] = Query(None, description="Filter by source (EURLEX, JORF)"),
    typologie: Optional[str] = Query(None, description="Filter by document type"),
    language: Optional[str] = Query(None, description="Filter by language"),
    processing_status: Optional[str] = Query(None, description="Filter by processing status"),
    date_from: Optional[str] = Query(None, description="Filter by date from (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Filter by date to (YYYY-MM-DD)")
):
    """
    Export filtered documents to an XLSX file.
    """
    try:
        repo = get_repository()
        
        # Get and filter documents
        documents = repo.get_all(skip=0, limit=100000)
        filters = DocumentFilter(
            source=source, typologie=typologie, language=language,
            processing_status=processing_status, date_from=date_from, date_to=date_to
        )
        filtered_docs = filter_documents(documents, filters)
        
        # Determine fieldnames
        fieldnames = repo.fieldnames
        if not fieldnames and filtered_docs:
            fieldnames = list(filtered_docs[0].keys())
        if not fieldnames:
            fieldnames = ['id', 'source', 'titre', 'date']

        def generate_xlsx():
            """Generate XLSX content in memory."""
            import io
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = "Documents"
            ws.append(fieldnames)

            for doc in filtered_docs:
                serialized_doc = serialize_document(doc)
                row = []
                for key in fieldnames:
                    value = serialized_doc.get(key, '')
                    row.append(value if value is not None else '')
                ws.append(row)

            # Save to bytes
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            yield buf.getvalue()

        repo.close()
        
        # Generate filename with timestamp
        filename = f"legal_documents_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return StreamingResponse(
            generate_xlsx(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Cache-Control": "no-cache"
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export documents: {str(e)}")


@app.post("/api/documents/delete")
def delete_documents(request: DeleteDocumentsRequest):
    """
    Delete documents by IDs.
    """
    if not request.document_ids:
        raise HTTPException(status_code=400, detail="No document IDs provided")

    repo = get_repository()
    try:
        deleted = repo.delete_documents(request.document_ids)
        logger.info(f"Deleted {deleted} documents")
        return {"status": "success", "deleted": deleted}
    except Exception as e:
        logger.error(f"Error deleting documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete documents")
    finally:
        repo.close()


@app.post("/api/documents/export/selected/xlsx")
async def export_selected_documents_xlsx(request: SelectedDocumentsRequest):
    """
    Export a specific list of documents to XLSX using their IDs.
    """
    repo = None
    try:
        repo = get_repository()
        all_docs = repo.get_all(skip=0, limit=100000)

        # Keep ordering identical to the received list
        doc_lookup = {doc.get('id'): doc for doc in all_docs}
        selected_docs = [
            doc_lookup[doc_id] for doc_id in request.document_ids
            if doc_id in doc_lookup
        ]

        if not selected_docs:
            raise HTTPException(
                status_code=404,
                detail="No documents matched the provided IDs"
            )

        # Determine fieldnames
        fieldnames = repo.fieldnames
        if not fieldnames and selected_docs:
            fieldnames = list(selected_docs[0].keys())
        if not fieldnames:
            fieldnames = ['id', 'source', 'titre', 'date']

        def generate_xlsx():
            """Generate XLSX content in memory."""
            import io
            from openpyxl import Workbook

            wb = Workbook()
            ws = wb.active
            ws.title = "Selected"
            ws.append(fieldnames)

            for doc in selected_docs:
                serialized_doc = serialize_document(doc)
                row = []
                for key in fieldnames:
                    value = serialized_doc.get(key, '')
                    row.append(value if value is not None else '')
                ws.append(row)

            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            yield buf.getvalue()

        filename = f"legal_documents_selected_{len(selected_docs)}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"

        return StreamingResponse(
            generate_xlsx(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f'attachment; filename=\"{filename}\"',
                "Content-Type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Cache-Control": "no-cache"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error exporting selected documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to export selected documents: {str(e)}")
    finally:
        if repo:
            repo.close()


@app.get("/api/documents/{document_id}")
async def get_document_by_id(document_id: str):
    """
    Get a specific document by ID
    
    - **document_id**: Unique document identifier
    """
    try:
        repo = get_repository()
        document = repo.get_by_id(document_id)
        repo.close()
        
        if not document:
            raise HTTPException(status_code=404, detail=f"Document {document_id} not found")
        
        return serialize_document(document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving document {document_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve document: {str(e)}")


@app.post("/api/process/llm", response_model=ProcessingStatus)
async def process_documents_with_llm(
    batch_size: int = Query(10, ge=1, le=100, description="Number of documents to process"),
    background_tasks: BackgroundTasks = None
):
    """
    Process pending documents with LLM (one-shot processing)
    
    Generates summaries and classifies applicability for pending documents.
    
    - **batch_size**: Number of documents to process (1-100)
    """
    logger.info(f"API: Starting LLM processing (batch size: {batch_size})")
    
    try:
        processor = create_llm_processor_instance()
        
        if processor is None:
            raise HTTPException(
                status_code=503,
                detail="LLM processing is not available. Check LLM_ENABLED configuration."
            )
        
        # Process batch
        stats = processor.process_batch(batch_size=batch_size)
        
        processor.repo.close()
        
        logger.info(f"LLM Processing completed: {stats}")
        
        return ProcessingStatus(
            status="success",
            message=f"LLM processing completed",
            processed=stats.get('processed', 0),
            failed=stats.get('failed', 0),
            skipped=stats.get('skipped', 0)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in LLM processing: {e}")
        raise HTTPException(status_code=500, detail=f"LLM processing failed: {str(e)}")


@app.get("/api/stats")
async def get_statistics():
    """
    Get repository statistics
    
    Returns document counts by source, processing status, and other metrics.
    """
    try:
        repo = get_repository()
        
        # Get counts by source
        eurlex_count = repo.count_by_source('EURLEX')
        jorf_count = repo.count_by_source('JORF')
        
        # Get all documents for status counts
        all_docs = repo.get_all(skip=0, limit=100000)
        
        pending = sum(1 for doc in all_docs if doc.get('processing_status') == 'pending')
        processed = sum(1 for doc in all_docs if doc.get('processing_status') == 'processed')
        error = sum(1 for doc in all_docs if doc.get('processing_status') == 'error')
        
        # Count by language
        languages = {}
        for doc in all_docs:
            lang = doc.get('language', 'unknown')
            languages[lang] = languages.get(lang, 0) + 1
        
        repo.close()
        
        return {
            "total_documents": len(all_docs),
            "by_source": {
                "EURLEX": eurlex_count,
                "JORF": jorf_count
            },
            "by_processing_status": {
                "pending": pending,
                "processed": processed,
                "error": error
            },
            "by_language": languages
        }
        
    except Exception as e:
        logger.error(f"Error getting statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "llm_enabled": os.getenv("LLM_ENABLED", "true").lower() == "true"
    }


@app.post("/api/process/llm/stream")
async def process_documents_with_llm_stream(
    batch_size: int = Query(10, ge=1, le=100, description="Number of documents to process")
):
    """
    Process pending documents with LLM and stream progress in real-time
    
    Uses Server-Sent Events (SSE) to send progress updates as each document is processed.
    
    - **batch_size**: Number of documents to process (1-100)
    
    Returns SSE stream with events:
    - start: Processing started
    - document_start: Document processing started
    - document_complete: Document successfully processed
    - document_error: Document processing failed
    - complete: All processing finished
    """
    
    async def generate_progress():
        """Generator function for SSE stream"""
        try:
            processor = create_llm_processor_instance()
            
            if processor is None:
                yield f"event: error\ndata: {json.dumps({'error': 'LLM processing not available'})}\n\n"
                return
            
            # Get pending documents
            pending_docs = processor.repo.get_pending_for_processing(limit=batch_size)
            
            if not pending_docs:
                yield f"event: start\ndata: {json.dumps({'message': 'No pending documents', 'total': 0})}\n\n"
                yield f"event: complete\ndata: {json.dumps({'processed': 0, 'failed': 0, 'skipped': 0})}\n\n"
                return
            
            total_docs = len(pending_docs)
            stats = {"processed": 0, "failed": 0, "skipped": 0}
            
            # Send start event
            yield f"event: start\ndata: {json.dumps({'message': 'Processing started', 'total': total_docs})}\n\n"
            await asyncio.sleep(0.1)  # Small delay to ensure client receives event
            
            # Process each document
            for i, doc in enumerate(pending_docs, 1):
                doc_id = doc.get('id')
                doc_title = doc.get('titre', 'Sans titre')[:100]
                
                # Send document start event
                progress_data = {
                    'document_id': doc_id,
                    'document_title': doc_title,
                    'current': i,
                    'total': total_docs,
                    'percentage': round((i / total_docs) * 100, 2)
                }
                yield f"event: document_start\ndata: {json.dumps(progress_data)}\n\n"
                
                try:
                    # Process document
                    success = processor.process_document(doc_id)
                    
                    if success:
                        stats["processed"] += 1
                        
                        # Get updated document for detailed info
                        updated_doc = processor.repo.get_by_id(doc_id)
                        
                        result_data = {
                            'document_id': doc_id,
                            'document_title': doc_title,
                            'current': i,
                            'total': total_docs,
                            'percentage': round((i / total_docs) * 100, 2),
                            'applicability': updated_doc.get('applicability', 'N/A'),
                            'themes': updated_doc.get('themes', 'N/A'),
                            'summary_length': len(updated_doc.get('summary', ''))
                        }
                        yield f"event: document_complete\ndata: {json.dumps(result_data)}\n\n"
                    else:
                        stats["failed"] += 1
                        
                        error_data = {
                            'document_id': doc_id,
                            'document_title': doc_title,
                            'current': i,
                            'total': total_docs,
                            'percentage': round((i / total_docs) * 100, 2),
                            'error': 'Processing failed'
                        }
                        yield f"event: document_error\ndata: {json.dumps(error_data)}\n\n"
                
                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"Error processing {doc_id}: {e}")
                    
                    error_data = {
                        'document_id': doc_id,
                        'document_title': doc_title,
                        'current': i,
                        'total': total_docs,
                        'percentage': round((i / total_docs) * 100, 2),
                        'error': str(e)
                    }
                    yield f"event: document_error\ndata: {json.dumps(error_data)}\n\n"
                
                # Small delay between documents
                await asyncio.sleep(0.1)
            
            # Send completion event
            completion_data = {
                'processed': stats['processed'],
                'failed': stats['failed'],
                'skipped': stats['skipped'],
                'total': total_docs
            }
            yield f"event: complete\ndata: {json.dumps(completion_data)}\n\n"
            
            processor.repo.close()
            
        except Exception as e:
            logger.error(f"Error in streaming LLM processing: {e}")
            yield f"event: error\ndata: {json.dumps({'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable buffering for nginx
        }
    )

@app.post("/api/scrape/eurlex", response_model=ScrapingStatus)
async def scrape_eurlex(
    series: SeriesEnum = Query(..., description="EUR-LEX series to scrape (L or C)"),
    scrape_details: bool = Query(True, description="Whether to scrape full document content"),
    target_date: Optional[str] = Query(None, description="Date to scrape (YYYY-MM-DD). Defaults to today."),
    background_tasks: BackgroundTasks = None
):
    """
    Scrape EUR-LEX Official Journal documents for a specific date
    
    - **series**: L (Legislation) or C (Information and Notices)
    - **scrape_details**: If True, scrapes full document content
    - **target_date**: Date to scrape in YYYY-MM-DD format. If not provided, scrapes today.
    """
    # Determine display date
    if target_date:
        print("\n\n target_date :::::: ", target_date)
        display_date = target_date
    else:
        display_date = datetime.now().strftime('%Y-%m-%d')
    
    logger.info(f"API: Starting EUR-LEX {series.value}-Series scraping for {display_date}")
    
    try:
        repo = get_repository()
        scraper = EURLexScraper()
        
        # Convert enum to Series type
        series_type = Series.L if series == SeriesEnum.L else Series.C
        
        # Scrape documents with optional target_date
        documents = scraper.scrape_daily_view(
            series=series_type, 
            scrape_details=scrape_details,
            target_date=target_date  # Nouveau paramètre
        )
        
        if not documents:
            return ScrapingStatus(
                status="success",
                message=f"No new documents found for EUR-LEX {series.value}-Series on {display_date}",
                documents_found=0
            )
        
        # Bulk create documents
        created, skipped = repo.bulk_create(documents)
        
        scraper.close()
        repo.close()
        
        logger.info(f"EUR-LEX {series.value} ({display_date}): {created} created, {skipped} skipped")
        
        return ScrapingStatus(
            status="success",
            message=f"EUR-LEX {series.value}-Series scraping completed for {display_date}",
            documents_found=len(documents),
            documents_created=created,
            documents_skipped=skipped
        )
        
    except Exception as e:
        logger.error(f"Error in EUR-LEX scraping: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")
    
@app.post("/api/scrape/eurlex/range", response_model=DateRangeScrapingStatus)
async def scrape_eurlex_date_range(
    series: SeriesEnum = Query(..., description="EUR-LEX series to scrape (L or C)"),
    scrape_details: bool = Query(True, description="Whether to scrape full document content"),
    date_from: str = Query(..., description="Start date (YYYY-MM-DD)"),
    date_to: str = Query(..., description="End date (YYYY-MM-DD)")
):
    """
    Scrape EUR-LEX Official Journal documents for a date range
    
    - **series**: L (Legislation) or C (Information and Notices)
    - **scrape_details**: If True, scrapes full document content
    - **date_from**: Start date in YYYY-MM-DD format
    - **date_to**: End date in YYYY-MM-DD format
    
    Note: For large date ranges, this may take several minutes.
    Consider using the streaming endpoint for progress updates.
    """
    logger.info(f"API: Starting EUR-LEX {series.value}-Series scraping from {date_from} to {date_to}")
    
    # Validate dates
    try:
        start = datetime.strptime(date_from, '%Y-%m-%d')
        end = datetime.strptime(date_to, '%Y-%m-%d')
        
        if start > end:
            raise HTTPException(
                status_code=400, 
                detail="date_from must be before or equal to date_to"
            )
        
        # Limit range to prevent abuse (max 30 days)
        delta = (end - start).days + 1
        if delta > 30:
            raise HTTPException(
                status_code=400,
                detail=f"Date range too large ({delta} days). Maximum is 30 days."
            )
            
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format. Use YYYY-MM-DD. Error: {e}")
    
    try:
        repo = get_repository()
        scraper = EURLexScraper()
        
        series_type = Series.L if series == SeriesEnum.L else Series.C
        
        # Scrape date range
        documents = scraper.scrape_date_range(
            series=series_type,
            scrape_details=scrape_details,
            date_from=date_from,
            date_to=date_to
        )
        
        if not documents:
            return DateRangeScrapingStatus(
                status="success",
                message=f"No documents found for EUR-LEX {series.value}-Series",
                date_from=date_from,
                date_to=date_to,
                days_scraped=delta,
                documents_found=0
            )
        
        created, skipped = repo.bulk_create(documents)
        
        scraper.close()
        repo.close()
        
        logger.info(f"EUR-LEX {series.value} ({date_from} to {date_to}): {created} created, {skipped} skipped")
        
        return DateRangeScrapingStatus(
            status="success",
            message=f"EUR-LEX {series.value}-Series scraping completed",
            date_from=date_from,
            date_to=date_to,
            days_scraped=delta,
            documents_found=len(documents),
            documents_created=created,
            documents_skipped=skipped
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in EUR-LEX date range scraping: {e}")
        raise HTTPException(status_code=500, detail=f"Scraping failed: {str(e)}")



# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    
    # Initialize CSV file on startup
    logger.info("Initializing CSV repository...")
    repo = get_repository()
    # Assuming CSVDocumentRepository has a close method that ensures the file structure is correct
    repo.close()
    logger.info("CSV repository initialized successfully")
    
    # Run server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
