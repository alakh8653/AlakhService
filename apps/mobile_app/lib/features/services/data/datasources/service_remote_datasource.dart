import 'package:dio/dio.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_errors.dart';
import '../../../reviews/data/reviews_api.dart';
import '../../domain/entities/service_filters.dart';
import '../models/service_model.dart';

abstract class ServiceRemoteDataSource {
  Future<List<ServiceModel>> getServices({
    int page = 1,
    int limit = 20,
    String? category,
    ServiceFilters filters = ServiceFilters.none,
  });

  Future<List<ServiceModel>> searchServices({
    required String query,
    String? category,
    ServiceFilters filters = ServiceFilters.none,
  });

  Future<ServiceModel> getServiceById(String id);
}

/// Browses service_catalog. Browsing is public, so these calls work signed in or not.
class ServiceRemoteDataSourceImpl implements ServiceRemoteDataSource {
  final ApiClient apiClient;

  /// Adds each listing's shop rating (one request per page of results); without it cards say "New".
  final ReviewsApi? ratings;

  ServiceRemoteDataSourceImpl({required this.apiClient, this.ratings});

  Future<List<ServiceModel>> _list(dynamic data) async {
    final services = (data as List<dynamic>).map((e) => ServiceModel.fromJson(e as Map<String, dynamic>)).toList();
    return _withRatings(services);
  }

  /// Ratings are extra: if they can't be had, the services still show.
  Future<List<ServiceModel>> _withRatings(List<ServiceModel> services) async {
    final api = ratings;
    final shopIds = services.map((s) => s.shopId).whereType<String>();
    if (api == null || shopIds.isEmpty) return services;
    try {
      final byShop = await api.ratings(shopIds);
      return [
        for (final s in services)
          if (byShop[s.shopId] case final r?) s.withRating(r.average, r.count, verified: r.isVerified) else s,
      ];
    } catch (_) {
      return services;
    }
  }

  @override
  Future<List<ServiceModel>> getServices({
    int page = 1,
    int limit = 20,
    String? category,
    ServiceFilters filters = ServiceFilters.none,
  }) async {
    try {
      final response = await apiClient.get<List<dynamic>>(
        ApiConstants.services,
        // The type picked on the home screen (a shop's type of work) narrows the list too.
        queryParameters: {
          'skip': (page - 1) * limit,
          'limit': limit,
          if (category != null) 'category': category,
          ...filters.toQuery(),
        },
      );
      return await _list(response.data);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  @override
  Future<List<ServiceModel>> searchServices({
    required String query,
    String? category,
    ServiceFilters filters = ServiceFilters.none,
  }) async {
    try {
      final response = await apiClient.get<List<dynamic>>(
        ApiConstants.searchServices,
        queryParameters: {'q': query, if (category != null) 'category': category, ...filters.toQuery()},
      );
      return await _list(response.data);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  @override
  Future<ServiceModel> getServiceById(String id) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>('${ApiConstants.services}/$id');
      return (await _withRatings([ServiceModel.fromJson(response.data!)])).single;
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
