import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// Extra charges on a booking: the provider asks after seeing the job, and only the customer can agree.
class ExtraChargeApi {
  final ApiClient apiClient;

  ExtraChargeApi(this.apiClient);

  String _charges(String bookingId) => '${ApiConstants.bookings}/$bookingId/extra-charges';

  Future<void> _call(Future<void> Function() body) async {
    try {
      await body();
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  Future<void> ask(String bookingId, int amountCents, String reason) => _call(() async {
        await apiClient.post<Map<String, dynamic>>(_charges(bookingId), data: {'amount_cents': amountCents, 'reason': reason});
      });

  Future<void> approve(String bookingId, String chargeId) => _call(() async {
        await apiClient.post<Map<String, dynamic>>('${_charges(bookingId)}/$chargeId/approve');
      });

  Future<void> decline(String bookingId, String chargeId) => _call(() async {
        await apiClient.post<Map<String, dynamic>>('${_charges(bookingId)}/$chargeId/decline');
      });

  Future<void> withdraw(String bookingId, String chargeId) => _call(() async {
        await apiClient.delete<void>('${_charges(bookingId)}/$chargeId');
      });
}
