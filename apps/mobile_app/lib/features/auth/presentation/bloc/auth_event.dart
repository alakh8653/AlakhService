import 'package:equatable/equatable.dart';

abstract class AuthEvent extends Equatable {
  const AuthEvent();

  @override
  List<Object?> get props => [];
}

class LoginRequested extends AuthEvent {
  final String phone;
  final String password;

  const LoginRequested({required this.phone, required this.password});

  @override
  List<Object> get props => [phone, password];
}

class RegisterRequested extends AuthEvent {
  final String name;
  final String phone;
  final String password;
  final String role;

  const RegisterRequested({
    required this.name,
    required this.phone,
    required this.password,
    required this.role,
  });

  @override
  List<Object> get props => [name, phone, password, role];
}

class OtpVerificationRequested extends AuthEvent {
  final String phone;
  final String otp;

  const OtpVerificationRequested({required this.phone, required this.otp});

  @override
  List<Object> get props => [phone, otp];
}

class LogoutRequested extends AuthEvent {
  const LogoutRequested();
}

class CheckAuthStatus extends AuthEvent {
  const CheckAuthStatus();
}
