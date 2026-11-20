# Architecture & Engineering Decisions

A running log of decisions made while building LaunchScout. Newest at the bottom of each section.

## Repository
- **Monorepo** at repository root (`frontend/`, `backend/`, `deploy/`, `.github/`). The brief's `launchscout/` folder is the repo root itself.
- Default branch `main`; conventional commits.

## Backend
- **Python 3.12**, dependency management via `pip` + `pyproject.toml` (uv not installed on the dev machine; pip keeps Docker builds simple).
- **CrewAI 1.15.x** with `@CrewBase`, `config/agents.yaml`, `config/tasks.yaml` — matches the CrewAI project convention from the spec.
- LLM chosen purely from `LLM_MODEL` env (LiteLLM string). No provider is hard-coded.
- Structured outputs: `CompetitorList`, `ReviewInsights`, `StrategyMatrix` (Pydantic v2) on tasks 1–3, each competitor with `source_urls: list[HttpUrl]`.
- Task-1 guardrail: function guardrail that parses the pydantic output and rejects < 3 competitors / missing price / missing source; `guardrail_max_retries=2`.
- "Not publicly listed" is an accepted price value, provided a source URL of the checked page is present (data-integrity rule).
- Post-run validator in `app/services/report_validator.py` — independent of CrewAI so it is unit-testable and also used by the worker to fail the job.
- Tool failures (Serper rate limit, scrape blocked) are caught in thin tool wrappers that return an error string to the agent instead of raising, so the agent continues with other sources.
- Agents are mapped to progress events by agent id first, then by the role-template prefix (roles contain `{city}`, which CrewAI interpolates at kickoff).
- `guardrails.py` deliberately omits `from __future__ import annotations`: CrewAI inspects the guardrail's return annotation at runtime and requires a real `tuple[bool, Any]`.
- The runner always (over)writes `outputs/<run_id>/report.md` from the final task output after kickoff. The Report Writer still saves it with `FileWriterTool` per spec; the runner's copy guarantees the saved file is byte-identical to what was validated.
- User inputs strip `{` `}` (CrewAI interpolation syntax), HTML tags and control characters before reaching prompts.
- Offline tests use a scripted `BaseLLM` subclass, so the real CrewAI pipeline (guardrail retry, `output_pydantic` conversion, event bus) is exercised without network or keys.
- mypy runs in strict mode with `disallow_untyped_decorators = false`, because CrewAI's `@agent`/`@task`/`event_bus.on` decorators are untyped.
- Installed extras: `crewai[anthropic,litellm]`. Anthropic/OpenAI/Gemini prefixes use CrewAI's native SDKs, and every other `LLM_MODEL` prefix falls back to LiteLLM.

## Job execution (planned for Phase 3)
- CrewAI's event bus is process-global. The worker therefore runs each crew in its own **subprocess**, which isolates progress events per run and lets `RUN_TIMEOUT_SECONDS` be enforced by killing the process.

## Data integrity: provenance enforcement (added after the first live run)
- **Finding:** in the first live run GPT-4.1 answered task 1 *without calling any tool*: five plausible competitors produced from memory. With tools attached, CrewAI leaves tool use up to the model, so prompts alone cannot guarantee "no invented competitors".
- **Fix:** `app/crew/provenance.py` records every URL and all text returned by Serper and the scraper during a run.
  - Task-1 and task-2 guardrails reject source URLs that never appeared in a tool result, and task 1 requires at least 3 searches.
  - Prices: every number in a competitor's price must appear on a page cited for that competitor, or within 400 characters of the competitor's name in a tool result. Matching "anywhere in the corpus" was tried first and rejected: common numbers (180, 200) matched by coincidence.
  - An unverifiable price is rejected once with specific feedback. If it is still unverifiable, it is downgraded to "Not publicly listed" with a note, which is the spec's own rule, rather than failing the run.
  - The post-run validator applies the URL and price rules to the final report's Sources and Key Competitors table.
  - The full tool output is saved to `outputs/<run_id>/evidence.json` for audit.
