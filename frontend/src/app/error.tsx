"use client";

import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function ErrorPage({ reset }: { error: Error; reset: () => void }) {
  return (
    <div className="container-page max-w-xl py-28 text-center">
      <p className="eyebrow">Something broke</p>
      <h1 className="mt-3 font-display text-4xl font-semibold">That didn&apos;t load properly</h1>
      <p className="mt-3 text-muted">It&apos;s on our side, not yours. Try again in a moment.</p>
      <Button className="mt-8" onClick={reset}>
        <RefreshCw aria-hidden /> Try again
      </Button>
    </div>
  );
}
