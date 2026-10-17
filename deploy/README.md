# Prepare a domain on a private Linux VPS

These are deployment templates, not an already deployed website. The app remains a single-instance Python/SQLite service. GitHub Pages and ordinary static/shared hosting cannot run it. Use a maintained Ubuntu 24.04 VPS with Python 3.12, an operator responsible for updates/backups, and a separate test environment before inviting customers.

## 1. Install the release privately

Install Git, Python 3.12 with venv support, Poppler (`poppler-utils`) and Caddy from their supported repositories. Create a system account named `chargeready` with no interactive login. Clone the GitHub repository into `/opt/chargeready`, owned by root and readable by that service account. Create `/opt/chargeready/.venv` and install `requirements-lock.txt`. Do not copy any local preview database or example test accounts to the server.

Create `/etc/chargeready` owned by root with mode 0700 and `/var/lib/chargeready` owned by chargeready with mode 0700. Copy `production.env.example` to `/etc/chargeready/production.env` owned by root with mode 0600. Fill it using a private server editor, never GitHub/chat. Generate a server key using the virtual environment: `python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'`. Store it privately in VISA_SECRET_KEY and keep a separate protected copy. Do not rotate it casually: existing encrypted server records depend on it.

Complete the operator policy text and actual independent legal/content/security review before changing LEGAL_REVIEW_APPROVED to yes. Configure working TLS SMTP and verify delivery. Configure PayPal sandbox and test captures/refunds/verified webhooks before using live checkout. AI is optional and needs its own server-side provider key and quality/cost evaluation. See HOSTINGER_DEPLOYMENT.md for the remaining owner work. Never expose development mode as a public workaround.

## 2. Connect the domain and HTTPS

The prepared app address is `https://prep.particlesolidlab.com`. This is a proposed subdomain, not a registered DNS change or a live deployment. Keep the current apex domain and www records, GitHub Pages custom-domain settings and Particle Solid Lab repository unchanged. Add only a new `prep` DNS record once a separate app server is provisioned. A `/chargeready` page on the existing GitHub Pages site cannot run this Python backend.

Set an A record for the chosen domain to the VPS public IPv4 address. Add an AAAA record only if IPv6 reaches the same server. Use precisely that HTTPS domain for VISA_ORIGIN. Confirm prep.particlesolidlab.com in Caddyfile and install it as `/etc/caddy/Caddyfile`; merge carefully if the server already hosts other sites. Validate with `caddy validate --config /etc/caddy/Caddyfile`. Only ports 80 and 443 need public web access; restrict SSH to the operator and keep port 8765 private. Preserve current SSH access while changing firewall rules.

Copy chargeready.service to `/etc/systemd/system/chargeready.service`, run `systemctl daemon-reload`, then enable/start chargeready and reload Caddy. The app deliberately binds to 127.0.0.1, reachable through Caddy only. The service uses `/var/lib/chargeready` for persistent data; code is read-only. Startup refuses missing production requirements.

## 3. Create the owner administrator

There is no shipped admin username/password and no public account upgrade endpoint. On the VPS, run this command as root. It loads the same private environment and runs the owner-only interactive setup as the service user:

```sh
sudo systemd-run --wait --pty --collect --service-type=exec   --property=User=chargeready --property=Group=chargeready   --property=WorkingDirectory=/opt/chargeready   --property=EnvironmentFile=/etc/chargeready/production.env   --property=UMask=0077   /opt/chargeready/.venv/bin/python /opt/chargeready/admin_setup.py
```

Enter your private admin email and a unique password when prompted. Open `https://YOUR-DOMAIN/admin`, sign in, enroll authenticator MFA, and store backup codes offline. This console manages users, payments, support and operational metadata; it does not reveal browser-encrypted raw applicant answers. Owner recovery resets sessions; follow README.md before resetting MFA or passwords. Never reuse the local test credentials.

## 4. Verify before launch

Run application tests in a disposable environment with synthetic data. On the real domain verify HTTPS, registration/email verification, sign-in/sign-out, refresh/unlock, save and resume after a restart, account separation, recovery, admin MFA, support reports, PayPal sandbox purchase/refund/webhook replay, AI consent/credits if enabled, and actual 2–3 page PDF download on desktop and phone. Watch `systemctl status chargeready` and `journalctl -u chargeready` for service errors; never log request bodies or secret values. The templates have not been executed on a live Linux VPS.

Set up encrypted off-server backups using maintenance.py and a separate VISA_BACKUP_KEY delivered through a private environment file. Preserve the server secret separately, choose lawful retention and test a restore into a new private database. A backup file on the same VPS is not disaster recovery. Stop the app before restoring; do not overwrite the only database. Before upgrades back up data, record the previous commit, run tests and restart the service. A code rollback may also need a compatible database snapshot; migrations are not automatically reversed.
