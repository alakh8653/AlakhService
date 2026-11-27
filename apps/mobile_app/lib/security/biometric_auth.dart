import 'package:flutter/services.dart';
import 'package:local_auth/local_auth.dart';

/// Checks that the person holding the phone is its owner: fingerprint, face, or the phone's own PIN,
/// pattern or password. Replaceable in tests.
abstract class DeviceAuthenticator {
  /// Whether the phone has a way to check (biometrics or a screen lock is set up).
  Future<bool> canAuthenticate();

  /// Shows the phone's prompt with [reason]; true once the owner is confirmed, false if they cancel or
  /// the phone cannot check.
  Future<bool> authenticate(String reason);
}

/// [DeviceAuthenticator] over local_auth: the system biometric prompt, falling back to the screen lock.
class BiometricAuthService implements DeviceAuthenticator {
  final LocalAuthentication _localAuth;

  BiometricAuthService([LocalAuthentication? localAuth]) : _localAuth = localAuth ?? LocalAuthentication();

  @override
  Future<bool> canAuthenticate() async {
    try {
      return await _localAuth.isDeviceSupported();
    } on PlatformException {
      return false;
    } on MissingPluginException {
      return false;
    }
  }

  /// Whether a fingerprint or face is enrolled (not just a screen lock).
  Future<bool> hasBiometrics() async {
    try {
      return await _localAuth.canCheckBiometrics && (await _localAuth.getAvailableBiometrics()).isNotEmpty;
    } on PlatformException {
      return false;
    }
  }

  @override
  Future<bool> authenticate(String reason) async {
    try {
      // Not biometricOnly: someone whose finger is not read can still use the phone's PIN.
      return await _localAuth.authenticate(localizedReason: reason, persistAcrossBackgrounding: true);
    } on LocalAuthException {
      // Cancelled, nothing to check with, or locked out after too many tries: not confirmed.
      return false;
    } on PlatformException {
      return false;
    }
  }

  /// Cancels an in-progress authentication attempt.
  Future<void> cancelAuthentication() => _localAuth.stopAuthentication();
}
