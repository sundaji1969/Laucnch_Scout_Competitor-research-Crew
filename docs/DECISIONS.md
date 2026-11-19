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
