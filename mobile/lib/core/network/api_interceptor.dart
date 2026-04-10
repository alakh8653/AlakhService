import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart';

import '../constants/app_constants.dart';
import '../errors/exceptions.dart';
import '../../data/datasources/local/local_storage.dart';

/// Injects the access token into every request and handles token refresh on
/// 401 responses.
class AuthInterceptor extends Interceptor {
  AuthInterceptor(this._dio);

  final Dio _dio;

  @override
  Future<void> onRequest(
    RequestOptions options,
    RequestInterceptorHandler handler,
  ) async {
    final token = await LocalStorage.instance.getString(AppConstants.authTokenKey);
    if (token != null && token.isNotEmpty) {
      options.headers['Authorization'] = 'Bearer $token';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    if (err.response?.statusCode == 401) {
      try {
        final newToken = await _refreshAccessToken();
        if (newToken != null) {
          // Retry original request with refreshed token
          final opts = err.requestOptions;
          opts.headers['Authorization'] = 'Bearer $newToken';
          final clonedRequest = await _dio.fetch(opts);
          return handler.resolve(clonedRequest);
        }
      } catch (e) {
        debugPrint('[AuthInterceptor] Token refresh failed: $e');
      }
      // Refresh failed – clear tokens so app redirects to login
      await LocalStorage.instance.remove(AppConstants.authTokenKey);
      await LocalStorage.instance.remove(AppConstants.refreshTokenKey);
      return handler.reject(
        DioException(
          requestOptions: err.requestOptions,
          error: const UnauthorizedException(),
          type: DioExceptionType.badResponse,
        ),
      );
    }
    handler.next(err);
  }

  Future<String?> _refreshAccessToken() async {
    final refreshToken =
        await LocalStorage.instance.getString(AppConstants.refreshTokenKey);
    if (refreshToken == null) return null;

    final response = await _dio.post(
      '/api/v1/auth/refresh',
      data: {'refresh_token': refreshToken},
    );

    if (response.statusCode == 200) {
      final newToken = response.data['access_token'] as String?;
      if (newToken != null) {
        await LocalStorage.instance.setString(AppConstants.authTokenKey, newToken);
        return newToken;
      }
    }
    return null;
  }
}
