export function Header() {
    return (
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-white">Compose Your Weekly</h1>
        <p className="text-sm text-slate-400">
          Upload an Excel workbook with columns such as date, url, class_daily, title, and abstract. Gemini will provide an initial comment and classification. You can overwrite the comment by adding your own CI insight—the exported report will always use the CI comment when present.
        </p>
      </div>
    );
  }
  