import 'package:alakh_service/app/app_links.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  Uri link(String pathAndQuery, {String host = appLinkDomain}) => Uri.parse('https://$host$pathAndQuery');

  group('app links', () {
    test('/b/{id} opens the booking', () {
      expect(parseAppLink(link('/b/7f3c9a10-1b2c-4d5e-8f90-123456789abc')),
          const BookingTarget('7f3c9a10-1b2c-4d5e-8f90-123456789abc'));
      expect(parseAppLink(link('/b/abc123/')), const BookingTarget('abc123'));
      expect(parseAppLink(link('/b/abc123', host: 'www.$appLinkDomain')), const BookingTarget('abc123'));
    });

    test('/reset-password?token= opens the reset screen', () {
      expect(parseAppLink(link('/reset-password?token=tok.en-1')), const ResetPasswordTarget('tok.en-1'));
      expect(parseAppLink(link('/reset-password')), isNull);
      expect(parseAppLink(link('/reset-password?token=')), isNull);
    });

    test('anything else is ignored', () {
      expect(parseAppLink(link('/terms')), isNull);
      expect(parseAppLink(link('/b')), isNull);
      expect(parseAppLink(link('/b/abc/extra')), isNull);
      expect(parseAppLink(link('/b/..%2Fadmin')), isNull);
      expect(parseAppLink(link('/b/abc123', host: 'evil.example')), isNull);
      expect(parseAppLink(Uri.parse('alakh://b/abc123')), isNull);
    });
  });

  group('push taps', () {
    test('a chat message opens the chat, other booking events the booking', () {
      expect(pushTarget({'event': 'booking.message', 'booking_id': 'b1'}), const BookingTarget('b1', chat: true));
      expect(pushTarget({'event': 'booking.confirmed', 'booking_id': 'b1'}), const BookingTarget('b1'));
      expect(pushTarget({'event': 'booking.reminder', 'booking_id': 'b2'}), const BookingTarget('b2'));
    });

    test('no booking, nothing to open', () {
      expect(pushTarget({'event': 'payment.completed'}), isNull);
      expect(pushTarget({}), isNull);
    });
  });
}
