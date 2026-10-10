import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';
import '../../../../core/errors/failures.dart';
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
    );
  }
}

class RegisterParams extends Equatable {
  final String name;
  final String phone;
  final String password;
  final String role;

  const RegisterParams({
    required this.name,
    required this.phone,
    required this.password,
    required this.role,
  });

  @override
  List<Object?> get props => [name, phone, password, role];
}
