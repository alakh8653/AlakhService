import '../../booking/domain/entities/booking.dart';
import '../../directions/data/shop_location_api.dart';
import '../../jobs/data/location_reporter.dart';
import '../../profile/data/address_api.dart';

/// Where the provider on a booking is heading, for the live map's distance and ETA.
class TrackingTarget {
  /// Shown on the map pin, e.g. "You" or the shop's name.
  final String label;
  final double latitude;
  final double longitude;

  const TrackingTarget(this.label, this.latitude, this.longitude);
}

/// Works out the provider's destination from the booking's step: the customer while they are
/// coming to them (or bringing an item back), the shop while a picked-up item is on its way there.
class TrackingDestinations {
  final ShopLocationApi shops;
  final AddressApi addresses;
  final LocationSource device;

  TrackingDestinations({required this.shops, required this.addresses, required this.device});

  static const _toCustomer = {BookingStatus.assigned, BookingStatus.enRoute};

  /// Null when the provider is not travelling or the place has no map position. Best effort: a
  /// failed lookup only means no ETA.
  Future<TrackingTarget?> forBooking(Booking booking) async {
    try {
      if (booking.status == BookingStatus.pickedUp && booking.shopId != null) {
        final shop = await shops.destination(booking.shopId!);
        if (!shop.hasCoordinates) return null;
        return TrackingTarget(shop.name, shop.latitude!, shop.longitude!);
      }
      final comingToCustomer = (booking.serviceMode != 'AT_SHOP' && _toCustomer.contains(booking.status)) ||
          booking.status == BookingStatus.outForDelivery;
      if (!comingToCustomer) return null;
      return await _customer(booking);
    } catch (_) {
      return null;
    }
  }

  Future<TrackingTarget?> _customer(Booking booking) async {
    if (booking.addressId != null) {
      final saved = (await addresses.list()).where((a) => a.id == booking.addressId).firstOrNull;
      if (saved?.latitude != null && saved?.longitude != null) {
        return TrackingTarget(saved!.label, saved.latitude!, saved.longitude!);
      }
    }
    // The address has no map position: the customer is usually there, waiting.
    final here = await device.current();
    return here == null ? null : TrackingTarget('You', here.latitude, here.longitude);
  }
}
