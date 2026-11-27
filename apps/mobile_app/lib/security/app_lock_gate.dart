import 'package:flutter/material.dart';
import 'package:flutter_bloc/flutter_bloc.dart';

import '../core/theme/app_text_styles.dart';
import '../core/theme/app_theme.dart';
import '../features/auth/presentation/bloc/auth_bloc.dart';
import '../features/auth/presentation/bloc/auth_event.dart';
import '../features/auth/presentation/bloc/auth_state.dart';
import '../l10n/l10n.dart';
import 'app_lock.dart';

/// Covers every screen (from MaterialApp.builder, so pushed screens and dialogs too) with the lock
/// screen while a signed-in customer's app is locked, and tells [lock] when the app leaves and comes
/// back. The screens below keep their state.
class AppLockGate extends StatefulWidget {
  final AppLockCubit lock;
  final Widget child;

  const AppLockGate({super.key, required this.lock, required this.child});

  @override
  State<AppLockGate> createState() => _AppLockGateState();
}

class _AppLockGateState extends State<AppLockGate> with WidgetsBindingObserver {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    switch (state) {
      case AppLifecycleState.paused:
      case AppLifecycleState.hidden:
        widget.lock.backgrounded();
      case AppLifecycleState.resumed:
        widget.lock.resumed();
      default:
        break;
    }
  }

  @override
  Widget build(BuildContext context) {
    return BlocListener<AuthBloc, AuthState>(
      // Signing in with a password or a code (not the session found at start-up) unlocks.
      listenWhen: (previous, current) => current is Authenticated && previous is! Authenticated && previous is! AuthInitial,
      listener: (_, __) => widget.lock.signedIn(),
      child: BlocBuilder<AuthBloc, AuthState>(
        buildWhen: (previous, current) => (previous is Authenticated) != (current is Authenticated),
        builder: (context, auth) => BlocBuilder<AppLockCubit, AppLockState>(
          bloc: widget.lock,
          builder: (context, lock) {
            final locked = auth is Authenticated && lock.locked;
            return Stack(
              children: [
                TickerMode(
                  enabled: !locked,
                  child: ExcludeSemantics(excluding: locked, child: widget.child),
                ),
                if (locked) Positioned.fill(child: LockScreen(lock: widget.lock)),
              ],
            );
          },
        ),
      ),
    );
  }
}

/// What a locked app shows: asks for the phone's fingerprint, face or PIN straight away, with a button
/// to ask again and a way out by signing out.
class LockScreen extends StatefulWidget {
  final AppLockCubit lock;

  const LockScreen({super.key, required this.lock});

  @override
  State<LockScreen> createState() => _LockScreenState();
}

class _LockScreenState extends State<LockScreen> {
  bool _asking = false;
  bool _failed = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _unlock();
    });
  }

  Future<void> _unlock() async {
    if (_asking) return;
    setState(() => _asking = true);
    final unlocked = await widget.lock.unlock(context.l10n.appLockReason);
    if (mounted) {
      setState(() {
        _asking = false;
        _failed = !unlocked;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l10n = context.l10n;
    return Material(
      color: context.colors.surface,
      child: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Icon(Icons.lock_outline, size: 56, color: context.colors.primary),
                const SizedBox(height: 16),
                Text(l10n.appLockTitle, style: AppTextStyles.heading3.themed(context), textAlign: TextAlign.center),
                const SizedBox(height: 8),
                Text(
                  _failed ? l10n.appLockFailed : l10n.appLockSubtitle,
                  style: AppTextStyles.body2.themed(context),
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 24),
                FilledButton.icon(
                  onPressed: _asking ? null : _unlock,
                  icon: const Icon(Icons.fingerprint),
                  label: Text(l10n.appLockUnlock),
                ),
                const SizedBox(height: 8),
                TextButton(
                  onPressed: _asking ? null : () => context.read<AuthBloc>().add(const LogoutRequested()),
                  child: Text(l10n.appLockSignOut),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
