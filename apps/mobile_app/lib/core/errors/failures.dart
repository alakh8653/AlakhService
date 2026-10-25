import 'package:equatable/equatable.dart';
import '../../l10n/l10n.dart';

abstract class Failure extends Equatable {
  final String message;
  const Failure({required this.message});

  @override
  List<Object> get props => [message];
}

class ServerFailure extends Failure {
  final int? statusCode;
  const ServerFailure({required super.message, this.statusCode});

  @override
  List<Object> get props => [message, statusCode ?? 0];
}

class NetworkFailure extends Failure {
  final String? _message;

  /// Without a [message], "No internet connection" in the language on screen.
  const NetworkFailure({String? message})
      : _message = message,
        super(message: '');

  @override
  String get message => _message ?? currentL10n.errorNoInternet;
}

class CacheFailure extends Failure {
  const CacheFailure({required super.message});
}

class AuthFailure extends Failure {
  const AuthFailure({required super.message});
}

class ValidationFailure extends Failure {
  final Map<String, List<String>>? errors;
  const ValidationFailure({required super.message, this.errors});
}

class UnexpectedFailure extends Failure {
  const UnexpectedFailure({super.message = 'An unexpected error occurred'});
}
