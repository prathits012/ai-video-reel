"use client";

// The canonical ordered list of pipeline steps shown to the user.
const PIPELINE_STEPS = [
  "Writing script...",
  "Writing lyrical script...",
  "Generating music...",
  "Selecting footage...",
  "Assembling clips...",
  "Adding captions and audio...",
  "Running safety check...",
  "Done!",
];

// Collapse lyrical/standard variants so we show a single "Writing script..." row.
function normalizeStep(step: string): string {
  if (step.startsWith("Writing")) return "Writing script...";
  return step;
}

type Props = {
  steps: string[];       // completed step labels from the API
  currentStep: string;   // the currently-in-progress label
  status: string;
};

export default function ProgressSteps({ steps, currentStep, status }: Props) {
  const completedNormalized = new Set(steps.map(normalizeStep));
  const currentNormalized = normalizeStep(currentStep);

  // Deduplicated display steps: collapse lyrical variant
  const displaySteps = PIPELINE_STEPS.filter(
    (s) => s !== "Writing lyrical script..."
  );

  return (
    <div className="flex flex-col gap-3 w-full max-w-sm">
      {displaySteps.map((step) => {
        const isDone = completedNormalized.has(normalizeStep(step));
        const isActive =
          !isDone && normalizeStep(currentNormalized) === normalizeStep(step);
        const isPending = !isDone && !isActive;

        return (
          <div key={step} className="flex items-center gap-3">
            {/* Status icon */}
            <div className="w-6 h-6 flex items-center justify-center flex-shrink-0">
              {isDone ? (
                <span className="text-emerald-400 text-base">✓</span>
              ) : isActive ? (
                <span className="text-white/80 text-base animate-spin inline-block">⟳</span>
              ) : (
                <span className="w-1.5 h-1.5 rounded-full bg-white/15 inline-block" />
              )}
            </div>
            {/* Label */}
            <span
              className={`text-sm transition-colors ${
                isDone
                  ? "text-white/50 line-through"
                  : isActive
                  ? "text-white font-medium"
                  : "text-white/25"
              }`}
            >
              {step}
            </span>
          </div>
        );
      })}

      {status === "failed" && (
        <div className="flex items-center gap-3 mt-1">
          <span className="text-red-400 text-base w-6 text-center">✗</span>
          <span className="text-red-400 text-sm font-medium">Generation failed</span>
        </div>
      )}
    </div>
  );
}
