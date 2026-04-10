/// Central place for all API endpoint constants.
abstract class ApiConstants {
  // Base URLs are handled by AppConfig; these are path segments only.
  static const String apiVersion = '/api/v1';

  // Auth
  static const String login = '$apiVersion/auth/login';
  static const String register = '$apiVersion/auth/register';
  static const String logout = '$apiVersion/auth/logout';
  static const String refreshToken = '$apiVersion/auth/refresh';
  static const String forgotPassword = '$apiVersion/auth/forgot-password';
  static const String resetPassword = '$apiVersion/auth/reset-password';
  static const String verifyOtp = '$apiVersion/auth/verify-otp';

  // User / Profile
  static const String profile = '$apiVersion/users/me';
  static const String updateProfile = '$apiVersion/users/me';
  static const String changePassword = '$apiVersion/users/me/password';
  static const String uploadAvatar = '$apiVersion/users/me/avatar';

  // Services
  static const String services = '$apiVersion/services';
  static String serviceById(String id) => '$apiVersion/services/$id';
  static const String serviceCategories = '$apiVersion/services/categories';

  // Bookings
  static const String bookings = '$apiVersion/bookings';
  static String bookingById(String id) => '$apiVersion/bookings/$id';
  static String cancelBooking(String id) => '$apiVersion/bookings/$id/cancel';
  static String rescheduleBooking(String id) => '$apiVersion/bookings/$id/reschedule';

  // Payments
  static const String payments = '$apiVersion/payments';
  static String paymentById(String id) => '$apiVersion/payments/$id';
  static String initiatePayment(String bookingId) => '$apiVersion/payments/$bookingId/initiate';

  // Providers
  static const String providers = '$apiVersion/providers';
  static String providerById(String id) => '$apiVersion/providers/$id';

  // Reviews
  static const String reviews = '$apiVersion/reviews';
  static String reviewsByService(String serviceId) => '$apiVersion/services/$serviceId/reviews';
}
