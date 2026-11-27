import 'package:alakh_service/app/app_view.dart';
import 'package:alakh_service/core/errors/failures.dart';
import 'package:alakh_service/core/settings/app_settings.dart';
import 'package:alakh_service/features/auth/domain/entities/user.dart';
import 'package:alakh_service/features/auth/domain/repositories/auth_repository.dart';
import 'package:alakh_service/features/auth/domain/usecases/login_usecase.dart';
import 'package:alakh_service/features/auth/domain/usecases/register_usecase.dart';
import 'package:alakh_service/features/auth/domain/usecases/session_usecases.dart';
import 'package:alakh_service/features/auth/domain/usecases/verify_otp_usecase.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_bloc.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_event.dart';
import 'package:alakh_service/features/auth/presentation/bloc/auth_state.dart';
import 'package:alakh_service/features/profile/presentation/pages/app_lock_setting.dart';
import 'package:alakh_service/security/app_lock.dart';
import 'package:alakh_service/security/biometric_auth.dart';
import 'package:dartz/dartz.dart';
import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// The phone's fingerprint/PIN prompt: [answers] are what the owner does, one per prompt.
class FakePhone implements DeviceAuthenticator {
  bool hasLock;
  final List<bool> answers;
  final reasons = <String>[];

  FakePhone({this.hasLock = true, List<bool>? answers}) : answers = answers ?? [];

  @override
  Future<bool> canAuthenticate() async => hasLock;

  @override
  Future<bool> authenticate(String reason) async {
    reasons.add(reason);
    return answers.isEmpty ? false : answers.removeAt(0);
  }
}

final _user = User(id: 'u1', name: 'Priya', phone: '+919876543210', role: 'customer', isVerified: true, createdAt: DateTime(2026));

/// A signed-in session at start-up; password sign-in always works.
class SignedIn implements AuthRepository {
  bool signedOut = false;

  @override
  Future<Either<Failure, User?>> getCurrentUser() async => Right(signedOut ? null : _user);

  @override
  Future<Either<Failure, User>> login({required String phone, required String password}) async => Right(_user);

