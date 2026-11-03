"""What each platform event says to each person it concerns.

Services report events (``booking.confirmed``, ``payment.completed``...) with the recipient's role in
them; the wording lives here so every channel (in-app list, push) says the same thing.
"""

import re
from typing import Optional

# (event, role) -> (title, body): str.format templates over the event's data.
MESSAGES: dict[tuple[str, Optional[str]], tuple[str, str]] = {
    ("booking.created", "shop"): (
        "New booking",
        "{service_name} booked for {scheduled_at}. Booking {booking_number}. {rework_line}",
    ),
    # Extra charges the shop or its provider asks for: nothing is added until the customer approves.
    ("booking.extras_requested", "customer"): (
        "Approve extra charges?",
        "The shop asks for ₹{total} more for booking {booking_number}. Nothing is charged unless you "
        "approve it in the app.",
    ),
    ("booking.extras_decided", None): (
        "Extra charges {decision}",
        "The customer {decision} the extra charges of ₹{total} for booking {booking_number}.",
    ),
    # A customer or provider asked for help during a booking: every admin, by push and email.
    ("safety.sos", None): (
        "SOS: someone needs help",
        "SOS from the {role} of booking {booking_number} at {raised_at}. Location: {location}. {note} "
        "Reach them now; if they cannot be reached, call 112 for them.",
    ),
    ("booking.confirmed", None): (
        "Booking confirmed",
        "Your booking {booking_number} for {scheduled_at} is confirmed.",
    ),
    ("booking.assigned", "customer"): (
        "Provider assigned",
        "A provider has been assigned to booking {booking_number}.",
    ),
    ("booking.assigned", "provider"): (
        "New job",
        "You have been assigned booking {booking_number} for {scheduled_at}.",
    ),
    ("booking.provider_en_route", None): (
        "Provider on the way",
        "Your provider is on the way for booking {booking_number}. {arrival_line}",
    ),
    ("booking.picked_up", "customer"): (
        "Item picked up",
        "We've collected your item for booking {booking_number}. We'll let you know when it's on its way back.",
    ),
    ("booking.picked_up", None): ("Item picked up", "The item for booking {booking_number} has been collected."),
    ("booking.in_progress", None): ("Service started", "Booking {booking_number} is in progress."),
    ("booking.ready_by", "customer"): (
        "Return time set",
        "Your item for booking {booking_number} should be back with you by {ready_by}.",
    ),
    ("booking.out_for_delivery", "customer"): (
        "On its way back",
        "Your item for booking {booking_number} is on its way back to you.",
    ),
    ("booking.out_for_delivery", None): (
        "Out for delivery",
        "The item for booking {booking_number} is on its way back to the customer.",
    ),
    ("booking.completed", "customer"): (
        "Service completed",
        "Booking {booking_number} is complete. Tap to rate your experience.",
    ),
    ("booking.completed", None): ("Booking completed", "Booking {booking_number} is complete."),
    ("booking.extra_requested", "customer"): (
        "Extra charge to approve",
        "Your provider asks for {amount} more on booking {booking_number}: {reason}. Open the app to approve or decline.",
    ),
    ("booking.extra_approved", None): (
        "Extra charge approved",
        "The customer approved {amount} more on booking {booking_number}. The new total is {new_total}.",
    ),
    ("booking.extra_declined", None): (
        "Extra charge declined",
        "The customer declined {amount} more on booking {booking_number}. The price stays as it was.",
    ),
    ("shop.photo_hidden", "shop"): (
        "A work photo was hidden",
        "A photo of {shop_name} is hidden from customers while we check it. Open your profile to see it or remove it.",
    ),
    ("shop.photo_removed", "shop"): (
        "A work photo was removed",
        "We removed a photo of {shop_name}. Please don't show customers' faces, documents or anything offensive.",
    ),
    ("shop.report", None): (
        "Your report is ready",
        "Your report for {label} is ready. Open Reports to see your profit.",
    ),
    ("booking.cancelled", "customer"): (
        "Booking cancelled",
        "Booking {booking_number} for {scheduled_at} was cancelled. {reason}",
    ),
    ("booking.cancelled", None): ("Booking cancelled", "Booking {booking_number} for {scheduled_at} was cancelled."),
    # Moved to another time by the customer, the shop or an admin (the one who moved it is not told).
    ("booking.rescheduled", "customer"): (
        "Booking moved",
        "Your booking {booking_number} has been moved to {scheduled_at}.",
    ),
    ("booking.rescheduled", None): (
        "Booking rescheduled",
        "Booking {booking_number} has moved from {previous_scheduled_at} to {scheduled_at}.",
    ),
    ("booking.disputed", None): ("Booking disputed", "Booking {booking_number} is under dispute."),
    ("booking.refunded", None): ("Booking refunded", "Booking {booking_number} has been refunded."),
    ("booking.refunded", "customer"): (
        "Refund on its way",
        "Booking {booking_number} has been refunded. It can take 5-7 working days to reach your account.",
    ),
    # Sent by booking_service's reminder worker 24 hours and 1 hour before the appointment.
    ("booking.reminder", "customer"): (
        "Booking reminder",
        "Reminder: your {service_name} booking {booking_number} is at {scheduled_at}.",
    ),
    ("booking.reminder", None): (
        "Upcoming booking",
        "Reminder: booking {booking_number} for {service_name} is at {scheduled_at}.",
    ),
    # On the day of a visit at the shop, from the live queue (booking_service's worker), once each.
    ("booking.turn_soon", "customer"): (
        "Almost your turn",
        "Booking {booking_number}: you're #{position} in line, about {wait_minutes} min to go. Please head to the shop.",
    ),
    ("booking.running_late", "customer"): (
        "The shop is running late",
        "Booking {booking_number} will start about {late_minutes} min after {scheduled_at}. Come a little later; we'll tell you when it's nearly your turn.",
    ),
    # The live queue's updates, when something the customer would notice changes (booking_service's
    # queue_notify): moving up the line, a new expected time, their turn, and a no-show.
    ("booking.queue_ahead", "customer"): (
        "You're moving up the line",
        "Booking {booking_number}: {people_ahead} ahead of you (#{position}), expected around {eta}.",
    ),
    ("booking.queue_update", "customer"): (
        "New expected time",
        "Booking {booking_number}: now expected around {eta}, {why}.",
    ),
    ("booking.your_turn", "customer"): (
        "It's your turn",
        "Booking {booking_number}: please go to the counter now. {staff_line}",
    ),
    ("booking.no_show", "customer"): (
        "Marked as a no-show",
        "You did not arrive for booking {booking_number} at {scheduled_at}, so it was cancelled. Book again any time.",
    ),
    # A day the customer wanted at a shop that was full: a time there has opened up.
    ("waitlist.time_opened", "customer"): (
        "A time just opened up",
        "A time is free on {date} at the shop you wanted. Book it before someone else does.",
    ),
    # Some weeks after a completed visit, to the customer, once (unless they have booked it again).
    ("booking.rebook", "customer"): (
        "Time for your next visit?",
        "It has been a few weeks since booking {booking_number}. Book again in a tap.",
    ),
    # A booking the shop never confirmed in time.
    ("booking.expired", "customer"): (
        "Booking request expired",
        "The shop did not confirm booking {booking_number} for {scheduled_at} in time, so it has been "
        "cancelled. Any online payment will be refunded in 5-7 working days.",
    ),
    ("booking.expired", None): (
        "Booking expired",
        "Booking {booking_number} for {scheduled_at} expired because it was not confirmed in time.",
    ),
    # In-app chat: only that there is a message, never what it says.
    ("booking.message", "customer"): ("New message", "The shop sent you a message about booking {booking_number}."),
    ("booking.message", None): ("New message", "The customer sent a message about booking {booking_number}."),
    ("queue.called", None): ("It's your turn", "Please come to the counter now."),
    ("queue.almost_turn", None): (
        "Almost your turn",
        "You're near the front of the queue: about {minutes} min to go. Please be back by then.",
    ),
    ("payment.completed", "customer"): ("Payment received", "We received your payment of ₹{amount}."),
    ("payment.completed", "shop"): ("Payment received", "A customer paid ₹{amount} for a booking."),
    ("payment.failed", "customer"): (
        "Payment failed",
        "Your payment of ₹{amount} did not go through. You can try again.",
    ),
    ("payment.refunded", "customer"): ("Refund issued", "₹{amount} has been refunded to you."),
    # A prepaid package of visits, bought online.
    ("payment.package", "customer"): (
        "Package bought",
        "Your ₹{amount} package is ready. Choose it when you book to use a visit.",
    ),
    ("payment.package", "shop"): (
        "Package sold",
        "A customer bought a ₹{amount} package. You earn each visit's share when it is completed.",
    ),
    # A tip on a completed booking: passed on in full, with the shop's next payout.
    ("payment.tip", "customer"): (
        "Thank you for the tip",
        "Your ₹{amount} tip goes in full to the professional who served you.",
    ),
    ("payment.tip", "shop"): (
        "Tip received",
        "A customer left a ₹{amount} tip. It comes with your next payout, for the staff member who did the job.",
    ),
    ("payment.tip", "provider"): ("You got a tip", "A customer tipped you ₹{amount}. Your shop passes it on to you."),
    # Shop onboarding (shop_service): the owner hears the review's outcome.
    ("shop.approved", "shop"): (
        "Your shop is live",
        "{shop_name} has been approved. Customers can now find it and book your services.",
    ),
    ("shop.rejected", "shop"): (
        "Shop not approved yet",
        "{shop_name} was not approved: {reason}. Update your details and submit it for review again.",
    ),
}

