/// Endpoints of the AlakhService API gateway (services/api_gateway/src/routes.ts).
class ApiConstants {
  ApiConstants._();

  /// Gateway origin. Point a dev build at a local stack with
  /// `--dart-define=API_BASE_URL=http://10.0.2.2:3000` (Android emulator) or `http://localhost:3000`.
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'https://api.alakhservice.com',
  );

  static const String apiVersion = '/api/v1';

  // Auth (auth_service)
  static const String login = '$apiVersion/auth/login';
  static const String register = '$apiVersion/auth/register';
  static const String sendOtp = '$apiVersion/auth/send-otp';
  static const String verifyOtp = '$apiVersion/auth/verify-otp';
  static const String refreshToken = '$apiVersion/auth/refresh';
  static const String logout = '$apiVersion/auth/logout';
  static const String me = '$apiVersion/auth/me';
  static const String resetPassword = '$apiVersion/auth/reset-password';
  static const String deleteAccount = '$apiVersion/auth/delete-account';

  // Catalogue (service_catalog_service)
  static const String services = '$apiVersion/services';
  static const String searchServices = '$apiVersion/services/search';

  // Bookings (booking_service)
  static const String bookings = '$apiVersion/bookings';
  static String booking(String id) => '$bookings/$id';
  static String cancelBooking(String id) => '$bookings/$id/cancel';
  static String bookingStatus(String id) => '$bookings/$id/status';
  static const String assignedBookings = '$bookings/assigned';
  static const String disputes = '$apiVersion/disputes';
  static String validateCoupon(String code) => '$apiVersion/coupons/${Uri.encodeComponent(code)}/validate';

  // Shops (shop_service)
  static String shop(String shopId) => '$apiVersion/shops/$shopId';
  static String rateShop(String shopId) => '$apiVersion/shops/$shopId/rating';

  // Profile (user_service)
  static const String profile = '$apiVersion/users/me/profile';
  static const String addresses = '$apiVersion/users/me/addresses';
  static String address(String id) => '$addresses/$id';
  static String defaultAddress(String id) => '$addresses/$id/default';

  // Payments (payment_service)
  static const String initiatePayment = '$apiVersion/payments/initiate';
  static const String payments = '$apiVersion/payments';
  static String verifyPayment(String paymentId) => '$apiVersion/payments/$paymentId/verify';

  // Queues (queue_service)
  static const String queues = '$apiVersion/queues';
  static String joinQueue(String queueId) => '$queues/$queueId/join';
  static String queuePosition(String queueId, String customerId) => '$queues/$queueId/position/$customerId';
  static String leaveQueue(String queueId, String entryId) => '$queues/$queueId/entries/$entryId';

  // Tracking (tracking_service)
  static const String locations = '$apiVersion/locations';
  static String providerLocation(String providerId) => '$locations/$providerId';

  // Notifications (notification_service)
  static const String notifications = '$apiVersion/notifications/me';
  static const String unreadCount = '$apiVersion/notifications/count/unread';
  static const String markAllRead = '$apiVersion/notifications/read-all';
  static String markRead(String id) => '$apiVersion/notifications/$id/read';

  // Timeouts
  static const int connectTimeout = 30000;
  static const int receiveTimeout = 30000;
}
