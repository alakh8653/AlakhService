import 'package:dio/dio.dart';

import '../constants/api_constants.dart';
import 'token_store.dart';

/// Requests that must not carry (or refresh) the user's token, e.g. signing in.
const String skipAuth = 'skipAuth';
const String _retried = 'authRetried';

/// Adds the access token to requests and, when it has expired, refreshes it once and retries.
///
/// Requests are queued while a refresh is in flight, so concurrent 401s refresh only once.
/// If the refresh fails the session is over: tokens are cleared and [onSessionExpired] runs.
class AuthInterceptor extends QueuedInterceptor {
  final TokenStore tokens;
  final Dio retryDio;
  final void Function()? onSessionExpired;

  AuthInterceptor({required this.tokens, required this.retryDio, this.onSessionExpired});

  @override
  Future<void> onRequest(RequestOptions options, RequestInterceptorHandler handler) async {
    if (options.extra[skipAuth] != true) {
      final token = await tokens.accessToken();
      if (token != null && token.isNotEmpty) {
        options.headers['Authorization'] = 'Bearer $token';
      }
    }
    handler.next(options);
  }

  @override
  Future<void> onError(DioException err, ErrorInterceptorHandler handler) async {
    final options = err.requestOptions;
    if (err.response?.statusCode != 401 || options.extra[skipAuth] == true || options.extra[_retried] == true) {
      return handler.next(err);
    }

    final sentToken = (options.headers['Authorization'] as String?)?.replaceFirst('Bearer ', '');
    var current = await tokens.accessToken();
    // Another request may already have refreshed while this one waited in the queue.
    if (current == null || current == sentToken) {
      current = await _refresh();
    }
    if (current == null) {
      await tokens.clear();
      onSessionExpired?.call();
      return handler.next(err);
    }

    try {
      options.headers['Authorization'] = 'Bearer $current';
      options.extra[_retried] = true;
      handler.resolve(await retryDio.fetch<dynamic>(options));
    } on DioException catch (e) {
      handler.next(e);
    }
  }

  Future<String?> _refresh() async {
    final refresh = await tokens.refreshToken();
    if (refresh == null || refresh.isEmpty) return null;
    try {
      final resp = await retryDio.post<Map<String, dynamic>>(
        ApiConstants.refreshToken,
        data: {'refresh_token': refresh},
        options: Options(extra: {skipAuth: true}),
      );
      final data = resp.data!;
      await tokens.save(
        accessToken: data['access_token'] as String,
        refreshToken: data['refresh_token'] as String,
      );
      return data['access_token'] as String;
    } on DioException {
      return null;
    }
  }
}
