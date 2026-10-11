import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

class CouponCheck {
  final String code;
  final bool isValid;

  /// Percent off, e.g. 10 (pricing_engine reports it as a fraction, 0.10).
  final double discountPct;
  final String message;

  const CouponCheck({required this.code, required this.isValid, required this.discountPct, required this.message});
}

/// Checks a promo code before booking (pricing_engine). The booking itself is priced by the server.
class CouponApi {
  final ApiClient apiClient;

  CouponApi(this.apiClient);

  Future<CouponCheck> check(String code) async {
    final normalized = code.trim().toUpperCase();
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.validateCoupon(normalized));
      final data = response.data!;
      return CouponCheck(
        code: normalized,
        isValid: data['is_valid'] as bool,
        discountPct: (data['discount_pct'] as num).toDouble() * 100,
        message: (data['message'] as String?) ?? '',
      );
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) {
        return CouponCheck(code: normalized, isValid: false, discountPct: 0, message: 'Coupon not found');
      }
      throw toServerException(e);
    }
  }
}
