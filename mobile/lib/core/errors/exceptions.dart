/// Typed exceptions thrown from data-layer operations.
class ServerException implements Exception {
  const ServerException({required this.message, this.statusCode});

  final String message;
  final int? statusCode;

  @override
  String toString() => 'ServerException(statusCode: $statusCode, message: $message)';
}

class UnauthorizedException implements Exception {
  const UnauthorizedException({this.message = 'Unauthorized. Please login again.'});

  final String message;

  @override
  String toString() => 'UnauthorizedException: $message';
}

class ForbiddenException implements Exception {
  const ForbiddenException({this.message = 'Access forbidden.'});

  final String message;

  @override
  String toString() => 'ForbiddenException: $message';
}

class NotFoundException implements Exception {
  const NotFoundException({this.message = 'Requested resource not found.'});

  final String message;

  @override
  String toString() => 'NotFoundException: $message';
}

class NetworkException implements Exception {
  const NetworkException({this.message = 'No internet connection.'});

  final String message;

  @override
  String toString() => 'NetworkException: $message';
}

class CacheException implements Exception {
  const CacheException({this.message = 'Cache operation failed.'});

  final String message;

  @override
  String toString() => 'CacheException: $message';
}

class ValidationException implements Exception {
  const ValidationException({required this.message});

  final String message;

  @override
  String toString() => 'ValidationException: $message';
}

class TimeoutException implements Exception {
  const TimeoutException({this.message = 'Request timed out.'});

  final String message;

  @override
  String toString() => 'TimeoutException: $message';
}
