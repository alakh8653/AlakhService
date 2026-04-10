import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/annotations.dart';
import 'package:mockito/mockito.dart';

import 'package:alakh_service/features/auth/domain/usecases/login_usecase.dart';
import 'package:alakh_service/features/auth/domain/usecases/register_usecase.dart';
import 'package:alakh_service/features/auth/domain/usecases/verify_otp_usecase.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_state.dart';
import 'package:alakh_service/features/auth/presentation/pages/login_page.dart';

@GenerateMocks([LoginUseCase, RegisterUseCase, VerifyOtpUseCase])
import 'login_page_test.mocks.dart';

void main() {
  late MockLoginUseCase mockLoginUseCase;
  late MockRegisterUseCase mockRegisterUseCase;
  late MockVerifyOtpUseCase mockVerifyOtpUseCase;

  setUp(() {
    mockLoginUseCase = MockLoginUseCase();
    mockRegisterUseCase = MockRegisterUseCase();
    mockVerifyOtpUseCase = MockVerifyOtpUseCase();
  });

  Widget buildTestableWidget() {
    return MaterialApp(
      home: BlocProvider<AuthBloc>(
        create: (_) => AuthBloc(
          loginUseCase: mockLoginUseCase,
          registerUseCase: mockRegisterUseCase,
          verifyOtpUseCase: mockVerifyOtpUseCase,
        ),
        child: const LoginPage(),
      ),
    );
  }

  testWidgets('renders phone field, password field, and login button',
      (tester) async {
    await tester.pumpWidget(buildTestableWidget());

    expect(find.text('Welcome Back'), findsOneWidget);
    expect(find.text('Phone Number'), findsOneWidget);
    expect(find.text('Password'), findsOneWidget);
    expect(find.text('Login'), findsOneWidget);
    expect(find.text('Forgot Password?'), findsOneWidget);
  });

  testWidgets('shows validation errors when form is submitted empty',
      (tester) async {
    await tester.pumpWidget(buildTestableWidget());

    await tester.tap(find.text('Login'));
    await tester.pump();

    expect(find.text('Phone number is required'), findsOneWidget);
    expect(find.text('Password is required'), findsOneWidget);
  });

  testWidgets('shows loading indicator when AuthLoading state is emitted',
      (tester) async {
    final bloc = AuthBloc(
      loginUseCase: mockLoginUseCase,
      registerUseCase: mockRegisterUseCase,
      verifyOtpUseCase: mockVerifyOtpUseCase,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: BlocProvider<AuthBloc>.value(
          value: bloc,
          child: const LoginPage(),
        ),
      ),
    );

    bloc.emit(const AuthLoading());
    await tester.pump();

    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });

  testWidgets('navigates to register page when register link is tapped',
      (tester) async {
    await tester.pumpWidget(buildTestableWidget());

    await tester.tap(find.text('Register'));
    await tester.pumpAndSettle();

    expect(find.text('Create Account'), findsOneWidget);
  });

  testWidgets(
      'shows error snackbar when AuthError state is emitted',
      (tester) async {
    final bloc = AuthBloc(
      loginUseCase: mockLoginUseCase,
      registerUseCase: mockRegisterUseCase,
      verifyOtpUseCase: mockVerifyOtpUseCase,
    );

    await tester.pumpWidget(
      MaterialApp(
        home: BlocProvider<AuthBloc>.value(
          value: bloc,
          child: const LoginPage(),
        ),
      ),
    );

    bloc.emit(const AuthError(message: 'Invalid credentials'));
    await tester.pump();

    expect(find.text('Invalid credentials'), findsOneWidget);
  });
}
