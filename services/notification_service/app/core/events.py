"""What each platform event says to each person it concerns.

Services report events (``booking.confirmed``, ``payment.completed``...) with the recipient's role in
them; the wording lives here so every channel (in-app list, push) says the same thing.
"""

from typing import Optional

# (event, role) -> (title, body). Bodies are str.format templates over the event's data.
MESSAGES: dict[tuple[str, Optional[str]], tuple[str, str]] = {
    ("booking.created", "shop"): ("New booking", "{service_name} booked for {scheduled_at}. Booking {booking_number}."),
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
        "Your provider is on the way for booking {booking_number}.",
    ),
    ("booking.in_progress", None): ("Service started", "Booking {booking_number} is in progress."),
    ("booking.completed", "customer"): (
        "Service completed",
        "Booking {booking_number} is complete. Tap to rate your experience.",
    ),
    ("booking.completed", None): ("Booking completed", "Booking {booking_number} is complete."),
    ("booking.cancelled", None): ("Booking cancelled", "Booking {booking_number} for {scheduled_at} was cancelled."),
    ("booking.disputed", None): ("Booking disputed", "Booking {booking_number} is under dispute."),
    ("booking.refunded", None): ("Booking refunded", "Booking {booking_number} has been refunded."),
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
}


class _Blank(dict):
    def __missing__(self, key):
        return ""


def render(event: str, role: Optional[str], data: dict) -> Optional[tuple[str, str]]:
    """The title and body for this event and recipient, or None for an event nobody is told about."""
    template = MESSAGES.get((event, role)) or MESSAGES.get((event, None))
    if template is None:
        return None
    title, body = template
    return title, " ".join(body.format_map(_Blank({k: v for k, v in data.items() if v is not None})).split())
