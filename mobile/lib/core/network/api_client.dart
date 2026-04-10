import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../../config/app_config.dart';
import 'api_interceptor.dart';

/// Singleton [Dio] HTTP client pre-configured for the AlakhService API.
class ApiClient {
  ApiClient._() {
    _dio = Dio(_buildBaseOptions());
    _dio.interceptors.addAll([
      AuthInterceptor(_dio),
      if (kDebugMode) LogInterceptor(requestBody: true, responseBody: true),
    ]);
  }

  static final ApiClient _instance = ApiClient._();
  static ApiClient get instance => _instance;

  late final Dio _dio;
  Dio get dio => _dio;

  BaseOptions _buildBaseOptions() {
    return BaseOptions(
      baseUrl: AppConfig.baseUrl,
      connectTimeout: Duration(milliseconds: AppConfig.connectTimeoutMs),
      receiveTimeout: Duration(milliseconds: AppConfig.receiveTimeoutMs),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
        if (AppConfig.apiKey.isNotEmpty) 'X-API-Key': AppConfig.apiKey,
      },
      validateStatus: (status) => status != null && status < 500,
    );
  }
}
