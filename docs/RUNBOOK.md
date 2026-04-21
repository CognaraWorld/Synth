# Synth Runbook

On-call reference for Synth v0.1 beta.

## Contents
- [Deploy a new version](#deploy)
- [Rollback](#rollback)
- [Read logs](#logs)
- [Check health](#health)
- [Refund credits manually](#refund)
- [Force-stop a stuck bot](#force-stop)
- [Read Sentry errors](#sentry)
- [Rotate a secret](#rotate-secret)
- [Escalation paths](#escalation)

## <a name="deploy"></a>Deploy a new version

```bash
# From your laptop, on main with a clean working tree
git pull
git tag v0.1.<patch>
git push origin v0.1.<patch>
```

This triggers `.github/workflows/deploy.yml`:
1. Builds backend Docker image → pushes to GHCR
2. SSHes to the VPS → `docker compose pull && up -d backend`
3. Waits for `/api/health` to return 200 (30 retries × 2s)

Watch progress: https://github.com/CognaraWorld/Synth/actions

After deploy, verify on the VPS:
```bash
ssh synth-prod
cd /srv/synth
docker compose ps
curl -fsS http://127.0.0.1:8000/api/health/ready | jq
```

## <a name="rollback"></a>Rollback

Every image is tagged with both the version (`v0.1.3`) and the commit SHA (`sha-abc1234`). To roll back:

```bash
ssh synth-prod
cd /srv/synth
# Pick a known-good tag
docker compose pull backend --quiet  # if using `latest` you need to pin
# Edit IMAGE_TAG in docker-compose override OR pass via env:
export IMAGE_TAG=v0.1.2
docker compose up -d backend
```

Rollbacks take ~30s. Session state (active meetings) is lost — warn users first.

## <a name="logs"></a>Read logs

Logs are JSON in production. Each line includes `request_id`, `session_id`, `bot_id` when applicable.

Tail live:
```bash
docker compose logs backend -f
```

Filter by session:
```bash
docker compose logs backend | jq -c 'select(.session_id == "<ID>")'
```

Find all errors in the last hour:
```bash
docker compose logs backend --since 1h | jq -c 'select(.level == "ERROR")'
```

Common fields:
- `timestamp` — ISO 8601
- `level` — DEBUG / INFO / WARNING / ERROR / CRITICAL
- `logger` — Python logger name
- `message` — human message
- `request_id` — 16-char hex, per HTTP request
- `session_id` — meeting session UUID
- `bot_id` — Recall.ai bot UUID

## <a name="health"></a>Check health

Two endpoints:

- `GET /api/health` — liveness. Returns 200 as long as the process is up. Docker HEALTHCHECK hits this.
- `GET /api/health/ready` — readiness. Checks DB + ChromaDB + TTS. Returns 200 if all healthy, 503 if any fail.

Response schema for `/api/health/ready`:
```json
{
  "status": "ready" | "degraded",
  "checks": {
    "db": "ok" | "fail: <ExceptionClassName>",
    "chroma": "ok" | "fail: ...",
    "tts": "ok" | "not_loaded" | "fail: ...",
    "active_sessions": 0
  }
}
```

"not_loaded" for TTS is acceptable during startup (models take ~30s).

## <a name="refund"></a>Refund credits manually

When an ops-level refund is needed (provider outage, billing bug):

```sql
-- Connect
docker compose exec postgres psql -U synth -d synth

-- Find the user
SELECT id, email, credits FROM users WHERE email = 'user@example.com';

-- Refund (idempotent if you use a unique meeting_id — SEE credits.py)
BEGIN;
UPDATE users SET credits = credits + 60 WHERE id = '<user-id>';
INSERT INTO credit_transactions (user_id, meeting_id, amount, transaction_type, reason)
VALUES ('<user-id>', NULL, 60, 'manual_refund', 'Recall outage 2026-04-30');
COMMIT;
```

Always log the manual transaction in #ops-log Slack.

## <a name="force-stop"></a>Force-stop a stuck bot

If a bot is stuck in a meeting (using credits, not responding):

```bash
# Find bot_id
docker compose exec postgres psql -U synth -d synth -c \
  "SELECT id, bot_id, status, started_at FROM meetings WHERE status = 'active';"

# Stop via API (requires admin service token)
curl -X POST https://synth-webhook.yourdomain.com/api/bot/<bot_id>/stop \
  -H "Authorization: Bearer <SERVICE_TOKEN>"

# OR directly via Recall
curl -X POST https://api.recall.ai/api/v1/bot/<bot_id>/leave_call/ \
  -H "Authorization: Token <RECALL_API_KEY>"
```

## <a name="sentry"></a>Read Sentry errors

Sentry: https://sentry.io/organizations/cognara/issues/ <TO VERIFY: confirm Sentry org slug is 'cognara'>

Filter by environment:
- `environment:production` — real users
- `environment:staging` — pre-prod

Common issue patterns:
- "TypeError: BotEngine.join_meeting() got unexpected keyword argument" — Devyansh's A1 regression
- "RecallClientError: 502" — Recall outage, check their status page
- "IntegrityError: duplicate key value" — Stripe webhook race (expected occasionally)

## <a name="rotate-secret"></a>Rotate a secret

See [docs/SECRETS-ROTATION.md](./SECRETS-ROTATION.md).

## <a name="escalation"></a>Escalation paths

| Severity | Contact | Response SLA |
|---|---|---|
| P0 — outage | Viraj (primary), Devyansh (secondary) | 15 min |
| P1 — degraded | on-call rotation | 1 hour |
| P2 — data issue | Viraj via Slack | same-day |
| Security | security@cognara.ai | ASAP |
