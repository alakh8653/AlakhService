/// Application-wide scalar constants.
abstract class AppConstants {
  // App metadata
  static const String appName = 'AlakhService';
  static const String appTagline = 'Your trusted home services partner';
  static const String supportEmail = 'support@alakhservice.com';
  static const String supportPhone = '+1-800-ALAKH-SV';
  static const String privacyPolicyUrl = 'https://alakhservice.com/privacy';
  static const String termsUrl = 'https://alakhservice.com/terms';

  // Storage keys
  static const String authTokenKey = 'auth_token';
  static const String refreshTokenKey = 'refresh_token';
  static const String userIdKey = 'user_id';
  static const String onboardingCompletedKey = 'onboarding_completed';
  static const String themePreferenceKey = 'theme_preference';
  static const String languagePreferenceKey = 'language_preference';

  // Pagination
  static const int defaultPageSize = 20;
  static const int maxPageSize = 100;

  // Timeouts (milliseconds)
  static const int splashDurationMs = 2500;
  static const int snackBarDurationMs = 3000;

  // Animation durations
  static const int shortAnimationMs = 200;
  static const int mediumAnimationMs = 400;
  static const int longAnimationMs = 600;

  // Validation
  static const int minPasswordLength = 8;
  static const int maxPasswordLength = 64;
  static const int minNameLength = 2;
  static const int maxNameLength = 100;
  static const int otpLength = 6;

  // Payment
  static const String currency = 'USD';
  static const String currencySymbol = '\$';
}
