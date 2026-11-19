import { Plus } from "lucide-react";
import Link from "next/link";
import { ThemeToggle } from "@/components/theme";
import { Button } from "@/components/ui/button";

export function Logo({ className = "" }: { className?: string }) {
  return (
    <Link href="/" className={`group inline-flex items-center gap-2.5 ${className}`} aria-label="LaunchScout home">
      <svg width="26" height="26" viewBox="0 0 32 32" aria-hidden className="shrink-0">
        <rect width="32" height="32" rx="8" className="fill-fg" />
        <path d="M9 22.5 16 8l7 14.5-7-3.6-7 3.6Z" className="fill-bg" />
        <circle cx="16" cy="15.2" r="2.1" className="fill-accent" />
      </svg>
      <span className="font-display text-[19px] font-semibold tracking-tight">LaunchScout</span>
    </Link>
  );
}

export function SiteHeader() {
  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-bg/80 backdrop-blur-md supports-[backdrop-filter]:bg-bg/65">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded-md focus:bg-elevated focus:px-3 focus:py-2"
      >
        Skip to content
      </a>
      <div className="container-page flex h-16 items-center justify-between gap-4">
        <Logo />
        <nav aria-label="Main" className="flex items-center gap-0.5 sm:gap-1">
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link href="/#how-it-works">How it works</Link>
          </Button>
          <Button asChild variant="ghost" size="sm">
            <Link href="/runs">Reports</Link>
          </Button>
          <ThemeToggle />
          <Button asChild size="sm" className="ml-1">
            <Link href="/scout" aria-label="New research">
              <Plus aria-hidden className="sm:hidden" />
              <span className="sm:hidden">New</span>
              <span className="hidden sm:inline">New research</span>
            </Link>
          </Button>
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-12 border-t border-border sm:mt-16">
      <div className="container-page flex flex-col gap-4 py-10 text-sm text-muted sm:flex-row sm:items-center sm:justify-between">
        <Logo className="opacity-90" />
        <p className="max-w-md">
          AI research can be wrong. Every price and claim links to its source, so check the important ones
          before you invest.
        </p>
      </div>
    </footer>
  );
}
