from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .services.optimizer import optimize_resume
from .services.pdf_export import build_resume_pdf
from .services.resume_parser import parse_resume_file
from .services.template_pdf_export import build_resume_pdf_from_template


class OptimizeRequest(BaseModel):
    resume_text: str = Field(min_length=20)
    job_description: str = Field(min_length=20)


class KeywordReport(BaseModel):
    required_keywords: list[str]
    present_keywords: list[str]
    missing_keywords: list[str]
    coverage_pct: float


class OptimizeResponse(BaseModel):
    optimized_resume: str
    summary: str
    keyword_report: KeywordReport
    warnings: list[str]
    mode: str


class ParseResumeResponse(BaseModel):
    filename: str
    extracted_text: str
    chars: int


class ExportPdfRequest(BaseModel):
    optimized_resume: str = Field(min_length=20)
    filename: str = Field(default="optimized_resume")


app = FastAPI(title="AI Resume Optimizer", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/optimize", response_model=OptimizeResponse)
def optimize(payload: OptimizeRequest) -> OptimizeResponse:
    try:
        result = optimize_resume(payload.resume_text, payload.job_description)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Optimization failed") from err

    return OptimizeResponse(**result)


@app.post("/api/parse-resume", response_model=ParseResumeResponse)
async def parse_resume(file: UploadFile = File(...)) -> ParseResumeResponse:
    try:
        content = await file.read()
        extracted = parse_resume_file(file.filename or "resume", content)
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception as err:  # pragma: no cover
        raise HTTPException(status_code=500, detail="Failed to parse resume file") from err

    return ParseResumeResponse(
        filename=file.filename or "resume",
        extracted_text=extracted,
        chars=len(extracted),
    )


@app.post("/api/export-pdf")
def export_pdf(payload: ExportPdfRequest) -> StreamingResponse:
    try:
        pdf_bytes, safe_filename = build_resume_pdf_from_template(
            payload.optimized_resume, payload.filename
        )
    except ValueError as err:
        raise HTTPException(status_code=400, detail=str(err)) from err
    except Exception:
        # Fallback to the previous renderer if Playwright template export fails.
        try:
            pdf_bytes, safe_filename = build_resume_pdf(
                payload.optimized_resume, payload.filename
            )
        except Exception as err:  # pragma: no cover
            raise HTTPException(status_code=500, detail="Failed to generate PDF") from err

    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{safe_filename}"'},
    )


app.mount("/", StaticFiles(directory="backend/app/static", html=True), name="static")
