import 'package:flutter/material.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart';
import '../../../../core/constants/app_constants.dart';
import '../../../../core/theme/app_colors.dart';
import '../../../../core/theme/app_text_styles.dart';

class LiveTrackingPage extends StatefulWidget {
  final String bookingId;
  final String providerName;

  const LiveTrackingPage({
    super.key,
    required this.bookingId,
    required this.providerName,
  });

  @override
  State<LiveTrackingPage> createState() => _LiveTrackingPageState();
}

class _LiveTrackingPageState extends State<LiveTrackingPage> {
  GoogleMapController? _mapController;

  // Default location: New Delhi
  static const CameraPosition _initialCamera = CameraPosition(
    target: LatLng(
      AppConstants.defaultLatitude,
      AppConstants.defaultLongitude,
    ),
    zoom: AppConstants.defaultMapZoom,
  );

  final Set<Marker> _markers = {
    const Marker(
      markerId: MarkerId('provider'),
      position: LatLng(
        AppConstants.defaultLatitude + 0.01,
        AppConstants.defaultLongitude + 0.01,
      ),
      infoWindow: InfoWindow(title: 'Provider Location'),
    ),
    const Marker(
      markerId: MarkerId('destination'),
      position: LatLng(
        AppConstants.defaultLatitude,
        AppConstants.defaultLongitude,
      ),
      infoWindow: InfoWindow(title: 'Your Location'),
    ),
  };

  @override
  void dispose() {
    _mapController?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Live Tracking')),
      body: Stack(
        children: [
          GoogleMap(
            initialCameraPosition: _initialCamera,
            markers: _markers,
            myLocationEnabled: true,
            myLocationButtonEnabled: false,
            zoomControlsEnabled: false,
            onMapCreated: (controller) => _mapController = controller,
          ),
          Positioned(
            bottom: 0,
            left: 0,
            right: 0,
            child: _ProviderStatusCard(
              providerName: widget.providerName,
              bookingId: widget.bookingId,
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        mini: true,
        backgroundColor: AppColors.surface,
        onPressed: () {
          _mapController?.animateCamera(
            CameraUpdate.newCameraPosition(_initialCamera),
          );
        },
        child: const Icon(Icons.my_location, color: AppColors.primary),
      ),
    );
  }
}

class _ProviderStatusCard extends StatelessWidget {
  final String providerName;
  final String bookingId;

  const _ProviderStatusCard({
    required this.providerName,
    required this.bookingId,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.all(16),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppColors.surface,
        borderRadius: BorderRadius.circular(20),
        boxShadow: const [
          BoxShadow(
            color: AppColors.shadow,
            blurRadius: 12,
            offset: Offset(0, -4),
          ),
        ],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Row(
            children: [
              CircleAvatar(
                backgroundColor: AppColors.primaryLight,
                child: const Icon(Icons.person, color: AppColors.primary),
              ),
              const SizedBox(width: 12),
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(providerName, style: AppTextStyles.subtitle1),
                  Text('On the way · ~15 min', style: AppTextStyles.caption),
                ],
              ),
              const Spacer(),
              IconButton(
                icon: const Icon(Icons.phone, color: AppColors.primary),
                onPressed: () {},
              ),
              IconButton(
                icon: const Icon(Icons.chat_bubble_outline,
                    color: AppColors.primary),
                onPressed: () {},
              ),
            ],
          ),
          const SizedBox(height: 12),
          LinearProgressIndicator(
            value: 0.45,
            backgroundColor: AppColors.border,
            valueColor: const AlwaysStoppedAnimation(AppColors.primary),
          ),
          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Provider dispatched', style: AppTextStyles.caption),
              Text('Arrived', style: AppTextStyles.caption),
            ],
          ),
        ],
      ),
    );
  }
}
