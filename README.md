# AI Resume Optimizer (MVP)

A truthful ATS-oriented resume tailoring tool.

## What it does
- Accepts resume text + job description.
- Parses uploaded PDF/DOCX resumes into text.
- Extracts and reports keyword coverage.
- Uses OpenAI to generate an ATS-friendly rewrite.
- Exports the optimized resume as a downloadable PDF.
- Falls back to manual-guidance mode if OpenAI config is missing.

## Stack
- FastAPI backend
- Vanilla HTML/CSS/JS frontend served by FastAPI

## Setup
1. Create and activate a Python virtual environment.
2. Install dependencies:
   ```bash
   pip install -r backend/requirements.txt
   ```
   Install PDF browser runtime once:
   ```bash
   python -m playwright install chromium
   ```
3. Configure environment:
   ```bash
   cp .env.example .env
   ```
   Add your API key to `.env`. The app auto-loads this file at runtime.

4. Run server:
   ```bash
   uvicorn backend.app.main:app --reload
   ```

5. Open:
   - http://127.0.0.1:8000

## API
### `POST /api/optimize`
Request:
```json
{
  "resume_text": "...",
  "job_description": "..."
}
```

Response includes:
- `optimized_resume`
- `summary`
- `keyword_report`
- `warnings`
- `mode` (`llm` or `fallback`)

### `POST /api/parse-resume`
Multipart form upload:
- field name: `file`
- supported types: `.pdf`, `.docx`

Response includes:
- `filename`
- `extracted_text`
- `chars`

### `POST /api/export-pdf`
Request:
```json
{
  "optimized_resume": "...",
  "filename": "optimized_resume"
}
```

Response:
- PDF file download (`application/pdf`)
- Deterministic HTML/CSS template rendering is used first; ReportLab fallback is used if needed.

## Important constraints
- The tool is designed to avoid fabricating experience.
- Users should verify every generated statement before submitting.