- `HttpUrl` fields advertise `{"type":"string"}` in the JSON schema (still validated as http(s) URLs), because OpenAI structured outputs reject `format: uri`.
- A guardrail that passes returns the original `TaskOutput`, and CrewAI then keeps `.pydantic=None`. The guardrails attach the parsed model, and the runner also re-parses raw JSON as a fallback.
- `FileWriterTool(base_dir=OUTPUTS_DIR)` sandboxes the Report Writer to the outputs directory.

## API / worker (Phase 3)
- arq (async, Redis-backed). `max_jobs = MAX_CONCURRENT_RUNS`; the API also returns 503 when more than `3 × MAX_CONCURRENT_RUNS` runs are queued or running.
- Each run executes in its own subprocess (`app.worker.child`), killed after `RUN_TIMEOUT_SECONDS`.
- The child publishes progress events. The **parent** publishes the terminal `run_completed`/`run_failed` event only after the database row is committed, so the UI never finds a "completed" run without its report.
- Events carry a per-run `seq`. They are stored in a capped Redis list (24h TTL) for replay and published on pub/sub for live delivery.
- **Bug found in live testing:** CrewAI fires tool events from parallel threads, which stored events out of order, and SSE dropped events numbered lower than the last one sent. Fixed with a publisher lock and exact-set de-duplication in SSE; covered by regression tests.
- SSE honours `Last-Event-ID` (and `?after=` for clients that can't set headers). Every 30s of silence it checks the database as a safety net, in case a worker died without publishing a terminal event.
- Rate limiting uses `limits` (moving window) on Redis via redis-py (`implementation="redispy"`), keyed by a salted hash of the client IP. Raw IPs are never stored.
- PDF: markdown-it → HTML template (cover page, clickable `[n]` citations linked to anchored sources) → WeasyPrint. WeasyPrint needs Pango, so the actual render test runs in Docker/CI and is skipped on Windows.
- Local dev API port is 8010 because port 8000 is used by other software on the dev machine.

## Cost observation
- One GPT-4.1 sample run used about 494k tokens (about $1). Scraped pages (up to 12k characters each) accumulate in agent context across iterations. Candidates to reduce cost: lower `MAX_SCRAPE_CHARS`, `max_iter`, or a cheaper model for the review step. To revisit after the core is shipped.

## Frontend (Phase 4)
- Next.js 16.4 (App Router, Turbopack, React 19.3), Tailwind CSS v4 via the `@tailwindcss/turbopack` loader, `output: "standalone"`.
- shadcn/ui is used the way shadcn intends: components copied into `src/components/ui` (Button with `cva` + Radix `Slot`, Card, Badge, Skeleton). `components.json` is present so `npx shadcn add …` works later.
- **Design:** Fraunces (display serif) + Geist (UI) + Geist Mono (activity feed and labels); warm ink/paper neutrals, a single saffron accent; light and dark via `next-themes` (class strategy) and CSS variables. Every text/background token pair is AA (≥4.5:1), checked by Lighthouse.
- **Data fetching:** the browser talks to the API directly (`NEXT_PUBLIC_API_BASE`; empty = same origin behind Caddy in production). No API keys ever reach the browser; the only public value is the optional Turnstile site key.
- **Live run:** `useRunEvents` wraps EventSource. It de-duplicates by `seq`, sorts, reconnects with exponential backoff and jitter, and resumes with `?after=<lastSeq>` (EventSource can't set `Last-Event-ID` on a new connection).
- **Report:** react-markdown + remark-gfm with custom renderers. `[n]` becomes a citation chip that scrolls to and highlights the source. Sources render from structured API data so anchors are guaranteed. Competitor table scrolls horizontally with a sticky first column. The Recharts price-vs-differentiation scatter uses greedy label placement to avoid overprinting.
- **Validation:** react-hook-form + `zod/mini` (Zod 4's tree-shakable build; the full `zod` import put a 162 KB chunk on the landing page via link prefetch).
- **Performance work, measured with Lighthouse (simulated slow-4G mobile):** 75 → 92–93. Changes: CSS animation instead of Framer Motion on the landing page; Fraunces without the opsz/SOFT axes (121 KB → 37 KB); Geist Mono not preloaded; `experimental.inlineCss`; `zod/mini`. Accessibility, Best Practices and SEO are 100. Remaining: simulated LCP ~3.2s, mostly framework JS. To be re-measured on the Linux deploy (Phase 8).
- **Local Lighthouse caveat:** on this Windows machine, Chrome's proxy auto-detection (WPAD) added ~20–28s to time-to-first-byte inside Lighthouse's browser and wrecked Speed Index. Run local audits with `--chrome-flags="--no-proxy-server"`.
- **Design review fixes from Playwright screenshots** (390px and 1440px, light and dark): header overflow at 390px (compact "New" button on phones); sample-card badge collision; long recommended price broke the offer card (split into headline price + qualifier); chart labels overprinting; empty-looking "running" history cards; source titles losing closing brackets (backend parser bug, fixed with tests); activity feed lines now name the site read ("Read sniffy.in · 12k characters").

## Data-quality follow-ups
- In markets where businesses sell only through Swiggy/Zomato, menu prices are rendered by JavaScript and invisible to `ScrapeWebsiteTool`. Coimbatore millet meals: 1 of 5 competitors priced. Pune pet grooming, where businesses publish price lists: 4 of 5 priced. Next step: a headless-browser scrape tool (Playwright) for aggregator menu pages, behind a flag.

## Docker (Phase 5)
- **Backend:** one image for API and worker (`docker-entrypoint.sh api|worker`). Multi-stage: build venv → `python:3.12-slim` runtime with Pango/HarfBuzz for WeasyPrint. Non-root uid 10001. 2.09 GB, mostly CrewAI's transitive ML deps (lancedb, onnxruntime, pyarrow).
- The API container runs `alembic upgrade head` before starting uvicorn. The worker never migrates, which avoids concurrent migrations.
- **Frontend:** Next.js standalone on `node:24-alpine`, non-root, 309 MB. `NEXT_PUBLIC_*` values are build args, public by design.
- **Healthchecks:** API `GET /api/health`, which checks the DB and Redis; frontend `GET /`; worker checks the arq process with `pgrep` (it has no HTTP port).
- **Local compose:** API on `127.0.0.1:8010`, web on `127.0.0.1:3000`; Postgres and Redis are not published. **Prod override:** `ports: !reset []` on everything; nothing is published. Named volumes for Postgres, Redis, reports and Caddy data.
- **Traefik in front:** the VPS already runs Traefik on 80/443, so prod sits behind it instead of running its own TLS. Traefik terminates HTTPS and gets the Let's Encrypt certificate (labels on the `caddy` service; `.env` sets `TRAEFIK_NETWORK`, `TRAEFIK_CERTRESOLVER`, `TRAEFIK_ENTRYPOINT`), then forwards to Caddy over plain HTTP. Caddy stays as the internal router so SSE handling is unchanged, and trusts private-range proxies so the real client IP stays first in `X-Forwarded-For` (rate limiting depends on it). The Traefik router lists only `$DOMAIN`. The first live deploy (`launchscout.sundajigenai.tech`) got Traefik's self-signed default certificate because the rule also listed `www.$DOMAIN`, which had no DNS record, and Let's Encrypt fails the whole order when one name fails. Caddy still redirects `www` to the bare domain if a `www` host is added to the rule.
- **Caddy:** the SSE route (`/api/runs/{id}/events`) is matched first with `flush_interval -1`, no compression and no read timeout, so events are never buffered. Everything else gets zstd/gzip.
- **Verified locally with `docker compose up --build`:** all services healthy; the sample input ran end to end (60 SSE events, none missing); PDF rendered by WeasyPrint in the container (4 pages, branded cover, clickable citations); Markdown download with all 6 sections.
- The PDF headings fall back to DejaVu Serif inside the container (Fraunces isn't installed system-wide). Acceptable; bundling the font file is a possible polish later.

## CI/CD (Phase 6)
- `ci.yml`: backend ruff + format check + mypy strict + pytest (live tests excluded); frontend typegen + tsc + eslint + build; both Docker images built with the GHA cache.
- `deploy.yml`: runs on push to `main` only when the repo variable `DEPLOY_ENABLED=true`, so the first push doesn't fail before the VPS exists. It SSHes as `VPS_USER`, runs `git reset --hard origin/main` and `compose up -d --build`, then polls `https://$DOMAIN/api/health`. Uses secrets `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` and the variable `DOMAIN`.

## Deploy and verification (Phases 7 and 8, 20 Nov 2026)
- Live at `https://launchscout.sundajigenai.tech` (a subdomain), behind n8n's Traefik: network `n8n_default`, resolver `mytlschallenge`, entrypoint `websecure`.
- Production model: `openai/gpt-4.1` (the OpenAI key was the one available). Two live runs: Coimbatore millet meal boxes (86 s, 417k tokens, 4 competitors, 9 sources) and Pune mobile pet grooming (95 s, 341k tokens, 5 competitors, 7 sources). Both have all six sections, saved `report.md` and `result.json`, and working MD and PDF downloads.
- GitHub `VPS_SSH_KEY` was corrupted when pasted through the browser ("error in libcrypto"); re-set from the file with `gh secret set < keyfile`. The workflow now strips CR and validates the key with `ssh-keygen -y` before using it.

## Daily run cap
- `DAILY_RUN_CAP` (default 30, 0 = off) limits new runs per UTC day across all visitors. It is an atomic Redis `INCR` on `launchscout:daily_runs:YYYYMMDD` (2-day TTL), so simultaneous requests can't overshoot it the way a database count could. It is checked before the per-IP limiter so a refusal doesn't use up the visitor's own quota, and the slot is given back if a later check (rate limit, busy) rejects the request. Refusals are HTTP 429 with `Retry-After` until midnight UTC and a message the form shows as-is.

## Report reuse
- `REUSE_WINDOW_DAYS` (default 7, 0 = off): `POST /api/runs` returns an existing run when idea, city, target customer and known competitors match, ignoring case, spacing and competitor order. Completed runs (with a report) are served; queued or running ones are joined, so a double submit pays once. Failed runs are never reused.
- Checked before both caps, so a reuse costs nothing and uses neither the daily cap nor the visitor's quota. The response is HTTP 200 with `reused: true` (new runs stay 202).
- The report page says the idea was already researched and when, and offers "Run fresh research", which posts `fresh: true` to skip reuse. A fresh run still goes through both caps.

## Price chart ranges
- The Strategy Analyst leaves `price_value` empty when a price is a range ("₹200-₹400 per meal"), so the chart used to drop those competitors and the caption wrongly called them unpriced. `frontend/src/lib/price.ts` now reads currency-marked amounts back out of the price text when `price_value` is empty: a range plots at its midpoint with a horizontal bar, and a single amount plots as-is. Only amounts with ₹/Rs/INR/$ count, so "500 ml" is never read as a price. Done in the frontend so existing reports are fixed without re-running them.
- Frontend unit tests use Node's built-in runner (`npm test`, Node 24 runs TypeScript directly), and CI runs them.

## Lighthouse on the live site (20 Nov 2026, Lighthouse 12.8.2, landing page)
- Mobile (simulated slow 4G), three runs: Performance 94 / 96 / 95; Accessibility, Best Practices, SEO 100. FCP 1.4 s, LCP 2.8 s, TBT 90-130 ms, CLS 0.
- Desktop: 100 in all four categories. LCP 0.5 s.
- The LCP element is the hero `<h1>`. Server response is 50 ms; most of the mobile LCP (about 2.2 s) is render delay from framework JavaScript and the display font. Remaining opportunity: about 60 KB of unused JavaScript.

## Known follow-ups
- Aggregator-only markets (Swiggy/Zomato) still yield few prices; a Playwright scrape tool behind a flag remains the plan.
- Stretch goals not started: hierarchical process (flag exists, `PROCESS_MODE=hierarchical`), Pitch Deck agent, weekly re-run.
