import '../../../../core/network/api_client.dart';
import '../../../../core/constants/api_constants.dart';
import '../../../../core/errors/exceptions.dart';
import '../models/service_model.dart';

abstract class ServiceRemoteDataSource {
  Future<List<ServiceModel>> getServices({
    int page = 1,
    int limit = 20,
    String? category,
  });

  Future<List<ServiceModel>> searchServices({
    required String query,
    String? category,
  });

  Future<ServiceModel> getServiceById(String id);
}

class ServiceRemoteDataSourceImpl implements ServiceRemoteDataSource {
  final ApiClient apiClient;

  ServiceRemoteDataSourceImpl({required this.apiClient});

  @override
  Future<List<ServiceModel>> getServices({
    int page = 1,
    int limit = 20,
    String? category,
  }) async {
    try {
      final response = await apiClient.get(
        ApiConstants.services,
        queryParameters: {
          'page': page,
          'limit': limit,
          if (category != null) 'category': category,
        },
      );
      final items = response.data['data'] as List<dynamic>;
      return items
          .map((e) => ServiceModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<List<ServiceModel>> searchServices({
    required String query,
    String? category,
  }) async {
    try {
      final response = await apiClient.get(
        ApiConstants.searchServices,
        queryParameters: {
          'q': query,
          if (category != null) 'category': category,
        },
      );
      final items = response.data['data'] as List<dynamic>;
      return items
          .map((e) => ServiceModel.fromJson(e as Map<String, dynamic>))
          .toList();
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }

  @override
  Future<ServiceModel> getServiceById(String id) async {
    try {
      final response = await apiClient.get('${ApiConstants.services}/$id');
      return ServiceModel.fromJson(
        response.data['data'] as Map<String, dynamic>,
      );
    } catch (e) {
      throw ServerException(message: e.toString());
    }
  }
}
