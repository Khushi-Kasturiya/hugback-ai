import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Child portal · Elara",
  description: "Prepare family background, manage voice setup and view parent-approved updates.",
  robots: { index: false, follow: false },
};

export default function ChildPortalLayout({ children }: { children: React.ReactNode }) {
  return children;
}
