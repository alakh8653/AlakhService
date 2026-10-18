import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/user.dart';

abstract class AuthRepository {
  /// Signs in with an email or phone number and password.
  Future<Either<Failure, User>> login({required String phone, required String password});

  /// Creates the account and texts a verification code to [phone].
  Future<Either<Failure, bool>> register({
    required String name,
    required String phone,
    required String password,
    required String role,
  });

  /// Confirms a 'registration' or 'login' code, which signs the user in.
  Future<Either<Failure, User>> verifyOtp({required String phone, required String otp, String purpose = 'registration'});

  /// Sends a (new) one-time code for [purpose]: 'registration', or 'login' to sign in without a password.
  Future<Either<Failure, bool>> resendOtp(String phone, {String purpose = 'registration'});

  Future<Either<Failure, bool>> logout();

  /// Texts (or emails) a password reset code.
  Future<Either<Failure, bool>> forgotPassword(String phone);

  /// Sets a new password with the code from [forgotPassword].
  Future<Either<Failure, bool>> resetPassword({
    required String phone,
    required String code,
    required String newPassword,
  });

  /// The signed-in user, if a session is stored and still valid.
  Future<Either<Failure, User?>> getCurrentUser();
}