# Shop owners use the web dashboard, which has no push, so these are always emailed to them too.
SHOP_EMAIL_EVENTS = frozenset(
    {"booking.created", "booking.rescheduled", "booking.extras_decided", "shop.approved", "shop.rejected"}
)

# Alerts every admin gets by email as well as push, whether or not they have the app.
ADMIN_EMAIL_EVENTS = frozenset({"safety.sos"})


# Updates that can wait: during the recipient's quiet hours they are kept in the app but not pushed.
QUIET_HOURS_HELD = frozenset(
    {"booking.queue_ahead", "booking.queue_update", "booking.turn_soon", "booking.running_late", "booking.rebook"}
)

# Events important enough to text or email someone who has no app installed (no push token).
CRITICAL_EVENTS = frozenset(
    {"booking.confirmed", "booking.cancelled", "booking.reminder", "booking.refunded", "booking.expired"}
)

# SMS wording, the same for every recipient so each event needs one DLT template. Register each
# with {#var#} in place of every {field} (docs/DEPLOYMENT.md lists them), e.g.
#   AlakhService: booking {#var#} for {#var#} is confirmed. Details in the app.
SMS_TEXTS: dict[str, str] = {
    "booking.confirmed": "AlakhService: booking {booking_number} for {scheduled_at} is confirmed. Details in the app.",
    "booking.cancelled": "AlakhService: booking {booking_number} for {scheduled_at} was cancelled. Details in the app.",
    "booking.reminder": "AlakhService reminder: booking {booking_number} is at {scheduled_at}.",
    "booking.refunded": (
        "AlakhService: booking {booking_number} has been refunded. It can take 5-7 working days to reach your account."
    ),
    "booking.expired": (
        "AlakhService: booking {booking_number} for {scheduled_at} expired as the shop did not confirm it in time. "
        "Any online payment will be refunded."
    ),
}

