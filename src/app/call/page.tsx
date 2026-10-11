import { redirect } from "next/navigation";

export default function ParentCallPage({ searchParams }: { searchParams: { recipient?: string } }) {
  const recipient = typeof searchParams.recipient === "string" ? `&recipient=${encodeURIComponent(searchParams.recipient)}` : "";
  redirect(`/?demo=parent${recipient}`);
}
