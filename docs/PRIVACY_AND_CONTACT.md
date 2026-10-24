# Privacy and contact between customers and shops

## The rule

A shop never gets a customer's direct contact details (phone number or email), and a customer
never sees a shop owner's or staff member's personal phone number through a booking. The two
talk through the platform: an in-app chat on each booking and, if enabled, masked calls. This
works the way Ola and Uber handle riders and drivers. It keeps both sides safe, and it keeps
bookings (and the commission on them) on the platform.

The server enforces the rule, not just the apps: the fields are never in the responses.

## What each side sees

| | Customer sees | Shop owner / assigned provider sees |
|---|---|---|
| Name | The shop's name; staff as "Provider" in chat | The customer's **display name**: first name and last initial ("Ravi S."), or "Customer" |
| Phone / email | Never a staff member's | Never the customer's |
| Address | Their own | The saved address id **only** for a home visit or pickup, and only while the booking is open (not after it is completed, cancelled, disputed or refunded) |
| Notes, item description, status reasons | As written | With phone numbers, emails and UPI handles replaced by "[hidden for your safety]" |
| Reviews | Reviewer as a display name; contact details in comments and replies hidden | The same |
| Walk-in queue | — | Display names |
| Disputes | The shop's messages, contact details hidden | The customer's description and messages, contact details hidden |

Admins see everything, including the original text of masked chat messages.

A shop's public listing shows its name, address and map pin, but not its phone or email. shop_service
returns those only to the shop's owner and to admins (`GET /shops`, `/shops/search` and
`/shops/{id}`); everyone else, signed in or not, gets them as null. Customers reach a shop through the
booking chat, or a masked call once calling is enabled.

### Display names

auth_service holds full names. Other services ask for display names in batches over an internal
route that needs the `X-Internal-Key` header and is not reachable through the gateway:
`POST /internal/users/display-names` with `{"user_ids": [...]}` (200 at most). It returns
`{"names": {"<id>": "Ravi S."}}` and never the phone, email or full name. A name containing digits or "@"
(someone typing a number as their name) reads "Customer". booking_service and queue_service
keep answers for two minutes, and show "Customer" if auth_service is down.

## Booking chat

`GET /api/v1/bookings/{id}/messages?page=1&per_page=50`: page 1 holds the newest messages, and each page is
sorted oldest first. The response also carries `unread`, `can_send`, `open_until` and `calling_enabled`.
`POST /api/v1/bookings/{id}/messages` with `{"body": "..."}` sends a message (1-1000 characters).
`POST /api/v1/bookings/{id}/messages/read` marks the other side's messages as read; they then see `read_at`.

- **Who:** the booking's customer, the owner of its shop and its assigned provider. Admins can
  read but not write. Anyone else gets 404.
- **When:** while the booking is open, and for 24 hours after it is completed, cancelled,
  disputed or refunded. After that the chat is read-only (409 on send).
- **Limits:** each person can send 10 messages a minute and 200 a day per booking (429 beyond that).
- **Notifications:** the other side gets a `booking.message` notification ("New message ...")
  for the first message they have not read yet. The message text is never put in a notification.

### Masking

Before a message is stored, `app/core/contact_filter.py` replaces these with "[hidden for your safety]":

- phone numbers: `+91 98765 43210`, `098765-43210`, `9 8 7 6 5 4 3 2 1 0`, a 10-digit number
  starting with 6-9 or 0, any run of 11 or more digits, and 8 or more digits spelled out
  ("nine eight seven ...")
- emails, including `name (at) gmail (dot) com`
- UPI handles: `ravi@okaxis`, `98765...@ybl`
- WhatsApp and Telegram links (`wa.me/...`, `t.me/...`) and the app names

Times, prices, dates, pin codes and booking numbers pass through unchanged. A masked message is
flagged and keeps its original text for admins. The sender is reported to trust_risk_service as a
`contact_sharing_attempt` signal. The filter catches the usual ways people share a number, not
every possible trick. Admins watch for the rest.

### Admin review

On the admin dashboard, **Contact Sharing** lists:

- `GET /api/v1/admin/chat/flagged?sender_id=&skip=&limit=`: flagged messages with what was written
- `GET /api/v1/admin/chat/repeat-offenders?min_attempts=2&days=30`: people with repeated attempts

Only admins can call these. The gateway maps them to booking_service's `/api/v1/chat-moderation/...`.

## Masked calls (off by default)

`POST /api/v1/bookings/{id}/call` follows the same rules on who and when as the chat. It also
allows 3 calls per 10 minutes. The platform first rings the caller, then connects them to the
other side, from a virtual number. A customer reaches the assigned provider while one is on the
job, and the shop owner otherwise. The shop or provider reaches the customer. booking_service gets
both numbers from auth_service (`GET /internal/users/{id}/call-contact`) at call time. It passes
them to the telephony provider only, and never stores or returns them.

The response is 202 with `{"status", "call_id", "callee", "message"}`. Other responses:

- 501 when calling is not enabled. The apps then show only the chat, and `calling_enabled` is false on the messages page.
- 409 when either side has no phone number on file.
- 502 or 503 when the provider or auth_service fails.

To enable calls, set `CALL_PROVIDER=exotel` and the `EXOTEL_*` settings. Steps are in
[DEPLOYMENT.md](DEPLOYMENT.md#6-fill-in-envproduction). Providers plug in behind the small
`CallBridge` interface in `services/booking_service/app/core/telephony.py`. Adding another one
means one class and one branch in `bridge_from_settings`.