# Never let a phone number or email address into a message, whatever a caller puts in the data:
# customers and shops only reach each other through the app (docs/PRIVACY_AND_CONTACT.md).
_EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")
_PHONE = re.compile(r"(?<![\w-])(?:\+?91[\s-]?)?[6-9]\d{4}[\s-]?\d{5}(?![\w-])|\+\d[\d\s-]{8,}\d")


def scrub(value):
    """A message value with any email address or phone number in it removed."""
    if not isinstance(value, str):
        return value
    return _PHONE.sub("", _EMAIL.sub("", value))


class _Blank(dict):
    def __missing__(self, key):
        return ""


def _fill(template: str, data: dict) -> str:
    values = _Blank({k: scrub(v) for k, v in data.items() if v is not None})
    return " ".join(template.format_map(values).split())


def render(event: str, role: Optional[str], data: dict) -> Optional[tuple[str, str]]:
    """The title and body for this event and recipient, or None for an event nobody is told about."""
    template = MESSAGES.get((event, role)) or MESSAGES.get((event, None))
    if template is None:
        return None
    title, body = template
    # A title may name a detail too ("Extra charges approved").
    return _fill(title, data), _fill(body, data)


def render_sms(event: str, data: dict) -> Optional[str]:
    """The SMS text for a critical event (matching its DLT template), or None if it is not texted."""
    template = SMS_TEXTS.get(event)
    return _fill(template, data) if template else None
