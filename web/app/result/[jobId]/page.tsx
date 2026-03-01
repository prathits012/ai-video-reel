"use client";

import { useEffect, useRef, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import ProgressSteps from "@/components/ProgressSteps";
import VideoPlayer from "@/components/VideoPlayer";

type JobStatus = {
  job_id: string;
  status: "pending" | "running" | "done" | "failed";
  progress: string;
  steps: string[];
  video_url: string | null;
  error: string | null;
};

const POLL_INTERVAL_MS = 3000;

export default function ResultPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const router = useRouter();
  const [job, setJob] = useState<JobStatus | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    async function poll() {
      try {
        const res = await fetch(`http://localhost:8000/api/jobs/${jobId}`);
        if (res.status === 404) {
          setFetchError("Job not found. It may have expired.");
          stopPolling();
          return;
        }
        const data: JobStatus = await res.json();
        setJob(data);

        if (data.status === "done" || data.status === "failed") {
          stopPolling();
        }
      } catch {
        setFetchError("Cannot reach the backend. Is the API server running?");
        stopPolling();
      }
    }

    function stopPolling() {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    }

    poll(); // immediate first call
    intervalRef.current = setInterval(poll, POLL_INTERVAL_MS);
    return stopPolling;
  }, [jobId]);

  // ---- Loading state ----
  if (!job && !fetchError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4">
        <div className="w-6 h-6 border-2 border-white/20 border-t-white rounded-full animate-spin" />
        <p className="text-white/40 text-sm">Connecting...</p>
      </div>
    );
  }

  // ---- Error fetching job ----
  if (fetchError) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center">
        <p className="text-red-400">{fetchError}</p>
        <button
          onClick={() => router.push("/")}
          className="text-white/50 text-sm underline hover:text-white transition"
        >
          Back to home
        </button>
      </div>
    );
  }

  // ---- Done ----
  if (job?.status === "done" && job.video_url) {
    const filename = job.video_url.split("/").pop() ?? "reel.mp4";
    return (
      <div className="flex flex-col items-center gap-10">
        <div className="text-center">
          <h2 className="text-2xl font-bold text-white mb-2">Your reel is ready</h2>
          <p className="text-white/40 text-sm">Plays inline · Download to save</p>
        </div>

        <VideoPlayer videoUrl={job.video_url} filename={filename} />

        <button
          onClick={() => router.push("/")}
          className="text-white/40 text-sm hover:text-white transition"
        >
          ← Generate another
        </button>
      </div>
    );
  }

  // ---- Failed ----
  if (job?.status === "failed") {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-4 text-center">
        <p className="text-red-400 text-lg font-medium">Generation failed</p>
        {job.error && (
          <p className="text-white/30 text-sm max-w-md font-mono bg-white/5 rounded-lg px-4 py-3">
            {job.error}
          </p>
        )}
        <button
          onClick={() => router.push("/")}
          className="mt-2 text-white/50 text-sm underline hover:text-white transition"
        >
          Try again
        </button>
      </div>
    );
  }

  // ---- In progress ----
  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] gap-10">
      <div className="text-center">
        <h2 className="text-2xl font-bold text-white mb-2">Generating your reel</h2>
        <p className="text-white/40 text-sm">
          This usually takes 1–3 minutes. Keep this tab open.
        </p>
      </div>

      <ProgressSteps
        steps={job?.steps ?? []}
        currentStep={job?.progress ?? "Starting..."}
        status={job?.status ?? "pending"}
      />

      <p className="text-white/20 text-xs">Job · {jobId}</p>
    </div>
  );
}
