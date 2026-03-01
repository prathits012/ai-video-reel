"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const DURATIONS = [20, 30, 45];

export default function PromptForm() {
  const router = useRouter();
  const [prompt, setPrompt] = useState("");
  const [mode, setMode] = useState<"standard" | "hamilton">("standard");
  const [duration, setDuration] = useState(30);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;

    setLoading(true);
    setError(null);

    try {
      const res = await fetch("http://localhost:8000/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: prompt.trim(), mode, duration }),
      });

      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data?.detail || "Failed to start generation");
      }

      const { job_id } = await res.json();
      router.push(`/result/${job_id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong");
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[70vh]">
      {/* Hero text */}
      <div className="text-center mb-10">
        <h1 className="text-4xl font-bold tracking-tight text-white mb-3">
          Turn any topic into a reel
        </h1>
        <p className="text-white/40 text-lg">
          AI-generated short educational videos, ready in under 3 minutes
        </p>
      </div>

      {/* Form card */}
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-xl bg-white/[0.03] border border-white/8 rounded-2xl p-8 flex flex-col gap-6"
      >
        {/* Prompt input */}
        <div className="flex flex-col gap-2">
          <label className="text-sm text-white/50 font-medium">Topic</label>
          <textarea
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder="How do volcanoes erupt?"
            rows={3}
            className="w-full bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-white placeholder-white/20 text-base resize-none focus:outline-none focus:ring-1 focus:ring-white/20 transition"
          />
        </div>

        {/* Mode toggle */}
        <div className="flex flex-col gap-2">
          <label className="text-sm text-white/50 font-medium">Style</label>
          <div className="flex gap-2">
            {(["standard", "hamilton"] as const).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => setMode(m)}
                className={`flex-1 py-2.5 px-4 rounded-xl text-sm font-medium border transition ${
                  mode === m
                    ? "bg-white text-black border-white"
                    : "bg-white/5 text-white/50 border-white/10 hover:border-white/20 hover:text-white/70"
                }`}
              >
                {m === "standard" ? "Standard" : "Hamilton ♪"}
              </button>
            ))}
          </div>
          <p className="text-xs text-white/25">
            {mode === "hamilton"
              ? "Musical reel — ElevenLabs generates a full song with female vocals"
              : "Educational reel — stock footage with text overlay"}
          </p>
        </div>

        {/* Duration selector */}
        <div className="flex flex-col gap-2">
          <label className="text-sm text-white/50 font-medium">Duration</label>
          <div className="flex gap-2">
            {DURATIONS.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDuration(d)}
                className={`flex-1 py-2 rounded-xl text-sm font-medium border transition ${
                  duration === d
                    ? "bg-white text-black border-white"
                    : "bg-white/5 text-white/50 border-white/10 hover:border-white/20 hover:text-white/70"
                }`}
              >
                {d}s
              </button>
            ))}
          </div>
        </div>

        {/* Error */}
        {error && (
          <p className="text-red-400 text-sm bg-red-400/10 border border-red-400/20 rounded-lg px-4 py-3">
            {error}
          </p>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={loading || !prompt.trim()}
          className="w-full py-3.5 rounded-xl font-semibold text-base bg-white text-black hover:bg-white/90 disabled:opacity-40 disabled:cursor-not-allowed transition"
        >
          {loading ? "Starting..." : "Generate Video →"}
        </button>
      </form>
    </div>
  );
}
