import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/user.dart';
import '../repositories/auth_repository.dart';

/// The user of a stored session, or null when signed out.
class GetCurrentUserUseCase {
  final AuthRepository repository;

  GetCurrentUserUseCase(this.repository);

  Future<Either<Failure, User?>> call() => repository.getCurrentUser();
}

class LogoutUseCase {
  final AuthRepository repository;

  LogoutUseCase(this.repository);

  Future<Either<Failure, bool>> call() => repository.logout();
}

class ResendOtpUseCase {
  final AuthRepository repository;

  ResendOtpUseCase(this.repository);

  Future<Either<Failure, bool>> call(String phone) => repository.resendOtp(phone);
}
