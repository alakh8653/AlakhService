import 'package:dartz/dartz.dart';
import 'package:equatable/equatable.dart';
import '../../../../core/errors/failures.dart';
import '../entities/user.dart';
import '../repositories/auth_repository.dart';

class LoginUseCase {
  final AuthRepository repository;

  LoginUseCase(this.repository);

  Future<Either<Failure, User>> call(LoginParams params) {
    return repository.login(
      phone: params.phone,
      password: params.password,
    );
  }
}

class LoginParams extends Equatable {
  final String phone;
  final String password;

  const LoginParams({required this.phone, required this.password});

  @override
  List<Object?> get props => [phone, password];
}
