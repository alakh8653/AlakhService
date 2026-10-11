import 'package:dio/dio.dart';

import '../errors/exceptions.dart';

/// A message fit to show a user, from an API error (FastAPI `detail`) or a transport failure.
String apiErrorMessage(Object error) {
  if (error is DioException) {
    final data = error.response?.data;
    if (data is Map) {
      final detail = data['detail'];
      if (detail is String && detail.isNotEmpty) return detail;
      if (detail is List && detail.isNotEmpty && detail.first is Map) {
        final msg = (detail.first as Map)['msg'];
        if (msg is String) return msg.replaceFirst('Value error, ', '');
      }
    }
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.receiveTimeout:
      case DioExceptionType.sendTimeout:
        return 'The server took too long to respond. Please try again.';
      case DioExceptionType.connectionError:
        return 'Cannot reach AlakhService. Check your connection.';
      default:
        break;
    }
    final status = error.response?.statusCode;
    if (status != null) return 'Request failed ($status)';
  }
  if (error is ServerException) return error.message;
  return 'Something went wrong. Please try again.';
}

/// Wraps any failure from a request as a [ServerException] carrying a readable message.
ServerException toServerException(Object error) => ServerException(
      message: apiErrorMessage(error),
      statusCode: error is DioException ? error.response?.statusCode : null,
    );
