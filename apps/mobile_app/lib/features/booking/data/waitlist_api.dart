import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// The waitlist for a full day at a shop (booking_service): the customer is told once if a time opens up.
class WaitlistApi {
  final ApiClient apiClient;

  WaitlistApi(this.apiClient);

  /// [day] is a calendar day in the shop's time zone (India); only its date is used.
  Future<void> join(String serviceId, DateTime day) async {
    final date = '${day.year.toString().padLeft(4, '0')}-${day.month.toString().padLeft(2, '0')}-'
        '${day.day.toString().padLeft(2, '0')}';
    try {
      await apiClient.post<dynamic>(ApiConstants.waitlist, data: {'service_id': serviceId, 'date': date});
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
