import { useState } from 'react';

interface NewsItem {
  id: string;
  keep: boolean;
  date: string;
  title: string;
  classDaily: string;
  abstract: string;
  geminClassification: string;
  geminComment: string;
  geminSimilarity: number;
  ciSimilarity: number;
  finalComment: string;
}

interface Props {
  items: NewsItem[];
  minSimilarity: string;
  onKeepToggle: (id: string) => void;
  onUpdateItem: (id: string, updates: Partial<NewsItem>) => void;
  onExportExcel: () => void;
  onExportHTML: () => void;
  onMinSimilarityChange: (value: string) => void;
}

const classifications = [
  'General Industry News',
  'Competitors',
  'M&A & Investments',
  'Travel Providers',
  'Financial Reports / Info',
  'Research & Reports',
];

export function NewsItemsTable({
  items,
  minSimilarity,
  onKeepToggle,
  onUpdateItem,
  onExportExcel,
  onExportHTML,
  onMinSimilarityChange,
}: Props) {
  const [expandedId, setExpandedId] = useState<string | null>(null);

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-6 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-xl font-semibold text-white">News Items</h2>
          <p className="text-sm text-slate-400 mt-1">
            Gemini comment and classification are loaded. Add CI comments to tailor the newsletter—these will be used when exporting.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <label className="text-sm text-slate-400">Min Similarity:</label>
            <select
              value={minSimilarity}
              onChange={(e) => onMinSimilarityChange(e.target.value)}
              className="bg-slate-700 border border-slate-600 text-white px-3 py-1 rounded text-sm"
            >
              <option>Any</option>
              <option>75+</option>
              <option>80+</option>
              <option>85+</option>
            </select>
          </div>
          <button
            onClick={onExportExcel}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded font-medium text-sm transition-colors"
          >
            Export Excel
          </button>
          <button
            onClick={onExportHTML}
            className="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded font-medium text-sm transition-colors"
          >
            Export HTML
          </button>
          <button className="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded font-medium text-sm transition-colors">
            Generating...
          </button>
        </div>
      </div>

      {/* Table */}
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-slate-700">
              <th className="text-left py-3 px-3 font-semibold text-slate-300 w-12">Keep?</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300">Date</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300 min-w-64">Title</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300 w-24">Class Daily</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300 min-w-48">Abstract</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300">Gemini - Classification</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300 min-w-56">Gemini - Comment</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300">Gemini - Similarity</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300">CI - Similarity</th>
              <th className="text-left py-3 px-3 font-semibold text-slate-300 min-w-48">Final Comment</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b border-slate-700 hover:bg-slate-700/50">
                <td className="py-3 px-3">
                  <input
                    type="checkbox"
                    checked={item.keep}
                    onChange={() => onKeepToggle(item.id)}
                    className="w-4 h-4 rounded accent-blue-500 cursor-pointer"
                  />
                </td>
                <td className="py-3 px-3 text-slate-300">{item.date}</td>
                <td className="py-3 px-3 relative group">
                  <a href="#" className="text-blue-400 hover:underline truncate block max-w-xs">
                    {item.title}
                  </a>
                  <div className="absolute left-0 top-full mt-1 hidden group-hover:block bg-slate-900 border border-slate-700 rounded p-3 shadow-xl z-10 min-w-[400px] max-w-2xl">
                    <p className="text-blue-400 text-sm whitespace-normal">{item.title}</p>
                  </div>
                </td>
                <td className="py-3 px-3 text-slate-300 w-24 text-xs truncate">{item.classDaily}</td>
                <td className="py-3 px-3 text-slate-400 text-xs max-w-xs truncate">{item.abstract}</td>
                <td className="py-3 px-3">
                  <select
                    value={item.geminClassification}
                    onChange={(e) => onUpdateItem(item.id, { geminClassification: e.target.value })}
                    className="bg-slate-700 border border-slate-600 text-white px-2 py-1 rounded text-xs w-full"
                  >
                    {classifications.map(c => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                </td>
                <td className="py-3 px-3 text-slate-300 text-xs max-w-xs truncate">{item.geminComment}</td>
                <td className="py-3 px-3 text-slate-300">{item.geminSimilarity}</td>
                <td className="py-3 px-3">
                  <button
                    onClick={() => setExpandedId(expandedId === item.id ? null : item.id)}
                    className="bg-slate-700 hover:bg-slate-600 text-white px-2 py-1 rounded text-xs transition-colors"
                  >
                    {expandedId === item.id ? 'Hide' : 'Add your CI Insight...'}
                  </button>
                </td>
                <td className="py-3 px-3">
                  <textarea
                    value={item.finalComment}
                    onChange={(e) => onUpdateItem(item.id, { finalComment: e.target.value })}
                    className="bg-slate-700 border border-slate-600 text-white px-2 py-1 rounded text-xs w-full h-12 resize-none font-mono"
                    placeholder="Add comment..."
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
