import 'dart:math';

/// Roads are rarely straight: in Indian cities the driving distance is about this much longer than
/// the straight line between two points.
const double roadFactor = 1.3;

/// Average city speed (two-wheelers and cars, with traffic) when the provider's own speed is unknown
/// or they are stopped at a signal.
const double citySpeedKmh = 22;

/// Straight-line distance in kilometres (haversine).
double straightLineKm(double lat1, double lng1, double lat2, double lng2) {
  const earthRadiusKm = 6371.0;
  double rad(double deg) => deg * pi / 180;
  final dLat = rad(lat2 - lat1);
  final dLng = rad(lng2 - lng1);
  final a = sin(dLat / 2) * sin(dLat / 2) + cos(rad(lat1)) * cos(rad(lat2)) * sin(dLng / 2) * sin(dLng / 2);
  return earthRadiusKm * 2 * atan2(sqrt(a), sqrt(1 - a));
}

/// Roughly how far the provider still has to travel and how long it should take.
class TravelEstimate {
  /// By road, approximately.
  final double kilometres;
  final int minutes;

  const TravelEstimate({required this.kilometres, required this.minutes});

  /// Close enough that a time estimate means nothing any more.
  bool get arriving => kilometres < 0.2;

  String get distanceText =>
      kilometres < 1 ? '${(kilometres * 1000 / 50).round() * 50} m' : '${kilometres.toStringAsFixed(1)} km';

  String get label => arriving ? 'Arriving now' : 'About $minutes min away · $distanceText';
}

/// Estimates the trip from the provider's position to the destination. [speedMps] is the speed the
/// provider's phone last reported; it is used when they are moving at a plausible road speed.
TravelEstimate estimateTravel({
  required double fromLatitude,
  required double fromLongitude,
  required double toLatitude,
  required double toLongitude,
  double? speedMps,
}) {
  final km = straightLineKm(fromLatitude, fromLongitude, toLatitude, toLongitude) * roadFactor;
  final reportedKmh = (speedMps ?? 0) * 3.6;
  final kmh = reportedKmh >= 8 ? reportedKmh.clamp(10, 60).toDouble() : citySpeedKmh;
  return TravelEstimate(kilometres: km, minutes: max(1, (km / kmh * 60).ceil()));
}
