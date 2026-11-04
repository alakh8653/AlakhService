# Trust and safety

These features help a customer trust a shop and a professional they have not met. The privacy
rules behind them are in [PRIVACY_AND_CONTACT.md](PRIVACY_AND_CONTACT.md#trust-and-safety-features).

Extra charges after inspection (`/bookings/{id}/extra-charges`, only with the customer's approval) are
documented with that feature in `services/booking_service/app/routers/extra_charges.py`.

All amounts are integer paise. Every route is under `/api/v1` through the gateway.

## Start code: no fake "work started"

- Every booking with `service_mode` `AT_HOME` or `PICKUP_DROP` gets a random 4-digit `start_code` when
  it is made. This includes free-fix bookings. Open bookings made before this feature got one in the
  migration.
- `BookingResponse.start_code` shows the code to the booking's customer and to admins only. Everyone
  else sees `null`.
- To start a home visit (`IN_PROGRESS`) or collect a pickup (`PICKED_UP`), any caller who is not an
  admin sends the code: `PUT /bookings/{id}/status {"status": ..., "start_code": "1234"}`. This covers
  the assigned provider and the shop owner alike.
  - A missing or wrong code returns **422** "Ask the customer for the 4-digit start code".
  - After **5 wrong tries in 15 minutes**, every try returns **429** with `Retry-After` until the
    window ends, even one with the right code. Tries are counted on the booking row, under a row lock,
    and are kept even though the request fails.
  - A move that is not allowed anyway (for example, a pickup step on a home visit) returns its usual
    400 and does not count as a try.
  - Admins may skip the code.
- Bookings at the shop (`AT_SHOP`) work as before.

## Free fix (service guarantee)

- Each shop has `guarantee_days` (0–90, default 7). The owner sets it with `PUT /shops/{id}`. It is
  public in shop responses and in `GET /shops/{id}/hours`, which is where booking_service reads it.
- When a booking is first `COMPLETED`, `guarantee_until` is set to completion time + `guarantee_days`.
  This also happens when a dispute is resolved back to COMPLETED. If shop_service cannot answer, the
  7-day default is used.
- `POST /bookings/{id}/rework {reason (10–500 chars), preferred_at?}`. Only the customer can call it,
  and only while the booking is `COMPLETED` and before `guarantee_until`.
  - It creates a new booking with the same shop, service, mode, address and item, `total_amount` 0,
    status `PENDING`, `rework_of` = the original's id (also in metadata), and a new start code if
    needed. The original gets `rework_booking_id`. The response is 201 with the new `BookingResponse`.
  - `preferred_at`, when given, is checked against opening hours and capacity. Without it, the fix is
    pencilled in for the same hour the next day, for the shop to confirm or move.
  - The shop is sent `booking.created` with `rework: true` and a line saying it costs nothing.
  - Each booking gets one free fix: a second request returns 409, as does a request for a booking
    that is itself a free fix. A unique constraint on `rework_of` covers two requests at once.
  - After the period: **409** "The free-fix period for this booking has ended".

## Share a visit

- `POST /bookings/{id}/share` (the customer only) returns `{url, expires_at}`.
  - The URL is `{SHARE_BASE_URL}/v/{token}`. In production, `SHARE_BASE_URL` is `https://<DOMAIN>`.
  - The path is `/v/` because `/s/` is the shops' app link.
  - Each call returns the same link. It expires 24 hours after the scheduled time, so it follows a
    rescheduled booking.
  - Cancelled bookings and visits that are already over return 409.
- `GET /public/shares/{token}` is public. It returns
  `{shop_name, service_name, status, scheduled_at, provider_first_name, provider_location, eta}`.
  - `provider_location` is `{lat, lng, updated_at}` while the professional is `PROVIDER_EN_ROUTE` or
    `OUT_FOR_DELIVERY`, otherwise null.
  - `eta` is the estimated arrival while the professional is on the way to a home visit, the booked
    time before the visit starts, and null once it has started.
  - An unknown or expired token returns 404.
  - The gateway limits each client to `SHARE_RATE_LIMIT_MAX` requests per `SHARE_RATE_LIMIT_WINDOW_MS`
    (30 a minute by default).
  - The provider's position comes from tracking_service. booking_service asks for it with a
    one-minute access token in the provider's name.
- The public site serves `/v/{token}` (`deploy/site/visit.html`). The page refreshes every 30 seconds.
  It is never cached, never indexed and never sent on as a referrer.

## SOS

- `POST /bookings/{id}/sos {lat?, lng?, note?}` (the customer or the assigned provider) records an
  `SosAlert`. It returns 201 `{alert_id, emergency_number: "112"}`, so the app can offer to call 112.
- Each booking takes at most **3 alerts per 10 minutes**. After that the call returns 429, with a
  message telling the person to call 112.
- Every active admin gets `safety.sos`, by push and always by email (never SMS). Admins are listed by
  auth_service's `GET /internal/users/admins`. Every alert is also logged as an error (`sos_raised`)
  for whoever watches the logs. The alert is recorded even when no admin can be reached.
- `GET /admin/safety/sos?page&per_page&booking_id` lists alerts for admins, newest first.

## Verified badge

- Shop responses include `is_verified` (true once APPROVED) and `verified_at`. `verified_at` is set
  when an admin approves the shop and cleared on rejection or resubmission.
- `GET /shops/ratings?ids=` rows include `is_verified`, so service cards can show the badge.
