import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/network/api_client.dart';
import '../../../core/network/api_errors.dart';
import '../../../offline/offline_queue.dart';
import '../../../offline/sync_manager.dart';
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
  final bool isVerified;

  const SavedShop({
    required this.id,
    required this.name,
    this.category = '',
    this.city,
    this.rating = 0,
    this.ratingCount = 0,
    this.isVerified = false,
  });

  factory SavedShop.fromJson(Map<String, dynamic> json) => SavedShop(
        id: json['id'] as String,
        name: json['name'] as String,
        category: (json['category'] as String?) ?? '',
        city: json['city'] as String?,
        rating: ((json['rating_avg'] as num?) ?? 0).toDouble(),
        ratingCount: (json['rating_count'] as int?) ?? 0,
        isVerified: json['is_verified'] == true,
      );
}

/// Shops the signed-in customer has saved (shop_service), and what each one offers (service_catalog).
class SavedShopsApi {
  final ApiClient apiClient;

  /// Ids of the saved shops once listed, so a heart can show without asking again.
  Set<String>? _ids;

  /// Saves and removes shops offline too, sending the last choice once back online.
  final SyncManager? offline;

  SavedShopsApi(this.apiClient, {this.offline});

  /// One business, to open from a link its owner shared.
  Future<SavedShop> shop(String shopId) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>(ApiConstants.shop(shopId));
      return SavedShop.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  Future<List<SavedShop>> list() async {
    try {
      final response = await apiClient.get<List<dynamic>>(ApiConstants.favoriteShops);
      // A shop removed while offline stays removed here until the change has gone out.
      final waiting = _waiting();
      final shops = [
        for (final s in response.data!)
          if (SavedShop.fromJson(s as Map<String, dynamic>) case final shop when waiting[shop.id] != 'DELETE') shop,
      ];
      _ids = {
        for (final s in shops) s.id,
        for (final entry in waiting.entries)
          if (entry.value == 'PUT') entry.key,
      };
      return shops;
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  /// The last waiting change (PUT or DELETE) per shop.
  Map<String, String> _waiting() => {
        for (final r in offline?.queue.items ?? const <PendingRequest>[])
          if (r.kind == PendingKind.savedShop && r.ref != null) r.ref!: r.method,
      };

  /// Whether [shopId] is saved (listing the saved shops the first time).
  Future<bool> isSaved(String shopId) async => (_ids ?? {for (final s in await list()) s.id}).contains(shopId);

  Future<void> save(String shopId) async {
    await _favorite(shopId, 'PUT');
    _ids?.add(shopId);
  }

  Future<void> unsave(String shopId) async {
    await _favorite(shopId, 'DELETE');
    _ids?.remove(shopId);
  }

  Future<void> _favorite(String shopId, String method) async {
    final path = ApiConstants.favoriteShop(shopId);
    try {
      final offline = this.offline;
      if (offline == null) {
        await apiClient.dio.request<dynamic>(path, options: Options(method: method));
      } else {
        await offline.send(offline.request(PendingKind.savedShop, method, path, ref: shopId, replaces: 'saved-shop:$shopId'));
      }
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
