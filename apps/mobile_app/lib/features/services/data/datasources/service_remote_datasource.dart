import 'package:dio/dio.dart';

import '../../../../core/constants/api_constants.dart';
import '../../../../core/network/api_client.dart';
import '../../../../core/network/api_errors.dart';
import '../models/service_model.dart';

abstract class ServiceRemoteDataSource {
  Future<List<ServiceModel>> getServices({int page = 1, int limit = 20, String? category});

  Future<List<ServiceModel>> searchServices({required String query, String? category});

  Future<ServiceModel> getServiceById(String id);
}

/// Browses service_catalog. Browsing is public, so these calls work signed in or not.
class ServiceRemoteDataSourceImpl implements ServiceRemoteDataSource {
  final ApiClient apiClient;

  ServiceRemoteDataSourceImpl({required this.apiClient});

  List<ServiceModel> _list(dynamic data) =>
      (data as List<dynamic>).map((e) => ServiceModel.fromJson(e as Map<String, dynamic>)).toList();

  @override
  Future<List<ServiceModel>> getServices({int page = 1, int limit = 20, String? category}) async {
    try {
      final response = await apiClient.get<List<dynamic>>(
        ApiConstants.services,
        queryParameters: {'skip': (page - 1) * limit, 'limit': limit},
      );
      return _list(response.data);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  @override
  Future<List<ServiceModel>> searchServices({required String query, String? category}) async {
    try {
      final response = await apiClient.get<List<dynamic>>(
        ApiConstants.searchServices,
        queryParameters: {'q': query, if (category != null) 'category': category},
      );
      return _list(response.data);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }

  @override
  Future<ServiceModel> getServiceById(String id) async {
    try {
      final response = await apiClient.get<Map<String, dynamic>>('${ApiConstants.services}/$id');
      return ServiceModel.fromJson(response.data!);
    } on DioException catch (e) {
      throw toServerException(e);
    }
  }
}
