import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Child portal · Hugback",
  description: "See parent check-ins, prepare personal context and view parent-approved Hugback updates.",
  robots: { index: false, follow: false },
};

export default function ChildPortalLayout({ children }: { children: React.ReactNode }) {
  return children;
}
