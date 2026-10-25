import 'dart:async';

import 'package:location/location.dart';

import '../../../shared/widgets/location_rationale.dart';
import '../../tracking/data/tracking_api.dart';

class Fix {
  final double latitude;
  final double longitude;
  final double? accuracy;
  final double? speed;
  final double? heading;

  const Fix(this.latitude, this.longitude, {this.accuracy, this.speed, this.heading});
}

/// Where the device is. Returns null when location is off or not permitted.
abstract class LocationSource {
  Future<Fix?> current();
}

class DeviceLocationSource implements LocationSource {
  final Location _location = Location();

  /// Shown before the system asks for location the first time; false stops there.
  final Future<bool> Function() explain;

  DeviceLocationSource({LocationPurpose purpose = LocationPurpose.eta, Future<bool> Function()? explain})
      : explain = explain ?? (() => explainLocation(purpose));

  // Asked once per run: a "Not now" isn't repeated on every location tick.
  bool _explained = false;
  bool _declined = false;

  @override
  Future<Fix?> current() async {
    if (!await _location.serviceEnabled() && !await _location.requestService()) return null;
    var permission = await _location.hasPermission();
    if (permission == PermissionStatus.denied) {
      if (_declined) return null;
      if (!_explained) {
        _explained = true;
        if (!await explain()) {
          _declined = true;
          return null;
        }
      }
      permission = await _location.requestPermission();
    }
    if (permission != PermissionStatus.granted && permission != PermissionStatus.grantedLimited) return null;
    final p = await _location.getLocation().timeout(const Duration(seconds: 15));
    return Fix(p.latitude, p.longitude, accuracy: p.accuracy, speed: p.speed, heading: p.heading);
  }
}

enum SharingState { off, sharing, noPermission, failing }

/// Sends the provider's position to tracking_service on a timer while a job is under way.
class LocationReporter {
  final TrackingApi tracking;
  final LocationSource source;
  final String providerId;
  final Duration interval;
  final void Function(SharingState state)? onState;

  Timer? _timer;
  bool _busy = false;

  LocationReporter({
    required this.tracking,
    required this.source,
    required this.providerId,
    this.interval = const Duration(seconds: 15),
    this.onState,
  });

  bool get isRunning => _timer != null;

  void start() {
    if (_timer != null) return;
    _timer = Timer.periodic(interval, (_) => reportNow());
    reportNow();
  }

  void stop() {
    _timer?.cancel();
    _timer = null;
    onState?.call(SharingState.off);
  }

  Future<void> reportNow() async {
    if (_busy) return;
    _busy = true;
    try {
      final fix = await source.current();
      if (fix == null) {
        onState?.call(SharingState.noPermission);
        return;
      }
      await tracking.report(
        providerId: providerId,
        latitude: fix.latitude,
        longitude: fix.longitude,
        accuracy: fix.accuracy,
        speed: fix.speed,
        heading: fix.heading,
      );
      onState?.call(SharingState.sharing);
    } catch (_) {
      onState?.call(SharingState.failing);
    } finally {
      _busy = false;
    }
  }
}
