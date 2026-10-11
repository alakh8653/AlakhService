import 'dart:math';

import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// The order the server opened at the payment gateway, for the app's checkout to pay.
class GatewayCheckout {
  final String keyId;
  final String orderId;
  final int amountCents;
  final String currency;

  const GatewayCheckout({required this.keyId, required this.orderId, required this.amountCents, required this.currency});

  factory GatewayCheckout.fromJson(Map<String, dynamic> json) => GatewayCheckout(
        keyId: json['key_id'] as String,
        orderId: json['order_id'] as String,
        amountCents: (json['amount_cents'] as num).toInt(),
        currency: json['currency'] as String,
      );
}

class PaymentResult {
  final String id;
  final double amount;
  final String status;

  /// Set while an online payment is waiting to be paid at the gateway.
  final GatewayCheckout? checkout;

  const PaymentResult({required this.id, required this.amount, required this.status, this.checkout});

  bool get isCompleted => status == 'COMPLETED';

  factory PaymentResult.fromJson(Map<String, dynamic> json) => PaymentResult(
        id: json['id'] as String,
        amount: ((json['amount_cents'] as num?) ?? 0) / 100,
        status: json['status'] as String,
        checkout: json['checkout'] == null ? null : GatewayCheckout.fromJson(json['checkout'] as Map<String, dynamic>),
      );
}

/// Payment for a booking (payment_service). The server sets the amount from the booking.
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

  /// Hands the gateway's signed receipt to the server, which completes the payment if it checks out.
  Future<PaymentResult> verify({
    required String paymentId,
    required String orderId,
    required String gatewayPaymentId,
    required String signature,
  }) async {
    try {
      final response = await apiClient.post<Map<String, dynamic>>(
        ApiConstants.verifyPayment(paymentId),
        data: {
          'razorpay_order_id': orderId,
          'razorpay_payment_id': gatewayPaymentId,
          'razorpay_signature': signature,
        },
      );
      return PaymentResult.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
