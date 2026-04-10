import 'package:equatable/equatable.dart';

/// Domain-layer failures used with [dartz.Either].
sealed class Failure extends Equatable {
  const Failure(this.message);

  final String message;

  @override
  List<Object?> get props => [message];
}

/// Failures from a remote API call.
class ServerFailure extends Failure {
  const ServerFailure(super.message, {this.statusCode});

  final int? statusCode;

  @override
  List<Object?> get props => [message, statusCode];
}

/// Failures from local cache/storage operations.
class CacheFailure extends Failure {
  const CacheFailure(super.message);
}

/// No internet connectivity.
class NetworkFailure extends Failure {
  const NetworkFailure([super.message = 'No internet connection.']);
}

/// 401 – token expired or invalid.
class AuthFailure extends Failure {
  const AuthFailure([super.message = 'Authentication failed.']);
}

/// 403 – insufficient permissions.
class PermissionFailure extends Failure {
  const PermissionFailure([super.message = 'You do not have permission.']);
}

/// Resource not found.
class NotFoundFailure extends Failure {
  const NotFoundFailure([super.message = 'Resource not found.']);
}

/// Client-side input validation failure.
class ValidationFailure extends Failure {
  const ValidationFailure(super.message);
}

/// Catch-all for unexpected errors.
class UnexpectedFailure extends Failure {
  const UnexpectedFailure([super.message = 'An unexpected error occurred.']);
}
