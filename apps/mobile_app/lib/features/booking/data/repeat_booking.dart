import '../domain/entities/booking.dart';
import '../domain/repositories/booking_repository.dart';
import 'availability_api.dart';

/// One visit of a repeat: booked, or why not.
class RepeatVisit {
  final DateTime at;

  /// The booking made, or null when the time was not free (or the booking was refused).
  final Booking? booking;

  /// Why it was not booked (the shop is full or closed then, or the server's reason).
  final String? problem;

  const RepeatVisit(this.at, {this.booking, this.problem});

  bool get booked => booking != null;
}

/// Books the same service again at the same time of day every [weeks] weeks, [times] times, as the customer
/// would one by one: through the normal booking route, so price, capacity and the shop's hours all apply.
///
/// Each visit carries a key made from the booking and its place in the repeat, so repeating the same booking
/// twice (a double tap, a retry) books nothing twice.
class RepeatBooker {
  final BookingRepository bookings;
  final AvailabilityApi availability;
  final DateTime Function() now;

  RepeatBooker({required this.bookings, required this.availability, DateTime Function()? now})
      : now = now ?? DateTime.now;

  /// Weeks between visits on offer, and how many visits.
  static const everyWeeks = [1, 2, 3, 4];
  static const counts = [2, 3, 4, 6];

  /// The next [times] dates after now, [weeks] weeks apart, at the booking's time of day.
  List<DateTime> datesFor(Booking original, int weeks, int times) {
    final first = original.scheduledAt.toLocal();
    final soonest = now().add(const Duration(hours: 2));
    final out = <DateTime>[];
    for (var k = 1; out.length < times && k < 200; k++) {
      // Calendar days, not 7 * 24 hours, so the time of day holds across clock changes.
      final at = DateTime(first.year, first.month, first.day + 7 * weeks * k, first.hour, first.minute);
      if (at.isAfter(soonest)) out.add(at);
    }
    return out;
  }

  Future<List<RepeatVisit>> book(Booking original, {required int weeks, required int times}) async {
    final visits = <RepeatVisit>[];
    for (final (i, at) in datesFor(original, weeks, times).indexed) {
      final free = await _isFree(original.serviceId, at);
      if (free == false) {
        visits.add(RepeatVisit(at, problem: 'full'));
        continue;
      }
      final result = await bookings.createBooking(
        serviceId: original.serviceId,
        scheduledAt: at,
        address: original.address,
        delivery: BookingDelivery(
          mode: original.serviceMode,
          addressId: original.addressId,
          itemDescription: original.itemDescription,
        ),
        idempotencyKey: 'repeat-${original.id}-w$weeks-$i',
      );
      visits.add(result.fold((f) => RepeatVisit(at, problem: f.message), (b) => RepeatVisit(at, booking: b)));
    }
    return visits;
  }

  /// Whether the shop has [at] free; null when it has no opening hours set (anything may be asked for).
  Future<bool?> _isFree(String serviceId, DateTime at) async {
    try {
      final day = await availability.forDay(serviceId, at);
      if (!day.hoursConfigured) return null;
      return day.slots.any((s) => s.at.toUtc() == at.toUtc());
    } catch (_) {
      return null; // the booking itself will say if the time is not possible
    }
  }
}
