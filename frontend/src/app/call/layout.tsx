import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Parent voice bridge · HugBack AI",
  description: "The parent-facing HugBack voice call experience.",
};

export default function CallLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return children;
}
