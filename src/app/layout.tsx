import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "HugBack AI — Distant, but still close",
  description: "A consent-led voice bridge that helps families stay close across distance, in the familiar voice parents miss most.",
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
