import { useState, useEffect, type ReactNode } from 'react';
import {
  FileText,
  RefreshCw,
  Database,
  Activity,
  Download,
  Upload,
  Search,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
  Sun,
  Moon,
  Filter,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  Menu,
  Trash2,
  Settings,
} from 'lucide-react';

// API Configuration
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL 
  || (typeof window !== 'undefined' ? window.location.origin : 'http://localhost:8000');

interface Document {
  id: string;
  source: string;
  typologie: string;
  titre: string;
  date: string;
  language: string;
  url: string;
  processing_status: string;
  summary?: string;
  applicability?: string;
  themes: string | string[];
  created_at: string;
  keywords: string | string[];
}

interface Stats {
  total_documents: number;
  by_source: { EURLEX: number; JORF: number };
  by_processing_status: { pending: number; processed: number; error: number };
  by_language: Record<string, number>;
}

interface FilterState {
  source: string;
  typologie: string;
  language: string;
  processing_status: string;
  date_from: string;
  date_to: string;
}

type SortOrder = 'asc' | 'desc';
type ViewMode = 'documents' | 'scrape' | 'process' | 'delete' | 'setup';
const DEFAULT_FILTERS: FilterState = {
  source: '',
  typologie: '',
  language: '',
  processing_status: '',
  date_from: '',
  date_to: '',
};


