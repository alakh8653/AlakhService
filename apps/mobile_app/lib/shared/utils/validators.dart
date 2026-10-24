import '../../l10n/l10n.dart';

/// Form validation helpers used across the app, with messages in the language on screen.
class Validators {
  Validators._();

  static String? phone(String? value) {
    if (value == null || value.trim().isEmpty) return currentL10n.vPhoneRequired;
    final stripped = value.replaceAll(RegExp(r'[\s\-\+\(\)]'), '');
    if (!RegExp(r'^\d{10,15}$').hasMatch(stripped)) {
      return currentL10n.vPhoneInvalid;
    }
    return null;
  }

  /// A 10-digit Indian mobile number typed after a fixed "+91" (starts with 6, 7, 8 or 9).
  static String? indianMobile(String? value) {
    final digits = (value ?? '').replaceAll(RegExp(r'\D'), '');
    if (digits.isEmpty) return currentL10n.vMobileRequired;
    if (!RegExp(r'^[6-9]\d{9}$').hasMatch(digits)) return currentL10n.vMobileInvalid;
    return null;
  }

  /// Sign-in accepts the account's phone number or its email.
  static String? phoneOrEmail(String? value) {
    if (value == null || value.trim().isEmpty) return currentL10n.vPhoneOrEmailRequired;
    if (value.contains('@')) return email(value);
    if (RegExp(r'[A-Za-z]').hasMatch(value)) return currentL10n.vPhoneOrEmailInvalid;
    return phone(value);
  }

  /// Signing in only needs a password: the strength rules apply when one is chosen, and an
  /// account made under older rules must still be able to sign in.
  static String? loginPassword(String? value) =>
      (value == null || value.isEmpty) ? currentL10n.vPasswordRequired : null;

  /// The rules [password] checks, to show before the customer types.
  static String get passwordRules => currentL10n.vPasswordRules;

  static String? email(String? value) {
    if (value == null || value.trim().isEmpty) return currentL10n.vEmailRequired;
    if (!RegExp(r'^[\w\.\+\-]+@[\w\-]+\.\w{2,}$').hasMatch(value.trim())) {
      return currentL10n.vEmailInvalid;
    }
    return null;
  }

  static String? password(String? value) {
    if (value == null || value.isEmpty) return currentL10n.vPasswordRequired;
    if (value.length < 8) return currentL10n.vPasswordShort;
    if (!RegExp(r'[A-Z]').hasMatch(value)) {
      return currentL10n.vPasswordUpper;
    }
    if (!RegExp(r'[0-9]').hasMatch(value)) {
      return currentL10n.vPasswordNumber;
    }
    return null;
  }

  static String? otp(String? value) {
    if (value == null || value.isEmpty) return currentL10n.vOtpRequired;
    if (!RegExp(r'^\d{6}$').hasMatch(value)) return currentL10n.vOtpInvalid;
    return null;
  }

  static String? name(String? value) {
    if (value == null || value.trim().isEmpty) return currentL10n.vNameRequired;
    if (value.trim().length < 2) return currentL10n.vNameShort;
    return null;
  }

  static String? required(String? value) {
    if (value == null || value.trim().isEmpty) return currentL10n.vFieldRequired;
    return null;
  }

  static String? Function(String?) minLength(int min, String fieldName) {
    return (String? value) {
      if (value == null || value.isEmpty) return currentL10n.vFieldRequiredNamed(fieldName);
      if (value.length < min) return currentL10n.vFieldMinLength(fieldName, min.toString());
      return null;
    };
  }

  static String? confirmPassword(String? value, String original) {
    if (value == null || value.isEmpty) return currentL10n.vConfirmPassword;
    if (value != original) return currentL10n.vPasswordsDontMatch;
    return null;
  }
}
