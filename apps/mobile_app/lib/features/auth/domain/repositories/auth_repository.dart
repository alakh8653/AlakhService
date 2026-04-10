import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/user.dart';

abstract class AuthRepository {
  Future<Either<Failure, User>> login({
    required String phone,
    required String password,
  });

  Future<Either<Failure, bool>> register({
    required String name,
    required String phone,
    required String password,
    required String role,
  });

  Future<Either<Failure, User>> verifyOtp({
    required String phone,
    required String otp,
  });

  Future<Either<Failure, bool>> logout();

  Future<Either<Failure, bool>> forgotPassword(String phone);

  Future<Either<Failure, User?>> getCurrentUser();
}
