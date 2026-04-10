class AppConstants {
  AppConstants._();

  static const String appName = 'AlakhService';
  static const String appTagline = 'Your Service, On Demand';

  // SharedPreferences keys
  static const String keyAccessToken = 'access_token';
  static const String keyRefreshToken = 'refresh_token';
  static const String keyUserId = 'user_id';
  static const String keyUserRole = 'user_role';
  static const String keyIsLoggedIn = 'is_logged_in';
  static const String keyOnboardingDone = 'onboarding_done';
  static const String keyThemeMode = 'theme_mode';

  // User roles
  static const String roleUser = 'user';
  static const String roleProvider = 'provider';
  static const String roleAdmin = 'admin';

  // Pagination
  static const int defaultPageSize = 20;
  static const int maxPageSize = 100;

  // OTP
  static const int otpLength = 6;
  static const int otpExpirySeconds = 300;

  // Map
  static const double defaultLatitude = 28.6139;
  static const double defaultLongitude = 77.2090;
  static const double defaultMapZoom = 14.0;

  // Animation durations
  static const Duration shortAnimation = Duration(milliseconds: 200);
  static const Duration mediumAnimation = Duration(milliseconds: 400);
  static const Duration longAnimation = Duration(milliseconds: 600);
}
