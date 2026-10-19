---
layout: default
title: Deploying AlakhService
---

# Deploying AlakhService to production

This guide takes you from nothing to a live AlakhService on **one Linux server** with Docker.
You do not need DevOps experience: every step says what to type and what you should see. Plan
for about two hours the first time, most of it waiting for DNS, Razorpay and the first build.

When you are done you will have:

| Address | What it is |
|---|---|
| `https://api.<your domain>` | The API. The mobile app and both dashboards talk to it. |
| `https://shop.<your domain>` | Shop owner dashboard |
| `https://admin.<your domain>` | Admin dashboard (you can limit it to your own IP) |

```
             Internet (80/443 only)
                     │
             ┌───────▼────────┐  automatic HTTPS (Let's Encrypt), security headers,
             │     Caddy      │  serves both dashboards as static files
             └───────┬────────┘
                     │ api.<domain>
             ┌───────▼────────┐  sign-in checks, rate limits, circuit breakers, /metrics
             │  API gateway   │
             └───────┬────────┘
     ┌───────────────┼──────────────────┐   17 Python services, each with its own
     │ auth  booking  payment  shop ... │   database; migrations run on start
     └───────────────┬──────────────────┘
          PostgreSQL · Redis · backup (daily, verified) · optional monitoring
```

Nothing except Caddy is reachable from the internet. The database, Redis and every service
listen only inside Docker's private network.

