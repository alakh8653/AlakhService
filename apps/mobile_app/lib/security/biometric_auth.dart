import 'package:local_auth/local_auth.dart';
import 'package:local_auth/error_codes.dart' as auth_error;
import 'package:flutter/services.dart';

/// Wraps [LocalAuthentication] for fingerprint / Face ID authentication.
class BiometricAuthService {
  final LocalAuthentication _localAuth = LocalAuthentication();

  /// Returns `true` if the device supports biometric authentication and has
  /// at least one enrolled biometric.
  Future<bool> isAvailable() async {
    try {
      final canCheck = await _localAuth.canCheckBiometrics;
      if (!canCheck) return false;
      final biometrics = await _localAuth.getAvailableBiometrics();
      return biometrics.isNotEmpty;
    } on PlatformException {
      return false;
    }
  }

  /// Lists available biometric types on the device.
  Future<List<BiometricType>> getAvailableBiometrics() async {
    try {
      return await _localAuth.getAvailableBiometrics();
    } on PlatformException {
      return [];
    }
  }

  /// Prompts the user for biometric authentication.
  ///
  /// Returns `true` on success, `false` if cancelled or failed.
  Future<bool> authenticate({
    String localizedReason = 'Authenticate to continue',
  }) async {
    try {
      return await _localAuth.authenticate(
        localizedReason: localizedReason,
        options: const AuthenticationOptions(
          biometricOnly: false,
          stickyAuth: true,
        ),
      );
    } on PlatformException catch (e) {
      if (e.code == auth_error.notAvailable ||
          e.code == auth_error.notEnrolled) {
        return false;
      }
      rethrow;
    }
  }

  /// Cancels an in-progress authentication attempt.
  Future<void> cancelAuthentication() => _localAuth.stopAuthentication();
}
