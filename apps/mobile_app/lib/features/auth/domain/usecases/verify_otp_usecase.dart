import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';
import '../../../../core/errors/failures.dart';
import '../entities/user.dart';
import '../repositories/auth_repository.dart';

class VerifyOtpUseCase {
  final AuthRepository repository;

  VerifyOtpUseCase(this.repository);

  Future<Either<Failure, User>> call(VerifyOtpParams params) {
    return repository.verifyOtp(phone: params.phone, otp: params.otp, purpose: params.purpose);
  }
}

class VerifyOtpParams extends Equatable {
  final String phone;
  final String otp;

  /// 'registration' (confirms a new account) or 'login' (signs in without a password).
  final String purpose;

  const VerifyOtpParams({required this.phone, required this.otp, this.purpose = 'registration'});

  @override
  List<Object?> get props => [phone, otp, purpose];
}
