# Secrets Rotation Playbook

Every secret in Synth has a rotation procedure. This doc describes which secrets exist, where they're stored, and how to rotate.

## Inventory

Sourced from `backend/app/config.py` and the deploy pipeline.

| Var | Secret? | Set by | Consumed by | Notes |
|---|---|---|---|---|
| DATABASE_URL | secret | VPS env | backend | postgres URL inside compose network |
| ENVIRONMENT | public | VPS env | backend | always `production` on VPS |
| EXPOSE_MEETING_LATENCY_METRICS | public | VPS env | backend | optional; leave unset in prod |
| SECRET_KEY | secret | GitHub secrets → VPS env | backend | JWT signing key |
| BACKEND_SERVICE_SECRET | secret | " | backend | admin/service API auth |
| ANTHROPIC_API_KEY | secret | " | backend | Claude fallback LLM |
| GEMINI_API_KEY | secret | " | backend | primary LLM |
| RECALL_API_KEY | secret | " | backend | meeting bot API |
| RECALL_REGION | public | VPS env | backend | `ap-northeast-1` |
| WEBHOOK_BASE_URL | public | VPS env | backend | Cloudflare tunnel hostname |
| WEBHOOK_SECRET | secret | " | backend | Recall.ai webhook HMAC |
| CORS_ORIGINS | public | VPS env | backend | comma-separated frontend origins |
| DEEPGRAM_API_KEY | secret | " | backend | transcription |
| SERPER_API_KEY | secret | " | backend | web search |
| SEARXNG_URL | public | VPS env | backend | internal search fallback URL |
| RESEND_API_KEY | secret | " | backend | transactional email (preferred) |
| SMTP_HOST | public | VPS env | backend | email fallback |
| SMTP_PORT | public | VPS env | backend | email fallback |
| SMTP_USER | secret | " | backend | email fallback auth |
| SMTP_PASSWORD | secret | " | backend | email fallback auth |
| FROM_EMAIL | public | VPS env | backend | sender address |
| STRIPE_SECRET_KEY | secret | " | backend | payments |
| STRIPE_WEBHOOK_SECRET | secret | " | backend | Stripe HMAC |
| FRONTEND_URL | public | VPS env | backend | frontend base URL |
| FRONTEND_SUCCESS_URL | public | VPS env | backend | Stripe checkout success redirect |
| FRONTEND_CANCEL_URL | public | VPS env | backend | Stripe checkout cancel redirect |
| SENTRY_DSN | secret | GitHub secrets → frontend build | frontend | error tracking (if enabled) |
| DEPLOY_HOST | secret | GitHub secrets | deploy.yml SSH step | VPS hostname/IP |
| DEPLOY_USER | secret | GitHub secrets | deploy.yml SSH step | SSH username |
| DEPLOY_KEY | secret | GitHub secrets | deploy.yml SSH step | SSH private key |
| IMAGE_TAG | public | deploy.yml → VPS env | docker-compose backend service | exported per deploy |

## Rotation steps

### Internal secrets (SECRET_KEY, BACKEND_SERVICE_SECRET, WEBHOOK_SECRET)

1. Generate new value:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
2. Update in the deploy platform's secret store (GitHub Actions secrets → production environment).
3. Trigger a redeploy: `git tag v0.1.X-rotate && git push origin v0.1.X-rotate`.
4. Verify `/api/health/ready` still returns 200 post-deploy.

**Impact of SECRET_KEY rotation:** all active JWTs invalidate immediately. All users must log in again. Expected for a scheduled rotation.

**Impact of BACKEND_SERVICE_SECRET rotation:** frontend ↔ backend service-token flow breaks until the frontend Next.js env is also rotated + redeployed. Rotate both together.

**Impact of WEBHOOK_SECRET rotation:** Recall.ai must also be updated to send the new secret in webhook headers. Rotate Recall first, then backend, with < 5 min gap.

### External API keys

Rotate at the provider's dashboard:
- Anthropic: https://console.anthropic.com/settings/keys
- Gemini: https://aistudio.google.com/apikey
- Recall.ai: <TO VERIFY: Recall dashboard URL — typically https://api.recall.ai/dashboard/api-keys or similar> → API Keys
- Stripe: https://dashboard.stripe.com/apikeys (primary), Stripe → Developers → Webhooks for `STRIPE_WEBHOOK_SECRET`
- Deepgram: https://console.deepgram.com/ → API Keys
- Serper: https://serper.dev/api-key
- Resend: https://resend.com/api-keys
- Sentry (DSN): https://sentry.io/settings/ → Projects → Client Keys <TO VERIFY: confirm Sentry org slug is 'cognara'>

For each: generate new → update deploy secret (GitHub Actions secrets → production environment) → redeploy → revoke old key at the provider.

### SMTP fallback (SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, FROM_EMAIL)

Only used when Resend is unavailable. Rotate at the SMTP provider's dashboard (values depend on provider). Update deploy secrets and redeploy.

### Deploy credentials (DEPLOY_HOST, DEPLOY_USER, DEPLOY_KEY)

Used by `.github/workflows/deploy.yml` to SSH into the VPS.

1. Generate a new SSH keypair on a workstation:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/synth-deploy -C "github-actions-synth"
   ```
2. Append the new public key to `/home/$DEPLOY_USER/.ssh/authorized_keys` on the VPS.
3. Update the `DEPLOY_KEY` GitHub Actions secret with the new private key.
4. Trigger a deploy to verify SSH works.
5. Remove the old public key line from `authorized_keys` on the VPS.

### Emergency rotation (suspected compromise)

1. Revoke the compromised key at the provider FIRST.
2. Check logs for unauthorized usage: `docker compose logs backend | grep -c "<partial-key-prefix>"`.
3. Generate new key, update deploy secret, redeploy.
4. If `SECRET_KEY` is compromised: rotate immediately, notify all beta users to re-authenticate.
5. If `DEPLOY_KEY` is compromised: revoke the public key on the VPS first, then rotate.
6. Post-mortem within 24h.

## Log leak check

After any rotation, verify the new value is not leaked in logs:
```bash
docker compose logs backend | grep -c "<new-secret-value>"
# Must return 0
```

If the count is > 0, the secret leaked through a log statement. Find and fix the offending logger.
