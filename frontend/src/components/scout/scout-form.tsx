"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { AlertCircle, ArrowRight, Loader2, Sparkles } from "lucide-react";
import { useRouter } from "next/navigation";
import Script from "next/script";
import { useRef, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import * as z from "zod/mini"; // tree-shakable Zod 4 build: ~10x smaller than "zod"
import { ChipInput } from "@/components/scout/chip-input";
import { Button } from "@/components/ui/button";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const text = (min: number, max: number, minMsg: string, maxMsg: string) =>
  z.string().check(z.trim(), z.minLength(min, minMsg), z.maxLength(max, maxMsg));

const schema = z.object({
  business_idea: text(3, 300, "Describe your idea in a few words", "Keep it under 300 characters"),
  city: text(2, 80, "Which city are you launching in?", "City name is too long"),
  target_customer: text(2, 300, "Who is your customer?", "Keep it under 300 characters"),
  known_competitors: z.array(z.string().check(z.maxLength(80))).check(z.maxLength(8)),
});
type FormValues = z.infer<typeof schema>;

const EXAMPLE: FormValues = {
  business_idea: "Healthy millet meal boxes delivered for lunch",
  city: "Coimbatore",
  target_customer: "Office workers, age 25 to 40",
  known_competitors: [],
};

const TURNSTILE_SITE_KEY = process.env.NEXT_PUBLIC_TURNSTILE_SITE_KEY;

declare global {
  interface Window {
    turnstile?: {
      render: (el: HTMLElement, opts: { sitekey: string; callback: (t: string) => void }) => string;
      reset: (id?: string) => void;
    };
  }
}

export function ScoutForm() {
  const router = useRouter();
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const turnstileRef = useRef<HTMLDivElement>(null);
  const [widgetId, setWidgetId] = useState<string | undefined>(undefined);

  const {
    register,
    handleSubmit,
    control,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { business_idea: "", city: "", target_customer: "", known_competitors: [] },
    mode: "onTouched",
  });

  const renderTurnstile = () => {
    if (!TURNSTILE_SITE_KEY || !turnstileRef.current || !window.turnstile || widgetId) return;
    setWidgetId(
      window.turnstile.render(turnstileRef.current, { sitekey: TURNSTILE_SITE_KEY, callback: setToken }),
    );
  };

  const onSubmit = async (values: FormValues) => {
    setSubmitError(null);
    if (TURNSTILE_SITE_KEY && !token) {
      setSubmitError("Please complete the quick check below.");
      return;
    }
    try {
      const { run_id } = await api.createRun({ ...values, turnstile_token: token });
      router.push(`/runs/${run_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        for (const fe of err.fieldErrors) {
          if (fe.field in values) setError(fe.field as keyof FormValues, { message: fe.message });
        }
        setSubmitError(err.message);
      } else {
        setSubmitError("Something went wrong. Please try again.");
      }
      if (widgetId) window.turnstile?.reset(widgetId);
      setToken(null);
    }
  };

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate className="space-y-7">
      {TURNSTILE_SITE_KEY && (
        <Script
          src="https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit"
          strategy="afterInteractive"
          onReady={renderTurnstile}
        />
      )}

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-[12px] border border-dashed border-border-strong px-4 py-3">
        <p className="text-sm text-muted">Not sure what to type? Start from an example.</p>
        <Button type="button" variant="outline" size="sm" onClick={() => reset(EXAMPLE)}>
          <Sparkles aria-hidden /> Use example
        </Button>
      </div>

      <Field id="business_idea" label="Business idea" hint="What will you sell?" error={errors.business_idea?.message}>
        <textarea
          id="business_idea"
          rows={2}
          placeholder="e.g. Healthy millet meal boxes delivered for lunch"
          {...register("business_idea")}
          aria-invalid={!!errors.business_idea}
          aria-describedby="business_idea-hint business_idea-error"
          className={inputClass(!!errors.business_idea, "resize-none leading-relaxed")}
        />
      </Field>

      <div className="grid gap-7 sm:grid-cols-[1fr_1.4fr]">
        <Field id="city" label="City" hint="Where you'll launch first" error={errors.city?.message}>
          <input
            id="city"
            autoComplete="address-level2"
            placeholder="e.g. Coimbatore"
            {...register("city")}
            aria-invalid={!!errors.city}
            aria-describedby="city-hint city-error"
            className={inputClass(!!errors.city)}
          />
        </Field>
        <Field
          id="target_customer"
          label="Target customer"
          hint="Who buys, and roughly how old"
          error={errors.target_customer?.message}
        >
          <input
            id="target_customer"
            placeholder="e.g. Office workers, age 25 to 40"
            {...register("target_customer")}
            aria-invalid={!!errors.target_customer}
            aria-describedby="target_customer-hint target_customer-error"
            className={inputClass(!!errors.target_customer)}
          />
        </Field>
      </div>

      <Field
        id="known_competitors"
        label="Known competitors"
        optional
        hint="Press Enter or comma after each name. We'll verify them and find others."
      >
        <Controller
          control={control}
          name="known_competitors"
          render={({ field }) => (
            <ChipInput
              id="known_competitors"
              value={field.value}
              onChange={field.onChange}
              placeholder="e.g. Millet Express"
              describedBy="known_competitors-hint"
            />
          )}
        />
      </Field>

      {TURNSTILE_SITE_KEY && <div ref={turnstileRef} className="min-h-[65px]" />}

      <div aria-live="assertive">
        {submitError && (
          <p
            role="alert"
            className="flex items-start gap-2 rounded-[10px] border border-[color-mix(in_oklab,var(--danger)_35%,transparent)] bg-[color-mix(in_oklab,var(--danger)_8%,transparent)] px-4 py-3 text-sm text-danger"
          >
            <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden />
            {submitError}
          </p>
        )}
      </div>

      <div className="flex flex-col-reverse items-stretch gap-4 border-t border-border pt-6 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-muted">Takes about 2–4 minutes. You can watch the agents work live.</p>
        <Button type="submit" size="lg" disabled={isSubmitting}>
          {isSubmitting ? (
            <>
              <Loader2 className="animate-spin" aria-hidden /> Starting the crew…
            </>
          ) : (
            <>
              Start research <ArrowRight aria-hidden />
            </>
          )}
        </Button>
      </div>
    </form>
  );
}

function inputClass(invalid: boolean, extra = "") {
  return cn(
    "w-full rounded-[10px] border bg-elevated px-3.5 py-3 text-[15px] placeholder:text-subtle transition-colors",
    "hover:border-[color-mix(in_oklab,var(--border-strong)_60%,var(--fg))] focus-visible:outline-offset-1",
    invalid ? "border-danger" : "border-border-strong",
    extra,
  );
}

function Field({
  id,
  label,
  hint,
  error,
  optional,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <label htmlFor={id} className="text-[15px] font-medium">
          {label}
          {!optional && (
            <span className="text-accent-strong" aria-hidden>
              {" "}
              *
            </span>
          )}
        </label>
        {optional && <span className="text-xs text-subtle">Optional</span>}
      </div>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="mt-1.5 text-[13px] text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} className="mt-1.5 text-[13px] font-medium text-danger">
          {error}
        </p>
      )}
    </div>
  );
}
