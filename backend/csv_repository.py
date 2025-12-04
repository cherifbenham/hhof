"""
CSV Repository for managing legal documents in CSV files.
File: csv_repository.py

Updated version: 'content' field now stores file paths instead of full text content.
Modification: 'date' field now handles only Year, Month, and Day (date object).
"""

import csv
import os
import tempfile
import shutil
import ctypes
from typing import List, Optional, Dict, Tuple, Any
from datetime import datetime, timedelta, date 
import logging

# --- CONFIGURATION ---
try:
    csv.field_size_limit(10485760) 
except OverflowError:
    csv.field_size_limit(int(ctypes.c_ulong(-1).value // 2))

CSV_DELIMITER = ';'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S' # For time-sensitive fields (created_at, updated_at, processed)
DATE_ONLY_FORMAT = '%Y-%m-%d'  # For the 'date' field
NEWLINE_ESCAPE = '\\n'
CARRIAGE_RETURN_ESCAPE = '\\r'
CONTENT_DIR = "content_files"
# ---------------------

logger = logging.getLogger(__name__)


class CSVDocumentRepository:
    """Repository for managing legal documents in CSV files"""
    
    def __init__(self, csv_file: str = "legal_documents.csv", content_directory: str = None):
        self.csv_file = csv_file
        self.content_dir = content_directory or CONTENT_DIR
        self.fieldnames = [
            'id', 'source', 'date', 'url', 'typologie', 'ministre',
            'titre', 'abstract', 'content', 'language', 'summary', 'themes',
            'applicability', 'keywords', 'processing_status',
            'created_at', 'updated_at', 'processed'
        ]
        
        # Create content directory if it doesn't exist
        os.makedirs(self.content_dir, exist_ok=True)
        
        if not os.path.exists(self.csv_file):
            self._create_csv_file()
            logger.info(f"Created new CSV file: {self.csv_file}")
    
    def _create_csv_file(self):
        """Create CSV file with headers using 'utf-8-sig' and QUOTING."""
        try:
            with open(self.csv_file, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, 
                                         delimiter=CSV_DELIMITER, 
                                         dialect='excel',
                                         quoting=csv.QUOTE_ALL)
                writer.writeheader()
        except IOError as e:
            logger.error(f"Error creating CSV file {self.csv_file}: {e}")
            raise
    
    def _escape_newlines(self, text: str) -> str:
        """Escape newlines for CSV storage"""
        if not isinstance(text, str):
            return text
        return text.replace('\n', NEWLINE_ESCAPE).replace('\r', CARRIAGE_RETURN_ESCAPE)
    
    def _unescape_newlines(self, text: str) -> str:
        """Restore newlines from CSV storage"""
        if not isinstance(text, str):
            return text
        return text.replace(NEWLINE_ESCAPE, '\n').replace(CARRIAGE_RETURN_ESCAPE, '\r')
    
    def read_content_from_file(self, filepath: str) -> Optional[str]:
        """
        Read document content from external file.
        
        Args:
            filepath: Path to the content file
            
        Returns:
            Content string or None if file doesn't exist
        """
        if not filepath or not os.path.exists(filepath):
            logger.warning(f"Content file not found: {filepath}")
            return None
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading content file {filepath}: {e}")
            return None
    
    def _parse_doc(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Convert stored string values (keywords, dates) back to Python types"""
        # Unescape newlines in text fields (but NOT content, since it's now a path)
        text_fields = ['titre', 'abstract', 'summary', 'applicability']
        for field in text_fields:
            if field in doc and doc[field]:
                doc[field] = self._unescape_newlines(doc[field])
        
        # Note: 'content' field now contains a file path, not content text
        # If you need to load the actual content, use read_content_from_file()
        
        # Parse keywords
        if 'keywords' in doc and doc['keywords'] and isinstance(doc['keywords'], str):
            doc['keywords'] = [k.strip() for k in doc['keywords'].split(',') if k.strip()]
        elif not isinstance(doc.get('keywords'), list):
            doc['keywords'] = []

        if 'themes' in doc and doc['themes'] and isinstance(doc['themes'], str):
            doc['themes'] = [k.strip() for k in doc['themes'].split(',') if k.strip()]
        elif not isinstance(doc.get('themes'), list):
            doc['themes'] = []
        
        # Parse dates
        date_fields = ['created_at', 'updated_at']
        datetime_fields = ['created_at', 'updated_at', 'processed'] # These fields keep full datetime

        # 1. Handle the 'date' field for date-only objects
        if 'date' in doc and doc['date'] and isinstance(doc['date'], str):
            try:
                # Attempt to parse as date-only first
                doc['date'] = datetime.strptime(doc['date'][:10], DATE_ONLY_FORMAT).date()
            except ValueError as e:
                logger.debug(f"Could not parse 'date' field to date object: {doc['date']} - {e}")
                pass
        
        # 2. Handle datetime fields
        for field in datetime_fields:
            if field in doc and doc[field] and isinstance(doc[field], str):
                try:
                    # Try to parse as full datetime
                    doc[field] = datetime.strptime(doc[field], DATE_FORMAT)
                except ValueError:
                    try:
                        # Fallback: Try to parse as date-only, then convert to datetime at midnight
                        doc[field] = datetime.combine(datetime.strptime(doc[field][:10], DATE_ONLY_FORMAT).date(), datetime.min.time())
                    except ValueError as e:
                        logger.debug(f"Could not parse datetime field '{field}': {doc[field]} - {e}")
                        pass

        return doc
    
    def _read_all_documents(self, parse: bool = True) -> List[Dict]:
        """Read all documents from CSV."""
        documents = []
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=CSV_DELIMITER, dialect='excel')
                for row in reader:
                    try:
                        documents.append(self._parse_doc(row) if parse else row)
                    except Exception as e:
                        logger.error(f"Error parsing row: {e}")
                        continue
        except FileNotFoundError:
            logger.warning(f"CSV file not found: {self.csv_file}. Returning empty list.")
        except csv.Error as e:
            logger.error(f"CSV error reading {self.csv_file}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error reading documents from {self.csv_file}: {e}")
        return documents
    
    def _write_all_documents(self, documents: List[Dict]):
        """Write all documents to CSV using atomic write (temp file + rename) and QUOTING."""
        temp_file = None
        try:
            temp_fd, temp_file = tempfile.mkstemp(suffix='.csv', dir=os.path.dirname(self.csv_file) or '.')
            
            with os.fdopen(temp_fd, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, 
                                         delimiter=CSV_DELIMITER, 
                                         dialect='excel',
                                         quoting=csv.QUOTE_ALL)
                writer.writeheader()
                writer.writerows(documents)
            
            shutil.move(temp_file, self.csv_file)
            temp_file = None
            
        except IOError as e:
            logger.error(f"Error writing documents to CSV file {self.csv_file}: {e}")
            raise
        finally:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
    
    def exists(self, document_id: str) -> bool:
        """Check if document exists by ID"""
        try:
            with open(self.csv_file, 'r', newline='', encoding='utf-8-sig') as f:
                reader = csv.DictReader(f, delimiter=CSV_DELIMITER, dialect='excel')
                return any(doc.get('id') == document_id for doc in reader)
        except Exception:
            return False
    
    def _prepare_doc_for_write(self, doc_data: Dict) -> Dict:
        """Standardize document data for CSV storage format"""
        document = {field: '' for field in self.fieldnames}
        
        if 'id' not in doc_data or not doc_data['id']:
            raise ValueError("Document must have an 'id' field")
        
        # Clean and escape text fields (NOT content - it's a path now)
        text_fields = ['titre', 'abstract', 'summary', 'applicability']
        for key in text_fields:
            value = doc_data.get(key)
            if isinstance(value, str):
                doc_data[key] = self._escape_newlines(value.strip())
        
        # CRITICAL: Content field must ONLY store the file path, never actual content
        # If content is provided, it should already be a path from the scraper
        if 'content' in doc_data and doc_data['content']:
            # Ensure it's stored as a simple string path (no escaping)
            content_value = str(doc_data['content'])
            # Verify it looks like a path, not actual content
            if len(content_value) > 500:
                logger.error(f"Content field appears to contain actual content instead of path for doc {doc_data.get('id')}. Skipping content.")
                doc_data['content'] = ''
            else:
                doc_data['content'] = content_value
        
        # Format dates
        for key, value in doc_data.items():
            if key == 'date':
                if isinstance(value, datetime):
                    doc_data[key] = value.strftime(DATE_ONLY_FORMAT) # Date-only format
                elif isinstance(value, date) and not isinstance(value, datetime):
                    doc_data[key] = value.strftime(DATE_ONLY_FORMAT) # Date-only format
            elif isinstance(value, datetime):
                doc_data[key] = value.strftime(DATE_FORMAT) # Full datetime format
            elif isinstance(value, date) and not isinstance(value, datetime):
                # Fallback for other date fields (e.g. if 'processed' was set to a date object)
                doc_data[key] = value.strftime(DATE_ONLY_FORMAT)
        
        # Format keywords
        if 'keywords' in doc_data and isinstance(doc_data['keywords'], list):
            doc_data['keywords'] = ", ".join(doc_data['keywords'])

        if 'themes' in doc_data and isinstance(doc_data['themes'], list):
            doc_data['themes'] = ", ".join(doc_data['themes'])
        
        document.update(doc_data)
        
        # Set timestamps
        now_str = datetime.now().strftime(DATE_FORMAT)
        document['processing_status'] = doc_data.get('processing_status', 'pending')
        
        # Ensure 'date' is present even if it's an empty string if not provided, for consistency
        if 'date' not in document:
            document['date'] = ''
            
        document['created_at'] = document.get('created_at', now_str)
        document['updated_at'] = now_str
        
        if document['processing_status'] == 'processed' and not document.get('processed'):
            document['processed'] = now_str
            
        return document

    def create(self, doc_data: Dict) -> Optional[Dict]:
        """Create a single document with QUOTING."""
        if self.exists(doc_data.get('id')):
            logger.info(f"Document {doc_data.get('id')} already exists, skipping...")
            return None
            
        if 'id' not in doc_data:
            logger.error("Cannot create document without 'id' field.")
            return None
            
        try:
            document = self._prepare_doc_for_write(doc_data)
            
            with open(self.csv_file, 'a', newline='', encoding='utf-8-sig') as f:
                writer = csv.DictWriter(f, fieldnames=self.fieldnames, 
                                         delimiter=CSV_DELIMITER, 
                                         dialect='excel',
                                         quoting=csv.QUOTE_ALL)
                writer.writerow(document)
            
            logger.info(f"Document {document['id']} created successfully")
            return document
            
        except Exception as e:
            logger.error(f"Error creating document {doc_data.get('id')}: {e}")
            return None
    
    def bulk_create(self, docs_data: List[Dict]) -> Tuple[int, int]:
        """Bulk create documents with atomic write"""
        created_docs = []
        skipped = 0
        existing_ids = {doc.get('id') for doc in self._read_all_documents(parse=False)}
        
        for doc_data in docs_data:
            doc_id = doc_data.get('id')
            if not doc_id:
                logger.error("Skipping document without 'id'.")
                skipped += 1
                continue
                
            if doc_id in existing_ids:
                logger.debug(f"Document {doc_id} already exists, skipping...")
                skipped += 1
                continue
            
            try:
                document = self._prepare_doc_for_write(doc_data)
                created_docs.append(document)
                existing_ids.add(doc_id)
            except ValueError as e:
                logger.error(f"Validation error for document {doc_id}: {e}")
                skipped += 1
            except Exception as e:
                logger.error(f"Error preparing document {doc_id} for bulk creation: {e}")
                skipped += 1
                
        if created_docs:
            try:
                existing_docs = self._read_all_documents(parse=False)
                all_docs = existing_docs + created_docs
                
                self._write_all_documents(all_docs)
                
                logger.info(f"Bulk creation successful. Created {len(created_docs)} documents.")
                return len(created_docs), skipped
            except Exception as e:
                logger.error(f"Error during bulk write operation: {e}")
                return 0, skipped + len(created_docs)
                
        return 0, skipped
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Dict]:
        """Get all documents with pagination"""
        documents = self._read_all_documents()
        
        def safe_sort_key(doc):
            created_at = doc.get('created_at')
            if isinstance(created_at, str) or created_at is None:
                return datetime.min
            return created_at

        documents.sort(key=safe_sort_key, reverse=True)
        
        return documents[skip:skip + limit]
    
    def get_by_id(self, document_id: str) -> Optional[Dict]:
        """Get document by ID"""
        documents = self._read_all_documents()
        for doc in documents:
            if doc.get('id') == document_id:
                return doc
        return None
    
    def get_pending_for_processing(self, limit: int = 100) -> List[Dict]:
        """
        Get pending documents that need processing and have content files.
        Now checks if content file exists instead of checking string content.
        """
        documents = self._read_all_documents()
        pending = [
            doc for doc in documents
            if doc.get('processing_status') == 'pending'
            and doc.get('content') 
            and isinstance(doc['content'], str) 
            and os.path.exists(doc['content'])  # Check file exists
        ]
        return pending[:limit]
    
    def update_document(self, document_id: str, updates: Dict) -> bool:
        """Update a document by ID"""
        try:
            documents = self._read_all_documents(parse=False)
            updated = False
            
            for i, doc in enumerate(documents):
                if doc.get('id') == document_id:
                    # Merge and prepare updates
                    prepared_updates = self._prepare_doc_for_write({**doc, **updates})
                    
                    # Update fields (preserve id and created_at)
                    for key, value in prepared_updates.items():
                        if key not in ['id', 'created_at'] and key in self.fieldnames:
                            doc[key] = value
                    
                    # Update timestamp
                    now_str = datetime.now().strftime(DATE_FORMAT)
                    doc['updated_at'] = now_str
                    
                    # Set processed timestamp if needed
                    if doc.get('processing_status') == 'processed' and not doc.get('processed'):
                        doc['processed'] = now_str
                    
                    documents[i] = doc
                    updated = True
                    break
            
            if updated:
                self._write_all_documents(documents)
                logger.info(f"Document {document_id} updated successfully")
                return True
            
            logger.warning(f"Document {document_id} not found for update")
            return False
            
        except Exception as e:
            logger.error(f"Error updating document {document_id}: {e}")
            return False

    def update_processing_status(self, document_id: str, status: str) -> bool:
        """Update processing status of a document"""
        updates = {'processing_status': status}
        return self.update_document(document_id, updates)
    
    def count_by_source(self, source: str) -> int:
        """Count documents by source"""
        documents = self._read_all_documents(parse=False)
        return sum(1 for doc in documents if doc.get('source') == source)
    
    def get_recent(self, days: int = 7, limit: int = 50) -> List[Dict]:
        """Get recent documents within specified days"""
        # Note: The 'date' field is now a date object (Year, Month, Day) in read documents
        cutoff_date = (datetime.now() - timedelta(days=days)).date()
        
        documents = self._read_all_documents()
        
        recent = []
        for doc in documents:
            doc_date = doc.get('date')
            # doc_date should already be a date object from _parse_doc
            if isinstance(doc_date, date):
                if doc_date >= cutoff_date:
                    recent.append(doc)
        
        # Sort by the date object
        recent.sort(key=lambda x: x.get('date', date.min), reverse=True)
        return recent[:limit]

    def delete_documents(self, document_ids: List[str]) -> int:
        """
        Delete documents by IDs from the CSV. Returns number of deleted rows.
        """
        if not document_ids:
            return 0

        id_set = set(document_ids)
        documents = self._read_all_documents(parse=False)
        remaining = [doc for doc in documents if doc.get('id') not in id_set]
        deleted = len(documents) - len(remaining)

        if deleted > 0:
            self._write_all_documents(remaining)

        return deleted
    
    def close(self):
        """Close repository (placeholder for compatibility)"""
        pass
