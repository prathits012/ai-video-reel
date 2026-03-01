"""
FastAPI backend for the AI Reels web app.

Endpoints:
  POST /api/generate          — start a video generation job
  GET  /api/jobs/{job_id}     — poll job status + progress
  GET  /videos/{filename}     — serve a finished video from output/
  GET  /api/health            — health check
"""

import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

# Ensure project root is importable (handles `uvicorn api.main:app` from project root)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

OUTPUT_DIR = PROJECT_ROOT / "output"

from api.jobs import create_job, get_job
from api.pipeline_runner import start_pipeline

app = FastAPI(title="AI Reels API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    # Allow any localhost port so Next.js dev server works on 3000 or 3001
    allow_origin_regex=r"http://localhost:\d+",
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=300)
    mode: str = Field("standard", pattern="^(standard|hamilton)$")
    duration: int = Field(30, ge=10, le=60)


class GenerateResponse(BaseModel):
    job_id: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: str
    progress: str
    steps: list[str]
    video_url: str | None
    error: str | None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/generate", response_model=GenerateResponse)
def generate(req: GenerateRequest):
    job = create_job()
    start_pipeline(
        job_id=job.id,
        prompt=req.prompt,
        mode=req.mode,
        duration=req.duration,
    )
    return GenerateResponse(job_id=job.id)


@app.get("/api/jobs/{job_id}", response_model=JobStatusResponse)
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    video_url = None
    if job.status == "done" and job.video_filename:
        video_url = f"http://localhost:8000/videos/{job.video_filename}"

    return JobStatusResponse(
        job_id=job.id,
        status=job.status,
        progress=job.progress,
        steps=job.steps,
        video_url=video_url,
        error=job.error,
    )


@app.get("/videos/{filename}")
def serve_video(filename: str):
    # Prevent path traversal
    safe_name = Path(filename).name
    video_path = OUTPUT_DIR / safe_name
    if not video_path.exists() or not video_path.is_file():
        raise HTTPException(status_code=404, detail="Video not found")
    return FileResponse(
        path=str(video_path),
        media_type="video/mp4",
        filename=safe_name,
    )
