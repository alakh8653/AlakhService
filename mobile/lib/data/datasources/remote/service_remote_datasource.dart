import 'package:dio/dio.dart';

import '../../../core/constants/api_constants.dart';
import '../../../core/errors/exceptions.dart';
import '../../models/service_model.dart';

abstract class ServiceRemoteDataSource {
  Future<List<ServiceModel>> getServices({int page = 1, int limit = 20, String? category});
  Future<ServiceModel> getServiceById(String id);
  Future<List<String>> getCategories();
}

class ServiceRemoteDataSourceImpl implements ServiceRemoteDataSource {
  const ServiceRemoteDataSourceImpl({required this.dio});

  final Dio dio;

  @override
  Future<List<ServiceModel>> getServices({
    int page = 1,
    int limit = 20,
    String? category,
  }) async {
    final response = await dio.get(
      ApiConstants.services,
      queryParameters: {
        'page': page,
        'limit': limit,
        if (category != null) 'category': category,
      },
    );
    _assertSuccess(response);
    final data = response.data['data'] as List<dynamic>;
    return data
        .map((json) => ServiceModel.fromJson(json as Map<String, dynamic>))
        .toList();
  }

  @override
  Future<ServiceModel> getServiceById(String id) async {
    final response = await dio.get(ApiConstants.serviceById(id));
    _assertSuccess(response);
    return ServiceModel.fromJson(response.data as Map<String, dynamic>);
  }

  @override
  Future<List<String>> getCategories() async {
    final response = await dio.get(ApiConstants.serviceCategories);
    _assertSuccess(response);
    return List<String>.from(response.data['data'] as List<dynamic>);
  }

  void _assertSuccess(Response<dynamic> response) {
    if (response.statusCode == null || response.statusCode! >= 400) {
      throw ServerException(
        message: response.data?['message']?.toString() ?? 'Unknown server error',
        statusCode: response.statusCode,
      );
    }
  }
}
