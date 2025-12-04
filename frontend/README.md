# HHOF Frontend (React + Vite)

Dashboard for monitoring the legal document ingestion pipeline. It consumes the FastAPI backend and surfaces scraping controls, LLM processing, filters, and CSV exports.

## Development
- Install deps: `npm install`
 - Configure API URL: copy `.env.example` to `.env` and set `VITE_API_BASE_URL` (falls back to the current origin or `http://localhost:8000`)
- Run dev server: `npm run dev` (Vite on port 5173)

## Build for the FastAPI host
- `npm run build` generates `dist/` with `base` set to `/app/`
- The backend serves the static build at `/app` when `dist/` exists

## Notable features
- Document table with filters, pagination, and selection
- CSV export (all or selected rows)
- Triggers for EUR-LEX and JORF scraping flows
- Manual LLM processing with batch size control and progress status
