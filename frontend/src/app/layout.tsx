import type { Metadata, Viewport } from "next";
import { Geist_Mono } from "next/font/google";
import localFont from "next/font/local";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { ThemeProvider } from "@/components/theme";
import "./globals.css";

// Geist and Fraunces are self-hosted as one file each: Google's "latin" subset plus ₹ (U+20B9).
// From Google Fonts, ₹ lives in the latin-ext files, so every page showing a rupee price also
// downloaded Geist and Fraunces latin-ext (49 KB) late, at high priority, for that one glyph.
// Same variable wght axis and outlines as Google's files (see docs/DECISIONS.md, "Font loading").
// Characters outside this set (e.g. some accented letters) fall back to the system font.
const geist = localFont({
  src: "./fonts/geist-latin-inr.woff2",
  weight: "100 900",
  variable: "--font-geist",
  display: "swap",
  adjustFontFallback: false,
  fallback: ["Geist Fallback", "Arial", "sans-serif"],
});
// Mono is only used for small labels: don't let it compete with critical resources.
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap", preload: false });
// Weight axis only: the opsz/SOFT axes tripled the file size (121 KB) for little visible gain.
const fraunces = localFont({
  src: "./fonts/fraunces-latin-inr.woff2",
  weight: "100 900",
  variable: "--font-fraunces",
  display: "swap",
  adjustFontFallback: false,
  fallback: ["Fraunces Fallback", "Times New Roman", "serif"],
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: {
    default: "LaunchScout · Competitor research for your next launch, in minutes",
    template: "%s · LaunchScout",
  },
  description:
    "Four AI agents research your market: real competitors and their prices, what customers complain about, the gap nobody serves, and a 30-day launch plan, with every claim linked to its source.",
  applicationName: "LaunchScout",
  keywords: ["competitor research", "market research", "AI agents", "launch plan", "pricing", "founders"],
  openGraph: {
    type: "website",
    siteName: "LaunchScout",
    title: "LaunchScout · Competitor research in minutes",
    description:
      "Real competitors, real prices, real complaints, and the gap nobody serves, with a sourced report and 30-day launch plan.",
    url: "/",
  },
  twitter: { card: "summary_large_image" },
  alternates: { canonical: "/" },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f7f5f0" },
    { media: "(prefers-color-scheme: dark)", color: "#0f1116" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geist.variable} ${geistMono.variable} ${fraunces.variable}`}
    >
      <body className="min-h-dvh">
        <ThemeProvider>
          <SiteHeader />
          <main id="main">{children}</main>
          <SiteFooter />
        </ThemeProvider>
      </body>
    </html>
  );
}
