# Cloudflare Tunnel — VPS setup playbook

Run on the production VPS. Replace `<TUNNEL_ID>` and `yourdomain.com` as you go.

0. Prepare backend mount points (so Docker does not auto-create them as root):
   `sudo mkdir -p /srv/synth/backend/chroma_data /srv/synth/backend/uploads /srv/synth/backend/summaries && sudo chown -R 1000:1000 /srv/synth/backend`.
1. Install cloudflared:
   `curl -fsSL https://pkg.cloudflare.com/install.sh | sudo bash && sudo apt-get install -y cloudflared`
2. Authenticate: `cloudflared tunnel login` (opens browser, authorises your zone).
3. Create tunnel: `cloudflared tunnel create synth-webhook` — note the `<TUNNEL_ID>` it prints.
4. Create `cloudflared` user: `sudo useradd --system --no-create-home --shell /usr/sbin/nologin cloudflared`.
5. Copy config: `sudo mkdir -p /etc/cloudflared && sudo cp cloudflared-config.yml /etc/cloudflared/config.yml`.
6. Edit `/etc/cloudflared/config.yml`, substitute `<TUNNEL_ID>` and hostname.
7. Move credentials: `sudo mv ~/.cloudflared/<TUNNEL_ID>.json /etc/cloudflared/ && sudo chown cloudflared:cloudflared /etc/cloudflared/<TUNNEL_ID>.json`.
8. Route DNS: `cloudflared tunnel route dns synth-webhook synth-webhook.yourdomain.com`.
9. Install systemd unit: `sudo cp cloudflared.service /etc/systemd/system/`.
10. Enable + start: `sudo systemctl daemon-reload && sudo systemctl enable --now cloudflared`.
11. Verify: `sudo systemctl status cloudflared` (active) and `curl -I https://synth-webhook.yourdomain.com/api/health`.
12. Set `WEBHOOK_BASE_URL=https://synth-webhook.yourdomain.com` in production `backend/.env`, restart backend.
