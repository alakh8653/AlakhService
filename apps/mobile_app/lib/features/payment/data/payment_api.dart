import 'dart:math';

import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

class PaymentResult {
  final String id;
  final double amount;
  final String status;

  const PaymentResult({required this.id, required this.amount, required this.status});

  factory PaymentResult.fromJson(Map<String, dynamic> json) => PaymentResult(
        id: json['id'] as String,
        amount: ((json['amount_cents'] as num?) ?? 0) / 100,
        status: json['status'] as String,
      );
}

/// Starts payment for a booking (payment_service). The server sets the amount from the booking.
class PaymentApi {
  final ApiClient apiClient;

  PaymentApi(this.apiClient);

  /// A key that makes retries of the same payment attempt safe.
  static String newIdempotencyKey() {
    final random = Random.secure();
    return List.generate(24, (_) => random.nextInt(16).toRadixString(16)).join();
  }

  Future<PaymentResult> payForBooking({
    required String bookingId,
    required String method,
    required String idempotencyKey,
  }) async {
    try {
      final response = await apiClient.post<Map<String, dynamic>>(
        ApiConstants.initiatePayment,
        data: {'booking_id': bookingId, 'payment_method': method, 'idempotency_key': idempotencyKey},
      );
      return PaymentResult.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
