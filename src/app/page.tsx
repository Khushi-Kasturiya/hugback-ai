"use client";

import React, { Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { LandingPage } from "@/components/LandingPage";
import { CallTest } from "@/components/CallTest";

export default function Home() {
  return (
    <Suspense fallback={<main className="min-h-screen bg-[#FFFDF8]" />}>
      <HomeRoute />
    </Suspense>
  );
}

function HomeRoute() {
  const params = useSearchParams();
  return params.get("demo") === "parent" ? <CallTest /> : <LandingPage />;
}
