import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI Reels",
  description: "Generate short educational video reels from any topic",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-[#0a0a0a] text-white antialiased">
        <header className="border-b border-white/5 px-6 py-4">
          <div className="mx-auto max-w-4xl flex items-center gap-3">
            <div className="h-7 w-7 rounded-lg bg-white/90 flex items-center justify-center">
              <span className="text-black text-xs font-bold">▶</span>
            </div>
            <span className="font-semibold tracking-tight text-white/90">AI Reels</span>
          </div>
        </header>
        <main className="mx-auto max-w-4xl px-6 py-12">{children}</main>
      </body>
    </html>
  );
}
