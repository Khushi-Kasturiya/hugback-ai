"use client";

import { Suspense } from "react";
import { CallTest } from "@/components/CallTest";

export default function ParentCallPage() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-[#FFFDF9]" />}>
      <CallTest />
    </Suspense>
  );
}
