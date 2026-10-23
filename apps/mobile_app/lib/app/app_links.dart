/// Where a link or notification takes the customer.
sealed class AppTarget {
  const AppTarget();
}

/// A booking's details, or straight to its chat with the shop.
class BookingTarget extends AppTarget {
  final String bookingId;
  final bool chat;

  const BookingTarget(this.bookingId, {this.chat = false});

  @override
  bool operator ==(Object other) => other is BookingTarget && other.bookingId == bookingId && other.chat == chat;

  @override
  int get hashCode => Object.hash(bookingId, chat);

  @override
  String toString() => 'BookingTarget($bookingId, chat: $chat)';
}

/// Choosing a new password with an emailed reset token.
class ResetPasswordTarget extends AppTarget {
  final String token;

  const ResetPasswordTarget(this.token);

  @override
  bool operator ==(Object other) => other is ResetPasswordTarget && other.token == token;

  @override
  int get hashCode => token.hashCode;

  @override
  String toString() => 'ResetPasswordTarget(…)';
}

/// The site app links are verified for. It is set in ONE place for the native side,
/// `apps/mobile_app/app_links.xcconfig` (APP_LINK_DOMAIN, read by Android's Gradle build and iOS's
/// xcconfig), and passed to Dart with `--dart-define=APP_LINK_DOMAIN=...` when it differs from the
/// placeholder below. PLACEHOLDER: replace before release.
const String appLinkDomain = String.fromEnvironment('APP_LINK_DOMAIN', defaultValue: 'alakhservice.in');

/// What an app link opens: https://{domain}/b/{booking_id} or /reset-password?token=...
/// Other hosts (the OS only hands the app verified ones) and unknown paths give null.
AppTarget? parseAppLink(Uri uri) {
  if (uri.scheme != 'https' && uri.scheme != 'http') return null;
  final host = uri.host.toLowerCase();
  if (host != appLinkDomain && host != 'www.$appLinkDomain') return null;
  final segments = uri.pathSegments.where((s) => s.isNotEmpty).toList();
  if (segments.length == 2 && segments[0] == 'b' && _isId(segments[1])) return BookingTarget(segments[1]);
  if (segments.length == 1 && segments[0] == 'reset-password') {
    final token = uri.queryParameters['token'];
    if (token != null && token.isNotEmpty) return ResetPasswordTarget(token);
  }
  return null;
}

/// What tapping a push notification opens, from its data (notification_service sends the event
/// name as `event` and the booking as `booking_id`): the chat for booking.message, else the booking.
AppTarget? pushTarget(Map<String, dynamic> data) {
  final booking = data['booking_id'];
  if (booking is! String || !_isId(booking)) return null;
  return BookingTarget(booking, chat: data['event'] == 'booking.message');
}

bool _isId(String s) => RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(s);
