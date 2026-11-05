import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// A link someone else can open to follow the visit, without signing in.
class ShareLink {
  final String url;
  final DateTime? expiresAt;

  const ShareLink(this.url, this.expiresAt);
}

/// The SOS the server recorded, and the number to call.
class SosResult {
  final String? alertId;
  final String emergencyNumber;

  const SosResult({this.alertId, this.emergencyNumber = defaultEmergencyNumber});

  /// India's single emergency number.
  static const defaultEmergencyNumber = '112';
}

/// Customer-trust actions on a booking (booking_service): the free fix within the shop's guarantee,
/// sharing a visit, and SOS. (Extra charges are ExtraChargeApi.)
class TrustApi {
  final ApiClient apiClient;

  TrustApi(this.apiClient);

  Future<T> _call<T>(Future<T> Function() body) async {
    try {
      return await body();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// Asks the shop for the free fix; returns the new booking's id.
  Future<String> requestRework(String bookingId, {required String reason, DateTime? preferredAt}) => _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(
          ApiConstants.bookingRework(bookingId),
          data: {
            'reason': reason.trim(),
            if (preferredAt != null) 'preferred_at': preferredAt.toUtc().toIso8601String(),
          },
        );
        return response.data!['id'].toString();
      });

  Future<ShareLink> share(String bookingId) => _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(ApiConstants.bookingShare(bookingId));
        final data = response.data!;
        return ShareLink(data['url'] as String, DateTime.tryParse((data['expires_at'] as String?) ?? '')?.toLocal());
      });

  /// Alerts the safety team. Throws when it could not; the caller still offers 112.
  Future<SosResult> sos(String bookingId, {double? latitude, double? longitude, String? note}) => _call(() async {
        final response = await apiClient.post<Map<String, dynamic>>(
          ApiConstants.bookingSos(bookingId),
          data: {
            if (latitude != null) 'lat': latitude,
            if (longitude != null) 'lng': longitude,
            if (note != null && note.isNotEmpty) 'note': note,
          },
        );
        final data = response.data ?? const {};
        final number = data['emergency_number']?.toString();
        return SosResult(
          alertId: data['alert_id']?.toString(),
          emergencyNumber: number == null || number.isEmpty ? SosResult.defaultEmergencyNumber : number,
        );
      });
}
