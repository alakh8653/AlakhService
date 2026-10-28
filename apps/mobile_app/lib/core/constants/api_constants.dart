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
  static String rescheduleBooking(String id) => '$bookings/$id/reschedule';
  static String bookingStatus(String id) => '$bookings/$id/status';
  // A booking's chat with the shop, and the masked call (booking_service).
  static String bookingMessages(String id) => '$bookings/$id/messages';
  static String bookingMessagesRead(String id) => '$bookings/$id/messages/read';
  static String bookingCall(String id) => '$bookings/$id/call';
  static const String assignedBookings = '$bookings/assigned';
  static const String disputes = '$apiVersion/disputes';
  /// Bookable times of a service on a day (?service_id=&date=YYYY-MM-DD); public.
  static const String availability = '$apiVersion/availability';
  static String validateCoupon(String code) => '$apiVersion/coupons/${Uri.encodeComponent(code)}/validate';

  // Shops (shop_service)
  static String shop(String shopId) => '$apiVersion/shops/$shopId';
  static String rateShop(String shopId) => '$apiVersion/shops/$shopId/rating';
  // Shops the customer has saved (shop_service).
  static const String favoriteShops = '$apiVersion/shops/favorites';
  static String favoriteShop(String shopId) => '$apiVersion/shops/${Uri.encodeComponent(shopId)}/favorite';
  // Reviews (public): ratings for several shops at once, and one shop's summary and reviews.
  static const String shopRatings = '$apiVersion/shops/ratings';
  static String shopReviews(String shopId) => '$apiVersion/shops/${Uri.encodeComponent(shopId)}/reviews';
  static String reviewSummary(String shopId) => '${shopReviews(shopId)}/summary';
  static String shopHours(String shopId) => '$apiVersion/shops/${Uri.encodeComponent(shopId)}/hours';

  // Profile (user_service)
  static const String profile = '$apiVersion/users/me/profile';
  static const String addresses = '$apiVersion/users/me/addresses';
  static String address(String id) => '$addresses/$id';
  static String defaultAddress(String id) => '$addresses/$id/default';

  // Payments (payment_service)
  static const String initiatePayment = '$apiVersion/payments/initiate';
  static const String payments = '$apiVersion/payments';
  // A tip for the provider of a completed booking (payment_service).
  static const String tips = '$apiVersion/payments/tips';
  // Loyalty points and referral codes (payment_service).
  static const String loyalty = '$apiVersion/loyalty/me';
  static const String referral = '$apiVersion/loyalty/referral';
  static String verifyPayment(String paymentId) => '$apiVersion/payments/$paymentId/verify';
  /// A printable HTML invoice for a completed payment.
  static String paymentInvoice(String paymentId) => '$apiVersion/payments/$paymentId/invoice';

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
  /// Registers this device's push (FCM) token for the signed-in user.
  static const String deviceTokens = '$apiVersion/notifications/device-tokens';

  // Legal and privacy (auth_service and compliance_service)
  /// The current Terms version and the legal page links; public.
  static const String legalCurrent = '$apiVersion/legal/current';
  /// The signed-in user's data export requests (GET lists them, POST asks for a new one).
  static const String dataExport = '$apiVersion/gdpr/export';

  // Timeouts
  static const int connectTimeout = 30000;
  static const int receiveTimeout = 30000;
}
