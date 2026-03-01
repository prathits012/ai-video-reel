"""
Job store: in-memory store for video generation jobs.
Each job tracks status, progress steps, and the output filename when done.
"""

import threading
import uuid
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Job:
    id: str
    status: Literal["pending", "running", "done", "failed"] = "pending"
    progress: str = "Queued..."
    steps: list[str] = field(default_factory=list)
    video_filename: str | None = None
    error: str | None = None


_store: dict[str, Job] = {}
_lock = threading.Lock()


def create_job() -> Job:
    job = Job(id=str(uuid.uuid4()))
    with _lock:
        _store[job.id] = job
    return job


def get_job(job_id: str) -> Job | None:
    with _lock:
        return _store.get(job_id)


def update_job(job_id: str, **kwargs) -> None:
    with _lock:
        job = _store.get(job_id)
        if job:
            for key, value in kwargs.items():
                setattr(job, key, value)


def append_step(job_id: str, step: str) -> None:
    with _lock:
        job = _store.get(job_id)
        if job:
            job.steps.append(step)
            job.progress = step
