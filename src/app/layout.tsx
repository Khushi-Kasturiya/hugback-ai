import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Elara - Voice Companion",
  description: "Empathetic, real-time voice companion powered by Gemini Live API",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-[#FBF9F5] text-[#2D2621] antialiased">
        {children}
      </body>
    </html>
  );
}
