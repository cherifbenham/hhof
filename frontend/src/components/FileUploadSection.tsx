import { useState } from 'react';
import { Upload } from 'lucide-react';

export function FileUploadSection() {
  const [excelFile, setExcelFile] = useState<string | null>(null);
  const [emailFiles, setEmailFiles] = useState<string[]>([]);

  const handleExcelChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setExcelFile(e.target.files[0].name);
    }
  };

  const handleEmailChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setEmailFiles(Array.from(e.target.files).map(f => f.name));
    }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* Excel Upload */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
        <div>
          <h3 className="font-semibold text-white mb-2">Upload Excel file</h3>
          <label className="relative inline-block">
            <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded font-medium transition-colors flex items-center gap-2">
              <Upload size={16} />
              Choose File
            </button>
            <input
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleExcelChange}
              className="absolute inset-0 opacity-0 cursor-pointer"
            />
          </label>
          <p className="text-sm text-slate-400 mt-2">
            {excelFile ? excelFile : 'No file chosen'}
          </p>
        </div>
        <p className="text-xs text-slate-400">
          Upload an Excel file with columns: date, url, title, abstract, class_daily.
        </p>
        <p className="text-xs text-slate-500">
          Gemini classification options: General Industry News, Competitors, M&A & Investments, Travel Providers, Financial Reports / Info, Research & Reports.
        </p>
      </div>

      {/* Email Upload */}
      <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
        <div>
          <h3 className="font-semibold text-white mb-2">Upload Email files (.eml)</h3>
          <label className="relative inline-block">
            <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded font-medium transition-colors flex items-center gap-2">
              <Upload size={16} />
              Choose Files
            </button>
            <input
              type="file"
              multiple
              accept=".eml"
              onChange={handleEmailChange}
              className="absolute inset-0 opacity-0 cursor-pointer"
            />
          </label>
          <p className="text-sm text-slate-400 mt-2">
            {emailFiles.length > 0 ? emailFiles.slice(0, 2).join(', ') + (emailFiles.length > 2 ? ` +${emailFiles.length - 2} more` : '') : 'No files chosen'}
          </p>
        </div>
        <p className="text-xs text-slate-400">
          Upload Industry News Review emails (.eml files) to extract and process news items.
        </p>
      </div>
    </div>
  );
}
