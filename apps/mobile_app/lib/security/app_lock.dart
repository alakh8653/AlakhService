import 'package:equatable/equatable.dart';
import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'biometric_auth.dart';

/// App lock: whether the customer turned it on, and whether the app is locked right now.
class AppLockState extends Equatable {
  final bool enabled;
  final bool locked;

  /// Whether this phone can check its owner (fingerprint, face or a screen lock); null until asked.
  final bool? available;

  const AppLockState({this.enabled = false, this.locked = false, this.available});

  AppLockState copyWith({bool? enabled, bool? locked, bool? available}) => AppLockState(
        enabled: enabled ?? this.enabled,
        locked: locked ?? this.locked,
        available: available ?? this.available,
      );

  @override
  List<Object?> get props => [enabled, locked, available];
}

/// Locks the app behind the phone's fingerprint, face or PIN when it starts and when it comes back
/// after [relockAfter] in the background. The choice is kept in shared_preferences; signing in with a
/// password or code also unlocks, since that already proved who it is.
class AppLockCubit extends Cubit<AppLockState> {
  static const String storageKey = 'app_lock_enabled';

  final SharedPreferences _prefs;
  final DeviceAuthenticator _auth;
  final Duration relockAfter;
  final DateTime Function() _now;

  DateTime? _leftAt;
  // The phone's own prompt sends the app to the background and back; that must not lock it again.
  bool _prompting = false;

  AppLockCubit(
    this._prefs,
    this._auth, {
    this.relockAfter = const Duration(minutes: 1),
    DateTime Function()? now,
  })  : _now = now ?? DateTime.now,
        super(_initial(_prefs));

  static AppLockState _initial(SharedPreferences prefs) {
    final enabled = prefs.getBool(storageKey) ?? false;
    return AppLockState(enabled: enabled, locked: enabled);
  }

  /// Asks the phone whether app lock can be offered.
  Future<void> checkAvailable() async => emit(state.copyWith(available: await _auth.canAuthenticate()));

  /// Turns app lock on once the owner confirms on the phone's prompt. False if they could not.
  Future<bool> enable(String reason) async {
    if (!await _auth.canAuthenticate()) {
      emit(state.copyWith(available: false));
      return false;
    }
    if (!await _prompt(reason)) return false;
    await _prefs.setBool(storageKey, true);
    emit(state.copyWith(enabled: true, locked: false, available: true));
    return true;
  }

  Future<void> disable() async {
    await _prefs.setBool(storageKey, false);
    emit(state.copyWith(enabled: false, locked: false));
  }

  /// Unlocks after the phone's prompt. True once unlocked.
  Future<bool> unlock(String reason) async {
    if (!state.locked) return true;
    if (!await _auth.canAuthenticate()) {
      // The screen lock was removed from the phone (which takes its PIN): nothing left to check with.
      await disable();
      return true;
    }
    if (!await _prompt(reason)) return false;
    emit(state.copyWith(locked: false));
    return true;
  }

  /// A fresh sign-in (password or code) proved who it is.
  void signedIn() {
    if (state.locked) emit(state.copyWith(locked: false));
  }

  /// The app went to the background.
  void backgrounded() {
    if (!_prompting) _leftAt ??= _now();
  }

  /// The app came back to the foreground: locked again if it was away long enough.
  void resumed() {
    final leftAt = _leftAt;
    _leftAt = null;
    if (_prompting || leftAt == null || !state.enabled || state.locked) return;
    if (_now().difference(leftAt) >= relockAfter) emit(state.copyWith(locked: true));
  }

  Future<bool> _prompt(String reason) async {
    _prompting = true;
    try {
      return await _auth.authenticate(reason);
    } finally {
      _prompting = false;
      _leftAt = null;
    }
  }
}