  @override
  Future<Either<Failure, bool>> logout() async {
    signedOut = true;
    return const Right(true);
  }

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

AuthBloc authFor(SignedIn repo) => AuthBloc(
      loginUseCase: LoginUseCase(repo),
      registerUseCase: RegisterUseCase(repo),
      verifyOtpUseCase: VerifyOtpUseCase(repo),
      getCurrentUserUseCase: GetCurrentUserUseCase(repo),
      logoutUseCase: LogoutUseCase(repo),
    );

void main() {
  late SharedPreferences prefs;
  var clock = DateTime(2026, 11, 27, 9);

  Future<AppLockCubit> lockWith(FakePhone phone, {bool enabled = false}) async {
    SharedPreferences.setMockInitialValues({if (enabled) AppLockCubit.storageKey: true});
    prefs = await SharedPreferences.getInstance();
    clock = DateTime(2026, 11, 27, 9);
    return AppLockCubit(prefs, phone, now: () => clock);
  }

  group('AppLockCubit', () {
    test('is off and unlocked until turned on', () async {
      final lock = await lockWith(FakePhone());
      expect(lock.state, const AppLockState());
    });

    test('turning it on needs the owner on the phone prompt, and is kept', () async {
      final phone = FakePhone(answers: [false, true]);
      final lock = await lockWith(phone);

      expect(await lock.enable('Unlock AlakhService'), isFalse);
      expect(lock.state.enabled, isFalse);
      expect(await lock.enable('Unlock AlakhService'), isTrue);
      expect(lock.state.enabled, isTrue);
      expect(lock.state.locked, isFalse);
      expect(prefs.getBool(AppLockCubit.storageKey), isTrue);
      expect(phone.reasons, ['Unlock AlakhService', 'Unlock AlakhService']);
    });

    test('a phone without a screen lock cannot turn it on', () async {
      final lock = await lockWith(FakePhone(hasLock: false));
      await lock.checkAvailable();
      expect(lock.state.available, isFalse);
      expect(await lock.enable('r'), isFalse);
    });

    test('starts locked when on, and stays locked until the owner confirms', () async {
      final lock = await lockWith(FakePhone(answers: [false, true]), enabled: true);
      expect(lock.state.locked, isTrue);

      expect(await lock.unlock('r'), isFalse);
      expect(lock.state.locked, isTrue);
      expect(await lock.unlock('r'), isTrue);
      expect(lock.state.locked, isFalse);
    });

    test('locks again after a minute in the background, not after a few seconds', () async {
      final lock = await lockWith(FakePhone(answers: [true]), enabled: true);
      await lock.unlock('r');

      lock.backgrounded();
      clock = clock.add(const Duration(seconds: 20));
      lock.resumed();
      expect(lock.state.locked, isFalse);

      lock.backgrounded();
      clock = clock.add(const Duration(minutes: 2));
      lock.resumed();
      expect(lock.state.locked, isTrue);
    });

    test('the phone prompt itself sending the app to the background does not lock it again', () async {
      late AppLockCubit lock;
      final phone = _PromptThatLeaves(() {
        lock.backgrounded();
        clock = clock.add(const Duration(minutes: 5));
        lock.resumed();
      });
      lock = await lockWith(FakePhone(), enabled: true);
      lock = AppLockCubit(prefs, phone, now: () => clock);

      expect(await lock.unlock('r'), isTrue);
      lock.resumed();
      expect(lock.state.locked, isFalse);
    });

    test('a fresh sign-in unlocks', () async {
      final lock = await lockWith(FakePhone(), enabled: true);
      lock.signedIn();
      expect(lock.state.locked, isFalse);
      expect(lock.state.enabled, isTrue);
    });

    test('if the phone lost its screen lock, unlocking turns app lock off', () async {
      final phone = FakePhone(hasLock: false);
      final lock = await lockWith(phone, enabled: true);
      expect(await lock.unlock('r'), isTrue);
      expect(lock.state, const AppLockState(enabled: false, locked: false));
      expect(phone.reasons, isEmpty);
    });
  });

  group('lock screen', () {
    Widget app(AuthBloc auth, AppLockCubit lock, {Widget? home}) => MultiBlocProvider(
          providers: [
            BlocProvider<AuthBloc>.value(value: auth),
            BlocProvider<SettingsCubit>.value(value: SettingsCubit(prefs)),
          ],
          child: AppView(
            appLock: lock,
            home: home ??
                Builder(
                  builder: (context) => Scaffold(
                    body: Center(
                      child: TextButton(
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute<void>(builder: (_) => const Scaffold(body: Text('Booking #1042'))),
                        ),
                        child: const Text('Open booking'),
                      ),
                    ),
                  ),
                ),
          ),
        );

    testWidgets('covers every screen, a pushed one too, until unlocked', (tester) async {
      final phone = FakePhone(answers: [true, false, true]);
      final lock = await lockWith(phone, enabled: true);
      await lock.unlock('r');
      final auth = authFor(SignedIn())..add(const CheckAuthStatus());
      await tester.pumpWidget(app(auth, lock));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Open booking'));
      await tester.pumpAndSettle();
      expect(find.text('Booking #1042'), findsOneWidget);

      // Away for five minutes.
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
      clock = clock.add(const Duration(minutes: 5));
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pumpAndSettle();

      // The prompt came up by itself and the owner cancelled it.
      expect(find.text('AlakhService is locked'), findsOneWidget);
      expect(find.textContaining("That didn't work"), findsOneWidget);
      expect(find.text('Booking #1042', skipOffstage: false), findsOneWidget); // kept underneath

      await tester.tap(find.text('Unlock'));
      await tester.pumpAndSettle();
      expect(find.text('AlakhService is locked'), findsNothing);
      expect(find.text('Booking #1042'), findsOneWidget);
      expect(phone.reasons.last, 'Unlock AlakhService');
    });

    testWidgets('signing out from the lock screen leaves it', (tester) async {
      final lock = await lockWith(FakePhone(), enabled: true);
      final repo = SignedIn();
      final auth = authFor(repo)..add(const CheckAuthStatus());
      await tester.pumpWidget(app(auth, lock));
      await tester.pumpAndSettle();
      expect(find.text('AlakhService is locked'), findsOneWidget);

      await tester.tap(find.text('Sign out'));
      await tester.pumpAndSettle();

      expect(repo.signedOut, isTrue);
      expect(auth.state, isA<Unauthenticated>());
      expect(find.text('AlakhService is locked'), findsNothing);
    });

    testWidgets('no lock before signing in, and signing in with a password does not ask again', (tester) async {
      final phone = FakePhone();
      final lock = await lockWith(phone, enabled: true);
      final repo = SignedIn()..signedOut = true;
      final auth = authFor(repo)..add(const CheckAuthStatus());
      await tester.pumpWidget(app(auth, lock));
      await tester.pumpAndSettle();
      expect(find.text('AlakhService is locked'), findsNothing);

      auth.add(const LoginRequested(phone: 'priya@example.com', password: 'pw'));
      await tester.pumpAndSettle();

      expect(auth.state, isA<Authenticated>());
      expect(find.text('AlakhService is locked'), findsNothing);
      expect(phone.reasons, isEmpty);
    });

    testWidgets('Profile offers the switch only on a phone that can check, and turns it on', (tester) async {
      final phone = FakePhone(answers: [true]);
      final lock = await lockWith(phone);
      await tester.pumpWidget(app(authFor(SignedIn()), lock, home: Scaffold(body: AppLockSetting(lock: lock))));
      await tester.pumpAndSettle();

      await tester.tap(find.text('App lock'));
      await tester.pumpAndSettle();
      expect(lock.state.enabled, isTrue);
      expect(tester.widget<SwitchListTile>(find.byType(SwitchListTile)).value, isTrue);

      final noLock = await lockWith(FakePhone(hasLock: false));
      await tester.pumpWidget(app(authFor(SignedIn()), noLock, home: Scaffold(body: AppLockSetting(key: const ValueKey('no-lock'), lock: noLock))));
      await tester.pumpAndSettle();
      expect(find.text('App lock'), findsNothing);
    });
  });
}

/// A prompt during which the app goes to the background and comes back, as on Android.
class _PromptThatLeaves implements DeviceAuthenticator {
  final void Function() duringPrompt;

  _PromptThatLeaves(this.duringPrompt);

  @override
  Future<bool> canAuthenticate() async => true;

  @override
  Future<bool> authenticate(String reason) async {
    duringPrompt();
    return true;
  }
}