const formatSummary = (summary: string): string => {
  if (!summary) return '';
  return summary
    .replace(/###?\s*/g, '')
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/####\s*\d+\.\s*/g, '• ')
    .replace(/---+/g, '')
    .replace(/\n{3,}/g, '\n\n')
    .trim();
};



const getThemesArray = (themes: string | string[]): string[] => {
  if (Array.isArray(themes)) return themes;
  if (typeof themes === 'string' && themes.trim()) {
    return themes.split(',').map(t => t.trim()).filter(t => t.length > 0);
  }
  return [];
};

const toTimestamp = (value: string | Date): number => {
  if (value instanceof Date) return value.getTime();
  if (!value) return 0;

  // YYYY-MM-DD
  if (/^\d{4}-\d{2}-\d{2}/.test(value)) {
    const ts = Date.parse(value);
    return Number.isNaN(ts) ? 0 : ts;
  }

  // DD/MM/YYYY
  const slash = value.match(/^(\d{2})\/(\d{2})\/(\d{4})/);
  if (slash) {
    const [_, d, m, y] = slash;
    const ts = Date.parse(`${y}-${m}-${d}`);
    return Number.isNaN(ts) ? 0 : ts;
  }

  const ts = Date.parse(value);
  return Number.isNaN(ts) ? 0 : ts;
};

const sortDocumentsByDate = (docs: Document[], order: SortOrder): Document[] => {
  return [...docs].sort((a, b) => {
    const da = toTimestamp(a.date as unknown as string);
    const db = toTimestamp(b.date as unknown as string);
    return order === 'asc' ? da - db : db - da;
  });
};

export default function LegalDashboard() {
  // Theme State
  const [isDarkMode, setIsDarkMode] = useState(true);
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [exportLoading, setExportLoading] = useState(false);

  const [scrapeMode, setScrapeMode] = useState<'today' | 'date' | 'range'>('today');
  const todayStr = new Date().toISOString().split('T')[0];
  const [scrapeDate, setScrapeDate] = useState(todayStr);
  const [scrapeDateFrom, setScrapeDateFrom] = useState('');
  const [scrapeDateTo, setScrapeDateTo] = useState('');
  const [scrapeProgress, setScrapeProgress] = useState<{
    current: number;
    total: number;
    currentDate: string;
    status: string;
  } | null>(null);

  // App State
  const [documents, setDocuments] = useState<Document[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeView, setActiveView] = useState<ViewMode>('scrape');
  const [deleteStatus, setDeleteStatus] = useState<string | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [sortOrder, setSortOrder] = useState<SortOrder>('desc');
  const [themeValues, setThemeValues] = useState<string[]>([]);
  const [applicabilityValues, setApplicabilityValues] = useState<string[]>([]);
  const [newThemeValues, setNewThemeValues] = useState('');
  const [newAppValues, setNewAppValues] = useState('');

  // Filters & Pagination
  const [filters, setFilters] = useState<FilterState>({ ...DEFAULT_FILTERS });
  const [showFilters, setShowFilters] = useState(false);
  const [pagination, setPagination] = useState({ skip: 0, limit: 50 });
  const [totalDocs, setTotalDocs] = useState(0);
  const [selectedDocIds, setSelectedDocIds] = useState<Set<string>>(new Set());
  const [selectAllChecked, setSelectAllChecked] = useState(false);

  // Scraping state
  const [scrapingSeries, setScrapingSeries] = useState<'L' | 'C'>('L');
  const [scrapeDetails, setScrapeDetails] = useState(true);
  const [jorfEmail, setJorfEmail] = useState('');
  const [scrapeStatus, setScrapeStatus] = useState<string | null>(null);

  // Processing state
  const [batchSize, setBatchSize] = useState(10);
  const [processStatus, setProcessStatus] = useState<string | null>(null);

  useEffect(() => {
    if (isDarkMode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDarkMode]);

  useEffect(() => {
    fetchDocuments();
    fetchStats();
  }, [pagination, filters, sortOrder]);

  useEffect(() => {
    const savedThemes = localStorage.getItem('themeValues');
    const savedApplicability = localStorage.getItem('applicabilityValues');
    if (savedThemes) {
      setThemeValues(JSON.parse(savedThemes));
    }
    if (savedApplicability) {
      setApplicabilityValues(JSON.parse(savedApplicability));
    }
    if (!savedThemes || !savedApplicability) {
      fetchClassificationConfig();
    }
  }, []);

  useEffect(() => {
    localStorage.setItem('themeValues', JSON.stringify(themeValues));
  }, [themeValues]);

  useEffect(() => {
    localStorage.setItem('applicabilityValues', JSON.stringify(applicabilityValues));
  }, [applicabilityValues]);

useEffect(() => {
  if (scrapeMode === 'date' && !scrapeDate) {
    setScrapeDate(todayStr);
  }
}, [scrapeMode, scrapeDate, todayStr]);

  // Fetch documents
  const fetchDocuments = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({
        skip: '0',
        limit: '1000', // API capped at 1000; we paginate client-side after fetch
      });

      if (filters.source) params.append('source', filters.source);
      if (filters.typologie) params.append('typologie', filters.typologie);
      if (filters.language) params.append('language', filters.language);
      if (filters.processing_status) params.append('processing_status', filters.processing_status);
      if (filters.date_from) params.append('date_from', filters.date_from);
      if (filters.date_to) params.append('date_to', filters.date_to);

      const response = await fetch(`${API_BASE_URL}/api/documents?${params}`);
      if (!response.ok) throw new Error('Failed to fetch documents');

      const data = await response.json();
      const sortedDocs = sortDocumentsByDate(data.documents, sortOrder);
      const paginated = sortedDocs.slice(pagination.skip, pagination.skip + pagination.limit);
      setDocuments(paginated);
      setTotalDocs(sortedDocs.length);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  // Toggle sélection d'un document
const toggleDocumentSelection = (docId: string) => {
  setSelectedDocIds(prev => {
    const newSet = new Set(prev);
    if (newSet.has(docId)) {
      newSet.delete(docId);
    } else {
      newSet.add(docId);
    }
    return newSet;
  });
};

// Toggle sélection de tous les documents visibles
const toggleSelectAll = () => {
  if (selectAllChecked) {
    // Désélectionner tous
    setSelectedDocIds(new Set());
  } else {
    // Sélectionner tous les documents visibles
    const allIds = new Set(documents.map(doc => doc.id));
    setSelectedDocIds(allIds);
  }
  setSelectAllChecked(!selectAllChecked);
};

// Réinitialiser la sélection quand les documents changent
useEffect(() => {
  setSelectedDocIds(new Set());
  setSelectAllChecked(false);
}, [documents]);

useEffect(() => {
  setSelectedDocIds(new Set());
  setSelectAllChecked(false);
  setDeleteStatus(null);
}, [activeView]);

// 3. Nouvelle fonction d'export des documents sélectionnés
const exportSelectedDocuments = async () => {
  if (selectedDocIds.size === 0) {
    setError('Please select at least one document to export');
    return;
  }

  setExportLoading(true);
  setError(null);
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/documents/export/selected/csv`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        document_ids: Array.from(selectedDocIds)
      })
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Export failed: ${errorText}`);
    }

    const blob = await response.blob();
    
    const contentDisposition = response.headers.get('Content-Disposition');
    let filename = `legal_documents_selected_${selectedDocIds.size}.csv`;
    if (contentDisposition) {
      const filenameMatch = contentDisposition.match(/filename="(.+)"/);
      if (filenameMatch && filenameMatch[1]) {
        filename = filenameMatch[1];
      }
    }

    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);

    // Réinitialiser la sélection après export
    setSelectedDocIds(new Set());
    setSelectAllChecked(false);

  } catch (err) {
    setError(err instanceof Error ? err.message : 'An unknown error occurred during export.');
  } finally {
    setExportLoading(false);
  }
};

  const exportDocuments = async (fileType: 'csv' | 'json') => {
    setExportLoading(true);
    setError(null);
    try {
      // Re-use current filters for the export
      const params = new URLSearchParams({
        format: fileType,
      });
  
      if (filters.source) params.append('source', filters.source);
      if (filters.typologie) params.append('typologie', filters.typologie);
      if (filters.language) params.append('language', filters.language);
      if (filters.processing_status) params.append('processing_status', filters.processing_status);
      if (filters.date_from) params.append('date_from', filters.date_from);
      if (filters.date_to) params.append('date_to', filters.date_to);
  
      const response = await fetch(`${API_BASE_URL}/api/documents/export/csv`);
  
      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Export failed: ${errorText}`);
      }
  
      // Get the file data (blob)
      const blob = await response.blob();
      
      // Determine file name and content type from the response headers (optional, but good practice)
      const contentDisposition = response.headers.get('Content-Disposition');
      let filename = `legal_documents_export.${fileType}`;
      if (contentDisposition) {
        const filenameMatch = contentDisposition.match(/filename="(.+)"/);
        if (filenameMatch && filenameMatch[1]) {
          filename = filenameMatch[1];
        }
      }
  
      // Create a URL for the blob and trigger download
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
  
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unknown error occurred during export.');
    } finally {
      setExportLoading(false);
    }
  };

  // Fetch statistics
  const fetchStats = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/stats`);
      if (!response.ok) throw new Error('Failed to fetch stats');
      const data = await response.json();
      setStats(data);
    } catch (err) {
      console.error('Failed to fetch stats:', err);
    }
  };

  // Scrape EUR-LEX
  const scrapeEURLex = async () => {
    setLoading(true);
    setScrapeStatus(null);
    setScrapeProgress(null);
  
    try {
      let url = '';
      let useStreaming = false;
  
      switch (scrapeMode) {
        case 'today':
          url = `${API_BASE_URL}/api/scrape/eurlex?series=${scrapingSeries}&scrape_details=${scrapeDetails}`;
          break;
        case 'date':
          if (!scrapeDate) {
            setScrapeStatus('Error: Please select a date');
            setLoading(false);
            return;
          }
          url = `${API_BASE_URL}/api/scrape/eurlex?series=${scrapingSeries}&scrape_details=${scrapeDetails}&target_date=${scrapeDate}`;
          break;
        case 'range':
          if (!scrapeDateFrom || !scrapeDateTo) {
            setScrapeStatus('Error: Please select both start and end dates');
            setLoading(false);
            return;
          }
          // Utiliser le streaming pour les intervalles
          useStreaming = true;
          url = `${API_BASE_URL}/api/scrape/eurlex/range?series=${scrapingSeries}&scrape_details=${scrapeDetails}&date_from=${scrapeDateFrom}&date_to=${scrapeDateTo}`;
          break;
      }
  
      if (useStreaming) {
        // Streaming avec Server-Sent Events
        const response = await fetch(url, { method: 'POST' });
        
        if (!response.ok) {
          throw new Error('Scraping failed');
        }
  
        const reader = response.body?.getReader();
        const decoder = new TextDecoder();
  
        if (!reader) {
          throw new Error('Unable to read response stream');
        }
  
        let buffer = '';
        
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
  
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('event:')) {
              continue;
            }
            if (line.startsWith('data:')) {
              try {
                const data = JSON.parse(line.replace('data:', '').trim());
                
                if (data.error) {
                  setScrapeStatus(`Error: ${data.error}`);
                  setLoading(false);
                  return;
                }
  
                if (data.total_days !== undefined && data.date === undefined) {
                  // Start event
                  setScrapeProgress({
                    current: 0,
                    total: data.total_days,
                    currentDate: '',
                    status: 'Starting...'
                  });
                } else if (data.day !== undefined) {
                  // Progress event
                  setScrapeProgress({
                    current: data.day,
                    total: data.total_days,
                    currentDate: data.date,
                    status: data.documents_found !== undefined 
                      ? `${data.documents_found} docs found` 
                      : 'Scraping...'
                  });
                } else if (data.total_documents !== undefined) {
                  // Complete event
                  setScrapeStatus(`Success: ${data.total_created} created, ${data.total_skipped} skipped (${data.total_days} days)`);
                  setScrapeProgress(null);
                }
              } catch (e) {
                // Ignore parse errors
              }
            }
          }
        }
      } else {
        // Requête simple sans streaming
        const response = await fetch(url, { method: 'POST' });
        if (!response.ok) throw new Error('Scraping failed');
  
        const data = await response.json();
        setScrapeStatus(`Success: ${data.documents_created} created, ${data.documents_skipped} skipped`);
      }
  
      fetchDocuments();
      fetchStats();
    } catch (err) {
      setScrapeStatus(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
      setScrapeProgress(null);
    }
  };


  // Scrape JORF
  const scrapeJORF = async () => {
    if (!jorfEmail.trim()) {
      setScrapeStatus('Error: Please enter JORF email content');
      return;
    }

    setLoading(true);
    setScrapeStatus(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/scrape/jorf`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email_body: jorfEmail }),
      });
      if (!response.ok) throw new Error('JORF parsing failed');

      const data = await response.json();
      setScrapeStatus(`Success: ${data.documents_created} created, ${data.documents_skipped} skipped`);
      setJorfEmail('');
      fetchDocuments();
      fetchStats();
    } catch (err) {
      setScrapeStatus(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  // Process with LLM
  const processDocuments = async () => {
    setLoading(true);
    setProcessStatus(null);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/process/llm?batch_size=${batchSize}`,
        { method: 'POST' }
      );
      if (!response.ok) throw new Error('Processing failed');

      const data = await response.json();
      setProcessStatus(`Success: ${data.processed} processed, ${data.failed} failed, ${data.skipped} skipped`);
      fetchDocuments();
      fetchStats();
    } catch (err) {
      setProcessStatus(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setLoading(false);
    }
  };

  const deleteSelectedDocuments = async () => {
    if (selectedDocIds.size === 0) {
      setDeleteStatus('Select at least one document to delete');
      return;
    }

    setDeleteLoading(true);
    setDeleteStatus(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/documents/delete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ document_ids: Array.from(selectedDocIds) })
      });

      if (!response.ok) throw new Error('Delete failed');
      const data = await response.json();

      setDocuments((prev) => prev.filter((doc) => !selectedDocIds.has(doc.id)));
      setTotalDocs((prev) => Math.max(0, prev - (data.deleted ?? 0)));
      setDeleteStatus(`Deleted ${data.deleted ?? 0} document(s)`);
      setSelectedDocIds(new Set());
      setSelectAllChecked(false);
      fetchStats();
    } catch (err) {
      setDeleteStatus(`Error: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleResetFilters = () => {
    setFilters({ ...DEFAULT_FILTERS });
    setPagination((p) => ({ ...p, skip: 0 }));
  };

  const fetchClassificationConfig = async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/api/config/classification`);
      if (!res.ok) throw new Error('Failed to load classification config');
      const data = await res.json();
      const themesFlat = Object.values<string[]>(data.themes || {}).flat();
      const appFlat = Object.values<string[]>(data.applicability_categories || {}).flat();
      setThemeValues(themesFlat);
      setApplicabilityValues(appFlat);
      localStorage.removeItem('themeValues');
      localStorage.removeItem('applicabilityValues');
    } catch (err) {
      console.error(err);
    }
  };

  const handleThemeValueChange = (index: number, value: string) => {
    setThemeValues((prev) =>
      prev.map((v, i) => (i === index ? value : v))
    );
  };

  const handleAppValueChange = (index: number, value: string) => {
    setApplicabilityValues((prev) =>
      prev.map((v, i) => (i === index ? value : v))
    );
  };

  const addThemeValue = () => {
    if (!newThemeValues.trim()) return;
    const parts = newThemeValues.split(',').map((v) => v.trim()).filter(Boolean);
    setThemeValues((prev) => [...prev, ...parts]);
    setNewThemeValues('');
  };

  const addAppValue = () => {
    if (!newAppValues.trim()) return;
    const parts = newAppValues.split(',').map((v) => v.trim()).filter(Boolean);
    setApplicabilityValues((prev) => [...prev, ...parts]);
    setNewAppValues('');
  };

  const removeThemeValue = (index: number) => {
    setThemeValues((prev) => prev.filter((_, i) => i !== index));
  };

  const removeAppValue = (index: number) => {
    setApplicabilityValues((prev) => prev.filter((_, i) => i !== index));
  };

  const clearSavedConfig = () => {
    localStorage.removeItem('themeValues');
    localStorage.removeItem('applicabilityValues');
    setThemeValues([]);
    setApplicabilityValues([]);
    fetchClassificationConfig();
  };

  const StatusBadge = ({ status }: { status: string }) => {
    const styles = {
      pending: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-500/20 dark:text-yellow-300',
      processed: 'bg-green-100 text-green-800 dark:bg-green-500/20 dark:text-green-300',
      error: 'bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-300',
    };
    const icons = {
      pending: <Clock className="w-3 h-3" />,
      processed: <CheckCircle className="w-3 h-3" />,
      error: <XCircle className="w-3 h-3" />,
    };
    const key = status as keyof typeof styles;
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${styles[key] || 'bg-gray-100 text-gray-800 dark:bg-gray-500/20 dark:text-gray-300'}`}>
        {icons[key as keyof typeof icons]}
        <span className="capitalize">{status}</span>
      </span>
    );
  };

  return (
    <div className={`min-h-screen transition-colors duration-300 ${isDarkMode ? 'bg-slate-950 text-slate-100' : 'bg-gray-50 text-gray-900'}`}>
      {/* Sidebar */}
      <aside className={`fixed top-0 left-0 z-40 h-screen transition-transform ${isSidebarOpen ? 'translate-x-0' : '-translate-x-full'} md:translate-x-0 w-64 border-r ${isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
        <div className="flex flex-col h-full">
          <div className="h-16 flex items-center px-6 border-b border-inherit">
            <FileText className="w-6 h-6 text-blue-500 mr-2" />
            <span className="font-bold text-lg tracking-tight">LegalDash</span>
          </div>

          <nav className="flex-1 px-4 py-6 space-y-2">
            <button
              onClick={() => setActiveView('scrape')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeView === 'scrape'
                  ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/20'
                  : 'hover:bg-gray-100 dark:hover:bg-slate-800 text-gray-600 dark:text-slate-400'
              }`}
            >
              <Download className="w-5 h-5" />
              Scrape Sources
            </button>
            <button
              onClick={() => setActiveView('process')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeView === 'process'
                  ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/20'
                  : 'hover:bg-gray-100 dark:hover:bg-slate-800 text-gray-600 dark:text-slate-400'
              }`}
            >
              <Activity className="w-5 h-5" />
              Process Data
            </button>
            <button
              onClick={() => setActiveView('documents')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeView === 'documents'
                  ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/20'
                  : 'hover:bg-gray-100 dark:hover:bg-slate-800 text-gray-600 dark:text-slate-400'
              }`}
            >
              <LayoutDashboard className="w-5 h-5" />
              Explore Documents
            </button>
            <button
              onClick={() => setActiveView('delete')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeView === 'delete'
                  ? 'bg-red-500 text-white shadow-lg shadow-red-500/20'
                  : 'hover:bg-gray-100 dark:hover:bg-slate-800 text-gray-600 dark:text-slate-400'
              }`}
            >
              <Trash2 className="w-5 h-5" />
              Delete Documents
            </button>
            <button
              onClick={() => setActiveView('setup')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeView === 'setup'
                  ? 'bg-amber-500 text-white shadow-lg shadow-amber-500/20'
                  : 'hover:bg-gray-100 dark:hover:bg-slate-800 text-gray-600 dark:text-slate-400'
              }`}
            >
              <Settings className="w-5 h-5" />
              Setup
            </button>
          </nav>

          <div className="p-4 border-t border-inherit">
            <div className={`p-4 rounded-xl ${isDarkMode ? 'bg-slate-800' : 'bg-gray-100'}`}>
              <p className="text-xs font-medium text-gray-500 dark:text-slate-400 mb-2">SYSTEM STATUS</p>
              <div className="flex items-center gap-2 text-sm">
                <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
                <span className="font-medium">Operational</span>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className={`transition-all duration-300 ${isSidebarOpen ? 'md:ml-64' : ''} min-h-screen flex flex-col`}>
        {/* Top Header */}
        <header className={`h-16 sticky top-0 z-30 border-b backdrop-blur-md flex items-center justify-between px-6 ${isDarkMode ? 'bg-slate-950/80 border-slate-800' : 'bg-white/80 border-gray-200'}`}>
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsSidebarOpen(!isSidebarOpen)}
              className="md:hidden p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-slate-800"
            >
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-lg font-semibold capitalize">{activeView.replace('-', ' ')}</h2>
          </div>

          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsDarkMode(!isDarkMode)}
              className={`p-2 rounded-full transition-colors ${isDarkMode ? 'bg-slate-800 text-yellow-400 hover:bg-slate-700' : 'bg-gray-100 text-slate-600 hover:bg-gray-200'}`}
              title="Toggle Theme"
            >
              {isDarkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </button>
            <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-blue-500 to-purple-500 flex items-center justify-center text-white font-bold text-xs">
              JD
            </div>
          </div>
        </header>

        {/* Content Area */}
        <div className="flex-1 p-6 overflow-x-hidden">
          {/* Stats Overview */}
          {stats && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
              <StatCard
                title="Total Documents"
                value={stats.total_documents}
                icon={<Database className="w-5 h-5" />}
                color="blue"
                isDarkMode={isDarkMode}
              />
              <StatCard
                title="Processed"
                value={stats.by_processing_status.processed}
                icon={<CheckCircle className="w-5 h-5" />}
                color="green"
                isDarkMode={isDarkMode}
              />
              <StatCard
                title="Pending"
                value={stats.by_processing_status.pending}
                icon={<Clock className="w-5 h-5" />}
                color="yellow"
                isDarkMode={isDarkMode}
              />
              <StatCard
                title="Sources (EUR/JORF)"
                value={`${stats.by_source.EURLEX} / ${stats.by_source.JORF}`}
                icon={<FileText className="w-5 h-5" />}
                color="purple"
                isDarkMode={isDarkMode}
              />
            </div>
          )}

          {/* View Content */}
          <div className="max-w-full">
            {(activeView === 'documents' || activeView === 'delete') && (
              <div className="space-y-4">
                {/* Toolbar */}
                <div className={`p-4 rounded-xl border flex flex-col md:flex-row gap-4 items-start md:items-center justify-between ${isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
                  <div className="flex items-center gap-2 w-full md:w-auto">
                    {/* ... Search Input and Filter Button (keep existing code here) ... */}
                    <div className="relative flex-1 md:w-64">
                      <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                      <input
                        type="text"
                        placeholder="Search documents..."
                        className={`w-full pl-9 pr-4 py-2 rounded-lg text-sm border focus:ring-2 focus:ring-blue-500 outline-none transition-all ${isDarkMode ? 'bg-slate-950 border-slate-700 placeholder-slate-500' : 'bg-gray-50 border-gray-300'}`}
                      />
                    </div>
                    <button
                      onClick={() => setShowFilters(!showFilters)}
                      className={`p-2 rounded-lg border transition-colors ${showFilters ? 'bg-blue-500 text-white border-blue-500' : isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-300 hover:bg-gray-100'}`}
                    >
                      <Filter className="w-4 h-4" />
                    </button>
              </div>

  <div className="flex items-center gap-2 w-full md:w-auto">
    {activeView === 'documents' && (
      <>
        <Button 
          onClick={() => exportDocuments('csv')} 
          loading={exportLoading} 
          variant="export"
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors"
          disabled={documents.length === 0}
        >
          <Download className={`w-4 h-4 ${exportLoading ? 'animate-spin' : ''}`} />
          Export ALL
        </Button>
        <button
          onClick={exportSelectedDocuments}
          disabled={selectedDocIds.size === 0 || exportLoading}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            selectedDocIds.size > 0
              ? 'bg-blue-600 hover:bg-blue-700 text-white shadow-lg shadow-blue-500/20'
              : isDarkMode 
                ? 'bg-slate-800 text-slate-400 opacity-50 cursor-not-allowed' 
                : 'bg-gray-100 text-gray-400 opacity-50 cursor-not-allowed'
          }`}
        >
          <Download className={`w-4 h-4 ${exportLoading ? 'animate-spin' : ''}`} />
          Export Selected {selectedDocIds.size > 0 ? `(${selectedDocIds.size})` : ''}
        </button>
      </>
    )}
    {activeView === 'delete' && (
      <Button
        onClick={deleteSelectedDocuments}
        loading={deleteLoading}
        variant="danger"
        className="flex items-center gap-2 px-4 py-2 text-sm font-medium transition-colors"
        disabled={selectedDocIds.size === 0}
      >
        <Trash2 className="w-4 h-4" />
        Delete Selected {selectedDocIds.size > 0 ? `(${selectedDocIds.size})` : ''}
      </Button>
    )}
    <button
      onClick={fetchDocuments}
      className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${isDarkMode ? 'bg-slate-800 hover:bg-slate-700 text-slate-200' : 'bg-gray-100 hover:bg-gray-200 text-gray-700'}`}
    >
      <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
      Refresh
    </button>
  </div>
</div>

                {/* Filters Panel */}
                {showFilters && (
                  <div className={`p-4 rounded-xl border grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4 ${isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
                    <Select
                      label="Source"
                      value={filters.source}
                      onChange={(v) => setFilters({ ...filters, source: v })}
                      options={[
                        { value: '', label: 'All' },
                        { value: 'EURLEX', label: 'EUR-LEX' },
                        { value: 'JORF', label: 'JORF' },
                      ]}
                      isDarkMode={isDarkMode}
                    />
                    <Select
                      label="Status"
                      value={filters.processing_status}
                      onChange={(v) => setFilters({ ...filters, processing_status: v })}
                      options={[
                        { value: '', label: 'All' },
                        { value: 'pending', label: 'Pending' },
                        { value: 'processed', label: 'Processed' },
                        { value: 'error', label: 'Error' },
                      ]}
                      isDarkMode={isDarkMode}
                    />
                    <Input
                      type="date"
                      label="From"
                      value={filters.date_from}
                      onChange={(v) => setFilters({ ...filters, date_from: v })}
                      isDarkMode={isDarkMode}
                    />
                    <Input
                      type="date"
                      label="To"
                      value={filters.date_to}
                      onChange={(v) => setFilters({ ...filters, date_to: v })}
                      isDarkMode={isDarkMode}
                    />
                    <div className="flex items-end">
                      <button
                        onClick={handleResetFilters}
                        className="w-full px-4 py-2 text-sm text-red-500 hover:bg-red-500/10 rounded-lg transition-colors"
                      >
                        Reset Filters
                      </button>
                    </div>
                  </div>
                )}

                {activeView === 'delete' && (
                  <div className={`p-4 rounded-lg flex items-center gap-3 ${isDarkMode ? 'bg-red-500/10 border border-red-500/30 text-red-200' : 'bg-red-50 border border-red-200 text-red-800'}`}>
                    <AlertCircle className="w-5 h-5" />
                    <div>
                      <p className="text-sm font-semibold">Delete mode</p>
                      <p className="text-xs opacity-80">Select documents and click "Delete Selected" to remove them from the dataset.</p>
                    </div>
                  </div>
                )}

                {activeView === 'delete' && deleteStatus && (
                  <div className={`p-3 rounded-lg text-sm ${deleteStatus.startsWith('Error') ? (isDarkMode ? 'bg-red-500/10 text-red-200 border border-red-500/30' : 'bg-red-50 text-red-800 border border-red-200') : (isDarkMode ? 'bg-green-500/10 text-green-200 border border-green-500/30' : 'bg-green-50 text-green-800 border border-green-200')}`}>
                    {deleteStatus}
                  </div>
                )}

                {/* Documents Table */}
                <div className={`rounded-xl border overflow-hidden ${isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm text-left">
                      <thead className={`text-xs uppercase font-semibold ${isDarkMode ? 'bg-slate-950/50 text-slate-400' : 'bg-gray-50 text-gray-500'}`}>
                        <tr>
                          <th className="px-6 py-4 w-12">
                            <input
                              type="checkbox"
                              checked={selectAllChecked}
                              onChange={toggleSelectAll}
                              className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                              title="Select all visible documents"
                            />
                          </th>
                          <th className="px-6 py-4">Source</th>
                          <th className="px-6 py-4">
                            <button
                              onClick={() => setSortOrder(prev => (prev === 'desc' ? 'asc' : 'desc'))}
                              className="flex items-center gap-2 text-left font-semibold hover:text-blue-500"
                            >
                              Date
                              <span className="text-[10px] uppercase tracking-wide text-gray-400">
                                {sortOrder === 'desc' ? 'Newest' : 'Oldest'}
                              </span>
                            </button>
                          </th>
                          <th className="px-6 py-4 w-1/3">Title</th>
                          <th className="px-6 py-4 w-32">Typologie</th>
                          <th className="px-6 py-4">Status</th>
                          <th className="px-6 py-4">Summary</th>
                          <th className="px-6 py-4">Applicability</th>
                          <th className="px-6 py-4">Themes</th>
                        </tr>
                      </thead>
                      <tbody className={`divide-y ${isDarkMode ? 'divide-slate-800' : 'divide-gray-100'}`}>
                        {loading && documents.length === 0 ? (
                          <tr>
                            <td colSpan={8} className="px-6 py-8 text-center text-gray-500">
                              <RefreshCw className="w-8 h-8 animate-spin text-blue-400 mx-auto mb-2" />
                              Loading documents...
                            </td>
                          </tr>
                        ) : error ? (
                          <tr>
                            <td colSpan={8} className="px-6 py-8">
                              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 flex items-center gap-2 text-red-300">
                                <AlertCircle className="w-5 h-5" />
                                {error}
                              </div>
                            </td>
                          </tr>
                        ) : (
                          documents.map((doc) => (
                            <tr key={doc.id} className={`group transition-colors ${isDarkMode ? 'hover:bg-slate-800/50' : 'hover:bg-gray-50'}`}>
                                  <td className="px-6 py-4">
                                      <input
                                        type="checkbox"
                                        checked={selectedDocIds.has(doc.id)}
                                        onChange={() => toggleDocumentSelection(doc.id)}
                                        className="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer"
                                        onClick={(e) => e.stopPropagation()}
                                      />
                                    </td>
                              <td className="px-6 py-4">
                                <span className={`px-2 py-1 rounded text-xs font-bold ${doc.source === 'EURLEX' ? 'bg-blue-100 text-blue-700 dark:bg-blue-500/20 dark:text-blue-300' : 'bg-purple-100 text-purple-700 dark:bg-purple-500/20 dark:text-purple-300'}`}>
                                  {doc.source}
                                </span>
                              </td>
                              <td className="px-6 py-4 whitespace-nowrap text-gray-500 dark:text-slate-400">{doc.date}</td>
                              <td className="px-6 py-4">
                                <a
                                  href={doc.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="font-medium text-blue-500 hover:underline line-clamp-2 transition-transform duration-150 ease-out hover:scale-[1.02]"
                                >
                                  {doc.titre || 'Untitled Document'}
                                </a>
                              </td>
                              <td className="px-6 py-4 text-sm">
                                <div className="text-sm text-gray-500 mt-1">{doc.typologie}</div>
                              </td>
                              <td className="px-6 py-4">
                                <StatusBadge status={doc.processing_status} />
                              </td>
                              <td className="px-6 py-4">
                                <div className="relative group max-w-xs text-sm text-gray-500 dark:text-slate-400">
                                  <div className="max-h-20 overflow-y-auto line-clamp-3">
                                    {doc.summary ? formatSummary(doc.summary) : <span className="italic opacity-50">No summary</span>}
                                  </div>
                                  {doc.summary && (
                                    <div className="invisible opacity-0 group-hover:visible group-hover:opacity-100 transition-opacity duration-150 absolute z-20 left-0 top-full mt-2 w-72 rounded-lg shadow-lg border text-sm p-3 whitespace-pre-wrap break-words bg-white text-gray-800 border-gray-200 dark:bg-slate-900 dark:text-slate-100 dark:border-slate-700">
                                      {formatSummary(doc.summary)}
                                    </div>
                                  )}
                                </div>
                              </td>
                              <td className="px-6 py-4">
                                  {doc.applicability !== undefined && (
                                      <span className={`inline-block whitespace-nowrap px-2 py-1 rounded text-[10px] ${doc.applicability ? (isDarkMode ? 'bg-slate-800 text-slate-300' : 'bg-gray-100 text-gray-600') : (isDarkMode ? 'bg-gray-500/20 text-gray-300' : 'bg-gray-300 text-gray-700')}`}>
                                          {doc.applicability ? doc.applicability : 'N/A'}
                                      </span>
                                  )}
                              </td>
                              <td className="px-6 py-4">
                                <div className="flex flex-wrap gap-1 max-w-xs">
                                  {getThemesArray(doc.themes).slice(0, 3).map((k, i) => (
                                    <span key={i} className={`text-[10px] px-1.5 py-0.5 rounded ${isDarkMode ? 'bg-slate-800 text-slate-300' : 'bg-gray-100 text-gray-600'}`}>
                                      {k}
                                    </span>
                                  ))}
                                  {getThemesArray(doc.themes).length > 3 && (
                                    <span className="text-[10px] text-gray-400">+{getThemesArray(doc.themes).length - 3}</span>
                                  )}
                                </div>
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>

                  {/* Pagination */}
                  <div className={`px-6 py-4 border-t flex items-center justify-between ${isDarkMode ? 'border-slate-800' : 'border-gray-100'}`}>
                    <span className="text-sm text-gray-500">
                      Showing {pagination.skip + 1}-{Math.min(pagination.skip + pagination.limit, totalDocs)} of {totalDocs}
                    </span>
                    <div className="flex gap-2">
                      <button
                        onClick={() => setPagination(p => ({ ...p, skip: Math.max(0, p.skip - p.limit) }))}
                        disabled={pagination.skip === 0}
                        className={`p-2 rounded-lg border disabled:opacity-50 ${isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-200 hover:bg-gray-100'}`}
                      >
                        <ChevronLeft className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => setPagination(p => ({ ...p, skip: p.skip + p.limit }))}
                        disabled={pagination.skip + pagination.limit >= totalDocs}
                        className={`p-2 rounded-lg border disabled:opacity-50 ${isDarkMode ? 'border-slate-700 hover:bg-slate-800' : 'border-gray-200 hover:bg-gray-100'}`}
                      >
                        <ChevronRight className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeView === 'scrape' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card title="EUR-LEX Scraping" icon={<Download className="w-5 h-5 text-blue-500" />} isDarkMode={isDarkMode}>
  <div className="space-y-4">
    {/* Mode de scraping */}
    <div>
      <label className="block text-xs font-medium mb-2 text-gray-500 dark:text-slate-400 uppercase">
        Scraping Mode
      </label>
      <div className="flex gap-2">
        {[
          { value: 'today', label: "Today" },
          { value: 'date', label: 'Specific Date' },
          { value: 'range', label: 'Date Range' }
        ].map((mode) => (
          <button
            key={mode.value}
            onClick={() => setScrapeMode(mode.value as 'today' | 'date' | 'range')}
            className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-all ${
              scrapeMode === mode.value
                ? 'bg-blue-500 text-white shadow-lg shadow-blue-500/20'
                : isDarkMode 
                  ? 'bg-slate-800 text-slate-300 hover:bg-slate-700' 
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            }`}
          >
            {mode.label}
          </button>
        ))}
      </div>
    </div>

    {/* Date inputs basés sur le mode */}
    {scrapeMode === 'date' && (
      <Input
        type="date"
        label="Date to Scrape"
        value={scrapeDate}
        onChange={setScrapeDate}
        isDarkMode={isDarkMode}
      />
    )}

    {scrapeMode === 'range' && (
      <div className="grid grid-cols-2 gap-3">
        <Input
          type="date"
          label="From"
          value={scrapeDateFrom}
          onChange={setScrapeDateFrom}
          isDarkMode={isDarkMode}
        />
        <Input
          type="date"
          label="To"
          value={scrapeDateTo}
          onChange={setScrapeDateTo}
          isDarkMode={isDarkMode}
        />
      </div>
    )}

    {/* Avertissement pour les intervalles */}
    {scrapeMode === 'range' && (
      <div className={`p-3 rounded-lg text-xs ${isDarkMode ? 'bg-yellow-500/10 text-yellow-300 border border-yellow-500/20' : 'bg-yellow-50 text-yellow-700 border border-yellow-200'}`}>
        <strong>Note:</strong> Maximum 30 days per request. Large ranges may take several minutes.
      </div>
    )}

    {/* Series selection */}
    <Select
      label="Series"
      value={scrapingSeries}
      onChange={(v: string) => setScrapingSeries(v as 'L' | 'C')}
      options={[
        { value: 'L', label: 'L - Legislation' },
        { value: 'C', label: 'C - Information' },
      ]}
      isDarkMode={isDarkMode}
    />

    {/* Scrape details checkbox */}
    <div className="flex items-center gap-2">
      <input
        type="checkbox"
        id="scrapeDetails"
        checked={scrapeDetails}
        onChange={(e) => setScrapeDetails(e.target.checked)}
        className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
      />
      <label htmlFor="scrapeDetails" className="text-sm text-gray-600 dark:text-slate-300">
        Scrape full content details
      </label>
    </div>

    {/* Progress bar pour le mode range */}
    {scrapeProgress && (
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-gray-500 dark:text-slate-400">
          <span>Day {scrapeProgress.current} / {scrapeProgress.total}</span>
          <span>{scrapeProgress.currentDate}</span>
        </div>
        <div className={`h-2 rounded-full overflow-hidden ${isDarkMode ? 'bg-slate-700' : 'bg-gray-200'}`}>
          <div 
            className="h-full bg-blue-500 transition-all duration-300 ease-out"
            style={{ width: `${(scrapeProgress.current / scrapeProgress.total) * 100}%` }}
          />
        </div>
        <p className="text-xs text-center text-gray-500 dark:text-slate-400">
          {scrapeProgress.status}
        </p>
      </div>
    )}

    {/* Start button */}
    <Button 
      onClick={scrapeEURLex} 
      loading={loading} 
      variant="primary"
      disabled={
        (scrapeMode === 'date' && !scrapeDate) ||
        (scrapeMode === 'range' && (!scrapeDateFrom || !scrapeDateTo))
      }
    >
      {scrapeMode === 'range' ? 'Start Range Scraping' : 'Start Scraping'}
    </Button>
  </div>
</Card>

                <Card title="JORF Email Parsing" icon={<Upload className="w-5 h-5 text-purple-500" />} isDarkMode={isDarkMode}>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium mb-1.5 text-gray-700 dark:text-slate-300">
                        Email Content
                      </label>
                      <textarea
                        value={jorfEmail}
                        onChange={(e) => setJorfEmail(e.target.value)}
                        placeholder="Paste the JORF email content here..."
                        className={`w-full h-32 rounded-lg border p-3 text-sm font-mono focus:ring-2 focus:ring-purple-500 outline-none ${isDarkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-gray-300'}`}
                      />
                    </div>
                    <Button onClick={scrapeJORF} loading={loading} variant="secondary" disabled={!jorfEmail.trim()}>
                      Parse Email
                    </Button>
                  </div>
                </Card>

                {scrapeStatus && (
                  <div className={`lg:col-span-2 p-4 rounded-lg flex items-center gap-3 ${
                    scrapeStatus.startsWith('Success')
                      ? 'bg-green-100 text-green-800 dark:bg-green-500/20 dark:text-green-300'
                      : 'bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-300'
                  }`}>
                    {scrapeStatus.startsWith('Success') ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                    <span className="font-medium">{scrapeStatus}</span>
                  </div>
                )}
              </div>
            )}

            {activeView === 'process' && (
              <div className="max-w-2xl mx-auto">
                <Card title="LLM Processing" icon={<Activity className="w-5 h-5 text-green-500" />} isDarkMode={isDarkMode}>
                  <div className="space-y-6">
                    <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-500/10 border border-blue-100 dark:border-blue-500/20">
                      <h4 className="text-sm font-semibold text-blue-800 dark:text-blue-300 mb-1">How it works</h4>
                      <p className="text-xs text-blue-600 dark:text-blue-400">
                        This process sends pending documents to the LLM for summarization and keyword extraction. It processes documents in batches to respect API limits.
                      </p>
                    </div>

                    <div>
                      <label className="block text-sm font-medium mb-1.5 text-gray-700 dark:text-slate-300">
                        Batch Size
                      </label>
                      <div className="flex items-center gap-4">
                        <input
                          type="range"
                          min="1"
                          max="50"
                          value={batchSize}
                          onChange={(e) => setBatchSize(parseInt(e.target.value))}
                          className="flex-1 h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer dark:bg-slate-700"
                        />
                        <span className={`px-3 py-1 rounded-md text-sm font-mono border ${isDarkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-gray-200'}`}>
                          {batchSize} docs
                        </span>
                      </div>
                    </div>

                    <Button onClick={processDocuments} loading={loading} variant="success" className="w-full">
                      Start Processing
                    </Button>

                    {processStatus && (
                      <div className={`mt-4 p-4 rounded-lg flex items-center gap-3 ${
                        processStatus.startsWith('Success')
                          ? 'bg-green-100 text-green-800 dark:bg-green-500/20 dark:text-green-300'
                          : 'bg-red-100 text-red-800 dark:bg-red-500/20 dark:text-red-300'
                      }`}>
                        {processStatus.startsWith('Success') ? <CheckCircle className="w-5 h-5" /> : <AlertCircle className="w-5 h-5" />}
                        <span className="font-medium">{processStatus}</span>
                      </div>
                    )}
                  </div>
                </Card>
              </div>
            )}

            {activeView === 'setup' && (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                <Card title="Themes (values only)" icon={<Settings className="w-5 h-5 text-amber-500" />} isDarkMode={isDarkMode}>
                  <div className="space-y-4">
                    <div className="flex flex-col gap-3">
                      {themeValues.map((val, idx) => (
                        <div key={`${val}-${idx}`} className="flex gap-2 items-start">
                          <input
                            value={val}
                            onChange={(e) => handleThemeValueChange(idx, e.target.value)}
                            className={`w-full px-3 py-2 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-amber-500 ${isDarkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-gray-300'}`}
                          />
                          <button onClick={() => removeThemeValue(idx)} className="text-xs text-red-500 hover:text-red-600 px-2 py-2">✕</button>
                        </div>
                      ))}
                      {themeValues.length === 0 && <span className="text-sm text-gray-400">No themes loaded yet.</span>}
                    </div>
                    <div className="flex gap-2">
                      <input
                        value={newThemeValues}
                        onChange={(e) => setNewThemeValues(e.target.value)}
                        placeholder="Themes (comma separated)"
                        className={`w-full px-3 py-2 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-amber-500 ${isDarkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-gray-300'}`}
                      />
                      <Button onClick={addThemeValue} variant="export">Add</Button>
                    </div>
                  </div>
                </Card>

                <Card title="Applicability (values only)" icon={<Settings className="w-5 h-5 text-amber-500" />} isDarkMode={isDarkMode}>
                  <div className="space-y-4">
                    <div className="flex flex-col gap-3">
                      {applicabilityValues.map((val, idx) => (
                        <div key={`${val}-${idx}`} className="flex gap-2 items-start">
                          <input
                            value={val}
                            onChange={(e) => handleAppValueChange(idx, e.target.value)}
                            className={`w-full px-3 py-2 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-amber-500 ${isDarkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-gray-300'}`}
                          />
                          <button onClick={() => removeAppValue(idx)} className="text-xs text-red-500 hover:text-red-600 px-2 py-2">✕</button>
                        </div>
                      ))}
                      {applicabilityValues.length === 0 && <span className="text-sm text-gray-400">No applicability values loaded yet.</span>}
                    </div>
                    <div className="flex gap-2">
                      <input
                        value={newAppValues}
                        onChange={(e) => setNewAppValues(e.target.value)}
                        placeholder="Applicability (comma separated)"
                        className={`w-full px-3 py-2 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-amber-500 ${isDarkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-gray-300'}`}
                      />
                      <Button onClick={addAppValue} variant="export">Add</Button>
                    </div>
                  </div>
                </Card>

                <div className="lg:col-span-2 flex flex-wrap gap-3">
                  <Button onClick={fetchClassificationConfig} variant="secondary">Reset from backend defaults</Button>
                  <Button onClick={clearSavedConfig} variant="danger">
                    Clear saved config
                  </Button>
                </div>
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}

// UI Components

type StatCardProps = {
  title: string;
  value: number | string;
  icon: ReactNode;
  color: 'blue' | 'green' | 'yellow' | 'purple';
  isDarkMode: boolean;
};

function StatCard({ title, value, icon, color, isDarkMode }: StatCardProps) {
  const colors = {
    blue: 'text-blue-500 bg-blue-500/10',
    green: 'text-green-500 bg-green-500/10',
    yellow: 'text-yellow-500 bg-yellow-500/10',
    purple: 'text-purple-500 bg-purple-500/10',
  };

  return (
    <div className={`p-5 rounded-xl border transition-all hover:shadow-md ${isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
      <div className="flex items-center justify-between mb-4">
        <span className="text-sm font-medium text-gray-500 dark:text-slate-400">{title}</span>
        <div className={`p-2 rounded-lg ${colors[color as keyof typeof colors]}`}>{icon}</div>
      </div>
      <div className="text-2xl font-bold tracking-tight">{value}</div>
    </div>
  );
}

type CardProps = {
  title: string;
  icon: ReactNode;
  children: ReactNode;
  isDarkMode: boolean;
};

function Card({ title, icon, children, isDarkMode }: CardProps) {
  return (
    <div className={`rounded-xl border overflow-hidden ${isDarkMode ? 'bg-slate-900 border-slate-800' : 'bg-white border-gray-200'}`}>
      <div className={`px-6 py-4 border-b flex items-center gap-3 ${isDarkMode ? 'border-slate-800' : 'border-gray-100'}`}>
        {icon}
        <h3 className="font-semibold">{title}</h3>
      </div>
      <div className="p-6">{children}</div>
    </div>
  );
}

type SelectOption = { value: string; label: string };
type SelectProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: SelectOption[];
  isDarkMode: boolean;
};

function Select({ label, value, onChange, options, isDarkMode }: SelectProps) {
  return (
    <div>
      <label className="block text-xs font-medium mb-1.5 text-gray-500 dark:text-slate-400 uppercase">{label}</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full px-3 py-2 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500 ${isDarkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-gray-300'}`}
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </div>
  );
}

type InputProps = {
  type: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  isDarkMode: boolean;
};

function Input({ type, label, value, onChange, isDarkMode }: InputProps) {
  const isDate = type === 'date';
  return (
    <div>
      <label className="block text-xs font-medium mb-1.5 text-gray-500 dark:text-slate-400 uppercase">{label}</label>
      <input
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={`w-full px-3 py-2 rounded-lg text-sm border outline-none focus:ring-2 focus:ring-blue-500 ${isDarkMode ? 'bg-slate-950 border-slate-700' : 'bg-white border-gray-300'} ${isDate ? 'appearance-auto' : ''}`}
      />
    </div>
  );
}

type ButtonVariant = 'primary' | 'secondary' | 'success' | 'export' | 'danger';
type ButtonProps = {
  children: ReactNode;
  onClick: () => void;
  loading?: boolean;
  variant?: ButtonVariant;
  disabled?: boolean;
  className?: string;
};

function Button({ children, onClick, loading, variant = 'primary', disabled, className = '' }: ButtonProps) {
  const variants = {
    primary: 'bg-blue-600 hover:bg-blue-700 text-white shadow-blue-500/20',
    secondary: 'bg-purple-600 hover:bg-purple-700 text-white shadow-purple-500/20',
    success: 'bg-green-600 hover:bg-green-700 text-white shadow-green-500/20',
    export: 'bg-amber-600 hover:bg-amber-700 text-white shadow-amber-500/20',
    danger: 'bg-red-600 hover:bg-red-700 text-white shadow-red-500/20',
  };

  return (
    <button
      onClick={onClick}
      disabled={loading || disabled}
      className={`px-4 py-2.5 rounded-lg font-medium transition-all shadow-lg active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 ${variants[variant as keyof typeof variants]} ${className}`}
    >
      {loading && <RefreshCw className="w-4 h-4 animate-spin" />}
      {children}
    </button>
  );
}
