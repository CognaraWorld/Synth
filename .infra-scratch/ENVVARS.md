# Deploy Pipeline — Env Var Inventory

Every variable the production backend reads. Sourced from `backend/app/config.py`. The Docs agent should consume this into `docs/SECRETS-ROTATION.md`.

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
