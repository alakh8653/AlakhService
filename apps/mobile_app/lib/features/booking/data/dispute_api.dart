import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import '../domain/entities/booking.dart';

/// Kinds of problem a customer can report, as dispute_service records them.
const disputeTypes = {
  'service_quality': 'Poor service',
  'no_show': 'Provider didn\'t show up',
  'damage': 'Something was damaged',
  'billing': 'Charged incorrectly',
  'other': 'Something else',
};

/// Reports a problem with a booking (dispute_service) and marks the booking as disputed.
class DisputeApi {
  final ApiClient apiClient;

  DisputeApi(this.apiClient);

  Future<void> report({required String bookingId, required String type, required String description}) async {
    try {
      await apiClient.post<dynamic>(
        ApiConstants.disputes,
        data: {'booking_id': bookingId, 'dispute_type': type, 'description': description},
      );
      // The dispute is what support works from; the status lets the shop see it on the booking too.
      await apiClient.put<dynamic>(ApiConstants.bookingStatus(bookingId), data: {'status': BookingStatus.disputed});
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
