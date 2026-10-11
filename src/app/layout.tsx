import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hugback - Voice Companion",
  description: "Empathetic, real-time voice companion powered by Gemini Live API",
  icons: { icon: "/logo.png", apple: "/logo.png" },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className="min-h-screen text-stone-900 antialiased">
        {children}
      </body>
    </html>
  );
}
