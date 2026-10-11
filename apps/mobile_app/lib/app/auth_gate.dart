import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/theme/app_colors.dart';
import '../features/auth/presentation/bloc/auth_bloc.dart';
import '../features/auth/presentation/bloc/auth_state.dart';
import '../features/auth/presentation/pages/login_page.dart';
import 'home_shell.dart';

/// Shows the app to a signed-in user and the sign-in screen otherwise.
///
/// Signing in or out also clears any screens pushed on top (registration, a booking, …), so the
/// user lands on the right root.
class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  bool _sessionChanged(AuthState previous, AuthState current) =>
      (current is Authenticated) != (previous is Authenticated) &&
      (current is Authenticated || current is Unauthenticated);

  @override
  Widget build(BuildContext context) {
    return BlocConsumer<AuthBloc, AuthState>(
      listenWhen: _sessionChanged,
      listener: (context, state) => Navigator.of(context).popUntil((route) => route.isFirst),
      buildWhen: (previous, current) =>
          previous is AuthInitial || current is AuthInitial || _sessionChanged(previous, current),
      builder: (context, state) {
        if (state is AuthInitial) {
          return const Scaffold(
            body: Center(child: CircularProgressIndicator(color: AppColors.primary)),
          );
        }
        if (state is Authenticated) return HomeShell(user: state.user);
        return const LoginPage();
      },
    );
  }
}
