import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import 'travel_options.dart';

/// Where a shop is (shop_service), for directions.
class ShopLocationApi {
  final ApiClient apiClient;

  ShopLocationApi(this.apiClient);

  Future<Destination> destination(String shopId) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.shop(shopId));
      final shop = response.data!;
      return Destination(
        name: shop['name'] as String,
        address: [shop['address'], shop['city']].whereType<String>().where((p) => p.trim().isNotEmpty).join(', '),
        latitude: (shop['latitude'] as num?)?.toDouble(),
        longitude: (shop['longitude'] as num?)?.toDouble(),
      );
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
