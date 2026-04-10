import 'package:bloc_test/bloc_test.dart';
import 'package:dartz/dartz.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';
import 'package:alakh_service_mobile/core/errors/failures.dart';
import 'package:alakh_service_mobile/domain/entities/user.dart';
import 'package:alakh_service_mobile/domain/repositories/auth_repository.dart';
import 'package:alakh_service_mobile/domain/usecases/login_usecase.dart';
import 'package:alakh_service_mobile/domain/usecases/register_usecase.dart';
import 'package:alakh_service_mobile/presentation/bloc/auth/auth_bloc.dart';
import 'package:alakh_service_mobile/presentation/bloc/auth/auth_event.dart';
import 'package:alakh_service_mobile/presentation/bloc/auth/auth_state.dart';

class MockLoginUseCase extends Mock implements LoginUseCase {}
class MockRegisterUseCase extends Mock implements RegisterUseCase {}
class MockAuthRepository extends Mock implements AuthRepository {}

void main() {
  late AuthBloc authBloc;
  late MockLoginUseCase mockLogin;
  late MockRegisterUseCase mockRegister;
  late MockAuthRepository mockRepo;

  const tUser = User(id: '1', name: 'Test', email: 'test@test.com', phone: '1234567890');

  setUp(() {
    mockLogin = MockLoginUseCase();
    mockRegister = MockRegisterUseCase();
    mockRepo = MockAuthRepository();
    authBloc = AuthBloc(loginUseCase: mockLogin, registerUseCase: mockRegister, authRepository: mockRepo);
    registerFallbackValue(const LoginParams(email: '', password: ''));
  });

  tearDown(() => authBloc.close());

  test('initial state is AuthInitial', () => expect(authBloc.state, isA<AuthInitial>()));

  blocTest<AuthBloc, AuthState>(
    'emits [AuthLoading, Authenticated] on successful login',
    build: () {
      when(() => mockRepo.isLoggedIn).thenReturn(false);
      when(() => mockLogin(any())).thenAnswer((_) async => const Right(tUser));
      return authBloc;
    },
    act: (b) => b.add(const LoginRequested(email: 'test@test.com', password: 'password')),
    expect: () => [isA<AuthLoading>(), isA<Authenticated>()],
  );

  blocTest<AuthBloc, AuthState>(
    'emits [AuthLoading, AuthError] on login failure',
    build: () {
      when(() => mockRepo.isLoggedIn).thenReturn(false);
      when(() => mockLogin(any())).thenAnswer((_) async => const Left(ServerFailure('Error')));
      return authBloc;
    },
    act: (b) => b.add(const LoginRequested(email: 'bad@test.com', password: 'wrong')),
    expect: () => [isA<AuthLoading>(), isA<AuthError>()],
  );
}
