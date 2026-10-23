# Legal pages, consent and account deletion

> **DRAFT – have a lawyer review before launch.** The Terms of Service, Privacy Policy, Cancellation
> and Refund Policy and Grievance page in `deploy/site/` were written as a starting point for an
> Indian local-services marketplace (IT Act 2000 and IT Rules 2021, Consumer Protection (E-Commerce)
> Rules 2020, DPDP Act 2023). They are not legal advice. A lawyer should check them against your
> business, and against the DPDP Rules in force when you launch, before you publish them.

## The public site

`deploy/site/` is plain HTML and CSS (no build step), served by Caddy at `https://<DOMAIN>`
(`deploy/Caddyfile`). It is mounted into the Caddy container, so edits on the server are live at once.

| URL | File | Purpose |
|---|---|---|
| `/` | `index.html` | Landing page with store links |
| `/terms` | `terms.html` | Terms of Service |
| `/privacy` | `privacy.html` | Privacy Policy (DPDP Act): data, purposes, retention, rights, Grievance Officer, contact never shared with shops |
| `/refunds` | `refunds.html` | Cancellation and refund policy. Razorpay's KYC review asks for this URL |
| `/grievance` | `grievance.html` | Grievance Officer and complaint timelines |
| `/delete-account` | `delete-account.html` + `delete-account.js` | Delete an account with an emailed/texted code. Use this as Google Play's "delete account" URL |
| `/b/<booking id>` | `open-app.html` | App link to a booking; this page shows only when the app is not installed |
| `/reset-password?token=…` | `reset-password.html` + `reset-password.js` | App link from reset emails; can also reset the password in the browser |
| `/.well-known/assetlinks.json` | | Android App Links for `com.alakhservice.alakh_service` |
| `/.well-known/apple-app-site-association` | | iOS Universal Links |
| `/shop-dashboard` | | Redirects to `https://shop.<DOMAIN>/` |

Each page has a short Hindi summary. The site makes only a few API calls (send code, delete with
code, reset password, legal links), which Caddy forwards on the same origin, so the gateway's CORS list
stays the two dashboards.

### Fill in before launch

The pages show every missing detail as a highlighted `[PLACEHOLDER]`. `grep -n 'class="placeholder"' deploy/site/*.html`
lists them; preflight warns while any remain.

- `[COMPANY LEGAL NAME]`, `[REGISTERED ADDRESS]`, `[CIN]`, `[CITY]` (courts' jurisdiction)
- `[GRIEVANCE OFFICER NAME]`, `[DESIGNATION]`, `[GRIEVANCE EMAIL]`, `[GRIEVANCE PHONE]`, `[HOURS]`,
  `[NODAL CONTACT NAME, EMAIL]`
- `[SUPPORT EMAIL]`, `[EFFECTIVE DATE]`
- Privacy: `[HOSTING PROVIDER, REGION]`, `[MSG91 / TWILIO]`, `[EMAIL PROVIDER]`, retention periods
  (`[180 days]` chat, `[1 year]` security logs, `[14 days]` backups: match `BACKUP_KEEP_DAYS`)
- Refunds: the late-cancellation rule `[No refund / 50% refund]` (match what payment_service does),
  the dispute window `[48 hours]` and decision time `[7 days]`
- Terms: the no-show grace period `[15]` minutes
- `.well-known/assetlinks.json`: the Play app-signing SHA-256 fingerprint; `apple-app-site-association`:
  the Apple Team ID. Both are explained in [DEPLOYMENT.md](DEPLOYMENT.md#6-fill-in-envproduction).
- The App Store button on `index.html` and `open-app.html`, once the iOS app is published.

The refund rules on `/refunds` must match the code: free cancellation 2 hours or more before the
booking; a full refund when the shop cancels or the booking expires unconfirmed; refunds in 5–7
working days.

### Changing the terms

When `terms.html` or `privacy.html` changes materially, update the version line on the pages and set
`TERMS_VERSION` in `.env.production` (e.g. `2027-01`), then `make prod-deploy`. The apps compare it
with the version the user accepted and ask again.

## Consent at sign-up (API)

- `GET /api/v1/legal/current` (public) returns
  `{terms_version, privacy_url, terms_url, refund_url, grievance_url}` (from `TERMS_VERSION` and
  `LEGAL_BASE_URL`, which production sets to `https://<DOMAIN>`).
- `POST /api/v1/auth/register` requires `accepted_terms_version` (the `terms_version` above). Without
  it the answer is **422** `{"detail": "Please accept the Terms and Privacy Policy"}`.
  The version and time are stored on the account (`accepted_terms_version`, `accepted_terms_at` in
  `UserResponse`, e.g. `GET /auth/me`), and recorded in compliance_service's consent register
  (`terms_of_service` and `privacy_policy`, with the IP address and user agent) after the response.
- `POST /api/v1/auth/accept-terms` `{accepted_terms_version}` (signed in) records acceptance of a newer
  version, for accounts created before the field existed (their version is `null`) or after a change.

**What the apps must do:**

1. Before sign-up, call `GET /legal/current`; show an unticked checkbox "I agree to the
   [Terms] and [Privacy Policy]" linking to `terms_url` and `privacy_url`; send
   `accepted_terms_version: terms_version` with the registration. Show the 422 `detail` if it comes back.
2. After sign-in, if `GET /auth/me`'s `accepted_terms_version` differs from `terms_version`, ask
   again and call `POST /auth/accept-terms`.
3. Link Terms, Privacy, Refunds and Grievance from the app's settings/help (the four URLs), and the
   refund policy from the booking/payment screen.

## Account deletion

- **In the app** (signed in): `POST /api/v1/auth/delete-account` `{password}` (existing).
- **On the web, without signing in** (`https://<DOMAIN>/delete-account`; required by Google Play):
  1. `POST /api/v1/auth/send-otp` `{phone_or_email, purpose: "delete_account"}`, answering the same
     whether or not the account exists;
  2. `POST /api/v1/auth/delete-account/otp` `{phone_or_email, code}`: 200 deleted; 401 wrong or expired
     code; 429 after 5 tries per hour per email/phone (on top of 5 guesses per code and the gateway's
     sign-in rate limit per IP).

Both erase the profile, addresses and devices (user_service), anonymise the sign-in so the email and
phone are free again, and sign out every device. Bookings, payments and invoices stay under the
anonymous id. In Play Console → *App content → Data safety*, give `https://<DOMAIN>/delete-account` as
the account deletion URL. Apps with a "Delete account" button should link to the same page as a fallback.

## Notifications and privacy

notification_service never puts anyone's phone number or email into a message (values that look like
one are removed, `app/core/events.py`). When it texts or emails people who have no app installed, it
looks up **their own** contact (`GET /internal/users/{id}/contact` on auth_service) and uses it only as
the address.
