/// Ways for a customer to reach a shop: their own vehicle, public transport, walking or a cab.
///
/// Each option is a link the phone opens in the right app: Google Maps directions (driving,
/// transit, walking) and Uber's documented deep link with the drop-off filled in. Booking a cab
/// inside this app would need a partnership API with each operator, so other ride apps (Ola,
/// Rapido, ...) get the shop's address to paste instead.
library;

/// Where the customer is going.
class Destination {
  final String name;

  /// Street address and city, as written by the shop.
  final String address;
  final double? latitude;
  final double? longitude;

  const Destination({required this.name, required this.address, this.latitude, this.longitude});

  bool get hasCoordinates => latitude != null && longitude != null;

  /// What maps search for: exact coordinates when the shop set them, otherwise the address.
  String get query => hasCoordinates ? '$latitude,$longitude' : [name, address].where((p) => p.trim().isNotEmpty).join(', ');

  /// For pasting into another ride app.
  String get copyText => [name, address].where((p) => p.trim().isNotEmpty).join(', ');
}

enum TravelMode { drive, transit, walk, uber }

class TravelOption {
  final TravelMode mode;
  final String title;
  final String subtitle;
  final Uri uri;

  const TravelOption(this.mode, this.title, this.subtitle, this.uri);
}

/// Google Maps directions from the customer's current location (https://developers.google.com/maps/documentation/urls/guide).
Uri googleDirections(Destination d, String travelMode) => Uri.https('www.google.com', '/maps/dir/', {
      'api': '1',
      'destination': d.query,
      'travelmode': travelMode,
    });

/// Uber with the pickup at the customer's location and the shop as drop-off
/// (https://developer.uber.com/docs/deep-linking). Needs coordinates.
Uri uberRide(Destination d) => Uri.https('m.uber.com', '/ul/', {
      'action': 'setPickup',
      'pickup': 'my_location',
      'dropoff[latitude]': '${d.latitude}',
      'dropoff[longitude]': '${d.longitude}',
      'dropoff[nickname]': d.name,
      if (d.address.trim().isNotEmpty) 'dropoff[formatted_address]': d.address,
    });

/// Every way to get there that works for this destination, own vehicle first.
List<TravelOption> travelOptions(Destination d) => [
      TravelOption(TravelMode.drive, 'Drive there', 'Your car or bike: turn-by-turn directions', googleDirections(d, 'driving')),
      TravelOption(TravelMode.transit, 'Public transport', 'Bus, metro and train routes and timings', googleDirections(d, 'transit')),
      TravelOption(TravelMode.walk, 'Walk', 'Walking directions', googleDirections(d, 'walking')),
      if (d.hasCoordinates)
        TravelOption(TravelMode.uber, 'Book an Uber', 'Opens Uber with the shop as your drop-off', uberRide(d)),
    ];
