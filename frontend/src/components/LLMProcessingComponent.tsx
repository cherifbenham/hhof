import { useState } from 'react';

type DocumentStatus = 'processing' | 'success' | 'error';

type ProcessedDocument = {
  id: string;
  title: string;
  status: DocumentStatus;
  applicability?: string;
  theme?: string;
  summary_length?: number;
  error?: string;
};

type ProgressState = {
  current: number;
  total: number;
  percentage: number;
};

type StatsState = {
  processed: number;
  failed: number;
  skipped: number;
};

const LLMProcessingComponent = () => {
  const [isProcessing, setIsProcessing] = useState(false);
  const [progress, setProgress] = useState<ProgressState>({
    current: 0,
    total: 0,
    percentage: 0
  });
  const [currentDocument, setCurrentDocument] = useState<ProcessedDocument | null>(null);
  const [processedDocuments, setProcessedDocuments] = useState<ProcessedDocument[]>([]);
  const [stats, setStats] = useState<StatsState>({ processed: 0, failed: 0, skipped: 0 });

  const startProcessing = async (batchSize = 10) => {
    setIsProcessing(true);
    setProcessedDocuments([]);
    setStats({ processed: 0, failed: 0, skipped: 0 });

    try {
      const eventSource = new EventSource(
        `http://localhost:8000/api/process/llm/stream?batch_size=${batchSize}`
      );

      eventSource.addEventListener('start', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('Processing started:', data);
        setProgress({ current: 0, total: data.total, percentage: 0 });
      });

      eventSource.addEventListener('document_start', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('Document started:', data);
        setCurrentDocument({
          id: data.document_id,
          title: data.document_title,
          status: 'processing'
        });
        setProgress({
          current: data.current,
          total: data.total,
          percentage: data.percentage
        });
      });

      eventSource.addEventListener('document_complete', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('Document completed:', data);
        
        setProcessedDocuments(prev => [...prev, {
          id: data.document_id,
          title: data.document_title,
          status: 'success',
          applicability: data.applicability,
          theme: data.theme,
          summary_length: data.summary_length
        }]);
        
        setStats(prev => ({ ...prev, processed: prev.processed + 1 }));
      });

      eventSource.addEventListener('document_error', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.error('Document error:', data);
        
        setProcessedDocuments(prev => [...prev, {
          id: data.document_id,
          title: data.document_title,
          status: 'error',
          error: data.error
        }]);
        
        setStats(prev => ({ ...prev, failed: prev.failed + 1 }));
      });

      eventSource.addEventListener('complete', (event: MessageEvent) => {
        const data = JSON.parse(event.data);
        console.log('Processing complete:', data);
        setStats(data);
        setIsProcessing(false);
        setCurrentDocument(null);
        eventSource.close();
      });

      eventSource.addEventListener('error', (event: MessageEvent) => {
        console.error('SSE Error:', event);
        setIsProcessing(false);
        setCurrentDocument(null);
        eventSource.close();
      });

      eventSource.onerror = (error) => {
        console.error('EventSource failed:', error);
        setIsProcessing(false);
        setCurrentDocument(null);
        eventSource.close();
      };

    } catch (error) {
      console.error('Error starting processing:', error);
      setIsProcessing(false);
    }
  };

  return (
    <div className="llm-processing-container">
      <h2>LLM Document Processing</h2>
      
      {/* Control Panel */}
      <div className="control-panel">
        <button 
          onClick={() => startProcessing(10)} 
          disabled={isProcessing}
          className="btn btn-primary"
        >
          {isProcessing ? 'Processing...' : 'Start Processing (10 docs)'}
        </button>
      </div>

      {/* Progress Bar */}
      {isProcessing && (
        <div className="progress-section">
          <h3>Progress: {progress.current} / {progress.total}</h3>
          <div className="progress-bar">
            <div 
              className="progress-fill" 
              style={{ width: `${progress.percentage}%` }}
            >
              {progress.percentage.toFixed(1)}%
            </div>
          </div>
          
          {/* Current Document */}
          {currentDocument && (
            <div className="current-document">
              <p><strong>Processing:</strong> {currentDocument.title}</p>
              <p><small>ID: {currentDocument.id}</small></p>
            </div>
          )}
        </div>
      )}

      {/* Statistics */}
      <div className="stats-panel">
        <h3>Statistics</h3>
        <div className="stats-grid">
          <div className="stat-item success">
            <span className="stat-value">{stats.processed}</span>
            <span className="stat-label">Processed</span>
          </div>
          <div className="stat-item error">
            <span className="stat-value">{stats.failed}</span>
            <span className="stat-label">Failed</span>
          </div>
          <div className="stat-item skipped">
            <span className="stat-value">{stats.skipped}</span>
            <span className="stat-label">Skipped</span>
          </div>
        </div>
      </div>

      {/* Processed Documents List */}
      {processedDocuments.length > 0 && (
        <div className="documents-list">
          <h3>Processed Documents</h3>
          <div className="documents-table">
            {processedDocuments.map((doc, index) => (
              <div 
                key={index} 
                className={`document-row ${doc.status}`}
              >
                <div className="document-info">
                  <strong>{doc.title}</strong>
                  <small>ID: {doc.id}</small>
                </div>
                
                {doc.status === 'success' ? (
                  <div className="document-results">
                    <span className="badge">{doc.applicability}</span>
                    <span className="badge">{doc.theme}</span>
                    <span className="summary-info">
                      Summary: {doc.summary_length} chars
                    </span>
                  </div>
                ) : (
                  <div className="document-error">
                    <span className="error-message">❌ {doc.error}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default LLMProcessingComponent;
