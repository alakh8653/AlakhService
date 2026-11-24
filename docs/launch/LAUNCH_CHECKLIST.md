# Launch checklist

Go through this top to bottom. Every box is something a person does or confirms; the commands come
from [DEPLOYMENT.md](../DEPLOYMENT.md). Do the whole list on a test server first
([STAGING.md](STAGING.md)), then again on the live one.

## Two to four weeks before

- [ ] **Company and tax:** company legal name, GSTIN and registered address decided. They go into
      `PLATFORM_LEGAL_NAME`, `PLATFORM_GSTIN` and `PLATFORM_ADDRESS` and print on every invoice.
- [ ] **Razorpay:** account created and KYC done. The Refund policy page (`/refunds`) must be live
      for KYC. Keep the test keys for staging and request the live keys.
- [ ] **MSG91:** account created; sender ID and message templates registered on the DLT portal
      (the exact texts are in DEPLOYMENT.md, "SMS"). Approval can take days.
- [ ] **Firebase:** project created; `google-services.json` and the service-account key downloaded.
- [ ] **Domain** bought; DNS ready for `@`, `api`, `shop` and `admin`.
- [ ] **Grievance Officer** named, with an email, phone number and hours.
- [ ] **Lawyer** has read Terms, Privacy, Refunds and Grievance (`deploy/site/`).
- [ ] **Business numbers** decided:
      - commission (`PLATFORM_COMMISSION_PERCENT`, default 10)
      - free cancellation window (`CANCEL_FREE_HOURS`, default 2)
      - late-cancellation fee (`CANCEL_FEE_PERCENT`, default 0)
- [ ] **Android signing key** created and stored in two safe places. Without it you can never
      update the app.
- [ ] **Google Play developer account** created (one-time fee).

## One week before

- [ ] Staging server running with **test** Razorpay keys ([STAGING.md](STAGING.md)).
- [ ] On staging, a full day done end to end by real people (two shops, three customers):
  - [ ] A shop signs up, uploads its documents and is approved from the admin panel.
  - [ ] The shop sets hours, capacity and services (at the shop, home visit, pickup).
  - [ ] A customer books, pays online (test card or UPI) and gets the invoice.
  - [ ] The customer cancels in time: refund appears in the Razorpay test dashboard.
  - [ ] The customer cancels late: the policy you chose applies.
  - [ ] Chat works both ways. Typing a phone number shows "[hidden for your safety]".
  - [ ] A home visit: live tracking shows the professional coming.
  - [ ] Walk-in line: join, check in, "Next customer", board on a TV.
  - [ ] Reminder notification arrives the day before and an hour before.
  - [ ] A dispute is opened and resolved with a refund from the admin panel.
  - [ ] A payout batch is created and marked paid; the shop sees it.
  - [ ] An account is deleted from the app and from `/delete-account`.
- [ ] App installed from Play **internal testing** on at least one cheap Android phone and one
      newer one, in English and in Hindi.
- [ ] Play listing, screenshots and data safety form filled in ([PLAY_STORE_LISTING.md](PLAY_STORE_LISTING.md)).

## Launch day

- [ ] `.env.production` filled with **live** keys; `make prod-preflight` passes with no FAIL lines.
- [ ] `make prod-deploy`, then `make prod-status`: every container healthy.
- [ ] `make prod-make-admin ACCOUNT=you@yourdomain.in`, then sign in at `https://admin.<domain>`.
- [ ] DEPLOYMENT.md, "10. Verify everything", all ticked. That includes a real ₹1 payment and its
      refund, and Razorpay webhook deliveries showing 200.
- [ ] `make prod-backup` finishes with a verified backup, and the off-site copy is there.
- [ ] Monitoring alerts reach your phone or email (send a test alert).
- [ ] First shops approved and visible in the app; every service shows the right price.
- [ ] Play production release rolled out (start at 20%).

## First week

- [ ] Every morning:
  - `make prod-status`
  - the admin panel's Disputes, Contact Sharing and Shops queues
  - Razorpay's failed payments and refunds
- [ ] Reply to every Play review and support email within a day.
- [ ] Watch for shops asking customers to pay outside the app (Contact Sharing page) and act early.
- [ ] After a week with no surprises, take the Play rollout to 100%.

## If something goes wrong

| Problem | First step |
|---|---|
| Site down | `make prod-status`, then `make prod-logs S=<service>` |
| A bad update | `make prod-rollback` |
| Data lost or damaged | [DISASTER_RECOVERY.md](../DISASTER_RECOVERY.md) |
| Payments failing | Razorpay dashboard status, then `make prod-logs S=payment_service` |
| SMS not arriving | MSG91 delivery report; DLT template IDs in `.env.production` |
