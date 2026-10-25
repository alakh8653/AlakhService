import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';
import '../../../../core/errors/failures.dart';
import '../../../legal/data/legal_api.dart';
import '../repositories/auth_repository.dart';

class RegisterUseCase {
  final AuthRepository repository;

  RegisterUseCase(this.repository);

  Future<Either<Failure, bool>> call(RegisterParams params) {
    return repository.register(
      name: params.name,
      phone: params.phone,
      password: params.password,
      role: params.role,
      acceptedTermsVersion: params.acceptedTermsVersion,
    );
  }
}

class RegisterParams extends Equatable {
  final String name;
  final String phone;
  final String password;
  final String role;
  final String acceptedTermsVersion;

  const RegisterParams({
    required this.name,
    required this.phone,
    required this.password,
    required this.role,
    this.acceptedTermsVersion = LegalLinks.fallbackTermsVersion,
  });

  @override
  List<Object?> get props => [name, phone, password, role, acceptedTermsVersion];
}
