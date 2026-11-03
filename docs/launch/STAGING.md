# A test server (staging)

A second, small copy of AlakhService where you and a few real shops can try everything with **test
money** before the live launch, and later before every big update. It is installed exactly like
production ([DEPLOYMENT.md](../DEPLOYMENT.md)), with four differences.

## 1. A separate server and subdomain

- Rent a second small server (2 vCPU, 4 GB RAM is enough). Never run staging on the live server.
- Use a subdomain such as `staging.yourdomain.in`. At your DNS provider, add four A records pointing
  at the staging server: `staging`, `api.staging`, `shop.staging`, `admin.staging`.
- Follow DEPLOYMENT.md steps 4 and 5 on that server, as for production.

## 2. `.env.production` on the staging server

Fill it as DEPLOYMENT.md step 6 describes, with these values:

```bash
DOMAIN=staging.yourdomain.in
# Razorpay TEST keys (Razorpay dashboard → Test mode → API keys): no real money moves.
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_WEBHOOK_SECRET=...      # a test-mode webhook pointing at https://api.staging.yourdomain.in/api/v1/webhooks/razorpay
# Your real company details, so test invoices look exactly like live ones.
PLATFORM_LEGAL_NAME=...
PLATFORM_GSTIN=...
PLATFORM_ADDRESS=...
# Calls stay off; chat is enough for testing.
CALL_PROVIDER=none
```

Use **new** random secrets (JWT, internal key, database password), never the live ones.

- **SMS:** either use your MSG91 account with the same DLT templates (each message costs a few
  paise), or set `SMS_PROVIDER=none` and sign in with email accounts only.
- **Firebase:** create a second Firebase project, e.g. "AlakhService Staging". Test notifications
  then never reach live customers.

`make prod-preflight` warns that the Razorpay keys are test keys. That is expected here, and is the
only warning about keys you should see.

## 3. A staging build of the app

Build the app against the staging server:

```bash
cd apps/mobile_app
flutter build apk --release \
  --dart-define=API_BASE_URL=https://api.staging.yourdomain.in \
  --dart-define=LEGAL_BASE_URL=https://staging.yourdomain.in \
  --dart-define=APP_LINK_DOMAIN=staging.yourdomain.in \
  --dart-define=SUPPORT_EMAIL=support@yourdomain.in \
  --dart-define=SUPPORT_PHONE=+91XXXXXXXXXX
```

Share the APK with your testers directly, or through a Play **internal testing** track. Don't use
the live track for this.

## 4. Test payments

In Razorpay test mode, use the test cards and UPI IDs from Razorpay's docs ("Test card details").
For example, `success@razorpay` for UPI succeeds, and `failure@razorpay` fails. Refunds appear in
the test dashboard straight away.

## Keeping it useful

- After each update to `main`, run `make prod-deploy` on staging first. Run it on the live server
  only once the [launch checklist](LAUNCH_CHECKLIST.md) flows still work there.
- Staging data is not precious. To start clean:
  - `make prod-backup` first if you want to keep it;
  - wipe it, on staging only, with
    `docker compose --env-file .env.production -f docker-compose.yml -f docker-compose.prod.yml down -v`;
  - then run `make prod-deploy` again.
- Never copy live customers' data to staging. It contains their names and phone numbers.
