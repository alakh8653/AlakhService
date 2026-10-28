import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import '../../payment/data/payment_api.dart';

/// A package a shop sells: [visits] of one service for [price] rupees, valid [validDays] days once bought.
class PackageOffer {
  final String id;
  final String serviceId;
  final String name;
  final int visits;
  final double price;
  final int validDays;

  const PackageOffer({
    required this.id,
    required this.serviceId,
    required this.name,
    required this.visits,
    required this.price,
    required this.validDays,
  });

  /// What it saves against paying [servicePrice] for each visit (0 when it saves nothing).
  double savingOn(double servicePrice) {
    final saving = servicePrice * visits - price;
    return saving > 0 ? saving : 0;
  }

  factory PackageOffer.fromJson(Map<String, dynamic> json) => PackageOffer(
        id: json['id'] as String,
        serviceId: json['service_id'] as String,
        name: json['name'] as String,
        visits: (json['visits'] as num).toInt(),
        price: ((json['price_cents'] as num?) ?? 0) / 100,
        validDays: (json['valid_days'] as num).toInt(),
      );
}

/// A package the customer bought: visits left to book until it expires.
class OwnedPackage {
  final String id;
  final String serviceId;
  final String name;
  final int visitsTotal;
  final int visitsLeft;
  final String status;
  final DateTime? expiresAt;

  /// Can be used for a booking now (paid, visits left, not expired).
  final bool usable;

  const OwnedPackage({
    required this.id,
    required this.serviceId,
    required this.name,
    required this.visitsTotal,
    required this.visitsLeft,
    required this.status,
    this.expiresAt,
    this.usable = false,
  });

  factory OwnedPackage.fromJson(Map<String, dynamic> json) => OwnedPackage(
        id: json['id'] as String,
        serviceId: json['service_id'] as String,
        name: json['name'] as String,
        visitsTotal: (json['visits_total'] as num).toInt(),
        visitsLeft: (json['visits_left'] as num).toInt(),
        status: json['status'] as String,
        expiresAt: DateTime.tryParse((json['expires_at'] as String?) ?? '')?.toLocal(),
        usable: (json['usable'] as bool?) ?? false,
      );
}

/// Prepaid packages (payment_service): what a service offers, buying one, and the customer's own.
class PackagesApi {
  final ApiClient apiClient;

  PackagesApi(this.apiClient);

  Future<List<PackageOffer>> forService(String serviceId) async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.packages, queryParameters: {'service_id': serviceId});
      return [for (final p in response.data ?? const []) PackageOffer.fromJson(p as Map<String, dynamic>)];
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// Starts buying [packageId]; the payment's checkout opens next, as for a booking.
  Future<PaymentResult> buy(String packageId, {required String idempotencyKey, String method = 'upi'}) async {
    try {
      final response = await apiClient.post<Map<String, dynamic>>(
        ApiConstants.buyPackage(packageId),
        data: {'payment_method': method, 'idempotency_key': idempotencyKey},
      );
      return PaymentResult.fromJson(response.data!['payment'] as Map<String, dynamic>);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  Future<List<OwnedPackage>> mine() async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.myPackages);
      return [for (final p in response.data ?? const []) OwnedPackage.fromJson(p as Map<String, dynamic>)];
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
