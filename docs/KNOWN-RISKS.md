# Known Risks — Synth v0.1 Beta

**Status:** Accepted for invite-only beta launch (2026-04-29). All items below are tracked for resolution in v0.2 or later.

## Infrastructure

### Single-worker deployment
Synth runs as a single uvicorn worker because all session state (active meetings, context buffers, entity tracker) lives in process memory. A restart drops every live meeting.
- **Mitigation:** schedule deploys during off-peak hours; send 5-min warning to active users.
- **Resolution:** move session state to Redis (v0.2, ~2 weeks).
- **Tracking:** audit finding A-01.

### No Alembic migrations
Schema changes are applied via 265 lines of inline `ALTER TABLE` statements in `backend/app/main.py`.
- **Mitigation:** all schema changes reviewed by two people; staging rehearsal before prod apply.
- **Resolution:** migrate to Alembic (v0.2, ~1 day).
- **Tracking:** A-10.

### No production circuit breaker for downstream
Recall.ai has retry (as of A6) but no full circuit-breaker open-state. Gemini / Claude retry transient errors but don't isolate a sick provider.
- **Mitigation:** JSON log alerts on elevated failure rate; manual rollout if provider degrades.

## Security

### 24-hour non-revocable JWT
No refresh token flow, no revocation list. Password change does not invalidate existing tokens.
- **Mitigation:** invite-only users; tokens are scoped per-user; service-token endpoint rate-limited.
- **Resolution:** refresh + revocation (v0.2).
- **Tracking:** S-04.

### Stripe webhook dedup is best-effort
SELECT-then-INSERT check for `stripe_session_id`. Race-condition window exists.
- **Mitigation:** low payment volume for beta (< 50 users).
- **Resolution:** add DB unique constraint (v0.2, ~1h).
- **Tracking:** S-15.

### Per-user resource limits not enforced
No caps on agents, documents, active meetings per user.
- **Mitigation:** invite-only gate limits user count to < 25.
- **Resolution:** add caps (v0.2, ~2h).
- **Tracking:** S-14.

## Code quality

### 119 latent mypy errors
Most are SQLAlchemy `Column[T]` vs `T` type confusion. Mypy is blocking on 3 critical files only; the rest is advisory.
- **Mitigation:** critical paths are type-clean; no runtime impact.
- **Resolution:** migrate ORM to SQLAlchemy 2.0 `Mapped[]` style (v0.2, ~12h).

## Observability

### No Prometheus metrics
Logs are structured JSON (B3); metrics are deferred.
- **Mitigation:** Sentry catches errors; log-based alerting via your log platform.
- **Resolution:** add Prometheus instrumentation (v0.2, ~4h).

### Insight detector not rate-limited
A chatty meeting can trigger unbounded LLM + search calls.
- **Mitigation:** feature flag lets ops disable insight detection mid-incident.
- **Resolution:** rate limit (v0.2, ~2h).

## Acknowledgement

Signed off by: Viraj Balakrishnan, Devyansh, <TO VERIFY: team lead name> — 2026-04-29.
