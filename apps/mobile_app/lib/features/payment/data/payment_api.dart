import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import '../../../core/network/idempotency.dart' as idempotency;

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
  static String newIdempotencyKey() => idempotency.newIdempotencyKey(length: 24);

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

  /// Starts a tip of [amountCents] for the provider of a completed booking; always paid online.
  Future<PaymentResult> tip({
    required String bookingId,
    required int amountCents,
    required String idempotencyKey,
    String method = 'upi',
  }) async {
    try {
      final response = await apiClient.post<Map<String, dynamic>>(
        ApiConstants.tips,
        data: {'booking_id': bookingId, 'amount_cents': amountCents, 'payment_method': method, 'idempotency_key': idempotencyKey},
      );
      return PaymentResult.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The tip already paid for the booking, in rupees, or null when there is none.
  Future<double?> tipPaid(String bookingId) async {
    try {
      final response = await apiClient.get<List<dynamic>>(
        ApiConstants.payments,
        queryParameters: {'booking_id': bookingId, 'purpose': 'TIP'},
      );
      for (final p in response.data ?? const []) {
        final m = p as Map<String, dynamic>;
        if (m['status'] == 'COMPLETED') return ((m['amount_cents'] as num?) ?? 0) / 100;
      }
      return null;
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// How each of the signed-in customer's bookings is being paid: booking id → 'paid' (settled)
  /// or 'cash' (chose to pay in person, not yet handed over).
  Future<Map<String, String>> paymentStateByBooking() async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.payments);
      final states = <String, String>{};
      for (final p in response.data ?? const []) {
        final m = p as Map<String, dynamic>;
        final status = m['status'] as String;
        final booking = m['booking_id'] as String;
        if (const {'COMPLETED', 'PARTIALLY_REFUNDED', 'REFUNDED'}.contains(status)) {
          states[booking] = 'paid';
        } else if (status == 'PENDING' && m['payment_method'] == 'cash' && states[booking] != 'paid') {
          states[booking] = 'cash';
        }
      }
      return states;
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The id of the booking's completed payment (refunded ones included), for its invoice; null
  /// when it has none.
  Future<String?> settledPaymentId(String bookingId) async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.payments);
      for (final p in response.data ?? const []) {
        final m = p as Map<String, dynamic>;
        if (m['booking_id'] == bookingId && const {'COMPLETED', 'PARTIALLY_REFUNDED', 'REFUNDED'}.contains(m['status'])) {
          return m['id'] as String;
        }
      }
      return null;
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The payment's invoice as a printable HTML page, fetched with the customer's session.
  Future<String> invoiceHtml(String paymentId) async {
    try {
      final response = await apiClient.get<String>(
        ApiConstants.paymentInvoice(paymentId),
        options: Options(responseType: ResponseType.plain, headers: {'Accept': 'text/html'}),
      );
      return response.data ?? '';
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
