import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import '../../services/data/models/service_model.dart';
import '../../services/domain/entities/service_entity.dart';

/// A shop the customer has saved, as the saved-shops list shows it.
class SavedShop {
  final String id;
  final String name;
  final String category;
  final String? city;
  final double rating;
  final int ratingCount;

  const SavedShop({
    required this.id,
    required this.name,
    this.category = '',
    this.city,
    this.rating = 0,
    this.ratingCount = 0,
  });

  factory SavedShop.fromJson(Map<String, dynamic> json) => SavedShop(
        id: json['id'] as String,
        name: json['name'] as String,
        category: (json['category'] as String?) ?? '',
        city: json['city'] as String?,
        rating: ((json['rating_avg'] as num?) ?? 0).toDouble(),
        ratingCount: (json['rating_count'] as int?) ?? 0,
      );
}

/// Shops the signed-in customer has saved (shop_service), and what each one offers (service_catalog).
class SavedShopsApi {
  final ApiClient apiClient;

  /// Ids of the saved shops once listed, so a heart can show without asking again.
  Set<String>? _ids;

  SavedShopsApi(this.apiClient);

  Future<List<SavedShop>> list() async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.favoriteShops);
      final shops = [for (final s in response.data!) SavedShop.fromJson(s as Map<String, dynamic>)];
      _ids = {for (final s in shops) s.id};
      return shops;
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// Whether [shopId] is saved (listing the saved shops the first time).
  Future<bool> isSaved(String shopId) async => (_ids ?? {for (final s in await list()) s.id}).contains(shopId);

  Future<void> save(String shopId) async {
    try {
      await apiClient.put<dynamic>(ApiConstants.favoriteShop(shopId));
      _ids?.add(shopId);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  Future<void> unsave(String shopId) async {
    try {
      await apiClient.delete<dynamic>(ApiConstants.favoriteShop(shopId));
      _ids?.remove(shopId);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The services the shop offers now, to book one.
  Future<List<ServiceEntity>> services(String shopId) async {
    try {
      final response = await apiClient.get<List<dynamic>>(
        ApiConstants.services,
        queryParameters: {'shop_id': shopId, 'limit': 100},
      );
      return [
        for (final s in response.data!)
          if (ServiceModel.fromJson(s as Map<String, dynamic>) case final service when service.isAvailable) service,
      ];
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