**Contents:**
[1. What you need](#1-what-you-need) ·
[2. Choose a server](#2-choose-a-server) ·
[3. DNS](#3-point-your-domain-at-the-server) ·
[4. Prepare the server](#4-prepare-the-server) ·
[5. Get the code](#5-get-the-code) ·
[6. Fill in .env.production](#6-fill-in-envproduction) ·
[7. Preflight](#7-preflight) ·
[8. Deploy](#8-deploy) ·
[9. First admin](#9-create-the-first-admin) ·
[10. Verify](#10-verify-everything) ·
[Backups](#backups) ·
[Monitoring](#monitoring) ·
[Updating](#updating) ·
[Rolling back](#rolling-back) ·
[Changing secrets](#changing-secrets) ·
[Android release](#android-release-play-store) ·
[Troubleshooting](#troubleshooting) ·
[Limits](#known-limits-of-this-setup)

---

## 1. What you need

- **A domain name** you control, e.g. `alakhservice.in` (any registrar: GoDaddy, Namecheap,
  BigRock, Cloudflare...).
- **A Linux server** (step 2), with an SSH key to log in.
- **A Razorpay account** with KYC completed, for online payments. Without it, customers can only
  pay cash; everything else works.
- **An SMS provider** for one-time sign-in codes. The code supports **Twilio**. Sending SMS to
  Indian numbers requires **DLT registration** (TRAI rules): register your business and an SMS
  template on a DLT portal (Jio, Airtel, Vodafone Idea or BSNL), then link the sender ID and
  template in Twilio. This can take a few days, so start early. Without SMS, phone-number sign-in
  does not work, but email and password sign-in does.
- **An email (SMTP) account** for password-reset emails and alerts, e.g. Amazon SES (Mumbai
  region), Zoho Mail, Brevo or Google Workspace. It must support port **587 (STARTTLS)**.
- *Optional:* a Firebase project for push notifications, and a Telegram bot for alerts.

## 2. Choose a server

**Size.** The stack runs about 25 containers.

| | vCPU | Memory | Disk | Good for |
|---|---|---|---|---|
| Minimum | 2 | 4 GB + 4 GB swap | 40 GB SSD | trying it out; builds are slow |
| **Recommended** | 2–4 | **8 GB** | 80 GB SSD | launch and the first thousands of users |
| Growing | 4–8 | 16 GB | 160 GB SSD | heavier traffic, monitoring on, room to spare |

Use **Ubuntu 24.04 LTS** (any modern Linux with Docker works; the commands below are for Ubuntu).

**Where.** Pick an **Indian region**: your users get lower latency (tens of milliseconds closer
than Singapore or Europe), and keeping customers' personal data in India keeps you on the simple
side of data-protection questions.

| Provider | Indian regions | Approx. monthly cost for 2–4 vCPU / 8 GB |
|---|---|---|
| DigitalOcean | Bangalore (BLR1) | about ₹4,000–4,500 (Basic droplet, 8 GB) |
| AWS Lightsail | Mumbai | about ₹3,500–4,000 (8 GB plan) |
| AWS EC2 | Mumbai (ap-south-1), Hyderabad (ap-south-2) | about ₹6,000–7,000 (t3.large + 80 GB gp3, on demand; less with a savings plan) |
| Azure | Central India (Pune), South India (Chennai) | about ₹6,000–8,000 |
| Google Cloud | Mumbai, Delhi | about ₹6,000–8,000 |
| Oracle Cloud | Mumbai, Hyderabad | low; the free tier's Arm VMs can run a small setup |
| E2E Networks, other Indian hosts | several Indian cities | often cheaper; check that Docker is allowed |
| Hetzner | **none in India** (nearest: Singapore) | cheapest, but data leaves India and latency is higher |

Prices are rough list prices before GST, converted at about ₹88/USD, and they change often:
check the provider's pricing page. Add about 20% for the provider's own snapshot backups if you
turn them on (recommended, in addition to the database backups below).

**Data protection (DPDP).** India's Digital Personal Data Protection Act, 2023 and its Rules apply
to the names, phone numbers and addresses this platform stores. Today they do not force all
personal data to stay in India, but the government can restrict transfers to particular
countries, and sector rules can be stricter (RBI's payment-data rules apply to payment providers
such as Razorpay; the platform itself stores only payment references, never card numbers).
Hosting in an Indian region, and keeping backups in India too, is the low-risk choice. This is
not legal advice; for a business launch, talk to a lawyer about your privacy policy, consent and
grievance-officer duties.

**Firewall.** In the provider's firewall / security group allow only:

| Port | From | Why |
|---|---|---|
| 22/tcp | your IP (or anywhere, with SSH keys only) | SSH |
| 80/tcp | anywhere | Let's Encrypt checks and redirect to HTTPS |
| 443/tcp and 443/udp | anywhere | HTTPS (udp = HTTP/3) |

Note the server's **public IP address**; you need it next.

## 3. Point your domain at the server

At your DNS provider create three **A records** (TTL 300 or "automatic"):

| Type | Name | Value |
|---|---|---|
| A | `api` | your server's public IP |
| A | `shop` | your server's public IP |
| A | `admin` | your server's public IP |

If the server also has an IPv6 address you may add matching `AAAA` records; otherwise do not add
any. **Using Cloudflare?** Set these records to **DNS only** (grey cloud). With the orange-cloud
proxy on, Caddy would see Cloudflare's addresses instead of your visitors', and rate limits and
the admin IP allowlist would stop working properly.

Check from your laptop (changes can take from minutes to a few hours to appear):

```bash
dig +short api.alakhservice.in     # must print your server's IP
dig +short shop.alakhservice.in
dig +short admin.alakhservice.in
```

## 4. Prepare the server

Log in (`ssh ubuntu@<server ip>`; the user name depends on the provider: `root`, `ubuntu`, ...),
then:

```bash
# Updates, and security updates installed automatically from now on
sudo apt update && sudo apt -y upgrade
sudo apt -y install git make python3 curl unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# If you logged in as root, create a normal user and use it from now on
#   adduser deploy && usermod -aG sudo deploy && rsync -a ~/.ssh /home/deploy/ && chown -R deploy: /home/deploy/.ssh

# Docker Engine + the Compose plugin (official installer)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# Log out and back in so the group change applies, then check:
docker run --rm hello-world
docker compose version          # needs v2.24 or newer

# Swap: lets the first build finish on smaller servers (recommended everywhere)
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Host firewall (in addition to the provider's). Docker's published ports are only 80/443.
sudo ufw allow OpenSSH && sudo ufw allow 80/tcp && sudo ufw allow 443/tcp && sudo ufw allow 443/udp
sudo ufw --force enable
```

## 5. Get the code

```bash
sudo mkdir -p /opt/alakhservice && sudo chown "$USER": /opt/alakhservice
git clone https://github.com/alakh8653/AlakhService.git /opt/alakhservice
cd /opt/alakhservice
```

If the repository is private, either add a read-only
[deploy key](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/managing-deploy-keys)
and clone with `git@github.com:alakh8653/AlakhService.git`, or log in with `gh auth login` first.

All commands from here on run in `/opt/alakhservice`.

## 6. Fill in .env.production

```bash
cp .env.production.example .env.production
chmod 600 .env.production
nano .env.production
```

Every setting is explained in the file. Replace every `REPLACE_ME`. The essentials:

**Domain and HTTPS**

- `DOMAIN`: your bare domain, e.g. `alakhservice.in` (no `https://`, no `www.`).
- `ACME_EMAIL`: your email; Let's Encrypt writes here if a certificate cannot be renewed.
- `CORS_ORIGINS`: `https://shop.<DOMAIN>,https://admin.<DOMAIN>`
- `PASSWORD_RESET_URL`: `https://shop.<DOMAIN>/reset-password`
- `ADMIN_ALLOWED_IPS` *(optional)*: your office/home IP, e.g. `203.0.113.7/32` (find it at
  [ifconfig.me](https://ifconfig.me)). Only these addresses can open the admin dashboard and call
  admin APIs. The default allows everyone (the admin login still applies).

**Secrets.** Generate each one separately; do not reuse values:

```bash
openssl rand -hex 32    # JWT_SECRET_KEY
openssl rand -hex 32    # INTERNAL_API_KEY
openssl rand -hex 32    # METRICS_TOKEN
openssl rand -hex 24    # POSTGRES_PASSWORD
openssl rand -hex 24    # RAZORPAY_WEBHOOK_SECRET (also pasted into Razorpay, below)
```

Save a copy of the finished file in a password manager. `POSTGRES_PASSWORD` is stored in the
database on the very first start; see [Changing secrets](#changing-secrets) before changing it later.

**Razorpay (online payments)**

1. In the [Razorpay dashboard](https://dashboard.razorpay.com), complete KYC and switch to
   **Live mode** (toggle at the top).
2. *Account & Settings → API Keys → Generate Key.* Put the **Key Id** (`rzp_live_...`) in
   `RAZORPAY_KEY_ID` and the **Key Secret** in `RAZORPAY_KEY_SECRET`. The secret is shown only once.
3. *Account & Settings → Webhooks → Add New Webhook:*
   - **Webhook URL:** `https://api.<DOMAIN>/api/v1/webhooks/razorpay`
   - **Secret:** the `RAZORPAY_WEBHOOK_SECRET` you generated
   - **Active events:** `payment.captured`, `payment.failed` and `order.paid`
4. *Account & Settings → Payment capture:* make sure payments are **captured automatically**.

Test first if you like: test-mode keys (`rzp_test_...`) work the same way (with a webhook created
in test mode); preflight warns you so you do not go live by accident with test keys.

**SMS (Twilio)**: `TWILIO_ACCOUNT_SID` (starts with `AC`), `TWILIO_AUTH_TOKEN` and
`TWILIO_FROM_NUMBER` from the [Twilio console](https://console.twilio.com). For Indian numbers,
complete DLT registration (see [What you need](#1-what-you-need)). Other Indian SMS providers
(MSG91, Gupshup, ...) are not supported by the code yet.

**Email (SMTP)**: `SMTP_HOST`, `SMTP_PORT=587`, `SMTP_USERNAME`, `SMTP_PASSWORD` and a verified
`SMTP_FROM_EMAIL`. Add the SPF and DKIM DNS records your provider gives you, or the emails will
land in spam.

**Push notifications** *(optional)*: Firebase console → Project settings → Service accounts →
*Generate new private key*. Put the JSON on one line into `FCM_SERVICE_ACCOUNT_JSON`:

```bash
python3 -c 'import json,sys; print(json.dumps(json.load(open(sys.argv[1]))))' ~/firebase-key.json
```

**Backups and monitoring**: see [Backups](#backups) and [Monitoring](#monitoring). The defaults
are fine to start with.

## 7. Preflight

```bash
make prod-preflight
```

This checks the file and the server **without changing anything**: every required value is
present, no placeholders are left, secrets are long enough and different, CORS matches your
domain, Razorpay/Twilio/SMTP are fully configured or deliberately off, Razorpay key type
(live/test), Docker and Compose versions, free disk and memory, and that `api.`, `shop.` and
`admin.` resolve to this server. Lines marked **FAIL** must be fixed; **WARN** lines are things to
know about (e.g. "Razorpay is not configured: customers can only pay cash"). It ends with
`PREFLIGHT PASSED` or `PREFLIGHT FAILED`.

## 8. Deploy

```bash
make prod-deploy
```

What it does (the same command is used for every later update):

1. `git pull` (fast-forward only) and the preflight again.
2. Builds every image, tagged with the git commit. **The first build takes 5–15 minutes.**
3. Starts PostgreSQL and Redis. On updates, backs up every database before anything migrates.
4. Restarts the services **one at a time**. Each service applies its own database migrations
   (`alembic upgrade head`) when it starts, and the next one waits until it answers `/ready`.
5. Starts the gateway, the backup scheduler and Caddy. On the first start Caddy fetches the HTTPS
   certificates (needs DNS from step 3 and ports 80/443 open).
6. Smoke-tests the live sites through Caddy and prints the URLs.

If a service does not become healthy, the deploy stops, prints that service's last log lines and
tells you what to do (fix and re-run, or `make prod-rollback`).

## 9. Create the first admin

1. Open `https://shop.<DOMAIN>/register` (or use the mobile app) and register your own account.
2. On the server:

   ```bash
   make prod-make-admin ACCOUNT=you@yourdomain.in     # your email or phone number
   ```

3. Sign out and back in at `https://admin.<DOMAIN>`.

Grant further admins the same way. To remove admin rights:
`docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml exec -T auth_service python -m app.cli revoke-admin <email or phone>`.

## 10. Verify everything

- [ ] `make prod-status`: every container `Up ... (healthy)`.
- [ ] The three sites open with a padlock (valid HTTPS).
- [ ] Sign in to the shop dashboard; set up a shop and a service.
- [ ] Book that service from the mobile app (see [Android release](#android-release-play-store)).
- [ ] Make a small **real** payment (e.g. ₹1 service), then refund it from the Razorpay dashboard.
      In Razorpay → Webhooks, the webhook's recent deliveries must show **200**.
- [ ] "Forgot password" on the shop dashboard sends an email.
- [ ] Phone sign-in on the app receives an SMS code.
- [ ] `make prod-backup` finishes with a verified backup.
- [ ] If monitoring is on: Grafana shows traffic, and a test alert reaches you (see below).

---

## Backups

The `backup` container backs up every database every `BACKUP_INTERVAL_HOURS` (24) into
`backups/<timestamp>/`, **restores each backup into a scratch database to prove it works**, and
keeps `BACKUP_KEEP_DAYS` (14) days. Details, restores and recovery: [DISASTER_RECOVERY.md](DISASTER_RECOVERY.md).

| Command | What it does |
|---|---|
| `make prod-backup` | Back up now, verify it, and copy it off-site (if configured) |
| `make prod-status` | Shows when the last verified backup was made |
| `make prod-verify-backup [BACKUP=backups/<ts>]` | Prove a backup restores (latest by default) |
| `make prod-restore BACKUP=backups/<ts> [DBS="booking_db"]` | Restore **next to** the live data as `<db>_restored`; nothing is overwritten |
| `make prod-restore-in-place BACKUP=backups/<ts> [DBS=...]` | Replace live databases (stops the services, restores, starts them again) |

On the server use these `prod-` targets: the `db-*` targets in DISASTER_RECOVERY.md are for a
development stack and do not read `.env.production`.

**Off-site copies (do this).** A backup on the same disk dies with the disk or the server. Copy
backups somewhere else with [rclone](https://rclone.org), which works with Amazon S3 (choose
`ap-south-1` Mumbai to keep data in India), Cloudflare R2, Backblaze B2, Google Drive and more:

```bash
sudo apt -y install rclone          # or: curl https://rclone.org/install.sh | sudo bash
rclone config                       # add a remote, e.g. "s3mumbai" (type s3, region ap-south-1)
#   recommended: add a second remote of type "crypt" on top of it, so files are encrypted
#   before they leave the server (backups contain customers' names and phone numbers)
```

Set `OFFSITE_RCLONE_REMOTE=s3mumbai:alakh-backups` (your remote and bucket) in `.env.production`,
test with `scripts/deploy/offsite-backup.sh`, then schedule it an hour after the daily backup:

```bash
sudo crontab -e
# add:
30 4 * * * cd /opt/alakhservice && scripts/deploy/offsite-backup.sh >> /var/log/alakh-offsite.log 2>&1
```

The script only adds files off-site, never deletes. Turn on **versioning or object lock** in the
bucket, and a lifecycle rule to delete copies after e.g. 90 days. (The `BACKUP_UPLOAD_COMMAND`
hook in DISASTER_RECOVERY.md runs inside the small backup container, which has no cloud tools;
on a single server the rclone cron above is simpler.)

**Also:** turn on your provider's snapshot backups for the whole server, and once a quarter
restore the latest off-site backup on a spare server (DISASTER_RECOVERY.md, "The whole server is lost").

## Monitoring

Optional, light (about 600 MB of memory), and private to the server. Turn it on in
`.env.production`:

```bash
COMPOSE_PROFILES=monitoring
GRAFANA_ADMIN_PASSWORD=<openssl rand -hex 16>
ALERT_EMAIL_TO=you@yourdomain.in         # uses the SMTP_* settings
TELEGRAM_BOT_TOKEN=                      # and/or Telegram (below)
TELEGRAM_CHAT_ID=
```

then `make prod-deploy`. It adds Prometheus, Alertmanager, Grafana, a blackbox prober and a
server-metrics exporter.

**Open Grafana** through an SSH tunnel (it is not exposed to the internet):

```bash
ssh -L 3001:127.0.0.1:3001 deploy@<server ip>       # on your laptop; keep it open
# then browse to http://localhost:3001  (user: admin, password: GRAFANA_ADMIN_PASSWORD)
```

The **AlakhService overview** dashboard shows services not ready, open circuits, error rate,
backup age, requests/errors/p95 latency per service, rate-limited (429) and auth (401/403)
responses, Redis errors, public HTTPS checks, CPU, memory, disk and certificate expiry.

**Alerts** (deploy/monitoring/prometheus/alerts.yml):

| Alert | Means | First thing to check |
|---|---|---|
| ServiceDown | a service fails `/ready` for 2 min | `make prod-logs S=<service>` |
| GatewayMetricsDown | gateway down, or METRICS_TOKEN changed | `make prod-logs S=api_gateway` |
| PublicSiteDown | HTTPS through Caddy fails for 5 min | `make prod-logs S=caddy`, DNS |
| CertificateExpiresSoon | certificate renewal failing | DNS, ports 80/443, Caddy logs |
| HighErrorRate | > 5% 5xx for a service for 5 min | that service's logs |
| HighLatencyP95 | p95 > 2 s for 10 min | `docker stats`, database load |
| CircuitOpen | gateway stopped calling a failing service | that service's logs |
| RedisErrors | gateway cannot reach Redis | `make prod-logs S=redis` |
| BackupTooOld / BackupMetricMissing | no verified backup for 50 h | `make prod-logs S=backup`, `make prod-backup` |
| DiskAlmostFull | < 15% disk free | `docker image prune -a`, old backups, bigger disk |
| MemoryLow | < 10% memory available | `docker stats`; consider a bigger server |

**Telegram alerts:** talk to [@BotFather](https://t.me/BotFather), `/newbot`, copy the token into
`TELEGRAM_BOT_TOKEN`. Send your new bot any message, open
`https://api.telegram.org/bot<TOKEN>/getUpdates` and copy `"chat":{"id": ...}` into
`TELEGRAM_CHAT_ID`.

**Test an alert:** stop a service for a few minutes, wait for the alert, then start it again:

```bash
docker stop alakh_analytics_service    # ServiceDown arrives after about 2-3 minutes
docker start alakh_analytics_service
```

Prefer a hosted uptime check too (UptimeRobot, Better Stack, ...) on `https://api.<DOMAIN>/health`:
it still alerts you when the whole server is down, which on-server monitoring cannot.

## Updating

```bash
cd /opt/alakhservice
make prod-deploy
```

This pulls the latest code, backs up the databases, rebuilds, restarts services one by one and
smoke-tests. It is safe to re-run. Each service is down for a few seconds while it restarts
(requests to it may briefly fail), so update at a quiet hour. Useful options:
`make prod-deploy ARGS=--no-pull` (deploy what is checked out, e.g. a specific tag after
`git checkout v1.2.0`).

Other day-to-day commands:

| Command | What it does |
|---|---|
| `make prod-status` | containers and health, deployed version, last backup, disk |
| `make prod-logs` / `make prod-logs S=payment_service` | follow logs (Ctrl-C to stop); logs rotate at 5 × 10 MB per container |
| `make prod-smoke` | re-run the smoke test |
| `make prod-restart` | start the deployed version again without building (after a restore, or if you stopped things) |
| `make prod-config` | check the compose files with your settings |

## Rolling back

```bash
make prod-rollback
```

Every deploy keeps the images of the previous one. Rollback switches back to them (no rebuild)
and smoke-tests. If the newer version changed a database, rollback first undoes those
migrations; it lists the affected services and **asks before doing that**, because data stored
only in new tables or columns is lost. If a migration cannot be undone, restore the backup taken
just before the deploy (DISASTER_RECOVERY.md). Running rollback again returns to the newer version.

After a rollback the checkout still has the newer code, and the next `make prod-deploy` deploys
it again; fix forward, or `git checkout <older commit>` and deploy with `ARGS=--no-pull`.

## Changing secrets

| Secret | How to change it | Effect |
|---|---|---|
| `JWT_SECRET_KEY` | edit, `make prod-deploy` | everyone is signed out |
| `INTERNAL_API_KEY`, `METRICS_TOKEN` | edit, `make prod-deploy` | none |
| Razorpay, Twilio, SMTP, Firebase | edit, `make prod-deploy` | none |
| `POSTGRES_PASSWORD` | first change it in the database, then in the file (below) | none |

```bash
C="docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml"
$C exec postgres psql -U alakh -d postgres -c "ALTER USER alakh PASSWORD 'NEW_PASSWORD';"
# put NEW_PASSWORD into POSTGRES_PASSWORD in .env.production, then
make prod-deploy
```

## Android release (Play Store)

The app finds the API through the `API_BASE_URL` build setting
(`apps/mobile_app/lib/core/constants/api_constants.dart`). Without it the app uses
`https://api.alakhservice.com`, so **always pass your own** when building a release.

**1. Create the upload keystore (once, keep it forever).** You need Java 17 (or Android Studio):

```bash
keytool -genkeypair -v -keystore ~/alakh-upload.jks -alias upload \
  -keyalg RSA -keysize 2048 -validity 10000
```

Store the `.jks` file and both passwords in your password manager and an offline backup. With
Play App Signing (the default for new apps) Google holds the real signing key; if you lose this
upload key you can ask Google to reset it, but it takes time.

**2. Build locally.** Create `apps/mobile_app/android/key.properties` (git-ignored):

```properties
storeFile=/home/you/alakh-upload.jks
storePassword=...
keyAlias=upload
keyPassword=...
```

then:

```bash
cd apps/mobile_app
flutter pub get
# Play Store wants an App Bundle (.aab); also set GOOGLE_MAPS_API_KEY if you use maps
flutter build appbundle --release --dart-define=API_BASE_URL=https://api.alakhservice.in
# output: build/app/outputs/bundle/release/app-release.aab
# or an APK to install directly on phones:
flutter build apk --release --dart-define=API_BASE_URL=https://api.alakhservice.in
```

Before each new upload, raise `version:` in `apps/mobile_app/pubspec.yaml` (e.g. `1.0.1+2`; the
number after `+` must always increase). The application id `com.alakhservice.alakh_service`
cannot be changed after the first Play Store upload.

**3. Or let GitHub build it.** The Mobile CI workflow signs its release APK when these
repository **secrets** exist (*Settings → Secrets and variables → Actions → Secrets*):

| Secret | Value |
|---|---|
| `ANDROID_KEYSTORE_BASE64` | `base64 -w0 ~/alakh-upload.jks` (on macOS: `base64 -i ~/alakh-upload.jks`) |
| `ANDROID_KEYSTORE_PASSWORD` | the keystore password |
| `ANDROID_KEY_ALIAS` | `upload` |
| `ANDROID_KEY_PASSWORD` | the key password |

and this repository **variable** (*... → Variables*): `API_BASE_URL` = `https://api.<DOMAIN>`.
The signed APK is attached to each run as the `android-apk` artifact. (CI builds an APK, handy for
testers; build the `.aab` for the Play Store locally as above.)

**4. Publish.** In the [Play Console](https://play.google.com/console): create the app, upload the
`.aab` to **Internal testing** first, fill in the store listing, content rating, and the **Data
safety** form (the app collects name, phone number, email, location for bookings, and payment
info handled by Razorpay), and a privacy-policy URL. Promote to production when testers are happy.

---

## Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| Preflight: "does not resolve yet" | DNS records missing or not propagated; check with `dig +short api.<DOMAIN>` and wait |
| Browser shows a certificate error | Caddy could not get a certificate: DNS wrong, or ports 80/443 closed in the provider firewall. `make prod-logs S=caddy` |
| Dashboard loads, but every action fails / "Network Error" | `CORS_ORIGINS` does not list the dashboard's exact address, or `DOMAIN` changed after the build; fix and `make prod-deploy` |
| A service keeps restarting | `make prod-logs S=<service>`. "Refusing to start in production" means a secret is too short or a placeholder |
| Deploy stops at "did not become healthy" | read the printed log lines; usually a migration error or the database is unreachable |
| Build killed / "exit code 137" | out of memory: add swap (step 4) or a bigger server |
| Razorpay payments stay "pending" | webhook URL or secret wrong; check Razorpay → Webhooks → deliveries; `make prod-logs S=payment_service` |
| No OTP SMS | Twilio not set, or DLT template/sender not approved; `make prod-logs S=auth_service` |
| Admin dashboard says "not allowed from this network" | your IP is not in `ADMIN_ALLOWED_IPS`; update it and `make prod-deploy` |
| Disk full | `docker image prune -a`, `docker builder prune`, check `backups/`, grow the disk |
| `PublicSiteDown` alert, but the sites work in your browser | the server cannot reach its own public IP (some providers block this "hairpin" traffic); rely on an external uptime check and ignore or delete that alert |

## Known limits of this setup

Be aware of what a single server does and does not give you:

- **One server, one point of failure.** If the server dies, the site is down until you restore
  it (DISASTER_RECOVERY.md) — hence off-site backups and provider snapshots. Restarts during
  updates cause a few seconds of errors per service; there is no zero-downtime deploy.
- **Avatar uploads are not stored yet.** `user_service` records a path but does not write the
  image anywhere; object storage (S3/R2) is still to be added in the code.
- **SMS: Twilio only;** SMTP: port 587 (STARTTLS) only.
- **Redis has no password.** It is reachable only inside the Docker network, never from the
  internet. Add one if other software will share the server.
- **The gateway has no `/ready`;** its health check uses `/health`, and the Python services'
  `/ready` checks cover the databases and Redis.
- **Verified here vs. on a server.** The repository's CI (`deploy-check.yml`) validates the
  compose files, Caddyfile, preflight, shell scripts, Prometheus/Alertmanager configs and alert
  rules, and builds the Caddy + dashboards image. The full stack starting on a real VM, Let's
  Encrypt issuance, Razorpay webhooks, SMS and email can only be confirmed on your server: that is
  what step 10 is for.
