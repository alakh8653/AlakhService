class ApiConstants {
  ApiConstants._();

  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://api.alakhservice.com',
  );

  static const String apiVersion = '/api/v1';

  // Auth endpoints
  static const String login = '$apiVersion/auth/login';
  static const String register = '$apiVersion/auth/register';
  static const String verifyOtp = '$apiVersion/auth/verify-otp';
  static const String refreshToken = '$apiVersion/auth/refresh';
  static const String logout = '$apiVersion/auth/logout';
  static const String forgotPassword = '$apiVersion/auth/forgot-password';

  // Service endpoints
  static const String services = '$apiVersion/services';
  static const String searchServices = '$apiVersion/services/search';

  // Booking endpoints
  static const String bookings = '$apiVersion/bookings';
  static const String cancelBooking = '$apiVersion/bookings/cancel';

  // User profile
  static const String profile = '$apiVersion/users/profile';
  static const String updateProfile = '$apiVersion/users/profile/update';

  // Payment
  static const String initiatePayment = '$apiVersion/payments/initiate';
  static const String paymentCallback = '$apiVersion/payments/callback';

  // Queue
  static const String queueStatus = '$apiVersion/queue/status';

  // Tracking
  static const String trackProvider = '$apiVersion/tracking/provider';

  // Notifications
  static const String notifications = '$apiVersion/notifications';
  static const String markRead = '$apiVersion/notifications/mark-read';

  // Timeouts
  static const int connectTimeout = 30000;
  static const int receiveTimeout = 30000;
}
