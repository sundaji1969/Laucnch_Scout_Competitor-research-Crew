import type { Metadata, Viewport } from "next";
import { Fraunces, Geist, Geist_Mono } from "next/font/google";
import { SiteFooter, SiteHeader } from "@/components/site-chrome";
import { ThemeProvider } from "@/components/theme";
import "./globals.css";

const geist = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });
// Mono is only used for small labels: don't let it compete with critical resources.
const geistMono = Geist_Mono({ subsets: ["latin"], variable: "--font-geist-mono", display: "swap", preload: false });
// Weight axis only: the opsz/SOFT axes tripled the file size (121 KB) for little visible gain.
const fraunces = Fraunces({ subsets: ["latin"], variable: "--font-fraunces", display: "swap" });

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
