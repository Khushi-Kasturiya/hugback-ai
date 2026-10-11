import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Your bridge home · HugBack AI",
  description: "Prepare your familiar voice and family context, then receive careful signals that help you stay close across distance.",
  robots: { index: false, follow: false },
};

export default function ChildPortalLayout({ children }: { children: React.ReactNode }) {
  return children;
}
