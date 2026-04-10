import 'package:dio/dio.dart';
import '../constants/app_constants.dart';

class ApiInterceptor extends Interceptor {
  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    // Add auth token if available.
    // In production, retrieve from secure storage via an injected dependency.
    const token = '';
    if (token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  void onResponse(Response response, ResponseInterceptorHandler handler) {
    handler.next(response);
  }

  @override
  void onError(DioException err, ErrorInterceptorHandler handler) {
    if (err.response?.statusCode == 401) {
      // Token expired — trigger refresh or logout flow here.
    }
    handler.next(err);
  }
}

// Suppress unused import warning; AppConstants is used by callers of this file.
// ignore: unused_element
const _kRole = AppConstants.roleUser;
