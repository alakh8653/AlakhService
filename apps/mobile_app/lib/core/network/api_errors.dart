import 'package:dio/dio.dart';

import '../errors/exceptions.dart';
import '../../l10n/l10n.dart';

/// A message fit to show a user, from an API error (FastAPI `detail`, shown as the server sent it) or a
/// transport failure (in the language on screen).
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
        return currentL10n.errorTimeout;
      case DioExceptionType.connectionError:
        return currentL10n.errorCannotReach;
      default:
        break;
    }
    final status = error.response?.statusCode;
    if (status != null) return currentL10n.errorRequestFailed(status);
  }
  if (error is ServerException) return error.message;
  return currentL10n.errorGeneric;
}

/// Wraps any failure from a request as a [ServerException] carrying a readable message.
ServerException toServerException(Object error) => ServerException(
      message: apiErrorMessage(error),
      statusCode: error is DioException ? error.response?.statusCode : null,
    );
