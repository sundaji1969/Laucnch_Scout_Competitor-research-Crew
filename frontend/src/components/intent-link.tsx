"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import type { ComponentProps, FocusEvent, MouseEvent, TouchEvent } from "react";

type Props = Omit<ComponentProps<typeof Link>, "prefetch" | "href"> & { href: string };

/**
 * A Link that prefetches on intent (hover, focus, touch) instead of when it scrolls into view.
 *
 * Next.js prefetches a visible Link's route code straight away. For the /scout buttons in the
 * header and hero that means every landing-page visit downloaded the form's code (Zod,
 * react-hook-form, captcha; about 34 KB), which Lighthouse flagged as unused. Prefetching on
 * intent still has the code ready by the time the click lands.
 */
export function IntentLink({ href, onMouseEnter, onFocus, onTouchStart, ...rest }: Props) {
  const router = useRouter();
  const prefetch = () => router.prefetch(href);
  return (
    <Link
      href={href}
      prefetch={false}
      onMouseEnter={(e: MouseEvent<HTMLAnchorElement>) => {
        prefetch();
        onMouseEnter?.(e);
      }}
      onFocus={(e: FocusEvent<HTMLAnchorElement>) => {
        prefetch();
        onFocus?.(e);
      }}
      onTouchStart={(e: TouchEvent<HTMLAnchorElement>) => {
        prefetch();
        onTouchStart?.(e);
      }}
      {...rest}
    />
  );
}
