import 'package:bloc_test/bloc_test.dart';
import 'package:dartz/dartz.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/annotations.dart';
import 'package:mockito/mockito.dart';

import 'package:alakh_service/core/errors/failures.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/auth/domain/usecases/login_usecase.dart';
import 'package:alakh_service/features/auth/domain/usecases/register_usecase.dart';
import 'package:alakh_service/features/auth/domain/usecases/verify_otp_usecase.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_event.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_state.dart';

@GenerateMocks([LoginUseCase, RegisterUseCase, VerifyOtpUseCase])
import 'auth_bloc_test.mocks.dart';

void main() {
  late MockLoginUseCase mockLoginUseCase;
  late MockRegisterUseCase mockRegisterUseCase;
  late MockVerifyOtpUseCase mockVerifyOtpUseCase;

  final tUser = User(
    id: 'user-1',
    name: 'John Doe',
    phone: '+919876543210',
    role: 'user',
    isVerified: true,
    createdAt: DateTime(2024, 1, 1),
  );

  setUp(() {
    mockLoginUseCase = MockLoginUseCase();
    mockRegisterUseCase = MockRegisterUseCase();
    mockVerifyOtpUseCase = MockVerifyOtpUseCase();
  });

  AuthBloc buildBloc() => AuthBloc(
        loginUseCase: mockLoginUseCase,
        registerUseCase: mockRegisterUseCase,
        verifyOtpUseCase: mockVerifyOtpUseCase,
      );

  group('AuthBloc — LoginRequested', () {
    const tPhone = '+919876543210';
    const tPassword = 'Password1';
    const tParams = LoginParams(phone: tPhone, password: tPassword);

    blocTest<AuthBloc, AuthState>(
      'emits [AuthLoading, Authenticated] on successful login',
      build: () {
        when(mockLoginUseCase(tParams))
            .thenAnswer((_) async => Right(tUser));
        return buildBloc();
      },
      act: (bloc) => bloc.add(
        const LoginRequested(phone: tPhone, password: tPassword),
      ),
      expect: () => [
        const AuthLoading(),
        Authenticated(user: tUser),
      ],
    );

    blocTest<AuthBloc, AuthState>(
      'emits [AuthLoading, AuthError] on server failure',
      build: () {
        when(mockLoginUseCase(tParams)).thenAnswer(
          (_) async => const Left(ServerFailure(message: 'Invalid credentials')),
        );
        return buildBloc();
      },
      act: (bloc) => bloc.add(
        const LoginRequested(phone: tPhone, password: tPassword),
      ),
      expect: () => [
        const AuthLoading(),
        const AuthError(message: 'Invalid credentials'),
      ],
    );

    blocTest<AuthBloc, AuthState>(
      'emits [AuthLoading, AuthError] on network failure',
      build: () {
        when(mockLoginUseCase(tParams)).thenAnswer(
          (_) async => const Left(NetworkFailure()),
        );
        return buildBloc();
      },
      act: (bloc) => bloc.add(
        const LoginRequested(phone: tPhone, password: tPassword),
      ),
      expect: () => [
        const AuthLoading(),
        const AuthError(message: 'No internet connection'),
      ],
    );
  });

  group('AuthBloc — RegisterRequested', () {
    const tParams = RegisterParams(
      name: 'John Doe',
      phone: '+919876543210',
      password: 'Password1',
      role: 'user',
    );

    blocTest<AuthBloc, AuthState>(
      'emits [AuthLoading, OtpRequired] on successful registration',
      build: () {
        when(mockRegisterUseCase(tParams))
            .thenAnswer((_) async => const Right(true));
        return buildBloc();
      },
      act: (bloc) => bloc.add(
        const RegisterRequested(
          name: 'John Doe',
          phone: '+919876543210',
          password: 'Password1',
          role: 'user',
        ),
      ),
      expect: () => [
        const AuthLoading(),
        const OtpRequired(phone: '+919876543210'),
      ],
    );
  });

  group('AuthBloc — OtpVerificationRequested', () {
    const tPhone = '+919876543210';
    const tOtp = '123456';
    const tParams = VerifyOtpParams(phone: tPhone, otp: tOtp);

    blocTest<AuthBloc, AuthState>(
      'emits [AuthLoading, Authenticated] on valid OTP',
      build: () {
        when(mockVerifyOtpUseCase(tParams))
            .thenAnswer((_) async => Right(tUser));
        return buildBloc();
      },
      act: (bloc) => bloc.add(
        const OtpVerificationRequested(phone: tPhone, otp: tOtp),
      ),
      expect: () => [
        const AuthLoading(),
        Authenticated(user: tUser),
      ],
    );
  });

  group('AuthBloc — LogoutRequested', () {
    blocTest<AuthBloc, AuthState>(
      'emits [Unauthenticated] immediately',
      build: buildBloc,
      act: (bloc) => bloc.add(const LogoutRequested()),
      expect: () => [const Unauthenticated()],
    );
  });
}
