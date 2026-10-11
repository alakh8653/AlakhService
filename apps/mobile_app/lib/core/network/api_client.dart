import 'package:dio/dio.dart';

import '../constants/api_constants.dart';
import 'api_interceptor.dart';
import 'token_store.dart';

/// HTTP client for the AlakhService API gateway, signed in as the stored session.
class ApiClient {
  final Dio dio;
  final TokenStore tokens;

  ApiClient({Dio? dio, TokenStore? tokens, void Function()? onSessionExpired})
      : dio = dio ?? _defaultDio(),
        tokens = tokens ?? MemoryTokenStore() {
    // Retries and refreshes go through a twin client without this interceptor, so they cannot loop.
    final retry = Dio(this.dio.options)..httpClientAdapter = this.dio.httpClientAdapter;
    this.dio.interceptors.add(
          AuthInterceptor(tokens: this.tokens, retryDio: retry, onSessionExpired: onSessionExpired),
        );
  }

  static Dio _defaultDio() => Dio(
        BaseOptions(
          baseUrl: ApiConstants.baseUrl,
          connectTimeout: const Duration(milliseconds: ApiConstants.connectTimeout),
          receiveTimeout: const Duration(milliseconds: ApiConstants.receiveTimeout),
          headers: {'Content-Type': 'application/json', 'Accept': 'application/json'},
        ),
      );

  Future<Response<T>> get<T>(String path, {Map<String, dynamic>? queryParameters, Options? options}) =>
      dio.get<T>(path, queryParameters: queryParameters, options: options);

  Future<Response<T>> post<T>(String path, {dynamic data, Map<String, dynamic>? queryParameters, Options? options}) =>
      dio.post<T>(path, data: data, queryParameters: queryParameters, options: options);

  Future<Response<T>> put<T>(String path, {dynamic data, Options? options}) =>
      dio.put<T>(path, data: data, options: options);

  Future<Response<T>> delete<T>(String path, {Map<String, dynamic>? queryParameters, Options? options}) =>
      dio.delete<T>(path, queryParameters: queryParameters, options: options);

  /// Options for calls made before there is a session (sign-in, registration, codes).
  static Options get anonymous => Options(extra: {skipAuth: true});
}
