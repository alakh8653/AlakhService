/// Form validation helpers used across the app.
class Validators {
  Validators._();

  static String? phone(String? value) {
    if (value == null || value.trim().isEmpty) return 'Phone number is required';
    final stripped = value.replaceAll(RegExp(r'[\s\-\+\(\)]'), '');
    if (!RegExp(r'^\d{10,15}$').hasMatch(stripped)) {
      return 'Enter a valid phone number';
    }
    return null;
  }

  /// A 10-digit Indian mobile number typed after a fixed "+91" (starts with 6, 7, 8 or 9).
  static String? indianMobile(String? value) {
    final digits = (value ?? '').replaceAll(RegExp(r'\D'), '');
    if (digits.isEmpty) return 'Mobile number is required';
    if (!RegExp(r'^[6-9]\d{9}$').hasMatch(digits)) return 'Enter a valid 10-digit mobile number';
    return null;
  }

  /// Sign-in accepts the account's phone number or its email.
  static String? phoneOrEmail(String? value) {
    if (value == null || value.trim().isEmpty) return 'Enter your phone number or email';
    if (value.contains('@')) return email(value);
    if (RegExp(r'[A-Za-z]').hasMatch(value)) return 'Enter a valid phone number or email';
    return phone(value);
  }

  /// Signing in only needs a password: the strength rules apply when one is chosen, and an
  /// account made under older rules must still be able to sign in.
  static String? loginPassword(String? value) =>
      (value == null || value.isEmpty) ? 'Password is required' : null;

  /// The rules [password] checks, to show before the customer types.
  static const passwordRules = 'At least 8 characters, with a capital letter and a number';

  static String? email(String? value) {
    if (value == null || value.trim().isEmpty) return 'Email is required';
    if (!RegExp(r'^[\w\.\+\-]+@[\w\-]+\.\w{2,}$').hasMatch(value.trim())) {
      return 'Enter a valid email address';
    }
    return null;
  }

  static String? password(String? value) {
    if (value == null || value.isEmpty) return 'Password is required';
    if (value.length < 8) return 'Password must be at least 8 characters';
    if (!RegExp(r'[A-Z]').hasMatch(value)) {
      return 'Include at least one uppercase letter';
    }
    if (!RegExp(r'[0-9]').hasMatch(value)) {
      return 'Include at least one number';
    }
    return null;
  }

  static String? otp(String? value) {
    if (value == null || value.isEmpty) return 'OTP is required';
    if (!RegExp(r'^\d{6}$').hasMatch(value)) return 'Enter a valid 6-digit OTP';
    return null;
  }

  static String? name(String? value) {
    if (value == null || value.trim().isEmpty) return 'Name is required';
    if (value.trim().length < 2) return 'Name must be at least 2 characters';
    return null;
  }

  static String? required(String? value) {
    if (value == null || value.trim().isEmpty) return 'This field is required';
    return null;
  }

  static String? Function(String?) minLength(int min, String fieldName) {
    return (String? value) {
      if (value == null || value.isEmpty) return '$fieldName is required';
      if (value.length < min) return '$fieldName must be at least $min characters';
      return null;
    };
  }

  static String? confirmPassword(String? value, String original) {
    if (value == null || value.isEmpty) return 'Please confirm your password';
    if (value != original) return 'Passwords do not match';
    return null;
  }
}
