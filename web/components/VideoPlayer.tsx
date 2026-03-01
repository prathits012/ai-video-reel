"use client";

type Props = {
  videoUrl: string;
  filename: string;
};

export default function VideoPlayer({ videoUrl, filename }: Props) {
  return (
    <div className="flex flex-col items-center gap-5 w-full">
      {/* Phone-shaped container for vertical reels */}
      <div className="relative w-64 rounded-3xl overflow-hidden border border-white/10 shadow-2xl bg-black">
        <video
          src={videoUrl}
          controls
          autoPlay
          loop
          playsInline
          className="w-full block"
          style={{ aspectRatio: "9/16" }}
        />
      </div>

      {/* Download button */}
      <a
        href={videoUrl}
        download={filename}
        className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-white text-black font-semibold text-sm hover:bg-white/90 transition"
      >
        ↓ Download video
      </a>
    </div>
  );
}
