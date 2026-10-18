import 'package:flutter_bloc/flutter_bloc.dart';
import '../../domain/usecases/login_usecase.dart';
import '../../domain/usecases/register_usecase.dart';
import '../../domain/usecases/session_usecases.dart';
import '../../domain/usecases/verify_otp_usecase.dart';
import 'auth_event.dart';
import 'auth_state.dart';

class AuthBloc extends Bloc<AuthEvent, AuthState> {
  final LoginUseCase loginUseCase;
  final RegisterUseCase registerUseCase;
  final VerifyOtpUseCase verifyOtpUseCase;
  final GetCurrentUserUseCase? getCurrentUserUseCase;
  final LogoutUseCase? logoutUseCase;
  final ResendOtpUseCase? resendOtpUseCase;

  AuthBloc({
    required this.loginUseCase,
    required this.registerUseCase,
    required this.verifyOtpUseCase,
    this.getCurrentUserUseCase,
    this.logoutUseCase,
    this.resendOtpUseCase,
  }) : super(const AuthInitial()) {
    on<CheckAuthStatus>(_onCheckAuthStatus);
    on<LoginRequested>(_onLoginRequested);
    on<RegisterRequested>(_onRegisterRequested);
    on<OtpVerificationRequested>(_onOtpVerificationRequested);
    on<OtpLoginRequested>(_onOtpLoginRequested);
    on<ResendOtpRequested>(_onResendOtpRequested);
    on<LogoutRequested>(_onLogoutRequested);
    on<SessionExpired>((event, emit) => emit(const Unauthenticated()));
  }

  /// On start-up: resume a stored session if it is still valid.
  Future<void> _onCheckAuthStatus(CheckAuthStatus event, Emitter<AuthState> emit) async {
    final check = getCurrentUserUseCase;
    if (check == null) return emit(const Unauthenticated());
    final result = await check();
    result.fold(
      (_) => emit(const Unauthenticated()),
      (user) => emit(user == null ? const Unauthenticated() : Authenticated(user: user)),
    );
  }

  Future<void> _onLoginRequested(
    LoginRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(const AuthLoading());
    final result = await loginUseCase(
      LoginParams(phone: event.phone, password: event.password),
    );
    result.fold(
      (failure) => emit(AuthError(message: failure.message)),
      (user) => emit(Authenticated(user: user)),
    );
  }

  Future<void> _onRegisterRequested(
    RegisterRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(const AuthLoading());
    final result = await registerUseCase(
      RegisterParams(
        name: event.name,
        phone: event.phone,
        password: event.password,
        role: event.role,
      ),
    );
    result.fold(
      (failure) => emit(AuthError(message: failure.message)),
      (_) => emit(OtpRequired(phone: event.phone)),
    );
  }

  Future<void> _onOtpVerificationRequested(
    OtpVerificationRequested event,
    Emitter<AuthState> emit,
  ) async {
    emit(const AuthLoading());
    final result = await verifyOtpUseCase(
      VerifyOtpParams(phone: event.phone, otp: event.otp, purpose: event.purpose),
    );
    result.fold(
      (failure) => emit(AuthError(message: failure.message)),
      (user) => emit(Authenticated(user: user)),
    );
  }

  /// Sends a sign-in code; the login screen then asks for it.
  Future<void> _onOtpLoginRequested(OtpLoginRequested event, Emitter<AuthState> emit) async {
    final send = resendOtpUseCase;
    if (send == null) return emit(const AuthError(message: 'Signing in with a code is not available right now.'));
    emit(const AuthLoading());
    final result = await send(event.identifier, purpose: 'login');
    result.fold(
      (failure) => emit(AuthError(message: failure.message)),
      (_) => emit(OtpRequired(phone: event.identifier, purpose: 'login')),
    );
  }

  Future<void> _onResendOtpRequested(ResendOtpRequested event, Emitter<AuthState> emit) async {
    final resend = resendOtpUseCase;
    if (resend == null) return;
    final result = await resend(event.phone, purpose: event.purpose);
    result.fold(
      (failure) => emit(AuthError(message: failure.message)),
      (_) => emit(OtpResent(phone: event.phone)),
    );
  }

  Future<void> _onLogoutRequested(
    LogoutRequested event,
    Emitter<AuthState> emit,
  ) async {
    await logoutUseCase?.call();
    emit(const Unauthenticated());
  }
}
