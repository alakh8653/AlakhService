import 'package:dartz/dartz.dart';
import '../../../../core/errors/failures.dart';
import '../entities/user.dart';
import '../repositories/auth_repository.dart';

class VerifyOtpUseCase {
  final AuthRepository repository;

  VerifyOtpUseCase(this.repository);

  Future<Either<Failure, User>> call(VerifyOtpParams params) {
    return repository.verifyOtp(phone: params.phone, otp: params.otp);
  }
}

class VerifyOtpParams {
  final String phone;
  final String otp;

  const VerifyOtpParams({required this.phone, required this.otp});
}
