"""
Pipeline runner: executes the video generation pipeline in a background thread.
Intercepts print() output from run.py to drive job progress updates.
"""

import io
import sys
import threading
from pathlib import Path

from api.jobs import append_step, update_job

# Maps substrings from pipeline print() output to human-readable step labels.
# Checked in order — first match wins.
STEP_MAP = [
    ("Generating script", "Writing script..."),
    ("Generating lyrical", "Writing lyrical script..."),
    ("ElevenLabs: generating", "Generating music..."),
    ("ElevenLabs:", "Music ready"),
    ("Scout:", "Selecting footage..."),
    ("Director:", "Assembling clips..."),
    ("Polish:", "Adding captions and audio..."),
    ("Safety:", "Running safety check..."),
    ("Done:", "Finishing up..."),
]


class _ProgressWriter(io.TextIOBase):
    """Captures print() calls from the pipeline and maps them to progress steps."""

    def __init__(self, job_id: str, original_stdout: io.TextIOBase):
        self.job_id = job_id
        self.original = original_stdout

    def write(self, text: str) -> int:
        if text and text.strip():
            for keyword, label in STEP_MAP:
                if keyword.lower() in text.lower():
                    append_step(self.job_id, label)
                    break
        # Always forward to the real stdout so the server terminal stays readable
        self.original.write(text)
        return len(text)

    def flush(self) -> None:
        self.original.flush()


def _run(job_id: str, prompt: str, mode: str, duration: int) -> None:
    """Runs inside a daemon thread. Updates job status throughout."""
    import sys
    from pathlib import Path

    # Insert project root so imports work regardless of cwd
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    update_job(job_id, status="running", progress="Starting...")

    original_stdout = sys.stdout
    sys.stdout = _ProgressWriter(job_id, original_stdout)

    try:
        if mode == "hamilton":
            from run import run_hamilton
            out_path = run_hamilton(prompt, duration=duration)
        else:
            from run import run
            out_path = run(prompt, duration=duration)

        update_job(
            job_id,
            status="done",
            progress="Done",
            video_filename=out_path.name,
        )
        append_step(job_id, "Done!")
    except Exception as exc:
        update_job(job_id, status="failed", error=str(exc), progress="Failed")
    finally:
        sys.stdout = original_stdout


def start_pipeline(job_id: str, prompt: str, mode: str, duration: int) -> None:
    """Launches the pipeline in a background daemon thread."""
    t = threading.Thread(
        target=_run,
        args=(job_id, prompt, mode, duration),
        daemon=True,
    )
    t.start()
