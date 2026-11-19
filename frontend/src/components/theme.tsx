"use client";

import { Moon, Sun } from "lucide-react";
import { ThemeProvider as NextThemes, useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      {children}
    </NextThemes>
  );
}

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  // true on the client, false during SSR: avoids a hydration mismatch on the icon
  const mounted = useSyncExternalStore(
    () => () => {},
    () => true,
    () => false,
  );
  const dark = mounted && resolvedTheme === "dark";
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={dark ? "Switch to light theme" : "Switch to dark theme"}
      onClick={() => setTheme(dark ? "light" : "dark")}
    >
      {mounted ? dark ? <Sun /> : <Moon /> : <span className="size-4" />}
    </Button>
  );
}
