# Webhook Ingress — Cloudflare Tunnel

Synth's backend does not expose a public IP. Recall.ai webhooks reach it through a Cloudflare Tunnel terminating at the production VPS.

## Prerequisites

- A Cloudflare account with a domain (e.g. `yourdomain.com`) managed by Cloudflare DNS.
- `cloudflared` installed on the VPS.
- Sudo access on the VPS.

## One-time setup

Run on the production VPS. Substitute `<TUNNEL_ID>` and `yourdomain.com` as you go. The reference files ship alongside this doc in `.infra-scratch/`.

1. **Install cloudflared** on the VPS:
   ```bash
   curl -fsSL https://pkg.cloudflare.com/install.sh | sudo bash
   sudo apt-get install -y cloudflared
   ```

2. **Authenticate** (one-time, interactive — opens a browser to authorise your zone):
   ```bash
   cloudflared tunnel login
   ```

3. **Create the tunnel** and note the `<TUNNEL_ID>` it prints:
   ```bash
   cloudflared tunnel create synth-webhook
   ```

4. **Create the `cloudflared` system user** that the systemd unit runs as:
   ```bash
   sudo useradd --system --no-create-home --shell /usr/sbin/nologin cloudflared
   ```

5. **Copy the reference config** into `/etc/cloudflared/config.yml`:
   ```bash
   sudo mkdir -p /etc/cloudflared
   sudo cp .infra-scratch/cloudflared-config.yml /etc/cloudflared/config.yml
   ```
   The reference (`.infra-scratch/cloudflared-config.yml`) is:
   ```yaml
   tunnel: <TUNNEL_ID>
   credentials-file: /etc/cloudflared/<TUNNEL_ID>.json
   ingress:
     - hostname: synth-webhook.yourdomain.com
       service: http://localhost:8000
     - service: http_status:404
   ```
   Edit it to substitute `<TUNNEL_ID>` and your real hostname.

6. **Move tunnel credentials** (generated in step 3) and set ownership:
   ```bash
   sudo mv ~/.cloudflared/<TUNNEL_ID>.json /etc/cloudflared/
   sudo chown cloudflared:cloudflared /etc/cloudflared/<TUNNEL_ID>.json
   ```

7. **Route DNS** to the tunnel:
   ```bash
   cloudflared tunnel route dns synth-webhook synth-webhook.yourdomain.com
   ```

8. **Install the systemd unit** at `/etc/systemd/system/cloudflared.service`:
   ```bash
   sudo cp .infra-scratch/cloudflared.service /etc/systemd/system/
   ```
   The unit (`.infra-scratch/cloudflared.service`) is:
   ```ini
   [Unit]
   Description=Cloudflare Tunnel for Synth webhook
   After=network.target docker.service
   Wants=docker.service

   [Service]
   Type=simple
   User=cloudflared
   ExecStart=/usr/local/bin/cloudflared tunnel --config /etc/cloudflared/config.yml run synth-webhook
   Restart=on-failure
   RestartSec=5s

   [Install]
   WantedBy=multi-user.target
   ```

9. **Enable + start**:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now cloudflared
   sudo systemctl status cloudflared
   ```

10. **Point the backend at the tunnel**: set `WEBHOOK_BASE_URL=https://synth-webhook.yourdomain.com` in production `backend/.env`, then restart the backend.

## Verification

From any machine:
```bash
curl -I https://synth-webhook.yourdomain.com/api/health
# Expect: HTTP/2 200 with Cloudflare headers (cf-ray, server: cloudflare)
```

From the Recall.ai dashboard (<TO VERIFY: Recall dashboard URL — https://api.recall.ai/dashboard/ or similar>), set `WEBHOOK_BASE_URL=https://synth-webhook.yourdomain.com` and deploy a test bot to a meeting. Watch `sudo journalctl -u cloudflared -f` for incoming requests.

## Local development

For quick webhook testing without a permanent hostname, use a temporary tunnel:
```bash
cloudflared tunnel --url http://localhost:8000
```
This prints a throwaway `*.trycloudflare.com` URL. Set it as `WEBHOOK_BASE_URL` in `backend/.env` for the session. The URL changes on every invocation — use a named `dev.*` tunnel for stable dev work.

## Rotation / rollback

To rotate the tunnel:
```bash
cloudflared tunnel delete synth-webhook
cloudflared tunnel create synth-webhook-v2
# Update DNS + /etc/cloudflared/config.yml + credentials file, restart cloudflared
sudo systemctl restart cloudflared
```

Tunnel credentials (`<TUNNEL_ID>.json`) are secrets. Store a backup in your password manager.

## Failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| 404 from tunnel | ingress rule mismatch | Check `hostname:` value in `/etc/cloudflared/config.yml` |
| 502 from tunnel | backend down | `docker compose ps backend`, restart if unhealthy |
| Tunnel won't connect | credentials missing or wrong owner | Re-copy `<TUNNEL_ID>.json` into `/etc/cloudflared/`, `chown cloudflared:cloudflared` |
| `systemctl status` shows "user cloudflared does not exist" | system user skipped | Run step 4 above |
| Cloudflare rate limit | free tier hit 100 req/s | Upgrade plan or switch to Caddy on public IP |
