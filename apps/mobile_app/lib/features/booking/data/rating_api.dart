import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';

/// Rates the shop behind a completed booking (shop_service; once per booking).
class RatingApi {
  final ApiClient apiClient;

  RatingApi(this.apiClient);

  Future<void> rate({required String shopId, required String bookingId, required double rating, String? comment}) async {
    try {
      await apiClient.post<dynamic>(
        ApiConstants.rateShop(shopId),
        data: {'booking_id': bookingId, 'rating': rating, if (comment != null && comment.isNotEmpty) 'comment': comment},
      );
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
