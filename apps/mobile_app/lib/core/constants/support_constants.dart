/// How customers reach the Alakh support team: the PLATFORM's contact, never a shop's. Customers and
/// shops talk through AlakhService (bookings, reports to support), not directly, so no shop phone,
/// WhatsApp or customer number belongs here.
///
/// REPLACE THE PLACEHOLDERS before release, or set them per build:
/// `--dart-define=SUPPORT_EMAIL=help@example.in --dart-define=SUPPORT_PHONE=+911234567890`.
class SupportContact {
  SupportContact._();

  /// Placeholder address: replace with the real support inbox.
  static const String email = String.fromEnvironment('SUPPORT_EMAIL', defaultValue: 'support@alakhservice.in');

  /// Placeholder number (all zeros): replace with the real support line, in E.164 (+91…).
  static const String phone = String.fromEnvironment('SUPPORT_PHONE', defaultValue: '+910000000000');
}
