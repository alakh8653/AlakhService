import 'dart:async';

import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';

import '../../../../core/constants/app_constants.dart';
import '../../../../core/di/injection_container.dart';
import '../../../../core/network/api_errors.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';
import '../../../booking/domain/entities/booking.dart';
import '../../data/tracking_api.dart';
import '../../data/tracking_destination.dart';
import '../../domain/travel_estimate.dart';

/// Shows where the provider on a booking is, refreshing every few seconds, and roughly how far
/// they are from where they are heading.
class LiveTrackingPage extends StatefulWidget {
  final Booking booking;
  final TrackingApi? trackingApi;
  final TrackingDestinations? destinations;
  final Duration pollInterval;

  const LiveTrackingPage({
    super.key,
    required this.booking,
    this.trackingApi,
    this.destinations,
    this.pollInterval = const Duration(seconds: 10),
  });

  @override
  State<LiveTrackingPage> createState() => _LiveTrackingPageState();
}

class _LiveTrackingPageState extends State<LiveTrackingPage> {
  late final TrackingApi _api = widget.trackingApi ?? sl<TrackingApi>();
  GoogleMapController? _mapController;
  Timer? _timer;
  ProviderLocation? _location;
  TrackingTarget? _target;
  String? _error;
  bool _loading = true;

  static const CameraPosition _initialCamera = CameraPosition(
    target: LatLng(AppConstants.defaultLatitude, AppConstants.defaultLongitude),
    zoom: AppConstants.defaultMapZoom,
  );

  @override
  void initState() {
    super.initState();
    (widget.destinations ?? sl<TrackingDestinations>()).forBooking(widget.booking).then((target) {
      if (mounted) setState(() => _target = target);
    });
    _refresh();
    _timer = Timer.periodic(widget.pollInterval, (_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    _mapController?.dispose();
    super.dispose();
  }

  Future<void> _refresh() async {
    final providerId = widget.booking.providerId;
    if (providerId == null) {
      setState(() => _loading = false);
      return;
    }
    try {
      final location = await _api.providerLocation(providerId);
      if (!mounted) return;
      setState(() {
        _location = location;
        _error = null;
        _loading = false;
      });
      if (location != null) {
        _mapController?.animateCamera(
          CameraUpdate.newLatLng(LatLng(location.latitude, location.longitude)),
        );
      }
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = apiErrorMessage(e);
        _loading = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final location = _location;
    final target = _target;
    return Scaffold(
      appBar: AppBar(title: const Text('Live Tracking')),
      body: Stack(
        children: [
          GoogleMap(
            initialCameraPosition: location == null
                ? _initialCamera
                : CameraPosition(
                    target: LatLng(location.latitude, location.longitude),
                    zoom: AppConstants.defaultMapZoom,
                  ),
            markers: {
              if (location != null)
                Marker(
                  markerId: const MarkerId('provider'),
                  position: LatLng(location.latitude, location.longitude),
                  infoWindow: const InfoWindow(title: 'Your provider'),
                ),
              if (target != null)
                Marker(
                  markerId: const MarkerId('destination'),
                  position: LatLng(target.latitude, target.longitude),
                  icon: BitmapDescriptor.defaultMarkerWithHue(BitmapDescriptor.hueAzure),
                  infoWindow: InfoWindow(title: target.label),
                ),
            },
            myLocationButtonEnabled: false,
            zoomControlsEnabled: false,
            onMapCreated: (controller) => _mapController = controller,
          ),
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: TrackingStatusCard(
              booking: widget.booking,
              location: location,
              target: target,
              loading: _loading,
              error: _error,
            ),
          ),
        ],
      ),
    );
  }
}

/// The card under the live map: what the provider is doing and, while they travel, how far away.
class TrackingStatusCard extends StatelessWidget {
  final Booking booking;
  final ProviderLocation? location;
  final TrackingTarget? target;
  final bool loading;
  final String? error;

  const TrackingStatusCard({
    super.key,
    required this.booking,
    required this.location,
    this.target,
    required this.loading,
    required this.error,
  });

  /// Distance and ETA, once both ends are known.
  String? get estimateText {
    final location = this.location;
    final target = this.target;
    if (loading || error != null || location == null || target == null) return null;
    final estimate = estimateTravel(
      fromLatitude: location.latitude,
      fromLongitude: location.longitude,
      toLatitude: target.latitude,
      toLongitude: target.longitude,
      speedMps: location.speed,
    );
    if (estimate.arriving) return 'Arriving now';
    final to = booking.status == BookingStatus.pickedUp ? ' from ${target.label}' : '';
    return '${estimate.label}$to';
  }

  String get _statusText {
    if (loading) return 'Finding your provider…';
    if (error != null) return error!;
    final location = this.location;
    if (location == null) {
      return 'Waiting for your provider to share their location';
    }
    final age = DateTime.now().difference(location.recordedAt);
    final ago = age.inMinutes < 1 ? 'just now' : '${age.inMinutes} min ago';
    final pickup = booking.serviceMode == 'PICKUP_DROP';
    return switch (booking.status) {
      BookingStatus.enRoute => pickup ? 'Coming to collect your item · updated $ago' : 'On the way · updated $ago',
      BookingStatus.pickedUp => 'Taking your item to the shop · updated $ago',
      BookingStatus.inProgress =>
        pickup ? 'Your item is being worked on · updated $ago' : 'Working on your booking · updated $ago',
      BookingStatus.outForDelivery => 'Bringing your item back · updated $ago',
      _ => 'Provider assigned · updated $ago',
    };
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        boxShadow: const [
          BoxShadow(color: AppColors.shadow, blurRadius: 12, offset: Offset(0, -4)),
        ],
      ),
      child: Row(
        children: [
          const CircleAvatar(
            backgroundColor: AppColors.primaryLight,
            child: Icon(Icons.person, color: AppColors.primary),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(booking.serviceName, style: AppTextStyles.subtitle1),
                if (estimateText != null)
                  Text(estimateText!, style: AppTextStyles.subtitle2.copyWith(color: AppColors.primary)),
                Text(_statusText, style: AppTextStyles.caption),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
