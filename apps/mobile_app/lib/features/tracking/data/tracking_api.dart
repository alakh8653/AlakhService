import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

class ProviderLocation {
  final double latitude;
  final double longitude;
  final DateTime recordedAt;

  const ProviderLocation({required this.latitude, required this.longitude, required this.recordedAt});

  factory ProviderLocation.fromJson(Map<String, dynamic> json) => ProviderLocation(
        latitude: (json['latitude'] as num).toDouble(),
        longitude: (json['longitude'] as num).toDouble(),
        recordedAt: DateTime.tryParse((json['timestamp'] as String?) ?? '')?.toLocal() ??
            DateTime.now(),
      );
}

/// Live position of the provider working on the customer's booking (tracking_service).
class TrackingApi {
  final ApiClient apiClient;

  TrackingApi(this.apiClient);

  /// The provider's latest position, or null until they have shared one.
  Future<ProviderLocation?> providerLocation(String providerId) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.providerLocation(providerId));
      return ProviderLocation.fromJson(response.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      throw toServerException(e);
    }
  }

  /// Shares the signed-in provider's position (only their own; the server checks).
  Future<void> report({
    required String providerId,
    required double latitude,
    required double longitude,
    double? accuracy,
    double? speed,
    double? heading,
  }) async {
    try {
      await apiClient.post<dynamic>(ApiConstants.locations, data: {
        'provider_id': providerId,
        'latitude': latitude,
        'longitude': longitude,
        if (accuracy != null) 'accuracy': accuracy,
        if (speed != null) 'speed': speed,
        if (heading != null) 'heading': heading,
      });
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
