# Live queue, waiting times and home visits

How AlakhService tells every customer where they stand in a shop's line today and when they will be
seen, how a shop runs that line from the dashboard or the phone, and how a professional's home visits
are planned so customers know when someone will be at their door. It works for any kind of shop
(salon, clinic, repair counter, spa): the team's services decide who can serve whom.

## 1. For the shop owner (one page)

**What customers get**
- On the booking: their place in line (#3), how many are ahead, the expected start **as a range**
  ("between 11:20 and 11:35"), who will serve them, and how late the shop is running.
- Messages only when something they would notice changes: 5 and 2 ahead, about 15 minutes to go,
  their turn, and a new expected time when it moves by 10 minutes or more, with the reason ("Asha is on a
  short break", "you may be seen sooner"). Never more than one every 5 minutes, 8 a day at most; quiet
  hours hold the updates in the app (their turn always comes through).
- "I'm here" to check in, and "Join today's line now" on a service page while the shop is open.
- Home visits: "your professional arrives around 10:40", the range, how many visits are before theirs,
  and "on the way, arriving around 10:05" when the professional sets off.

**What the shop gets** (dashboard **Live line**, or the **My shop** tab in the app)
- The team today: free, serving whom until when, on a break, off. "Next customer" per person.
- Everyone in line, in order, with expected times; walk-ins added at the counter in seconds.
- Move someone up or down, make a few VIPs a day (capped, so the line stays fair), check people in,
  mark no-shows after a grace period (default 10 minutes; the customer is told, and the usual
  late-cancellation rule decides any refund).
- A breaks or day off button: that person's customers move to whoever else can serve them.
- Each person's own working hours (dashboard **Staff**, the clock button): split shifts and days off; the
  line gives them customers only then, and the team view says "works 12:00 PM – 2:00 PM" today.
- A **screen for the shop** (TV or spare tablet): now serving and next, by ticket and masked name
  ("R•••"), live, no account needed.
- Settings: grace period, when walk-ins catch up with appointments (20 min), VIPs per day, extra time
  per service, and whether customers must check in.

**How accurate it is** (simulated 1,000 days, 44,902 customers, 3 staff, 20% random service lengths,
8% no-shows, breaks): the wait shown on arrival was off by **5.9 minutes on average**; 81% within
10 minutes; 90% within 15.7 minutes; the actual start fell inside the range shown 81% of the time;
almost no bias (+0.3 min). It gets better as it learns how long each person really takes.

## 2. Architecture

```
 mobile app ─┐                       ┌─ booking_service ──────────────────────────────┐
 shop web ───┼─ api_gateway ─ HTTP ──┤  routers/queue.py      queue REST + WebSocket    │
 TV board ───┘   (forwards /ws/...)  │  routers/home_visits.py arrival + route          │
                                     │  core/queue_engine.py  pure engine (no I/O)       │
                                     │  core/live_queue.py    loads a shop's day → engine│
                                     │  core/queue_ops.py     start/finish, walk-ins, …  │
                                     │  core/queue_notify.py  diff → which message       │
                                     │  core/queue_hub.py     rooms, versions, pub/sub   │
                                     │  core/home_visits.py   route planner              │
                                     │  core/worker.py        every minute: notices, …   │
                                     └──┬───────────┬──────────────┬─────────────────────┘
                                        │           │              │
                          shop_service (team,   user_service   notification_service
                          hours, shop location) (address lat/lng) (push/SMS/email, quiet hours,
                                                                   retries, delivery status)
```

- **One source of truth**: the bookings table. A walk-in is a booking (`source = WALK_IN`), so payments,
  refunds, reviews, loyalty and history work for walk-ins too. A walk-in added at the counter without an
  account gets a `walk-in:` customer id: nobody to notify, no loyalty points.
- **The engine is pure** (no database, no clock), so the API, the worker and the simulator run the same
  code. Each request recomputes the shop's day (cheap; see §5).
- The older token queues (`queue_service`, dashboard **Token queues**) still work for shops that prefer
  a simple numbered token per service.

## 3. Data model

New on `bookings`: `source` (BOOKED/WALK_IN), `priority` (0 VIP, 1 appointment, 2 walk-in),
`checked_in_at`, `queue_rank` (manual order), `served_by_staff_id`, `started_at`, `walk_in_name`,
`queue_notice_state` (JSON: what the customer was last told).

```sql
-- migration 20261029_f3c5a7e9b2d4_live_queue_v2 (PostgreSQL)
ALTER TABLE bookings
  ADD COLUMN source varchar(10) NOT NULL DEFAULT 'BOOKED',
  ADD COLUMN priority integer NOT NULL DEFAULT 1,
  ADD COLUMN checked_in_at timestamptz,
  ADD COLUMN queue_rank double precision,
  ADD COLUMN served_by_staff_id varchar,
  ADD COLUMN started_at timestamptz,
  ADD COLUMN walk_in_name varchar(80),
  ADD COLUMN queue_notice_state text;
-- One customer at a time per team member: a second start fails (no double booking of a person).
CREATE UNIQUE INDEX uq_bookings_one_in_service_per_staff ON bookings (shop_id, served_by_staff_id)
  WHERE status = 'IN_PROGRESS' AND served_by_staff_id IS NOT NULL;
CREATE INDEX ix_bookings_shop_scheduled ON bookings (shop_id, scheduled_at);

CREATE TABLE queue_settings (            -- per shop; defaults when absent
  shop_id varchar PRIMARY KEY,
  buffer_pct double precision NOT NULL DEFAULT 0,
  alpha double precision NOT NULL DEFAULT 0.2,
  grace_minutes integer NOT NULL DEFAULT 10,
  aging_minutes integer NOT NULL DEFAULT 20,
  check_in_required boolean NOT NULL DEFAULT false,
  vip_per_day integer NOT NULL DEFAULT 5,
  updated_at timestamptz NOT NULL);
CREATE TABLE duration_stats (            -- learnt service lengths; staff_id '' = whole shop
  shop_id varchar, service_id varchar, staff_id varchar,
  mean double precision NOT NULL, var double precision NOT NULL, n integer NOT NULL,
  updated_at timestamptz NOT NULL,
  PRIMARY KEY (shop_id, service_id, staff_id));
CREATE TABLE worker_status (             -- today's AVAILABLE / BREAK (until) / OFF
  shop_id varchar, staff_id varchar, status varchar(10) NOT NULL, until timestamptz,
  updated_at timestamptz NOT NULL, PRIMARY KEY (shop_id, staff_id));
CREATE TABLE queue_audit (               -- who changed the line, and how
  id varchar PRIMARY KEY, shop_id varchar NOT NULL, booking_id varchar,
  action varchar(30) NOT NULL, actor_id varchar NOT NULL, detail text, created_at timestamptz NOT NULL);
CREATE INDEX ix_queue_audit_shop_id ON queue_audit (shop_id);
```

Workers are the shop's team (shop_service: each member's `service_ids` are their skills; none means all)
working the shop's opening hours (+90 minutes overtime for those already in line at closing), or their own
week when the owner sets one (`staff_members.working_hours`, the same JSON shape as the shop's week: split
shifts, days off; clipped to the shop's open hours and holidays, and the overtime applies to whoever works
until closing). A customer who asks for someone with their own hours can book them only while they work
(409 otherwise). A shop with no team uses its capacity as that many places that do everything.

## 4. Algorithms

**Priority** at time t: `(manual rank, tier, ready time, booked time, customer, id)`. Tiers: VIP <
appointment < walk-in. A walk-in who has waited `aging_minutes` since they were ready is served like an
appointment (then by who was ready first), so nobody starves; aging never makes anyone a VIP (the
simulator caught an early version that let a waiting appointment jump into the VIP tier). Every tie is
broken deterministically. Ready time: the booked time; for a walk-in, when they joined; for someone
arriving after the grace period, when they checked in (late requeue). With `check_in_required`, a late
customer who has not checked in is out of the line (CHECK_IN_NEEDED) until they do.

**Dispatch** (skill-aware earliest-available worker): a min-heap of (next free time, worker). The
worker popped at t takes the highest-priority customer who is ready by t and whom they may serve
(skills; a customer's chosen professional while that person works today, else anyone; load cap). If
another worker is free at the same moment and could take the first in line, this worker takes someone
only they can serve (e.g. who asked for them), so nobody waits while a worker stands idle. A job never
runs into a break or past the shift: the worker takes a shorter job that fits, or resumes after the
break. Nobody eligible → `UNSERVABLE` with `NO_ELIGIBLE_WORKER` or `BEYOND_SHIFT`.

**Durations**: per (service, team member) an exponentially weighted mean and variance of actual lengths,
updated on every completed visit (West's EW variance, α = 0.2 by default, tuned with the simulator;
implausible values outside 0.25–4× the listed length are ignored as forgotten taps). A member's own
figure is used after 3 visits, else the shop's, else the catalogue length with a 20% spread. A job in
progress holds its worker until start + learnt length and never ends earlier than a minute from now, so
an overrun pushes everyone behind it (and is flagged `overrun` after 5 minutes).

**ETA range**: sigma = sqrt(sum of the variances of the jobs before theirs on the same worker); the low
end is pulled earlier by the shop's recent no-show rate × the minutes ahead; `eta_min..eta_max` =
likely start − z·sigma .. start + z·sigma (z = 1.28). Confidence HIGH/MEDIUM/LOW from the range's width
relative to the wait.

**Notifications (diff-based)**: each worker pass compares each customer's spot with
`queue_notice_state` and sends at most one message (your turn > about 15 min > new time ±10 min >
running late vs booked > 5/2 ahead); each kind or step once; throttle 5 min except "your turn"; 8 a day.
notification_service does delivery, retries with backoff, delivery status, channels and quiet hours.

**Home visits**: per professional, today's route: the job under way, the one they're driving to, then
the rest in booked order. Arrival = max(booked time, previous end + drive); drive = haversine × 1.4 at
25 km/h + 3 min parking (5–120 min; 20 when a place has no coordinates). The range widens down the route.

## 5. Complexity and performance

M waiting, N workers. One dispatch: heap pop O(log N) + scan of ready customers O(M) + the idle-worker
check O(N·M) only when several are free at once. Full day: O(M·(M + N + log N)). 200 customers, 5
workers: well under 100 ms (asserted in `tests/test_queue_engine.py`). Removing a customer replays only
from the dispatch step that served them (`QueueEngine.remove`, verified equal to a full recompute).
Positions O(M log M). Route planning O(V log V). Diff notifications O(M) per shop per minute.
At 5,000 bookings a day spread over shops, a shop rarely has more than ~50 in a day's line; each look is
one indexed query (`ix_bookings_shop_scheduled`) plus the engine.

## 6. Concurrency and integrity

- Joining a line, adding walk-ins, calling next and reordering take the shop's advisory lock
  (`hold_shop_capacity`), so concurrent actions serialise per shop.
- The partial unique index makes "one customer at a time per team member" a database fact: a second
  start for the same person returns 409.
- Bookings keep their Idempotency-Key handling; a customer may hold one active walk-in per shop and join
  at most 3 times a day (429), against cancel-and-rejoin games.
- Walk-ins get strictly increasing join times per shop (ticket order even within a microsecond).

## 7. Real-time

| Option | Fit |
| --- | --- |
| **WebSocket + snapshot diff (chosen)** | Two-way, cheap, already in the stack; full snapshot per change is small (one shop's day) and makes reconnects trivial |
| Server-Sent Events | One-way is enough, but the gateway and mobile already speak WS; no gain |
| Redis pub/sub | Used *behind* the sockets to fan changes out across replicas (`QUEUE_PUBSUB=true`) |
| Firebase / FCM | Kept for push notifications (app closed), not for screens that are open |
| MQTT | A broker to run and secure for no benefit at this scale |

`/ws/shops/{id}/queue?token=…` (owner/admin) and `/ws/shops/{id}/board` (public, masked). Each shop
and view is a room with one refresher: it rebuilds on a change in this process (`hub.poke`), on Redis
when enabled, or every 15 s (time alone moves waits), and sends only when the version changes.
Backpressure: a socket that does not take a frame in 5 s is dropped (the client reconnects to the
latest); 50 sockets per room. Clients reconnect with exponential backoff (1 s → 30 s) and poll every
30 s while disconnected. The gateway forwards exactly these socket paths (and the booking status
socket) and refuses any other upgrade. The customer's own spot uses `GET /bookings/{id}/queue` every
30 s plus pushed messages (one socket per waiting customer is not worth it).

## 8. API contracts (all under `/api/v1`)

Customer:
```http
GET  /bookings/{id}/queue
200 {"booking_id":"b1","state":"WAITING","position":3,"people_ahead":2,"being_served":2,
     "estimated_start":"2030-11-04T05:45:00Z","eta_min":"2030-11-04T05:38:00Z",
     "eta_max":"2030-11-04T05:55:00Z","confidence":"MEDIUM","wait_minutes":45,
     "running_late_minutes":15,"staff_name":"Asha","ahead_with_staff":1,"reason":null,
     "checked_in":false,"can_check_in":true,"capacity":2,"scheduled_at":"2030-11-04T05:30:00Z"}
POST /bookings/{id}/check-in                       → QueueStatus
POST /bookings/walk-in {"service_id":"svc1"}        → 201 QueueStatus | 409 closed / already in line | 429
GET  /bookings/{id}/arrival
200 {"booking_id":"b9","state":"PLANNED","scheduled_at":"…T04:30:00Z","arrive_at":"…T04:40:00Z",
     "arrive_min":"…T04:36:00Z","arrive_max":"…T04:50:00Z","travel_minutes":20,"jobs_before":1,"late_minutes":10}
```
States: WAITING, YOUR_TURN, IN_PROGRESS, CHECK_IN_NEEDED, UNSERVABLE, NOT_TODAY, NOT_QUEUED;
arrival: PLANNED, ON_THE_WAY, ARRIVED, NOT_ASSIGNED, NOT_TODAY, NOT_HOME_VISIT, DONE.

Shop (owner or admin):
```http
GET  /bookings/shop/{shop}/queue                    → [ShopQueueEntry] in order
     {"booking_id":"b1","booking_number":"BK1","customer_display_name":"Ravi","state":"WAITING",
      "position":1,"scheduled_at":"…","estimated_start":"…","estimated_end":"…","eta_min":"…","eta_max":"…",
      "confidence":"HIGH","running_late_minutes":0,"service_id":"svc1","source":"WALK_IN",
      "priority":"WALK_IN","checked_in":true,"staff_id":"st-a","staff_name":"Asha","reason":null,
      "overrun":false,"moved":false,"can_mark_no_show":false}
POST /bookings/shop/{shop}/walk-ins {"service_id":"svc1","name":"Ravi","vip":false} → 201 entry
POST /bookings/shop/{shop}/queue/call-next {"staff_id":"st-a"} → entry (409 nobody / busy)
POST /bookings/shop/{shop}/queue/reorder {"booking_ids":["b3","b1"]} → [entries]
PUT  /bookings/{id}/priority {"vip":true}           → QueueStatus (409 over the daily cap)
POST /bookings/{id}/no-show                         → 409 within grace / checked in / walk-in
PUT  /bookings/{id}/status {"status":"IN_PROGRESS","staff_id":"st-a"} → 409 if busy
GET  /bookings/shop/{shop}/queue/team               → [{"staff_id","name","status","until","serving_*","overrun","waiting"}]
PUT  /bookings/shop/{shop}/queue/team/{staff} {"status":"BREAK","minutes":15}
GET|PUT /bookings/shop/{shop}/queue/settings        {"buffer_pct":0,"alpha":0.2,"grace_minutes":10,…}
GET  /bookings/shop/{shop}/queue/board              public, ETag / If-None-Match → 304
GET  /bookings/assigned/route                       the professional's home visits today, with leave_at
```
WebSocket frames: `{"type":"queue","shop_id","version","entries":[…]}`,
`{"type":"board","version","now_serving":[{"ticket":"0001","name":"R•••","staff_name":"Asha"}],"next":[…],"waiting":3}`,
client `"ping"` → `{"type":"pong"}`.

## 9. Multi-tenancy, roles and privacy

Every queue route is shop-scoped: `require_shop_access` (the shop's owner or an admin); booking routes
check the caller's relationship (customer, provider, shop, admin) and answer 404 to anyone else. The
board masks names to an initial and shows the last 4 characters of the booking number only; the shop
sees display names, never customer phone numbers or emails. user_service's internal address location
returns the city and coordinates only. Every change to a line is audited (`queue_audit`).

## 10. Edge cases (simulated 60 days each)

| Case | MAE | P90 | In range | Notes |
| --- | --- | --- | --- | --- |
| One worker | 11.1 | 28.8 | 76% | long waits magnify every overrun |
| 3× walk-in spike 12:00–14:00 | 9.8 | 24.6 | 77% | |
| Nearly empty shop | 0.1 | 0.0 | 99% | |
| Everyone on break at 15:00 | 6.7 | 17.6 | 83% | breaks are known in advance |
| 10% of visits take twice as long | 9.4 | 24.9 | 82% | overruns are flagged and re-planned |

Also handled: no team member does the service (flagged to the shop and customer), a chosen professional
off today (served by someone else, customer told), shop_service unreachable (falls back to capacity
places), all workers off (unservable), split shifts, late arrivals, no-shows, empty queue.

## 11. Tests

- `booking_service/tests/test_queue_engine.py` (22): order, skills, preferred worker, breaks, split
  shifts, shift end, load caps, overruns, EWMA, ETA ranges, determinism, incremental removal = full
  recompute, 200 customers < 100 ms.
- `test_queue_ops.py` (11): walk-ins, self-join limits, breaks moving customers, call-next with the
  unique index, learnt durations, reorder, VIP cap, no-show rules, check-in-required, settings, team
  lookup down, the live WebSocket and the board.
- `test_queue_notify.py` (5), `test_live_queue.py`, `test_home_visits.py` (5), `test_queue_sim.py` (3),
  `test_metrics.py` (7: the `/metrics` page, which routes are timed, start error, notification outcomes, worker passes).
- notification_service `test_queue_messages.py` (quiet hours hold updates, never "your turn").
- Gateway `websocket.test.ts` (forwarding, refusals, 502), `routes.test.ts` (public board only).
- Shop dashboard `LiveLinePage.test.tsx` (live frames, every action, settings, board).
- Mobile `live_queue_test.dart`, `shop_line_test.dart`, `home_visit_test.dart`.
- Simulator: `python tools/queue_sim.py --days 1000 --edge`, `--sweep` to retune α and the buffer.
- Not yet run: a k6 load test (suggested: 200 virtual users polling `GET /bookings/{id}/queue` every
  30 s and 20 shops with open sockets, P95 < 200 ms) and chaos tests (kill shop_service: the line falls
  back to capacity places; kill Redis with QUEUE_PUBSUB on: screens fall back to 15 s refreshes).

## 12. Observability

The gateway measures traffic, errors and latency per service. booking_service also serves `/metrics`
(`app/core/metrics.py`, Prometheus job `booking`, internal network only) for what the gateway cannot see:

| Metric | What it is |
|---|---|
| `alakh_queue_request_seconds{endpoint}` | time to answer `customer` (`GET /bookings/{id}/queue`), `shop_line` and `board` |
| `alakh_booking_worker_pass_seconds`, `…_last_pass_timestamp_seconds` | each worker pass, and the last one that did not fail |
| `alakh_booking_notifications_total{event,outcome}` | messages handed to notification_service: `sent`, `rejected`, `failed` |
| `alakh_queue_start_error_minutes_total{shop_id}`, `alakh_queue_starts_measured_total{shop_id}` | at each start, \|actual − the time the customer was last told\| (also logged as `queue_start_error`) |

Alerts (`deploy/monitoring/prometheus/alerts.yml`, group `live_queue`, tested in `alerts.test.yml`):
**QueueSlow** p95 > 300 ms for 10 min; **QueueNotificationsFailing** > 5% of queue messages not handed
over in 10 min; **BookingWorkerSlow** passes over 20 s; **BookingWorkerStopped** no good pass for 5 min;
**QueueWaitsOff** a shop's mean error > 15 min over a day (at least 10 starts), the signal that its
listed lengths or team are far off. Delivery after the handover (push, SMS) is notification_service's
and shows as its failed notifications, not here. With several booking_service replicas, list each one
as a target of the `booking` job.

## 13. Deployment

1. `alembic upgrade head` in booking_service (adds the columns, the partial unique index and 4 tables).
2. Rebuild booking_service, notification_service, user_service and api_gateway.
3. Set `QUEUE_PUBSUB=true` on booking_service when running more than one replica (uses `REDIS_URL`).
4. user_service needs `INTERNAL_API_KEY` (shared, already in compose) for address locations.
5. Dashboard: new routes `/line` and public `/board/:shopId`. Mobile: new screens, English and Hindi.

## 14. Trade-offs

- Recompute per look instead of a cached incremental state: simpler, always consistent with the database,
  fast enough at shop scale; `QueueEngine.remove` exists for when a shop's line gets very long.
- One global line per shop with skills, rather than a queue per worker: customers are not stuck behind
  a slow line when someone else is free; a chosen professional is still honoured.
- Walk-ins as bookings: one model for payments, refunds and history, at the cost of a few extra columns.
- No-show rate only pulls the low end of the range (the planned start stays honest): customers are told
  they *may* be seen sooner rather than being late for their turn.
- Per-person hours are a weekly pattern; a one-off change (a late start today) is still a break or
  "off today" on the Live line rather than an edit to their week.
