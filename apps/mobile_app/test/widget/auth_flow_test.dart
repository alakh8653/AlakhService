import 'package:alakh_service/core/errors/failures.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/auth/domain/repositories/auth_repository.dart';
import 'package:alakh_service/features/auth/domain/usecases/login_usecase.dart';
import 'package:alakh_service/features/auth/domain/usecases/register_usecase.dart';
import 'package:alakh_service/features/auth/domain/usecases/session_usecases.dart';
import 'package:alakh_service/features/auth/domain/usecases/verify_otp_usecase.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_state.dart';
import 'package:alakh_service/features/auth/presentation/pages/forgot_password_page.dart';
import 'package:alakh_service/features/auth/presentation/pages/login_page.dart';
import 'package:alakh_service/features/auth/presentation/pages/otp_verification_page.dart';
import 'package:alakh_service/features/legal/data/legal_api.dart';
import 'package:dartz/dartz.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';

final _user = User(id: 'u1', name: 'Priya', phone: '+919876543210', role: 'customer', isVerified: true, createdAt: DateTime(2026));

/// Records what the screens ask auth_service for.
class FakeAuth implements AuthRepository {
  final calls = <String>[];
  String? registerError;
  String? termsVersion;

  @override
  Future<Either<Failure, User>> login({required String phone, required String password}) async {
    calls.add('login $phone $password');
    return const Left(ServerFailure(message: 'Invalid credentials'));
  }

  @override
  Future<Either<Failure, bool>> register({required String name, required String phone, required String password, required String role, String acceptedTermsVersion = LegalLinks.fallbackTermsVersion}) async {
    calls.add('register $phone');
    termsVersion = acceptedTermsVersion;
    return registerError == null ? const Right(true) : Left(ServerFailure(message: registerError!));
  }

  @override
  Future<Either<Failure, User>> verifyOtp({required String phone, required String otp, String purpose = 'registration'}) async {
    calls.add('verify $phone $otp $purpose');
    return Right(_user);
  }

  @override
  Future<Either<Failure, bool>> resendOtp(String phone, {String purpose = 'registration'}) async {
    calls.add('send $phone $purpose');
    return const Right(true);
  }

  @override
  Future<Either<Failure, bool>> forgotPassword(String phone) async {
    calls.add('forgot $phone');
    return const Right(true);
  }

  @override
  Future<Either<Failure, bool>> resetPassword({required String phone, required String code, required String newPassword}) async =>
      const Right(true);

  @override
  Future<Either<Failure, bool>> logout() async => const Right(true);

  @override
  Future<Either<Failure, User?>> getCurrentUser() async => const Right(null);
}

AuthBloc blocFor(FakeAuth repo) => AuthBloc(
      loginUseCase: LoginUseCase(repo),
      registerUseCase: RegisterUseCase(repo),
      verifyOtpUseCase: VerifyOtpUseCase(repo),
      resendOtpUseCase: ResendOtpUseCase(repo),
    );

Widget app(AuthBloc bloc, {Widget home = const LoginPage()}) =>
    BlocProvider<AuthBloc>.value(value: bloc, child: MaterialApp(home: home));

void main() {
  testWidgets('sign-in field takes an email (not a digits-only keypad) and the password is not strength-checked',
      (tester) async {
    final repo = FakeAuth();
    await tester.pumpWidget(app(blocFor(repo)));

    final idField = tester.widget<TextField>(find.byType(TextField).first);
    expect(idField.keyboardType, TextInputType.emailAddress);

    await tester.enterText(find.byType(TextFormField).at(0), 'ravi@example.com');
    await tester.enterText(find.byType(TextFormField).at(1), 'oldpass'); // no capital, no digit
    await tester.tap(find.text('Login'));
    await tester.pumpAndSettle();

    expect(repo.calls, ['login ravi@example.com oldpass']);
    expect(find.text('Invalid credentials'), findsOneWidget);
  });

  testWidgets('Login with OTP sends a login code and asks for it; six digits sign in', (tester) async {
    final repo = FakeAuth();
    final bloc = blocFor(repo);
    await tester.pumpWidget(app(bloc));

    await tester.enterText(find.byType(TextFormField).at(0), '98765 43210');
    await tester.tap(find.text('Login with OTP instead'));
    await tester.pumpAndSettle();

    expect(repo.calls, ['send 98765 43210 login']);
    expect(find.byType(OtpVerificationPage), findsOneWidget);
    expect(find.textContaining('You can resend in'), findsOneWidget);

    await tester.enterText(find.byType(TextField), '123456'); // e.g. filled in from the SMS
    await tester.pumpAndSettle();

    expect(repo.calls.last, 'verify 98765 43210 123456 login');
    expect(bloc.state, isA<Authenticated>());
  });

  testWidgets('Login with OTP needs the phone or email first', (tester) async {
    final repo = FakeAuth();
    await tester.pumpWidget(app(blocFor(repo)));

    await tester.tap(find.text('Login with OTP instead'));
    await tester.pump();

    expect(find.text('Enter your phone number or email'), findsOneWidget);
    expect(repo.calls, isEmpty);
  });

  testWidgets('a registration error is shown once, not again by the login screen underneath', (tester) async {
    final repo = FakeAuth()..registerError = 'User with phone +919876543210 already exists';
    await tester.pumpWidget(app(blocFor(repo)));

    await tester.tap(find.text('Register'));
    await tester.pumpAndSettle();
    await tester.enterText(find.byType(TextFormField).at(0), 'Priya Sharma');
    await tester.enterText(find.byType(TextFormField).at(1), '9876543210');
    await tester.enterText(find.byType(TextFormField).at(2), 'Passw0rd!');
    await tester.ensureVisible(find.byType(Checkbox));
    await tester.tap(find.byType(Checkbox));
    await tester.ensureVisible(find.text('Create account'));
    await tester.tap(find.text('Create account'));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));

    expect(find.text('User with phone +919876543210 already exists'), findsOneWidget);
    // Let the first snackbar finish: nothing queued behind it repeats the message.
    for (var i = 0; i < 4; i++) {
      await tester.pump(const Duration(seconds: 3));
    }
    await tester.pumpAndSettle();
    expect(find.text('User with phone +919876543210 already exists'), findsNothing);
  });

  testWidgets('registration asks for a valid Indian mobile number and shows the password rules up front',
      (tester) async {
    await tester.pumpWidget(app(blocFor(FakeAuth())));
    await tester.tap(find.text('Register'));
    await tester.pumpAndSettle();

    expect(find.text('+91'), findsOneWidget); // visible before the field is focused
    expect(find.text('At least 8 characters, with a capital letter and a number'), findsOneWidget);
    await tester.enterText(find.byType(TextFormField).at(1), '12345');
    await tester.ensureVisible(find.text('Create account'));
    await tester.tap(find.text('Create account'));
    await tester.pump();
    expect(find.text('Enter a valid 10-digit mobile number'), findsOneWidget);
  });

  testWidgets('forgot password accepts an email too', (tester) async {
    final repo = FakeAuth();
    await tester.pumpWidget(MaterialApp(home: ForgotPasswordPage(repository: repo)));

    await tester.enterText(find.byType(TextFormField).first, 'customer@example.com');
    await tester.tap(find.text('Send Code'));
    await tester.pumpAndSettle();

    expect(repo.calls, ['forgot customer@example.com']);
    expect(find.textContaining('Enter the code we sent to customer@example.com'), findsOneWidget);
  });
}
