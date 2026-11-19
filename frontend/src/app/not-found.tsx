import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="container-page max-w-xl py-28 text-center">
      <p className="eyebrow">404</p>
      <h1 className="mt-3 font-display text-4xl font-semibold">Nothing to scout here</h1>
      <p className="mt-3 text-muted">This page doesn&apos;t exist. Your next market might, though.</p>
      <div className="mt-8 flex justify-center gap-3">
        <Button asChild>
          <Link href="/scout">Start research</Link>
        </Button>
        <Button asChild variant="outline">
          <Link href="/">Home</Link>
        </Button>
      </div>
    </div>
  );
}
